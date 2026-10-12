import base64
from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from hpc_job import canonical_json, hash_data
from hpc_job_control import (
    find_completion_files,
    get_terminal_scheduler_state,
    parse_sbatch_result,
    read_log_stream,
    validate_scheduler_job,
)
from hpc_job_lifecycle import (
    HpcJobLifecycleError,
    build_final_record,
    build_submission_receipt,
    create_state_record,
    read_state_record,
    replace_state_record,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_HELPER_ROOT = REPO_ROOT / 'dev_scratch/hpc/helper_src/local'
sys.path.insert(0, LOCAL_HELPER_ROOT.as_posix())
COMMIT = 'a' * 40
NOW = '2026-10-10T12:00:00+00:00'
LATER = '2026-10-10T12:01:00+00:00'
FIXTURES = json.loads((
    REPO_ROOT /
    'dev_scratch/hpc/helper_src/test_fixtures/b1_job_cases.json'
).read_text())


def load_script_module(name, relpath):
    """Load one extensionless candidate script as a test module."""
    fpath = REPO_ROOT / relpath
    loader = SourceFileLoader(name, fpath.as_posix())
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


LETHE = load_script_module(
    'hpc_lethe_job_candidate',
    'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-job',
)
GRID = load_script_module(
    'hpc_grid_job_candidate',
    'dev_scratch/hpc/helper_src/remote_grid/hpc-grid-job',
)
LOCAL = load_script_module(
    'hpc_job_candidate',
    'dev_scratch/hpc/helper_src/local/hpc-job',
)


def make_scheduler_job(job_id=117950, raw_state='COMPLETED'):
    """Return one normalized A5 scheduler result."""
    normalized = {
        'CANCELLED': 'cancelled',
        'COMPLETED': 'completed',
        'FAILED': 'failed',
        'RUNNING': 'running',
    }[raw_state]
    return {
        'job_id': job_id,
        'source': 'sacct' if raw_state == 'COMPLETED' else 'squeue',
        'raw_state': raw_state,
        'normalized_state': normalized,
        'reason': '',
        'exit_code': '0:0' if raw_state == 'COMPLETED' else '',
        'accounting_gap': False,
        'retry_after_sec': None,
    }


class HpcJobControlUnitTests(unittest.TestCase):
    def test_remote_configuration_is_accepted_by_both_hosts(self):
        """Keep lethe and lattice on one exact non-secret configuration."""
        fpath = (
            REPO_ROOT /
            'dev_scratch/hpc/helper_src/config_examples/'
            'remote-hpc-job.json.example'
        )
        config = json.loads(fpath.read_text())
        self.assertEqual(LETHE.validate_config(config), config)
        self.assertEqual(GRID.validate_config(config), config)

    def test_sbatch_result_is_strict(self):
        """Accept only one positive job ID with an optional cluster suffix."""
        for case in FIXTURES['sbatch_cases']:
            self.assertEqual(parse_sbatch_result(case['value']), case['job_id'])
        for value in FIXTURES['invalid_sbatch_results']:
            with self.subTest(value=value):
                with self.assertRaises(HpcJobLifecycleError):
                    parse_sbatch_result(value)

    def test_scheduler_result_and_terminal_state_are_bound(self):
        """Require the known job ID and a supported terminal Slurm token."""
        job = make_scheduler_job()
        self.assertEqual(validate_scheduler_job(job, 117950), job)
        self.assertEqual(get_terminal_scheduler_state(job), 'COMPLETED')
        for state in FIXTURES['terminal_states']:
            case = {**job, 'raw_state': state}
            self.assertEqual(get_terminal_scheduler_state(case), state)
        with self.assertRaises(HpcJobLifecycleError):
            validate_scheduler_job(job, 117951)
        with self.assertRaises(HpcJobLifecycleError):
            get_terminal_scheduler_state(make_scheduler_job(raw_state='RUNNING'))

    def test_log_reader_is_incremental_and_bounded(self):
        """Advance by inode and byte offset without returning unlimited data."""
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'slurm.out'
            case = FIXTURES['log_case']
            fpath.write_text(case['content'])
            first = read_log_stream(fpath, None, 1024, 2)
            cursor = {
                'identity': first['identity'],
                'offset': first['end_offset'],
            }
            second = read_log_stream(fpath, cursor, 1024, 2)
        self.assertEqual(first['content'], case['first_chunk'])
        self.assertTrue(first['more_available'])
        self.assertEqual(first['limit_reason'], 'lines')
        self.assertEqual(second['content'], case['second_chunk'])
        self.assertFalse(second['more_available'])

    def test_grid_sbatch_call_has_only_the_prepared_script(self):
        """Call `sbatch --parsable` with no caller-supplied scheduler flags."""
        config = {
            'scheduler': {
                'sbatch_path': '/usr/bin/sbatch',
                'command_timeout_sec': 90,
            },
        }
        completed = SimpleNamespace(
            returncode=0,
            stdout=b'117950\n',
            stderr=b'',
        )
        with patch.object(GRID.subprocess, 'run', return_value=completed) as run:
            job_id = GRID.run_sbatch(config, '/repo/hpc_jobs/runs/b1/submit.sh')
        self.assertEqual(job_id, 117950)
        self.assertEqual(
            run.call_args.args[0],
            [
                '/usr/bin/sbatch',
                '--parsable',
                '/repo/hpc_jobs/runs/b1/submit.sh',
            ],
        )

    def test_grid_scancel_call_has_only_recorded_job_ids(self):
        """Call `scancel` with no caller-supplied scheduler options."""
        config = {
            'scheduler': {
                'scancel_path': '/usr/bin/scancel',
                'command_timeout_sec': 90,
            },
        }
        completed = SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with patch.object(GRID.subprocess, 'run', return_value=completed) as run:
            GRID.run_scancel(config, [117950, 117951])
        self.assertEqual(
            run.call_args.args[0],
            ['/usr/bin/scancel', '--quiet', '--', '117950', '117951'],
        )

    def test_local_cancel_accepts_only_one_run_id(self):
        """Expose cancellation without accepting a job ID or Slurm option. """
        parser = LOCAL.build_parser()
        args = LOCAL.validate_args(parser.parse_args([
            'cancel',
            'b2-child-fixture-001',
        ]))
        self.assertEqual(args.operation, 'cancel')
        self.assertEqual(args.run_id, 'b2-child-fixture-001')

    def test_local_cursor_state_accepts_only_inode_identities(self):
        """Reject local cursor identities that the remote reader cannot use."""
        valid = {
            'schema_version': 1,
            'runs': {
                'b1-single-fixture-001': {
                    'stdout': {'identity': '12:34', 'offset': 10},
                },
            },
        }
        self.assertEqual(LOCAL.validate_cursor_state(valid), valid)
        valid['runs']['b1-single-fixture-001']['stdout']['identity'] = '12:x'
        with self.assertRaises(LOCAL.HelperFailure):
            LOCAL.validate_cursor_state(valid)

    def test_local_cursor_state_separates_child_logs(self):
        """Keep one incremental cursor pair for each recorded child key. """
        state = {'schema_version': 1, 'runs': {}}
        result = {
            'streams': {
                'stdout': {
                    'status': 'ok',
                    'identity': '12:34',
                    'end_offset': 10,
                },
                'stderr': {'status': 'missing'},
            },
        }
        LOCAL.update_cursors(
            state,
            'b2-child-fixture-001',
            result,
            'run_00000',
        )
        self.assertEqual(
            state['runs']['b2-child-fixture-001']['children']
            ['run_00000']['stdout']['offset'],
            10,
        )
        self.assertEqual(LOCAL.validate_cursor_state(state), state)

    def test_local_child_log_argument_is_validated(self):
        """Accept one safe child key and reject path-like values. """
        parser = LOCAL.build_parser()
        args = parser.parse_args([
            'log',
            'b2-child-fixture-001',
            '--child',
            'run_00000',
        ])
        self.assertEqual(LOCAL.validate_args(args).child_key, 'run_00000')
        unsafe = parser.parse_args([
            'log',
            'b2-child-fixture-001',
            '--child',
            '../run',
        ])
        with self.assertRaises(LOCAL.RejectedInput):
            LOCAL.validate_args(unsafe)


class HpcJobControlLifecycleTests(unittest.TestCase):
    def setUp(self):
        """Create one complete protected-run fixture without a scheduler."""
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / 'repo'
        self.state = root / 'state'
        self.run_id = 'b1-single-fixture-001'
        self.run_dir = self.repo / 'hpc_jobs/runs' / self.run_id
        self.run_dir.mkdir(parents=True, mode=0o700)
        self.run_dir.chmod(0o700)
        for name in ('runs', 'submissions', 'finals', 'releases'):
            (self.state / name).mkdir(parents=True)
        for name in ('code-update.lock', 'grid-submit.lock', 'job.lock'):
            fpath = self.state / name
            fpath.write_text('')
            fpath.chmod(0o600)

        request = {'schema_version': 1, 'request_id': 'b1-single-fixture'}
        script = '#!/bin/bash\necho fixture\n'
        request_path = self.run_dir / 'request.json'
        script_path = self.run_dir / 'submit.sh'
        request_path.write_text(canonical_json(request) + '\n')
        script_path.write_text(script)
        request_path.chmod(0o444)
        script_path.chmod(0o444)
        self.prepared = {
            'schema_version': 1,
            'request_id': 'b1-single-fixture',
            'request_sha256': hash_data(request),
            'run_id': self.run_id,
            'job_kind': 'single',
            'git_commit': COMMIT,
            'simulation_job_limit': 1,
            'expected_result_path': 'exp_results/group/smoke/exp_fixture',
            'completion_files': ['results/result.json'],
            'job_run_dir': self.run_dir.as_posix(),
            'submit_script': script_path.as_posix(),
            'stdout_path': (self.run_dir / 'slurm-%j.out').as_posix(),
            'stderr_path': (self.run_dir / 'slurm-%j.err').as_posix(),
            'status': 'prepared',
            'rendered_script_sha256': __import__('hashlib').sha256(
                script.encode()
            ).hexdigest(),
        }
        run_path = self.run_dir / 'run.json'
        run_path.write_text(canonical_json(self.prepared) + '\n')
        run_path.chmod(0o444)
        create_state_record(
            self.state / 'runs' / f'{self.run_id}.json',
            self.prepared,
        )
        self.config = {
            'schema_version': 1,
            'deployment_id': 'fixture',
            'git': {
                'path': '/usr/bin/git',
                'automation_checkout': self.repo.as_posix(),
                'branch': 'codex-hpc',
            },
            'ssh': {'grid_host_alias': 'lattice', 'connect_timeout_sec': 15},
            'remote_helpers': {'grid_job': '/helpers/grid/hpc-grid-job'},
            'runs': {'root': (self.repo / 'hpc_jobs/runs').as_posix()},
            'state': {
                'root': self.state.as_posix(),
                'code_update_lock': (self.state / 'code-update.lock').as_posix(),
                'grid_submit_lock': (self.state / 'grid-submit.lock').as_posix(),
                'job_lock': (self.state / 'job.lock').as_posix(),
                'active_run': (self.state / 'active-run.json').as_posix(),
            },
            'scheduler': {
                'user': 'fixture',
                'sbatch_path': '/usr/bin/sbatch',
                'scancel_path': '/usr/bin/scancel',
                'status_helper': '/helpers/grid/hpc-grid-status',
                'command_timeout_sec': 90,
            },
            'logs': {
                'max_lines_per_stream': 200,
                'max_bytes_per_stream': 65536,
                'max_cursor_payload_bytes': 16384,
            },
        }

    def tearDown(self):
        """Remove the isolated lifecycle fixture."""
        self.tmp.cleanup()

    def submit_fixture(self):
        """Create an intent, emulate one grid receipt, and reconcile it."""
        intent = LETHE.create_submission_intent(self.config, self.prepared)
        receipt = build_submission_receipt(
            intent,
            self.prepared,
            117950,
            LATER,
        )
        replace_state_record(
            self.run_dir / 'submission.json',
            intent,
            receipt,
        )
        reconciled = LETHE.load_submission(self.config, self.prepared)
        return receipt, reconciled

    def test_intent_precedes_receipt_and_reconciles_to_protected_state(self):
        """Persist the active marker and intent before accepting one receipt."""
        receipt, reconciled = self.submit_fixture()
        protected = read_state_record(
            self.state / 'submissions' / f'{self.run_id}.json',
            'submission',
        )
        self.assertEqual(reconciled, receipt)
        self.assertEqual(protected, receipt)
        self.assertTrue((self.state / 'active-run.json').is_file())

    def test_log_finalize_and_explicit_release_complete_the_lifecycle(self):
        """Read logs, prove completion, then explicitly release the checkout."""
        self.submit_fixture()
        (self.run_dir / 'slurm-117950.out').write_text('started\nfinished\n')
        (self.run_dir / 'slurm-117950.err').write_text('')
        payload = base64.urlsafe_b64encode(canonical_json({
            'schema_version': 1,
            'streams': {'stdout': None, 'stderr': None},
        }).encode()).decode()
        logs = LETHE.log_job(self.config, self.run_id, payload)
        self.assertEqual(logs['streams']['stdout']['content'], 'started\nfinished\n')

        result_dir = self.repo / self.prepared['expected_result_path'] / 'results'
        result_dir.mkdir(parents=True)
        (result_dir / 'result.json').write_text('{}\n')
        self.assertEqual(find_completion_files(self.repo, self.prepared), [
            'results/result.json',
        ])
        scheduler = make_scheduler_job()
        with patch.object(
            LETHE,
            'scheduler_status',
            return_value=(scheduler, NOW),
        ):
            final = LETHE.finalize_job(self.config, self.run_id)
            repeated = LETHE.finalize_job(self.config, self.run_id)
        self.assertEqual(final['result'], 'created')
        self.assertEqual(repeated['result'], 'existing')
        self.assertTrue((self.state / 'active-run.json').exists())

        released = LETHE.release_job(self.config, self.run_id)
        repeated_release = LETHE.release_job(self.config, self.run_id)
        self.assertEqual(released['result'], 'released')
        self.assertEqual(repeated_release['result'], 'existing')
        self.assertFalse((self.state / 'active-run.json').exists())

    def test_completed_scheduler_without_outputs_finalizes_as_failed(self):
        """Record failed evidence and release even when Slurm reports success. """
        self.submit_fixture()
        scheduler = make_scheduler_job()
        with patch.object(
            LETHE,
            'scheduler_status',
            return_value=(scheduler, NOW),
        ):
            final = LETHE.finalize_job(self.config, self.run_id)
        self.assertEqual(final['scheduler_state'], 'COMPLETED')
        self.assertEqual(final['run_status'], 'failed')
        stored = read_state_record(
            self.state / 'finals' / f'{self.run_id}.json',
            'final',
        )
        self.assertEqual(stored['status'], 'failed')
        released = LETHE.release_job(self.config, self.run_id)
        self.assertEqual(released['result'], 'released')
        self.assertFalse((self.state / 'active-run.json').exists())

    def test_batch_status_includes_recorded_child_scheduler_states(self):
        """Query the main allocation and every recorded child together. """
        batch = {
            **self.prepared,
            'job_kind': 'batch',
            'simulation_job_limit': 2,
        }
        submission = {'status': 'submitted', 'slurm_job_id': 117950}
        child = {
            'child_key': 'run_00000',
            'expected_outputs': ['exp_results/group/smoke/exp_fixture/result.json'],
            'parameters': {'seed': 1},
            'slurm_job_id': 117951,
            'stderr_path': 'exp_results/group/smoke/exp_fixture/jobs/run_00000.err',
            'stdout_path': 'exp_results/group/smoke/exp_fixture/jobs/run_00000.run',
        }
        jobs = [
            make_scheduler_job(raw_state='RUNNING'),
            make_scheduler_job(117951, raw_state='FAILED'),
        ]
        with patch.object(LETHE, 'load_prepared', return_value=batch):
            with patch.object(LETHE, 'load_submission', return_value=submission):
                with patch.object(LETHE, 'load_child_records', return_value=[child]):
                    with patch.object(
                        LETHE,
                        'scheduler_statuses',
                        return_value=(jobs, NOW),
                    ) as status:
                        result = LETHE.status_job(self.config, self.run_id)
        status.assert_called_once_with(self.config, [117950, 117951])
        self.assertEqual(result['scheduler']['normalized_state'], 'running')
        self.assertEqual(
            result['children'][0]['scheduler']['normalized_state'],
            'failed',
        )

    def test_batch_child_log_uses_only_recorded_paths(self):
        """Read one selected child's bounded streams from its fixed record. """
        batch = {
            **self.prepared,
            'job_kind': 'batch',
            'simulation_job_limit': 2,
        }
        result_root = self.repo / batch['expected_result_path']
        jobs_dir = result_root / 'jobs'
        jobs_dir.mkdir(parents=True)
        (jobs_dir / 'run_00000.run').write_text('child output\n')
        (jobs_dir / 'run_00000.err').write_text('child error\n')
        child = {
            'schema_version': 1,
            'run_id': self.run_id,
            'child_key': 'run_00000',
            'slurm_job_id': 117951,
            'parameters': {'seed': 1},
            'stdout_path': (
                f'{batch["expected_result_path"]}/jobs/run_00000.run'
            ),
            'stderr_path': (
                f'{batch["expected_result_path"]}/jobs/run_00000.err'
            ),
            'expected_outputs': [
                f'{batch["expected_result_path"]}/result.json',
            ],
            'submitted_at_utc': NOW,
        }
        payload = base64.urlsafe_b64encode(canonical_json({
            'schema_version': 1,
            'streams': {'stdout': None, 'stderr': None},
        }).encode()).decode()
        submission = {'status': 'submitted', 'slurm_job_id': 117950}
        with patch.object(LETHE, 'load_prepared', return_value=batch):
            with patch.object(LETHE, 'load_submission', return_value=submission):
                with patch.object(LETHE, 'load_child_records', return_value=[child]):
                    result = LETHE.log_job(
                        self.config,
                        self.run_id,
                        payload,
                        'run_00000',
                    )
        self.assertEqual(result['slurm_job_id'], 117951)
        self.assertEqual(result['streams']['stdout']['content'], 'child output\n')
        self.assertEqual(result['streams']['stderr']['content'], 'child error\n')

    def test_cancel_forwards_only_the_bound_active_run(self):
        """Bind cancellation to the protected receipt and active marker. """
        receipt, _ = self.submit_fixture()
        grid_result = {
            'schema_version': 1,
            'operation': 'grid-job-cancel',
            'status': 'ok',
            'result': 'cancel-requested',
            'run_id': self.run_id,
            'slurm_job_id': receipt['slurm_job_id'],
            'child_job_ids': [],
        }
        with patch.object(
            LETHE,
            'run_grid_command',
            return_value=(grid_result, LETHE.EXIT_SUCCESS),
        ) as remote:
            result = LETHE.cancel_job(self.config, self.run_id)
        remote.assert_called_once_with(
            self.config,
            '/helpers/grid/hpc-grid-job',
            (
                'cancel',
                self.run_id,
                COMMIT,
                self.prepared['request_sha256'],
                self.prepared['rendered_script_sha256'],
            ),
        )
        self.assertEqual(result['operation'], 'job-cancel')
        self.assertEqual(result['slurm_job_id'], receipt['slurm_job_id'])

    def test_cancel_forwards_recorded_children_without_caller_job_ids(self):
        """Cancel children resolved only from the protected batch index."""
        receipt, _ = self.submit_fixture()
        batch = {
            **self.prepared,
            'job_kind': 'batch',
            'simulation_job_limit': 2,
        }
        child = {'slurm_job_id': 117951}
        grid_result = {
            'schema_version': 1,
            'operation': 'grid-job-cancel',
            'status': 'ok',
            'result': 'cancel-requested',
            'run_id': self.run_id,
            'slurm_job_id': receipt['slurm_job_id'],
            'child_job_ids': [child['slurm_job_id']],
        }
        with (
            patch.object(LETHE, 'load_prepared', return_value=batch),
            patch.object(LETHE, 'load_submission', return_value=receipt),
            patch.object(
                LETHE,
                'load_child_records',
                return_value=[child],
            ),
            patch.object(
                LETHE,
                'run_grid_command',
                return_value=(grid_result, LETHE.EXIT_SUCCESS),
            ) as remote,
        ):
            result = LETHE.cancel_job(self.config, self.run_id)
        remote.assert_called_once_with(
            self.config,
            '/helpers/grid/hpc-grid-job',
            (
                'cancel',
                self.run_id,
                COMMIT,
                self.prepared['request_sha256'],
                self.prepared['rendered_script_sha256'],
            ),
        )
        self.assertEqual(result['child_job_ids'], [child['slurm_job_id']])

    def test_invalid_child_output_declaration_finalizes_as_failed(self):
        """Release terminal batches with malformed child declarations."""
        receipt, _ = self.submit_fixture()
        batch = {
            **self.prepared,
            'job_kind': 'batch',
            'simulation_job_limit': 1,
        }
        child = {
            'schema_version': 1,
            'run_id': self.run_id,
            'child_key': 'run_00000',
            'slurm_job_id': 117951,
            'parameters': {'seed': 1},
            'stdout_path': (
                f'{batch["expected_result_path"]}/jobs/run_00000.run'
            ),
            'stderr_path': (
                f'{batch["expected_result_path"]}/jobs/run_00000.err'
            ),
            'expected_outputs': [
                f'{batch["expected_result_path"]}/results/wrong.json',
            ],
            'submitted_at_utc': NOW,
        }
        final = build_final_record(
            batch,
            receipt,
            'CANCELLED',
            [],
            [child],
            LATER,
        )
        self.assertEqual(final['status'], 'failed')
        self.assertEqual(final['child_job_ids'], [117951])

    def test_grid_cancel_resolves_only_the_recorded_receipt(self):
        """Resolve controller and child IDs from protected records."""
        receipt, _ = self.submit_fixture()
        child = {'slurm_job_id': 117951}
        with patch.object(
            GRID.pwd,
            'getpwuid',
            return_value=SimpleNamespace(pw_name='fixture'),
        ), patch.object(
            GRID,
            'load_child_records',
            return_value=[child],
        ), patch.object(GRID, 'run_scancel') as scancel:
            result = GRID.cancel(
                self.config,
                self.run_id,
                COMMIT,
                self.prepared['request_sha256'],
                self.prepared['rendered_script_sha256'],
            )
        scancel.assert_called_once_with(
            self.config,
            [receipt['slurm_job_id'], child['slurm_job_id']],
        )
        self.assertEqual(result['operation'], 'grid-job-cancel')
        self.assertEqual(result['slurm_job_id'], receipt['slurm_job_id'])
        self.assertEqual(result['child_job_ids'], [child['slurm_job_id']])


if __name__ == '__main__':
    unittest.main()
