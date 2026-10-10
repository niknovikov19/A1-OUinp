from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_workflow


class HpcWorkflowEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.workflow_params = {
            'workflow_name': 'fixture',
            'retention': {},
            'batch_run_defaults': {
                'partition': 'manual.q',
                'realtime': '7:00:00',
                'nodes': 1,
                'cores_per_node': 60,
                'mem_gb': 256,
                'max_concurrent': 6,
            },
        }
        self.stage_cfg = {
            'name': 'sweep',
            'experiment': 'batch_fixture/sweep',
            'executor': None,
            'processor': 'process.py',
            'batch_param_overrides': {},
            'experiment_overrides': {},
            'batch_run': {},
        }
        self.stage_jobs = {
            'sweep': {
                'resources': {
                    'partition': 'cpu.q',
                    'nodes': 1,
                    'cores': 4,
                    'memory_gb': 8,
                    'wall_time_min': 15,
                },
                'max_concurrent_simulation_jobs': 2,
            },
        }

    def test_request_resources_override_only_stage_job_settings(self):
        batch_mod = SimpleNamespace(get_batch_params=lambda: {'seed': [1, 2]})
        with patch.object(run_workflow, 'load_module', return_value=batch_mod):
            spec, _ = run_workflow._resolve_stage_spec(
                self.workflow_params,
                self.stage_cfg,
                iteration=0,
                run_id='run-1',
                dynamic_overrides={},
                stage_jobs=self.stage_jobs,
            )
        self.assertEqual(spec['batch_params'], {'seed': [1, 2]})
        self.assertEqual(spec['batch_run'], {
            'partition': 'cpu.q',
            'realtime': '00:15:00',
            'nodes': 1,
            'cores_per_node': 4,
            'mem_gb': 8,
            'max_concurrent': 2,
        })

    def test_resolved_stage_consumes_bounded_job_budget(self):
        stage_spec = {
            'stage': 'sweep',
            'executor': None,
            'batch_params': {'seed': [1, 2], 'weight': [0.1, 0.2]},
            'batch_run': {'max_concurrent': 2},
        }
        budget = {'remaining': 5}
        run_workflow._consume_hpc_job_budget(stage_spec, budget)
        self.assertEqual(budget['remaining'], 1)
        with self.assertRaises(ValueError):
            run_workflow._consume_hpc_job_budget(stage_spec, budget)


if __name__ == '__main__':
    unittest.main()
