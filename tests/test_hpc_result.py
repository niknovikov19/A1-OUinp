import base64
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import tempfile
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hpc_job import hash_data
from hpc_result import (
    HpcResultError,
    build_result_inventory,
    read_inventory_artifact,
    select_artifact,
    validate_result_inventory,
)
COMMIT = '1' * 40
NOW = '2026-10-11T12:00:00+00:00'
REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_HELPER_ROOT = REPO_ROOT / 'dev_scratch/hpc/helper_src/local'
sys.path.insert(0, LOCAL_HELPER_ROOT.as_posix())


def load_script_module(name, relpath):
    """Load one extensionless candidate script as a test module. """
    fpath = REPO_ROOT / relpath
    loader = SourceFileLoader(name, fpath.as_posix())
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


LOCAL = load_script_module(
    'hpc_result_candidate',
    'dev_scratch/hpc/helper_src/local/hpc-result',
)


def make_prepared(repo, run_id='b5-result-fixture'):
    """Build one complete batch prepared record. """
    result = 'exp_results/batch_fixture/b5/result_001'
    run_dir = repo / 'hpc_jobs' / 'runs' / run_id
    return {
        'schema_version': 1,
        'request_id': 'b5-result-fixture',
        'request_sha256': hash_data({'request': 'b5'}),
        'run_id': run_id,
        'job_kind': 'batch',
        'git_commit': COMMIT,
        'simulation_job_limit': 2,
        'expected_result_path': result,
        'completion_files': [
            'jobs/index.jsonl',
            'results/run_00000.json',
            'results/run_00001.json',
        ],
        'job_run_dir': run_dir.as_posix(),
        'submit_script': (run_dir / 'submit.sh').as_posix(),
        'stdout_path': (run_dir / 'slurm-%j.out').as_posix(),
        'stderr_path': (run_dir / 'slurm-%j.err').as_posix(),
        'status': 'prepared',
        'rendered_script_sha256': '2' * 64,
    }


def make_final(prepared):
    """Build one matching successful final record. """
    return {
        'schema_version': 1,
        'run_id': prepared['run_id'],
        'request_id': prepared['request_id'],
        'request_sha256': prepared['request_sha256'],
        'git_commit': prepared['git_commit'],
        'rendered_script_sha256': prepared['rendered_script_sha256'],
        'submit_script': prepared['submit_script'],
        'status': 'complete',
        'slurm_job_id': 117900,
        'scheduler_state': 'COMPLETED',
        'completion_files_verified': prepared['completion_files'],
        'child_job_ids': [117901, 117902],
        'finalized_at_utc': NOW,
    }


def make_children(prepared):
    """Build two validated-child-shaped records. """
    result = prepared['expected_result_path']
    return [
        {
            'child_key': f'run_{index:05d}',
            'parameters': {'seed': index + 1},
            'expected_outputs': [f'{result}/results/run_{index:05d}.json'],
        }
        for index in range(2)
    ]


class HpcResultTests(unittest.TestCase):
    def setUp(self):
        """Create one finalized two-child result fixture. """
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.prepared = make_prepared(self.repo)
        self.final = make_final(self.prepared)
        self.children = make_children(self.prepared)
        result = self.repo / self.prepared['expected_result_path']
        (result / 'results').mkdir(parents=True)
        (result / 'jobs').mkdir()
        (result / 'jobs/index.jsonl').write_text('{}\n')
        for index in range(2):
            (result / f'results/run_{index:05d}.json').write_text(
                f'{{"seed": {index + 1}}}\n'
            )
        self.types = {'result-json': ['.json'], 'raster': ['.png']}
        self.limits = {'max_artifacts': 4, 'checksum_max_bytes': 1024}

    def tearDown(self):
        """Remove the temporary result fixture. """
        self.temp.cleanup()

    def build_inventory(self):
        """Build the fixture inventory. """
        return build_result_inventory(
            self.repo,
            self.prepared,
            self.final,
            self.children,
            self.types,
            self.limits,
            NOW,
        )

    def test_inventory_uses_only_declared_child_outputs(self):
        """Inventory exact child outputs with parameters and fingerprints. """
        unrelated = self.repo / self.prepared['expected_result_path'] / 'large.bin'
        unrelated.write_bytes(b'x' * 10000)
        inventory = self.build_inventory()
        validate_result_inventory(inventory, self.prepared)
        self.assertEqual(inventory['artifact_count'], 2)
        self.assertEqual(inventory['known_output_count'], 2)
        self.assertEqual(inventory['artifacts'][0]['parameters'], {'seed': 1})
        self.assertIsNotNone(inventory['artifacts'][0]['sha256'])
        self.assertNotIn('large.bin', str(inventory))

    def test_inventory_accepts_child_outputs_not_repeated_in_the_request(self):
        """Retrieve child files verified by the repaired finalization rule. """
        required = list(self.prepared['completion_files'])
        self.prepared['completion_files'] = ['jobs/index.jsonl']
        self.final['completion_files_required'] = required
        inventory = self.build_inventory()
        artifact = select_artifact(inventory, 'run_00001', 'result-json')
        self.assertEqual(read_inventory_artifact(self.repo, artifact, 1024), b'{"seed": 2}\n')

    def test_exact_selection_and_bounded_read(self):
        """Read one exact known artifact and reject unknown selectors. """
        inventory = self.build_inventory()
        artifact = select_artifact(inventory, 'run_00001', 'result-json')
        data = read_inventory_artifact(self.repo, artifact, 1024)
        self.assertEqual(data, b'{"seed": 2}\n')
        with self.assertRaises(HpcResultError):
            select_artifact(inventory, '../run_00001', 'result-json')
        with self.assertRaises(HpcResultError):
            select_artifact(inventory, 'run_00001', 'unknown')

    def test_changed_symlink_and_oversize_artifacts_are_rejected(self):
        """Reject changed files, symlinks, and transfers above the byte cap. """
        inventory = self.build_inventory()
        artifact = select_artifact(inventory, 'run_00000', 'result-json')
        fpath = self.repo / artifact['relative_path']
        fpath.write_text('{"changed": true}\n')
        with self.assertRaises(HpcResultError):
            read_inventory_artifact(self.repo, artifact, 1024)
        fpath.unlink()
        fpath.symlink_to('/etc/passwd')
        with self.assertRaises(HpcResultError):
            read_inventory_artifact(self.repo, artifact, 1024)
        artifact['size_bytes'] = 2048
        with self.assertRaises(HpcResultError):
            read_inventory_artifact(self.repo, artifact, 1024)

    def test_local_cache_avoids_a_second_artifact_transfer(self):
        """Download once and satisfy the repeated request from verified cache. """
        data = b'{"seed": 2}\n'
        artifact = {
            'child_key': 'run_00001',
            'parameters': {'seed': 2},
            'artifact_type': 'result-json',
            'relative_path': 'exp_results/group/result.json',
            'size_bytes': len(data),
            'mtime_ns': 1,
            'sha256': hashlib.sha256(data).hexdigest(),
        }
        inventory_result = {
            'status': 'ok',
            'inventory': {'artifacts': [artifact]},
        }
        transfer_result = {
            'status': 'ok',
            'artifact': artifact,
            'content_base64': base64.b64encode(data).decode(),
            'result': 'transfer',
        }
        args = SimpleNamespace(
            operation='get',
            run_id='b5-result-fixture',
            child_key='run_00001',
            artifact_type='result-json',
        )
        config = {'schema_version': 1}
        result_config = {
            'cache_root': (self.repo / 'cache').as_posix(),
            'remote_helper': '/fixed/helper',
        }
        with patch.object(
            LOCAL,
            'run_remote',
            side_effect=[(inventory_result, 0), (transfer_result, 0)],
        ) as remote:
            first, first_code = LOCAL.get_result(config, result_config, args)
        self.assertEqual(first_code, 0)
        self.assertEqual(first['result'], 'downloaded')
        self.assertEqual(remote.call_count, 2)
        with patch.object(
            LOCAL,
            'run_remote',
            return_value=(inventory_result, 0),
        ) as remote:
            second, second_code = LOCAL.get_result(config, result_config, args)
        self.assertEqual(second_code, 0)
        self.assertEqual(second['result'], 'cache-hit')
        self.assertEqual(remote.call_count, 1)

    def test_local_unknown_selector_is_rejected(self):
        """Classify a missing inventory selector as rejected, not unknown. """
        inventory = {'artifacts': []}
        with self.assertRaises(LOCAL.RejectedInput):
            LOCAL.select_inventory_artifact(
                inventory,
                'unknown',
                'result-json',
            )


if __name__ == '__main__':
    unittest.main()
