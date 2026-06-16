import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import xarray as xr

import run_workflow
from workflow_utils import load_job_records, read_json


DIR_REPO = Path(__file__).resolve().parents[1]
DIR_DUMMY = DIR_REPO / 'workflow_configs' / 'wmat_transfer_dummy'
DIR_WSWEEP = (
    DIR_REPO / 'workflow_configs' / 'wmat_transfer_dummy_wsweep'
)
DIR_CONNECTED_WSWEEP = (
    DIR_REPO / 'workflow_configs' /
    'wmat_transfer_dummy_connected_wsweep'
)


def load_module_unique(fpath, name):
    """Load one source file without reusing its repository module name."""
    spec = importlib.util.spec_from_file_location(name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executor = load_module_unique(
            DIR_DUMMY / 'link_existing_results.py',
            'workflow_dummy_executor_test',
        )

    def _write_fixture(self, dirpath, params_by_job, missing_jobs=None):
        """Write one small cfg and result fixture batch."""
        missing_jobs = set(missing_jobs or [])
        dirpath_cfg = dirpath / 'cfg'
        dirpath_results = dirpath / 'results'
        dirpath_cfg.mkdir(parents=True)
        dirpath_results.mkdir()

        # Keep cfg and output names compatible with the real fixtures
        for job_id, params in enumerate(params_by_job):
            sim_label = f'fixture_{job_id:05d}'
            payload = {
                'simConfig': {
                    'simLabel': sim_label,
                    **params,
                },
            }
            fpath_cfg = (
                dirpath_cfg /
                f'cfg_{job_id:05d}_fixture.json'
            )
            fpath_cfg.write_text(json.dumps(payload))
            if job_id in missing_jobs:
                continue
            fpath_output = (
                dirpath_results /
                f'result_{job_id:05d}_fixture.json'
            )
            fpath_output.write_text(json.dumps({'job_id': job_id}))

    def _get_stage_spec(self):
        """Return a two-job executor stage specification."""
        return {
            'workflow_name': 'test',
            'run_id': 'run',
            'iteration': 0,
            'stage': 'fixture',
            'stage_spec_hash': 'fixture-hash',
            'executor': 'link_existing_results.py',
            'executor_params': {},
            'batch_params': {
                'seed': [1],
                'amp': [10, 20],
            },
        }

    def _get_executor_params(self, dirpath_source):
        """Return executor parameters for a JSON result fixture."""
        return {
            'source_dir': dirpath_source.as_posix(),
            'linked_dirs': {
                'cfg': 'cfg',
                'results': 'results',
            },
            'output_dir': 'results',
            'output_pattern': 'result_{job:05d}_*.json',
        }

    def test_executor_links_results_and_writes_compact_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_source = dirpath / 'source'
            dirpath_stage = dirpath / 'stage'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 20},
            ]
            self._write_fixture(dirpath_source, params)
            executor_params = self._get_executor_params(dirpath_source)
            stage_spec = self._get_stage_spec()

            self.executor.run_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            )

            # Raw data stay in the source while local links and metadata appear
            self.assertTrue(
                (dirpath_stage / 'sim_results' / 'cfg').is_symlink()
            )
            self.assertTrue(
                (dirpath_stage / 'sim_results' / 'results').is_symlink()
            )
            records = load_job_records(dirpath_stage)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[1]['batch_params']['amp'], 20)
            manifest = read_json(
                dirpath_stage / 'meta' / 'source_manifest.json'
            )
            self.assertEqual(len(manifest['jobs']), 2)
            self.assertIn('mtime_ns', manifest['jobs'][0]['output'])
            self.assertTrue(self.executor.validate_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            ))

    def test_executor_reuse_is_idempotent_and_repairs_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_source = dirpath / 'source'
            dirpath_stage = dirpath / 'stage'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 20},
            ]
            self._write_fixture(dirpath_source, params)
            executor_params = self._get_executor_params(dirpath_source)
            stage_spec = self._get_stage_spec()

            self.executor.run_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            )
            fpath_manifest = (
                dirpath_stage / 'meta' / 'source_manifest.json'
            )
            manifest_before = fpath_manifest.read_text()

            # A wrong local symlink invalidates resume but is repairable
            fpath_link = dirpath_stage / 'sim_results' / 'results'
            fpath_link.unlink()
            dirpath_wrong = dirpath / 'wrong'
            dirpath_wrong.mkdir()
            fpath_link.symlink_to(dirpath_wrong, target_is_directory=True)
            self.assertFalse(self.executor.validate_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            ))

            self.executor.run_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            )
            self.assertEqual(fpath_manifest.read_text(), manifest_before)
            self.assertEqual(
                fpath_link.resolve(),
                (dirpath_source / 'results').resolve(),
            )

    def test_executor_rejects_missing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_source = Path(tmp) / 'source'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 20},
            ]
            self._write_fixture(
                dirpath_source,
                params,
                missing_jobs=[1],
            )
            with self.assertRaises(ValueError):
                self.executor.run_stage(
                    Path(tmp) / 'stage',
                    self._get_stage_spec(),
                    **self._get_executor_params(dirpath_source),
                )

    def test_executor_rejects_duplicate_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_source = Path(tmp) / 'source'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 10},
            ]
            self._write_fixture(dirpath_source, params)
            with self.assertRaisesRegex(ValueError, 'Duplicate fixture'):
                self.executor.run_stage(
                    Path(tmp) / 'stage',
                    self._get_stage_spec(),
                    **self._get_executor_params(dirpath_source),
                )

    def test_executor_refuses_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_source = dirpath / 'source'
            dirpath_stage = dirpath / 'stage'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 20},
            ]
            self._write_fixture(dirpath_source, params)
            executor_params = self._get_executor_params(dirpath_source)
            stage_spec = self._get_stage_spec()
            self.executor.run_stage(
                dirpath_stage,
                stage_spec,
                **executor_params,
            )

            # Size and mtime changes both appear in the saved fingerprint
            fpath_output = (
                dirpath_source / 'results' /
                'result_00000_fixture.json'
            )
            fpath_output.write_text('changed fixture output')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                self.executor.validate_stage(
                    dirpath_stage,
                    stage_spec,
                    **executor_params,
                )

    def test_runner_dispatches_executor_without_batchtools(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_source = dirpath / 'source'
            dirpath_stage = dirpath / 'stage'
            params = [
                {'seed': 1, 'amp': 10},
                {'seed': 1, 'amp': 20},
            ]
            self._write_fixture(dirpath_source, params)
            stage_spec = self._get_stage_spec()
            stage_spec['executor_params'] = self._get_executor_params(
                dirpath_source
            )
            workflow_params = {
                'wait_refresh_sec': 0,
                'wait_timeout_sec': 1,
            }

            # The executor path must remain usable without BatchTools imports
            with patch.object(
                run_workflow,
                '_load_batchtools',
                side_effect=AssertionError('BatchTools should not load'),
            ) as load_batchtools:
                run_workflow._run_stage(
                    dirpath_stage,
                    stage_spec,
                    {},
                    workflow_params,
                    DIR_DUMMY,
                )
            load_batchtools.assert_not_called()
            complete = read_json(
                dirpath_stage / 'meta' / 'stage_complete.json'
            )
            self.assertEqual(complete['job_count'], 2)
            self.assertEqual(
                complete['executor'],
                'link_existing_results.py',
            )


class DummyWorkflowConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_DUMMY / 'workflow_cfg.py',
            'workflow_dummy_cfg_test',
        )

    def test_default_run_id_describes_fixture_grids(self):
        params = self.cfg.get_workflow_params()
        expected = (
            'exp_wmat_transfer_dummy_'
            'dw_nseed_1_nibkg_10_t_5_15_'
            'rr_nseed_1_npre_5_nf_1_namp_1_t_5_7'
        )
        self.assertEqual(self.cfg.get_run_id(params), expected)

        # Grid-size changes should select another result directory
        params['stages'][0]['batch_param_overrides']['seed_main'].append(
            1001
        )
        self.assertNotEqual(self.cfg.get_run_id(params), expected)


class DummyWeightSweepConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_WSWEEP / 'workflow_cfg.py',
            'workflow_dummy_wsweep_cfg_test',
        )

    def test_workflow_processors_are_physical_files(self):
        workflow_dirs = [DIR_DUMMY, DIR_WSWEEP]
        for dirpath in workflow_dirs:
            for fname in ['process_dw.py', 'process_rr.py']:
                with self.subTest(dirpath=dirpath.name, fname=fname):
                    fpath = dirpath / fname
                    self.assertTrue(fpath.is_file())
                    self.assertFalse(fpath.is_symlink())

    def test_weight_context_advances_for_three_iterations(self):
        params = self.cfg.get_workflow_params()
        context = params['initial_context']
        current_values = []
        next_values = []

        # Reuse a small fake transfer result while advancing only the context
        for iteration in range(params['max_iterations']):
            current_values.append(
                context['wmat_multipliers'][0]['mult']
            )
            outcome = self.cfg.finish_iteration(
                iteration,
                context,
                {
                    'dw': {'IT2': -0.01},
                    'rr': SimpleNamespace(
                        sizes={'pop_pre': 5, 'pop_post': 5},
                    ),
                },
                [],
            )
            next_values.append(
                outcome['next_context'][
                    'wmat_multipliers'
                ][0]['mult']
            )
            self.assertIsNone(outcome['stop_reason'])
            self.assertFalse(outcome['result']['scientific_use'])
            context = outcome['next_context']

        self.assertEqual(current_values, [2, 3, 4.5])
        self.assertEqual(next_values, [3, 4.5, 6.75])

    def test_stage_overrides_include_current_weights(self):
        context = {
            'wmat_multipliers': [
                {'pre': 'IT2', 'post': 'IT2', 'mult': 3},
            ],
        }
        corrections = {'IT2': -0.01}
        dw = self.cfg.get_stage_overrides(
            'dw',
            1,
            context,
            {},
            [],
        )
        rr = self.cfg.get_stage_overrides(
            'rr',
            1,
            context,
            {'dw': corrections},
            [],
        )
        self.assertEqual(
            dw['experiment_overrides']['wmat_multipliers'],
            context['wmat_multipliers'],
        )
        self.assertEqual(
            rr['experiment_overrides']['wmat_multipliers'],
            context['wmat_multipliers'],
        )
        self.assertEqual(
            rr['experiment_overrides']['ibkg_corrections'],
            corrections,
        )

    def test_default_run_id_includes_iteration_count(self):
        params = self.cfg.get_workflow_params()
        run_id = self.cfg.get_run_id(params)
        self.assertIn('wmat_transfer_dummy_wsweep_niter_3', run_id)


class DummyConnectedWeightSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_CONNECTED_WSWEEP / 'workflow_cfg.py',
            'workflow_dummy_connected_wsweep_cfg_test',
        )
        cls.processor = load_module_unique(
            DIR_CONNECTED_WSWEEP / 'process_connected_psd.py',
            'workflow_dummy_connected_wsweep_processor_test',
        )

    def _make_rates(self):
        """Create two-seed rates with one known spectral peak."""
        time = np.arange(2, 3, 0.005)
        values = np.zeros((2, 5, len(time)))
        for n_seed in range(2):
            for n_pop in range(5):
                values[n_seed, n_pop] = (
                    5 +
                    (n_pop + 1) *
                    np.sin(2 * np.pi * 5 * time)
                )
        return xr.DataArray(
            values,
            dims=['seed_main', 'pop', 'time'],
            coords={
                'seed_main': [1000, 1001],
                'pop': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
                'time': time,
            },
        )

    def test_workflow_files_are_physical_and_stages_are_ordered(self):
        fnames = [
            'workflow_cfg.py',
            'link_existing_results.py',
            'process_dw.py',
            'process_connected_psd.py',
        ]
        for fname in fnames:
            with self.subTest(fname=fname):
                fpath = DIR_CONNECTED_WSWEEP / fname
                self.assertTrue(fpath.is_file())
                self.assertFalse(fpath.is_symlink())

        params = self.cfg.get_workflow_params()
        self.assertEqual(
            [stage['name'] for stage in params['stages']],
            ['dw', 'connected'],
        )
        self.assertEqual(
            params['stages'][1]['batch_param_overrides']['seed_main'],
            [1000, 1001],
        )

    def test_weight_context_and_connected_overrides(self):
        params = self.cfg.get_workflow_params()
        context = params['initial_context']
        current_values = []
        next_values = []

        # Advance the scientific context using fake persisted stage results
        for iteration in range(params['max_iterations']):
            current_values.append(
                context['wmat_multipliers'][0]['mult']
            )
            overrides = self.cfg.get_stage_overrides(
                'connected',
                iteration,
                context,
                {'dw': {'IT2': -0.01}},
                [],
            )
            self.assertNotIn(
                'ibkg_corrections',
                overrides['experiment_overrides'],
            )
            outcome = self.cfg.finish_iteration(
                iteration,
                context,
                {
                    'dw': {'IT2': -0.01},
                    'connected': SimpleNamespace(
                        sizes={'seed_main': 2, 'pop': 5, 'freq': 51},
                    ),
                },
                [],
            )
            next_values.append(
                outcome['next_context'][
                    'wmat_multipliers'
                ][0]['mult']
            )
            context = outcome['next_context']

        self.assertEqual(current_values, [2, 3, 4.5])
        self.assertEqual(next_values, [3, 4.5, 6.75])

    def test_run_id_describes_connected_fixture(self):
        run_id = self.cfg.get_run_id(
            self.cfg.get_workflow_params()
        )
        self.assertIn('connected_wsweep_niter_3', run_id)
        self.assertIn('L2_ee_fade_nseed_2_t_2_3', run_id)

    def test_analyzer_psd_recovery_and_plot_grouping(self):
        rates = self._make_rates()
        psd = self.processor.calc_xr_welch(
            rates,
            win_len=1,
            win_overlap=0.5,
            fmin=0,
            fmax=50,
            average='median',
            compute=True,
        )
        peak_freq = psd.sel(
            seed_main=1000,
            pop='IT2',
        ).idxmax('freq').item()
        self.assertEqual(psd.dims, ('seed_main', 'pop', 'freq'))
        self.assertAlmostEqual(peak_freq, 5)

        stage_spec = {
            'iteration': 2,
            'experiment_overrides': {
                'wmat_multipliers': [
                    {'pre': 'IT2', 'post': 'IT2', 'mult': 4.5},
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            outputs = self.processor._plot_psd_batch(
                psd,
                Path(tmp),
                stage_spec,
                dpi=50,
            )
            self.assertEqual(len(outputs), 2)
            self.assertEqual(
                sorted(Path(path).name for path in outputs),
                ['psd_seed_1000.png', 'psd_seed_1001.png'],
            )
            for relpath in outputs:
                self.assertTrue((Path(tmp) / relpath).is_file())

    def test_load_stage_result_reads_persisted_psd(self):
        rates = self._make_rates()
        psd = self.processor.calc_xr_welch(
            rates,
            win_len=1,
            win_overlap=0.5,
            fmin=0,
            fmax=50,
            average='median',
            compute=True,
            store_proc_info=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'processed' / 'psd.nc'
            self.processor.save_xr(psd, fpath)
            loaded = self.processor.load_stage_result(
                tmp,
                {},
            )
            xr.testing.assert_allclose(loaded, psd)


if __name__ == '__main__':
    unittest.main()
