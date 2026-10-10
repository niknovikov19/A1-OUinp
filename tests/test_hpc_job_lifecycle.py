import json
from pathlib import Path
import stat
import tempfile
import unittest

from hpc_job_lifecycle import (
    HpcJobLifecycleError,
    build_active_run_marker,
    build_final_record,
    build_submission_receipt,
    build_unknown_submission,
    create_state_record,
    decide_submission,
    parse_child_records,
    read_state_record,
    remove_state_record,
    replace_state_record,
    release_active_run,
    require_exact_checkout,
    resolve_child_log_path,
    resolve_top_level_log_path,
    validate_final_record,
    validate_submission_record,
)


COMMIT = 'a' * 40
NOW = '2026-10-10T12:00:00+00:00'
LATER = '2026-10-10T12:01:00+00:00'


def make_prepared(job_kind='batch'):
    """Return one minimal prepared record for lifecycle tests."""
    run_id = f'b0-{job_kind}-001'
    run_dir = f'/repo/A1_OUinp/hpc_jobs/runs/{run_id}'
    result = f'exp_results/group/{job_kind}/exp_001'
    record = {
        'schema_version': 1,
        'request_id': f'b0-{job_kind}',
        'request_sha256': 'b' * 64,
        'run_id': run_id,
        'job_kind': job_kind,
        'git_commit': COMMIT,
        'simulation_job_limit': 2 if job_kind != 'single' else 1,
        'expected_result_path': result,
        'completion_files': ['result.json'],
        'job_run_dir': run_dir,
        'submit_script': f'{run_dir}/submit.sh',
        'stdout_path': f'{run_dir}/slurm-%j.out',
        'stderr_path': f'{run_dir}/slurm-%j.err',
        'status': 'prepared',
        'rendered_script_sha256': 'c' * 64,
    }
    return record


def make_child(prepared, child_key='sim-000', slurm_job_id=120001):
    """Return one valid child-job record beneath the scientific result."""
    result = prepared['expected_result_path']
    return {
        'schema_version': 1,
        'run_id': prepared['run_id'],
        'child_key': child_key,
        'slurm_job_id': slurm_job_id,
        'stdout_path': f'{result}/batchtools/logs/{child_key}.out',
        'stderr_path': f'{result}/batchtools/logs/{child_key}.err',
    }


class ExactCommitTests(unittest.TestCase):
    def test_exact_clean_commit_is_required(self):
        prepared = make_prepared()
        self.assertEqual(require_exact_checkout(prepared, COMMIT, True), COMMIT)
        with self.assertRaises(HpcJobLifecycleError):
            require_exact_checkout(prepared, 'd' * 40, True)
        with self.assertRaises(HpcJobLifecycleError):
            require_exact_checkout(prepared, COMMIT, False)


class SubmissionTransitionTests(unittest.TestCase):
    def test_one_intent_one_receipt_and_idempotent_repeat(self):
        prepared = make_prepared()
        intent, result = decide_submission(None, prepared, NOW)
        self.assertEqual(result, 'intent')
        self.assertEqual(intent['status'], 'pending')

        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        existing, result = decide_submission(receipt, prepared, LATER)
        self.assertEqual(result, 'existing')
        self.assertEqual(existing['slurm_job_id'], 117900)
        with self.assertRaises(HpcJobLifecycleError):
            build_submission_receipt(receipt, prepared, 117901, LATER)

    def test_pending_and_unknown_records_fail_closed(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        with self.assertRaises(HpcJobLifecycleError):
            decide_submission(intent, prepared, LATER)
        unknown = build_unknown_submission(
            intent,
            prepared,
            'scheduler reply was lost',
            LATER,
        )
        with self.assertRaises(HpcJobLifecycleError):
            decide_submission(unknown, prepared, LATER)

    def test_receipt_is_bound_to_prepared_inputs(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        changed = {**prepared, 'rendered_script_sha256': 'd' * 64}
        with self.assertRaises(HpcJobLifecycleError):
            validate_submission_record(receipt, changed)

    def test_intent_and_receipt_are_persisted_once(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'submission.json'
            create_state_record(fpath, intent)
            self.assertEqual(stat.S_IMODE(fpath.stat().st_mode), 0o600)
            with self.assertRaises(HpcJobLifecycleError):
                create_state_record(fpath, intent)
            replace_state_record(fpath, intent, receipt)
            self.assertEqual(read_state_record(fpath, 'submission'), receipt)
            with self.assertRaises(HpcJobLifecycleError):
                replace_state_record(fpath, intent, receipt)

    def test_state_reads_reject_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'target.json'
            target.write_text('{}')
            symlink = Path(tmp) / 'submission.json'
            symlink.symlink_to(target)
            with self.assertRaises(HpcJobLifecycleError):
                read_state_record(symlink, 'submission')


class LogResolutionTests(unittest.TestCase):
    def test_top_level_logs_use_only_the_receipt_job_id(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        self.assertEqual(
            resolve_top_level_log_path(prepared, receipt, 'stdout'),
            Path(prepared['job_run_dir']) / 'slurm-117900.out',
        )
        with self.assertRaises(HpcJobLifecycleError):
            resolve_top_level_log_path(prepared, receipt, '../stdout')

    def test_child_logs_resolve_only_from_ingested_records(self):
        prepared = make_prepared()
        child = make_child(prepared)
        self.assertEqual(
            resolve_child_log_path(prepared, [child], 'sim-000', 'stderr'),
            Path('/repo/A1_OUinp') / child['stderr_path'],
        )
        with self.assertRaises(HpcJobLifecycleError):
            resolve_child_log_path(prepared, [child], 'sim-999', 'stderr')


class ChildRecordTests(unittest.TestCase):
    def test_bounded_records_are_ingested_under_the_run_limit(self):
        prepared = make_prepared()
        children = [
            make_child(prepared),
            make_child(prepared, 'sim-001', 120002),
        ]
        payload = b'\n'.join(
            json.dumps(record, sort_keys=True).encode()
            for record in children
        )
        self.assertEqual(parse_child_records(payload, prepared), children)

        extra = make_child(prepared, 'sim-002', 120003)
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(payload + b'\n' + json.dumps(extra).encode(), prepared)

    def test_duplicate_and_escaped_child_records_are_rejected(self):
        prepared = make_prepared()
        child = make_child(prepared)
        duplicate = {**child, 'child_key': 'sim-001'}
        payload = b'\n'.join((
            json.dumps(child).encode(),
            json.dumps(duplicate).encode(),
        ))
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(payload, prepared)

        escaped = {**child, 'stdout_path': 'hpc_jobs/runs/other/log.out'}
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(json.dumps(escaped).encode(), prepared)

    def test_single_job_rejects_child_records(self):
        prepared = make_prepared('single')
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(json.dumps(make_child(prepared)).encode(), prepared)

    def test_child_record_byte_limits_are_enforced(self):
        prepared = make_prepared()
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(b'x' * 65537, prepared)
        with self.assertRaises(HpcJobLifecycleError):
            parse_child_records(b'x' * 4097, prepared)


class FinalizeReleaseTests(unittest.TestCase):
    def test_complete_run_requires_files_then_releases_commit_lock(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        child = make_child(prepared)
        active = build_active_run_marker(prepared, NOW)
        final = build_final_record(
            prepared,
            receipt,
            'COMPLETED',
            ['result.json'],
            [child],
            LATER,
        )
        self.assertEqual(final['status'], 'complete')
        released = release_active_run(active, final, prepared, LATER)
        self.assertEqual(released['status'], 'released')

    def test_finalize_rejects_active_state_and_missing_results(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        with self.assertRaises(HpcJobLifecycleError):
            build_final_record(prepared, receipt, 'RUNNING', [], [], LATER)
        with self.assertRaises(HpcJobLifecycleError):
            build_final_record(prepared, receipt, 'COMPLETED', [], [], LATER)

    def test_failed_run_can_finalize_before_explicit_release(self):
        prepared = make_prepared('single')
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        active = build_active_run_marker(prepared, NOW)
        final = build_final_record(
            prepared,
            receipt,
            'FAILED',
            [],
            [],
            LATER,
        )
        self.assertEqual(final['status'], 'failed')
        mismatched = {**final, 'git_commit': 'd' * 40}
        with self.assertRaises(HpcJobLifecycleError):
            release_active_run(active, mismatched, prepared, LATER)

    def test_release_rejects_an_incomplete_final_record(self):
        prepared = make_prepared()
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        final = build_final_record(
            prepared,
            receipt,
            'COMPLETED',
            ['result.json'],
            [],
            LATER,
        )
        validate_final_record(final, prepared)
        incomplete = {**final, 'completion_files_verified': []}
        with self.assertRaises(HpcJobLifecycleError):
            validate_final_record(incomplete, prepared)

    def test_release_record_is_explicitly_removed_after_finalization(self):
        prepared = make_prepared('single')
        intent, _ = decide_submission(None, prepared, NOW)
        receipt = build_submission_receipt(intent, prepared, 117900, LATER)
        active = build_active_run_marker(prepared, NOW)
        final = build_final_record(
            prepared,
            receipt,
            'FAILED',
            [],
            [],
            LATER,
        )
        release_active_run(active, final, prepared, LATER)
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'active-run.json'
            create_state_record(fpath, active)
            with self.assertRaises(HpcJobLifecycleError):
                remove_state_record(fpath, {**active, 'run_id': 'other-run'})
            remove_state_record(fpath, active)
            self.assertFalse(fpath.exists())


class CheckedFixtureTests(unittest.TestCase):
    def test_fixed_fixture_covers_the_full_lifecycle(self):
        fpath = (
            Path(__file__).resolve().parents[1]
            / 'dev_scratch/hpc/helper_src/test_fixtures/b0_lifecycle_cases.json'
        )
        fixture = json.loads(fpath.read_text())
        prepared = fixture['prepared']
        require_exact_checkout(prepared, prepared['git_commit'], True)
        intent, result = decide_submission(None, prepared, fixture['intent_at_utc'])
        self.assertEqual(result, 'intent')
        receipt = build_submission_receipt(
            intent,
            prepared,
            fixture['slurm_job_id'],
            fixture['submitted_at_utc'],
        )
        children = parse_child_records(
            fixture['children_jsonl'].encode(),
            prepared,
        )
        final = build_final_record(
            prepared,
            receipt,
            fixture['scheduler_state'],
            fixture['present_completion_files'],
            children,
            fixture['finalized_at_utc'],
        )
        active = build_active_run_marker(prepared, fixture['intent_at_utc'])
        released = release_active_run(
            active,
            final,
            prepared,
            fixture['released_at_utc'],
        )
        self.assertEqual(released['status'], 'released')


if __name__ == '__main__':
    unittest.main()
