from types import SimpleNamespace
import unittest
from unittest.mock import patch

import grid_search_slurm_local as batch_main


class HpcBatchEntrypointTests(unittest.TestCase):
    def test_manual_no_argument_settings_remain_unchanged(self):
        args = SimpleNamespace(
            hpc_request=None,
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

    def test_request_resources_reach_batchtools_slurm_fields(self):
        args = SimpleNamespace(
            hpc_request='hpc_jobs/requests/b2-batch.json',
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


if __name__ == '__main__':
    unittest.main()
