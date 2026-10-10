from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from hpc_preflight import (
    HpcPreflightError,
    preflight_request,
    read_tracked_request,
)


def make_resources():
    """Return one small valid Slurm resource mapping."""
    return {
        'partition': 'cpu.q',
        'nodes': 1,
        'cores': 1,
        'memory_gb': 2,
        'wall_time_min': 10,
    }


def make_single_request():
    """Return one valid preflight fixture request."""
    return {
        'schema_version': 1,
        'request_id': 'b1-single',
        'job_kind': 'single',
        'target': 'single_fixture/smoke',
        'template_path': 'hpc_jobs/templates/single.sh',
        'expected_result_path': (
            'exp_results/single_fixture/smoke/exp_duration_10_seed_2'
        ),
        'completion_files': ['smoke_result.json'],
        'top_level_resources': make_resources(),
    }


class ModuleLoader:
    """Return fixture modules by their source filename."""

    def __init__(self, modules):
        self.modules = modules

    def __call__(self, fpath):
        return self.modules[Path(fpath).name]


class HpcPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def add_experiment(self, target, batch=False):
        """Create the tracked file shape required by one fixture experiment."""
        dirpath = self.repo_root / 'exp_configs' / target
        dirpath.mkdir(parents=True)
        (dirpath / 'exp_cfg.py').write_text('# fixture\n')
        if batch:
            (dirpath / 'batch_params.py').write_text('# fixture\n')

    def test_single_path_is_derived_from_experiment_config(self):
        request = make_single_request()
        self.add_experiment(request['target'])
        exp_mod = SimpleNamespace(
            apply_exp_cfg=lambda cfg: setattr(cfg, 'duration', 10),
            get_result_subdir=lambda cfg: f'exp_duration_{cfg.duration}_seed_2',
        )
        result = preflight_request(
            self.repo_root,
            request,
            cfg_factory=SimpleNamespace,
            module_loader=ModuleLoader({'exp_cfg.py': exp_mod}),
        )
        self.assertEqual(result['planned_jobs'], 1)
        self.assertEqual(
            result['resolved_result_path'],
            request['expected_result_path'],
        )

    def test_result_mismatch_and_collision_are_rejected(self):
        request = make_single_request()
        self.add_experiment(request['target'])
        exp_mod = SimpleNamespace(
            apply_exp_cfg=lambda cfg: None,
            get_result_subdir=lambda cfg: 'exp_actual',
        )
        loader = ModuleLoader({'exp_cfg.py': exp_mod})
        with self.assertRaises(HpcPreflightError):
            preflight_request(
                self.repo_root,
                request,
                cfg_factory=SimpleNamespace,
                module_loader=loader,
            )

        exp_mod.get_result_subdir = lambda cfg: 'exp_duration_10_seed_2'
        result_dir = self.repo_root / request['expected_result_path']
        result_dir.mkdir(parents=True)
        (result_dir / 'old.json').write_text('{}')
        with self.assertRaises(HpcPreflightError):
            preflight_request(
                self.repo_root,
                request,
                cfg_factory=SimpleNamespace,
                module_loader=loader,
            )

    def test_batch_count_comes_from_batch_params(self):
        request = {
            **make_single_request(),
            'request_id': 'b2-batch',
            'job_kind': 'batch',
            'target': 'batch_fixture/sweep',
            'template_path': 'hpc_jobs/templates/batch.sh',
            'expected_result_path': (
                'exp_results/batch_fixture/sweep/exp_nseed_2_nweight_3'
            ),
            'simulation_job_resources': make_resources(),
            'max_concurrent_simulation_jobs': 2,
            'max_simulation_jobs': 6,
        }
        self.add_experiment(request['target'], batch=True)
        exp_mod = SimpleNamespace(
            apply_exp_cfg=lambda cfg: None,
            gen_exp_name_sub=lambda cfg: 'exp_nseed_2_nweight_3',
        )
        batch_mod = SimpleNamespace(
            get_batch_params=lambda: {
                'seed': [1, 2],
                'weight': [0.1, 0.2, 0.3],
            },
        )
        result = preflight_request(
            self.repo_root,
            request,
            cfg_factory=SimpleNamespace,
            module_loader=ModuleLoader({
                'exp_cfg.py': exp_mod,
                'batch_params.py': batch_mod,
            }),
        )
        self.assertEqual(result['planned_jobs'], 6)
        self.assertEqual(result['parameter_axis_sizes'], {'seed': 2, 'weight': 3})

    def test_workflow_count_and_stage_names_come_from_configs(self):
        request = {
            **make_single_request(),
            'request_id': 'b3-workflow',
            'job_kind': 'workflow',
            'target': 'workflow_fixture',
            'template_path': 'hpc_jobs/templates/workflow.sh',
            'expected_result_path': (
                'exp_results/workflows/workflow_fixture/exp_iterations_2'
            ),
            'stage_jobs': {
                'sweep': {
                    'resources': make_resources(),
                    'max_concurrent_simulation_jobs': 2,
                },
            },
            'max_simulation_jobs': 8,
        }
        workflow_dir = self.repo_root / 'workflow_configs/workflow_fixture'
        workflow_dir.mkdir(parents=True)
        (workflow_dir / 'workflow_cfg.py').write_text('# fixture\n')
        self.add_experiment('batch_fixture/sweep', batch=True)
        workflow = {
            'workflow_name': 'workflow_fixture',
            'max_iterations': 2,
            'stages': [{
                'name': 'sweep',
                'experiment': 'batch_fixture/sweep',
                'executor': None,
                'batch_param_overrides': {'seed': [1, 2]},
            }],
        }
        workflow_mod = SimpleNamespace(
            get_workflow_params=lambda: workflow,
            get_run_id=lambda params: 'exp_iterations_2',
        )
        batch_mod = SimpleNamespace(
            get_batch_params=lambda: {'seed': [1], 'weight': [0.1, 0.2]},
        )
        result = preflight_request(
            self.repo_root,
            request,
            module_loader=ModuleLoader({
                'workflow_cfg.py': workflow_mod,
                'batch_params.py': batch_mod,
            }),
        )
        self.assertEqual(result['planned_jobs'], {'sweep': 8})

    def test_tracked_request_path_and_filename_are_fixed(self):
        request = make_single_request()
        dirpath = self.repo_root / 'hpc_jobs/requests'
        dirpath.mkdir(parents=True)
        (dirpath / 'b1-single.json').write_text(json.dumps(request))
        loaded = read_tracked_request(
            self.repo_root,
            'hpc_jobs/requests/b1-single.json',
        )
        self.assertEqual(loaded, request)
        with self.assertRaises(HpcPreflightError):
            read_tracked_request(
                self.repo_root,
                'hpc_jobs/requests/wrong.json',
            )


if __name__ == '__main__':
    unittest.main()
