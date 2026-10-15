import argparse
import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from hpc_archive import build_archive, hash_path, read_archive, unpack_archive, verify_unpacked
from hpc_bounded import run_bounded
from hpc_result import HpcResultError
from test_hpc_job_control import LETHE, LOCAL, load_script_module
from test_hpc_result import LOCAL as RESULT_LOCAL


GRID_STATUS = load_script_module('chunked_grid_status', 'dev_scratch/hpc/helper_src/remote_grid/hpc-grid-status')
RESULT_REMOTE = load_script_module('archive_remote', 'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-result')


class ChunkedStatusTests(unittest.TestCase):
    def setUp(self):
        """Load the reviewable scheduler policy without contacting Slurm. """
        root = Path(__file__).resolve().parents[1]
        self.config = json.loads((root / 'dev_scratch/hpc/helper_src/config_examples/remote-hpc-status.json.example').read_text())

    def test_chunk_boundaries_coverage_and_query_counts(self):
        """Keep one squeue call and partition only absent IDs into accounting chunks. """
        for count in (1, 13, 25, 26, 61, 101, 1000):
            commands = []

            def query(command, timeout):
                """Return one active ID and completed accounting fixtures. """
                commands.append(command)
                if command[0].endswith('squeue'):
                    return '1|RUNNING|None\n99999|PENDING|Resources\n'
                ids = command[command.index('--jobs') + 1].split(',')
                self.assertLessEqual(len(ids), 25)
                return ''.join(f'{item}|COMPLETED|0:0|None\n' for item in ids)

            with patch.object(GRID_STATUS, 'run_fixed', side_effect=query):
                jobs, counts = GRID_STATUS.query_scheduler(self.config, list(range(1, count + 1)))
            self.assertEqual(counts, {'squeue': 1, 'sacct': (count - 1 + 24) // 25})
            self.assertEqual([job['job_id'] for job in jobs], list(range(1, count + 1)))
            self.assertEqual(jobs[0]['normalized_state'], 'running')
            self.assertTrue(all(job['normalized_state'] == 'completed' for job in jobs[1:]))

    def test_missing_accounting_and_partial_failure_never_imply_completion(self):
        """Keep missing IDs unknown and reject failed or expired observations. """
        with patch.object(GRID_STATUS, 'run_fixed', return_value=''):
            jobs, counts = GRID_STATUS.query_scheduler(self.config, [1, 2])
        self.assertTrue(all(job['accounting_gap'] for job in jobs))
        with patch.object(GRID_STATUS, 'run_fixed', side_effect=['', '', GRID_STATUS.StatusUnavailable('chunk failed')]):
            with self.assertRaises(GRID_STATUS.StatusUnavailable):
                GRID_STATUS.query_scheduler(self.config, list(range(1, 62)))
        with patch.object(GRID_STATUS.time, 'monotonic', side_effect=[0, 0, 200]):
            with patch.object(GRID_STATUS, 'run_fixed', return_value='') as query:
                with self.assertRaises(GRID_STATUS.StatusUnavailable):
                    GRID_STATUS.query_scheduler(self.config, [1])
                self.assertEqual(query.call_count, 1)

    def test_shared_policy_remains_accepted_on_both_status_hops(self):
        """Accept the chunking fields on both grid and Lethe status validators. """
        lethe = load_script_module('chunked_lethe_status', 'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-status')
        self.assertEqual(GRID_STATUS.validate_config(deepcopy(self.config)), self.config)
        self.assertEqual(lethe.validate_config(deepcopy(self.config)), self.config)
        invalid = deepcopy(self.config)
        invalid['scheduler']['accounting_chunk_size'] = 0
        with self.assertRaises(GRID_STATUS.StatusFailure):
            GRID_STATUS.validate_config(invalid)

    def test_multi_chunk_reply_survives_the_lethe_status_hop(self):
        """Accept real grid-parser replies with multiple accounting calls at the next hop. """
        lethe = load_script_module('chunked_status_transport', 'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-status')
        for count in (26, 61):
            job_ids = list(range(1, count + 1))

            def query(command, timeout):
                """Return a completed allocation for each requested accounting ID. """
                if command[0].endswith('squeue'):
                    return ''
                ids = command[command.index('--jobs') + 1].split(',')
                return ''.join(f'{item}|COMPLETED|0:0|None\n' for item in ids)

            with patch.object(GRID_STATUS, 'run_fixed', side_effect=query):
                jobs, counts = GRID_STATUS.query_scheduler(self.config, job_ids)
            reply = {'operation': 'grid-status', 'status': 'ok', 'job_ids': job_ids,
                     'jobs': jobs, 'query_count': counts, 'accounting_grace_sec': 120,
                     'observed_at_utc': '2026-10-15T04:00:00+00:00', 'helper': GRID_STATUS.helper_identity()}
            completed = subprocess.CompletedProcess([], 0, json.dumps(reply).encode(), b'')
            with patch.object(lethe, 'run_command', return_value=completed):
                result, code = lethe.run_grid(self.config, 'status', job_ids)
            self.assertEqual(code, 0)
            self.assertEqual(result['query_count']['sacct'], (count + 24) // 25)
            for invalid in (True, -1, (count + 24) // 25 + 1):
                bad = deepcopy(reply)
                bad['query_count']['sacct'] = invalid
                completed = subprocess.CompletedProcess([], 0, json.dumps(bad).encode(), b'')
                with patch.object(lethe, 'run_command', return_value=completed):
                    with self.assertRaises(lethe.StatusUnavailable):
                        lethe.run_grid(self.config, 'status', job_ids)


class BoundedProcessTests(unittest.TestCase):
    def test_streaming_limits_and_timeout(self):
        """Stream large payloads to disk and stop oversized or stalled processes. """
        with tempfile.TemporaryFile() as stream:
            result = run_bounded([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"x" * 2000000)'],
                                 10, 2000000, output=stream)
            self.assertEqual(result.stdout, b'')
            self.assertEqual(stream.tell(), 2000000)
        with self.assertRaises(ValueError):
            run_bounded([sys.executable, '-c', 'print("x" * 10000)'], 10, 100)
        with self.assertRaises(ValueError):
            run_bounded([sys.executable, '-c', 'import sys; sys.stderr.write("x" * 10000)'], 10, 100, 100)
        with self.assertRaises(subprocess.TimeoutExpired):
            run_bounded([sys.executable, '-c', 'import time; time.sleep(2)'], 0.05, 100)


class BatchLimitPolicyTests(unittest.TestCase):
    def setUp(self):
        """Load the reviewed policies and isolated preparation/promotion functions. """
        self.root = Path(__file__).resolve().parents[1]
        prefix = self.root / 'dev_scratch/hpc/helper_src'
        self.local = json.loads((prefix / 'config_examples/hpc-helper.json.example').read_text())
        self.remote = json.loads((prefix / 'config_examples/remote-hpc-prepare.json.example').read_text())
        self.prepare = load_script_module('batch_limit_prepare', 'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-prepare')
        self.promotion = load_script_module('batch_limit_promotion', 'dev_scratch/hpc/helper_src/promotion/promote_batch_limits.py')

    def test_both_policies_validate_and_source_hashes_match(self):
        """Keep both policy layers aligned and all per-job resource bounds unchanged. """
        from hpc_common import validate_config
        validate_config(self.local)
        self.prepare.validate_config(self.remote)
        self.assertEqual(self.local['scheduler']['limits'], self.remote['scheduler']['limits'])
        limits = self.remote['scheduler']['limits']
        self.assertEqual(limits['max_child_jobs'], 60)
        self.assertEqual(limits['max_concurrent_jobs'], 10)
        self.assertEqual(limits['max_cores_per_job'], 30)
        self.assertEqual(limits['max_memory_gb_per_job'], 128)
        self.assertEqual(limits['max_nodes_per_job'], 1)
        self.assertEqual(limits['max_wall_time_min'], 1440)
        for policy in self.promotion.POLICIES.values():
            digest = hashlib.sha256((self.root / policy['source']).read_bytes()).hexdigest()
            self.assertEqual(digest, policy['new'])

    def test_sixty_ten_accepts_and_excess_job_or_resource_requests_reject(self):
        """Enforce the requested count/concurrency boundary without relaxing per-job ceilings. """
        request = json.loads((self.root / 'hpc_jobs/requests/hstep-l2-long-pilot.json').read_text())
        request.update(max_simulation_jobs=60, max_concurrent_simulation_jobs=10)
        self.prepare.validate_request_policy(request, self.remote)
        for key, excessive in (('max_simulation_jobs', 61), ('max_concurrent_simulation_jobs', 11)):
            changed = {**request, key: excessive}
            with self.assertRaises(self.prepare.RejectedInput):
                self.prepare.validate_request_policy(changed, self.remote)
        for key, excessive in (('cores', 31), ('memory_gb', 129), ('nodes', 2), ('wall_time_min', 1441)):
            changed = deepcopy(request)
            changed['simulation_job_resources'][key] = excessive
            with self.assertRaises(self.prepare.RejectedInput):
                self.prepare.validate_request_policy(changed, self.remote)

    def test_promotion_permits_only_two_limit_changes_and_idempotence(self):
        """Reject unrelated policy edits while allowing old-to-new and repeat promotions. """
        for proposed in (self.local, self.remote):
            old = deepcopy(proposed)
            old['scheduler']['limits'].update(max_child_jobs=12, max_concurrent_jobs=5)
            self.promotion.validate_transition(old, proposed)
            self.promotion.validate_transition(proposed, proposed)
            changed = deepcopy(proposed)
            changed['scheduler']['limits']['max_memory_gb_per_job'] = 256
            with self.assertRaises(ValueError):
                self.promotion.validate_transition(old, changed)


class LogPageTests(unittest.TestCase):
    def test_page_sizes_offsets_and_incremental_streams(self):
        """Page twelve child logs without scheduler calls or repeated prefix reads. """
        config = {'logs': {'max_cursor_payload_bytes': 65536, 'max_bytes_per_stream': 65536,
                           'max_lines_per_stream': 100}}
        records = [{'child_key': f'child_{index:03d}', 'slurm_job_id': 100 + index} for index in range(12)]
        payload = base64.urlsafe_b64encode(json.dumps({'schema_version': 1, 'children': {}}).encode()).decode()
        with tempfile.TemporaryDirectory() as temporary:
            for record in records:
                for name in ('stdout', 'stderr'):
                    (Path(temporary) / f"{record['child_key']}_{name}").write_text('first\nsecond\n')
            resolve = lambda prepared, children, key, name: Path(temporary) / f'{key}_{name}'
            with patch.object(LETHE, 'load_prepared', return_value={'run_id': 'fixture'}), \
                 patch.object(LETHE, 'load_submission', return_value={'status': 'submitted', 'slurm_job_id': 99}), \
                 patch.object(LETHE, 'load_child_records', return_value=records) as load_index, \
                 patch.object(LETHE, 'resolve_child_log_path', side_effect=resolve), \
                 patch.object(LETHE, 'scheduler_statuses', side_effect=AssertionError('No scheduler query for logs')):
                page = LETHE.log_page(config, 'fixture', payload, 5)
                self.assertEqual(load_index.call_count, 1)
                self.assertEqual(page['next_offset'], 10)
                self.assertEqual(len(page['children']), 5)
                state = {'schema_version': 1, 'runs': {}}
                for child in page['children']:
                    LOCAL.update_cursors(state, 'fixture', child, child['child_key'])
                payload2 = {'schema_version': 1, 'children': state['runs']['fixture']['children']}
                encoded = base64.urlsafe_b64encode(json.dumps(payload2).encode()).decode()
                repeated = LETHE.log_page(config, 'fixture', encoded, 5)
                self.assertTrue(all(not child['streams']['stdout']['content'] for child in repeated['children']))
                last = LETHE.log_page(config, 'fixture', payload, 10)
                self.assertEqual(len(last['children']), 2)
                self.assertIsNone(last['next_offset'])
        args = LOCAL.build_parser().parse_args(['logs', 'fixture', '--offset', '-1'])
        with self.assertRaises(ValueError):
            LOCAL.validate_args(args)


class CompactArchiveTests(unittest.TestCase):
    def setUp(self):
        """Build a synthetic sixty-child compact-result tree. """
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.result_root = 'exp_results/fixture/sixty'
        self.prepared = {'run_id': 'archive-fixture', 'git_commit': 'a' * 40,
                         'expected_result_path': self.result_root, 'completion_files': ['jobs/index.jsonl']}
        for index in range(60):
            for directory, suffix in (('cfg', 'json'), ('results', 'json'), ('rvec_xr', 'nc'), ('hvec_xr', 'nc')):
                self.prepared['completion_files'].append(f'{directory}/job_{index:05d}.{suffix}')
        for relative in self.prepared['completion_files']:
            target = self.root / self.result_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(relative.encode() * 10)
        self.prepared['completion_files'].append('raw.pkl')
        (self.root / self.result_root / 'raw.pkl').write_bytes(b'not copied')
        self.final = {'status': 'complete', 'completion_files_verified': self.prepared['completion_files']}
        self.archive = self.root / 'compact.tar.gz'
        self.metadata = build_archive(self.root, self.prepared, self.final, self.archive)

    def tearDown(self):
        """Remove only the temporary archive fixture. """
        self.temporary.cleanup()

    def test_sixty_child_roundtrip_and_preservation(self):
        """Verify all 241 compact files and preserve existing changed local data. """
        manifest = read_archive(self.archive, self.metadata)
        self.assertEqual(len(manifest['files']), 241)
        self.assertNotIn('raw.pkl', [item['path'] for item in manifest['files']])
        destination = unpack_archive(self.archive, self.metadata, self.root / 'unpacked')
        verify_unpacked(destination, manifest)
        (destination / 'cfg/job_00000.json').write_text('user change')
        with self.assertRaises(HpcResultError):
            verify_unpacked(destination, manifest)
        with self.assertRaises(HpcResultError):
            unpack_archive(self.archive, self.metadata, destination)
        self.assertEqual((destination / 'cfg/job_00000.json').read_text(), 'user change')

    def test_symlink_unfinalized_and_tampered_archive_rejected(self):
        """Reject unsafe sources, absent final evidence, and corrupted transfers. """
        path = self.root / self.result_root / 'cfg/job_00000.json'
        path.unlink()
        path.symlink_to(self.archive)
        with self.assertRaises(HpcResultError):
            build_archive(self.root, self.prepared, self.final, self.root / 'bad.tar.gz')
        with self.assertRaises(HpcResultError):
            build_archive(self.root, self.prepared, {'status': 'failed'}, self.root / 'failed.tar.gz')
        self.archive.write_bytes(b'corrupted')
        with self.assertRaises(HpcResultError):
            read_archive(self.archive, self.metadata)

    def test_per_file_hashes_and_finalization_evidence_are_required(self):
        """Reject incomplete final evidence and payload changes even with a new bundle hash. """
        missing = {**self.final, 'completion_files_verified': ['jobs/index.jsonl']}
        with self.assertRaises(HpcResultError):
            build_archive(self.root, self.prepared, missing, self.root / 'missing.tar.gz')
        changed = self.root / 'changed.tar.gz'
        with tarfile.open(self.archive, 'r:gz') as original, tarfile.open(changed, 'w:gz') as output:
            for member in original:
                payload = original.extractfile(member).read()
                if member.name == 'cfg/job_00000.json':
                    payload = b'x' * len(payload)
                output.addfile(member, io.BytesIO(payload))
        metadata = {**self.metadata, 'size_bytes': changed.stat().st_size, 'sha256': hash_path(changed)}
        with self.assertRaises(HpcResultError):
            read_archive(changed, metadata)

    def test_traversal_and_link_members_rejected(self):
        """Never extract archive members outside the fixed compact profile. """
        for name, link in (('../escape', False), ('cfg/link.json', True)):
            with tarfile.open(self.archive, 'w:gz') as archive:
                member = tarfile.TarInfo(name)
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '/etc/passwd'
                    archive.addfile(member)
                else:
                    member.size = 1
                    archive.addfile(member, io.BytesIO(b'x'))
            metadata = {**self.metadata, 'size_bytes': self.archive.stat().st_size, 'sha256': hash_path(self.archive)}
            with self.assertRaises(HpcResultError):
                read_archive(self.archive, metadata, self.root / 'attack')
        self.assertFalse((self.root / 'escape').exists())

    def test_local_archive_download_cache_and_unpack(self):
        """Use one binary transfer and reuse its verified local cache on repetition. """
        response = {'schema_version': 1, 'operation': 'result-archive', 'status': 'ok',
                    'run_id': self.prepared['run_id'], 'archive': self.metadata, 'result': 'created'}
        args = argparse.Namespace(operation='archive', run_id=self.prepared['run_id'], unpack=True)
        result_config = {'cache_root': str(self.root / 'cache'), 'remote_helper': '/fixed/helper'}
        config = {'ssh': {'lethe_host_alias': 'lethe', 'connect_timeout_sec': 15}}

        def transfer(command, timeout, maximum, output):
            """Stream the synthetic payload without a network connection. """
            output.write(self.archive.read_bytes())
            return subprocess.CompletedProcess(command, 0, b'', b'')

        with patch.object(RESULT_LOCAL, 'run_remote', side_effect=lambda *args: (deepcopy(response), 0)), \
             patch.object(RESULT_LOCAL, 'run_bounded', side_effect=transfer) as download:
            first, code = RESULT_LOCAL.get_archive(config, result_config, args)
            second, code = RESULT_LOCAL.get_archive(config, result_config, args)
        self.assertEqual(first['result'], 'downloaded')
        self.assertEqual(second['result'], 'cache-hit')
        self.assertEqual(download.call_count, 1)
        self.assertTrue(Path(first['unpacked_path']).is_dir())

    def test_remote_archive_reuses_bundle_without_rereading_sources(self):
        """Create a protected-state-shaped bundle once and reuse its metadata. """
        state = self.root / 'state'
        (state / 'result-archives').mkdir(parents=True)
        lock = state / 'result.lock'
        lock.touch(mode=0o600)
        config = {'git': {'automation_checkout': str(self.root)},
                  'state': {'root': str(state), 'result_lock': str(lock)}}
        with patch.object(RESULT_REMOTE, 'load_completed_run', return_value=(self.prepared, self.final)):
            first = RESULT_REMOTE.archive_result(config, self.prepared['run_id'])
            with patch.object(RESULT_REMOTE, 'build_archive', side_effect=AssertionError('No source rescan')):
                second = RESULT_REMOTE.archive_result(config, self.prepared['run_id'])
        self.assertEqual(first['result'], 'created')
        self.assertEqual(second['result'], 'existing')
        self.assertEqual(first['archive'], second['archive'])
        self.assertEqual(first['archive']['file_count'], 241)


if __name__ == '__main__':
    unittest.main()
