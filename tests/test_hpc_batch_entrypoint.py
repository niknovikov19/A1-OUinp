from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import grid_search_slurm_local as batch_main


class HpcBatchEntrypointTests(unittest.TestCase):
    def test_child_script_uses_shared_checkout_and_preserves_failure(self):
        """Keep child jobs on shared storage and expose the srun status. """
        script = batch_main._get_child_script_template()
        checkout = batch_main.DIR_REPO.as_posix()
        self.assertIn(f'#SBATCH --chdir={checkout}', script)
        self.assertIn(f'cd {checkout}', script)
        self.assertIn('set -eo pipefail', script)
        self.assertIn('exec {command}', script)
        self.assertNotIn('{project_path}', script)
        self.assertNotIn('\nwait\n', script)

    def test_local_ray_uses_shared_checkout_without_packaging(self):
        """Avoid transferring the repository to workers on the same node. """
        with patch.dict('os.environ', {'PYTHONPATH': '/existing'}):
            ray_config = batch_main._configure_local_ray()
            python_path = batch_main.os.environ['PYTHONPATH'].split(':')
        self.assertEqual(ray_config, {'include_dashboard': False})
        self.assertEqual(python_path[0], batch_main.DIR_REPO.as_posix())
        self.assertEqual(python_path[1], '/existing')

    def test_manual_no_argument_settings_remain_unchanged(self):
        args = SimpleNamespace(
            hpc_request=None,
            hpc_run_id=None,
            experiment=None,
            partition=None,
            nodes=None,
            cores=None,
            memory_gb=None,
            wall_time_min=None,
            max_concurrent=None,
        )
        settings = batch_main._get_run_settings(args)
        self.assertEqual(settings['experiment'], batch_main.DEFAULT_EXPERIMENT)
        self.assertEqual(settings['resources'], batch_main.DEFAULT_RESOURCES)
        self.assertEqual(
            settings['max_concurrent'],
            batch_main.DEFAULT_MAX_CONCURRENT,
        )

    def test_hpc_batch_summary_is_archived_outside_checkout_root(self):
        """Move each generated HPC summary to its ignored run-specific path. """
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch_main, 'DIR_REPO', Path(tmp)):
                source, archive = batch_main._get_hpc_summary_paths(
                    'b2_child_discovery',
                    'b2-child-discovery-005',
                )
                source.write_text('done\n')
                batch_main._archive_hpc_summary(source, archive)
            self.assertFalse(source.exists())
            self.assertEqual(archive.read_text(), 'done\n')

    def test_request_resources_reach_batchtools_slurm_fields(self):
        args = SimpleNamespace(
            hpc_request='hpc_jobs/requests/b2-batch.json',
            hpc_run_id='b2-batch-001',
            experiment=None,
            partition=None,
            nodes=None,
            cores=None,
            memory_gb=None,
            wall_time_min=None,
            max_concurrent=None,
        )
        resources = {
            'partition': 'cpu.q',
            'nodes': 1,
            'cores': 4,
            'memory_gb': 8,
            'wall_time_min': 15,
        }
        request = {
            'job_kind': 'batch',
            'target': 'batch_fixture/sweep',
            'simulation_job_resources': resources,
            'max_concurrent_simulation_jobs': 2,
            'expected_result_path': 'exp_results/batch_fixture/sweep/exp_001',
        }
        with patch.object(
            batch_main,
            'read_tracked_request',
            return_value=request,
        ), patch.object(batch_main, 'preflight_request'):
            settings = batch_main._get_run_settings(args)
        config = batch_main._build_slurm_config(
            settings['resources'],
            'batch_fixture',
        )
        self.assertEqual(settings['max_concurrent'], 2)
        self.assertEqual(config['partition'], 'cpu.q')
        self.assertEqual(config['realtime'], '00:15:00')
        self.assertEqual(config['nodes'], 1)
        self.assertEqual(config['coresPerNode'], 4)
        self.assertEqual(config['mem'], '8G')
        self.assertIn('--subdir batch_fixture', config['command'])
        self.assertIn(
            'export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"',
            config['custom'],
        )
        self.assertEqual(config['custom'].format(), config['custom'])


if __name__ == '__main__':
    unittest.main()
