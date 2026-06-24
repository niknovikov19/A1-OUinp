import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr

import run_workflow
from workflow_result_utils import organize_standard_outputs
from workflow_utils import (
    collect_batchtools_artifacts,
    file_fingerprint,
    make_job_record,
    merge_batch_params,
    poll_job_records,
    write_json_atomic,
)


DIR_REPO = Path(__file__).resolve().parents[1]
DIR_WORKFLOW = DIR_REPO / 'workflow_configs' / 'wmat_transfer'
DIR_WORKFLOW_LIST = (
    DIR_REPO / 'workflow_configs' /
    'ibkg_adj__fullsim__var_wmult_list_1d'
)


def load_module_unique(fpath, name):
    """Load one source file without reusing the repository module name."""
    spec = importlib.util.spec_from_file_location(name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClock:
    """Provide deterministic time and sleep behavior for polling tests."""

    def __init__(self):
        self.value = 0
        self.on_sleep = None

    def time(self):
        """Return current fake time."""
        return self.value

    def sleep(self, delay):
        """Advance fake time and run an optional callback."""
        self.value += delay
        if self.on_sleep is not None:
            self.on_sleep()


class WorkflowUtilsTests(unittest.TestCase):
    def test_batch_overrides_patch_existing_axes(self):
        defaults = {'seed': [1, 2], 'amp': [3], 'freq': [5]}
        merged = merge_batch_params(defaults, {'amp': [7, 9]})
        self.assertEqual(merged, {
            'seed': [1, 2],
            'amp': [7, 9],
            'freq': [5],
        })
        with self.assertRaises(KeyError):
            merge_batch_params(defaults, {'unknown': [1]})

    def test_compact_metadata_and_delayed_polling(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_stage = Path(tmp)
            context = {
                'workflow_name': 'test',
                'run_id': 'run',
                'iteration': 0,
                'stage': 'alpha',
                'stage_spec_hash': 'abc',
            }
            expected = [{'seed': 1}]
            clock = FakeClock()

            # Publish the output and marker after the first refresh
            def publish():
                clock.on_sleep = None
                fpath_output = dirpath_stage / 'sim_results' / 'result.json'
                fpath_output.parent.mkdir(parents=True)
                fpath_output.write_text('{}')
                record = make_job_record(
                    context,
                    'experiment_00000',
                    0,
                    {'seed': 1},
                    ['sim_results/result.json'],
                )
                write_json_atomic(
                    dirpath_stage / 'job_meta' / 'experiment_00000.json',
                    record,
                )

            clock.on_sleep = publish
            records = poll_job_records(
                dirpath_stage,
                expected,
                ['seed'],
                'abc',
                refresh_sec=1,
                timeout_sec=5,
                sleep_fn=clock.sleep,
                clock_fn=clock.time,
                print_fn=lambda message: None,
            )
            self.assertEqual(records[0]['batch_params'], {'seed': 1})

    def test_polling_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            with self.assertRaises(TimeoutError):
                poll_job_records(
                    tmp,
                    [{'seed': 1}],
                    ['seed'],
                    'abc',
                    refresh_sec=1,
                    timeout_sec=2,
                    sleep_fn=clock.sleep,
                    clock_fn=clock.time,
                    print_fn=lambda message: None,
                )


class WorkflowBatchToolsLaunchTests(unittest.TestCase):
    def test_shutdown_ray_if_initialized(self):
        calls = []
        fake_ray = SimpleNamespace(
            is_initialized=lambda: True,
            shutdown=lambda: calls.append('shutdown'),
        )
        with patch.dict(sys.modules, {'ray': fake_ray}):
            run_workflow._shutdown_ray_if_initialized()
        self.assertEqual(calls, ['shutdown'])

    def test_ray_reinit_error_gets_finite_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_stage = Path(tmp) / 'stage'
            captured = {}

            # Simulate BatchTools failing before submitting any child jobs
            def fake_search(**kwargs):
                raise RuntimeError(
                    'Maybe you called ray.init twice by accident?'
                )

            def fake_poll(stage_dir, expected, param_names, stage_hash,
                          refresh_sec, timeout_sec):
                captured['timeout_sec'] = timeout_sec
                raise TimeoutError('stop after one report')

            workflow_params = {
                'ray_checkpoint_path': str(Path(tmp) / 'ray'),
                'wait_refresh_sec': 30,
                'wait_timeout_sec': None,
            }
            stage_spec = {
                'batch_params': {'seed_main': [1000]},
                'batch_run': {
                    'partition': 'cpu.q',
                    'realtime': '1:00:00',
                    'nodes': 1,
                    'cores_per_node': 1,
                    'mem_gb': 1,
                    'max_concurrent': 1,
                },
                'stage_spec_hash': 'abc',
            }
            exp_paths = {
                'name': 'dummy_exp',
                'subdir': None,
            }
            with patch.object(
                run_workflow,
                '_load_batchtools',
                return_value=(fake_search, object, object),
            ), patch.object(
                run_workflow,
                'poll_job_records',
                side_effect=fake_poll,
            ), patch(
                'builtins.print',
            ):
                with self.assertRaises(TimeoutError):
                    run_workflow._run_batchtools_stage(
                        dirpath_stage,
                        stage_spec,
                        exp_paths,
                        workflow_params,
                        dirpath_stage / 'meta' / 'stage_spec.json',
                    )
            self.assertEqual(captured['timeout_sec'], 0)


class WorkflowArtifactTests(unittest.TestCase):
    def test_workflow_outputs_are_sorted_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_stage = Path(tmp)
            cfg = SimpleNamespace(
                saveFolder=tmp,
                simLabel='experiment_00000',
                workflow_context={},
                workflow_retention={
                    'keep_cfg': True,
                    'keep_netparams': False,
                    'keep_pkl': False,
                },
            )
            files = {
                'experiment_00000_raster.png': 'raster',
                'experiment_00000_data.pkl': 'pkl',
                'experiment_00000_cfg.json': 'cfg',
                'experiment_00000_netParams.json': 'net',
                'experiment_00000_params.json': 'params',
                'experiment_00000_result.json': 'result',
            }
            for name, value in files.items():
                (dirpath_stage / name).write_text(value)

            dirpath_result = organize_standard_outputs(
                cfg,
                'sim_results',
                '00000',
            )
            self.assertTrue(
                (dirpath_result / 'cfg' / 'cfg_00000.json').is_file()
            )
            self.assertTrue(
                (
                    dirpath_result / 'results_last' /
                    'result_last_00000.json'
                ).is_file()
            )
            self.assertFalse((dirpath_stage / 'experiment_00000_data.pkl').exists())
            self.assertFalse((dirpath_stage / 'experiment_00000_netParams.json').exists())
            self.assertFalse((dirpath_stage / 'experiment_00000_params.json').exists())

    def test_artifacts_are_attempt_safe_and_preserve_summary_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_stage = dirpath / 'stage'
            dirpath_stage.mkdir()
            fpath_root = dirpath / 'experiment.csv'

            # Archive the first attempt
            (dirpath_stage / 'experiment.sh').write_text('first')
            (dirpath_stage / 'experiment.csv').write_text('local first')
            fpath_root.write_text('root first')
            first = collect_batchtools_artifacts(
                dirpath_stage,
                root_summary=fpath_root,
                root_summary_before=None,
            )
            self.assertEqual(first['attempt'], 0)
            self.assertFalse(fpath_root.exists())
            self.assertTrue(
                (
                    dirpath_stage / 'batchtools' / 'scripts' /
                    'attempt_000_experiment.sh'
                ).is_file()
            )
            self.assertTrue(
                (
                    dirpath_stage / 'batchtools' / 'summaries' /
                    'attempt_000_experiment.csv'
                ).is_file()
            )
            self.assertEqual(len(first['summaries']), 2)

            # Archive a relaunch without overwriting the first attempt
            (dirpath_stage / 'experiment.sh').write_text('second')
            fpath_root.write_text('root second')
            second = collect_batchtools_artifacts(
                dirpath_stage,
                root_summary=fpath_root,
                root_summary_before=None,
            )
            self.assertEqual(second['attempt'], 1)
            self.assertTrue(
                (
                    dirpath_stage / 'batchtools' / 'scripts' /
                    'attempt_001_experiment.sh'
                ).is_file()
            )
            self.assertEqual(len(second['summaries']), 1)

    def test_unchanged_root_summary_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_stage = dirpath / 'stage'
            dirpath_stage.mkdir()
            fpath_root = dirpath / 'experiment.csv'
            fpath_root.write_text('preexisting')
            before = file_fingerprint(fpath_root)
            messages = []

            artifacts = collect_batchtools_artifacts(
                dirpath_stage,
                root_summary=fpath_root,
                root_summary_before=before,
                print_fn=messages.append,
            )
            self.assertTrue(fpath_root.is_file())
            self.assertEqual(artifacts['summaries'], [])
            self.assertIn('unchanged', messages[0].lower())

    def test_changed_root_summary_is_claimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_stage = dirpath / 'stage'
            dirpath_stage.mkdir()
            fpath_root = dirpath / 'experiment.csv'
            fpath_root.write_text('old')
            before = file_fingerprint(fpath_root)
            fpath_root.write_text('new')

            artifacts = collect_batchtools_artifacts(
                dirpath_stage,
                root_summary=fpath_root,
                root_summary_before=before,
            )
            self.assertFalse(fpath_root.exists())
            self.assertEqual(len(artifacts['summaries']), 1)
            self.assertTrue(
                (
                    dirpath_stage / artifacts['summaries'][0]
                ).is_file()
            )


class WorkflowProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dw = load_module_unique(
            DIR_WORKFLOW / 'process_dw.py',
            'workflow_dw_processor_test',
        )
        cls.rr = load_module_unique(
            DIR_WORKFLOW / 'process_rr.py',
            'workflow_rr_processor_test',
        )

    def test_synthetic_ibkg_intersection(self):
        x = np.linspace(-0.1, 0.1, 15)
        true_params = [0, 20, 30, 0, 1]
        y = self.dw.richards(x, *true_params)
        fitted = self.dw.fit_richards(x, y)
        crossing = self.dw.find_target_intersection(
            fitted,
            target_rate=10,
            x_min=x.min(),
            x_max=x.max(),
        )
        self.assertAlmostEqual(crossing, 0, places=4)

    def test_missing_required_ibkg_population_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'processed' / 'ibkg_intersections.csv'
            fpath.parent.mkdir()
            pd.DataFrame([
                {'pop': 'IT2', 'median_ibkg': 0},
            ]).to_csv(fpath, index=False)
            with self.assertRaises(ValueError):
                self.dw.load_stage_result(
                    tmp,
                    {},
                    'unused.csv',
                    required_pops=['IT2', 'PV2'],
                )

    def test_synthetic_transfer_recovery(self):
        time = np.arange(0, 20, 0.005)
        osc_f = 5
        osc_amp = 15
        osc_t0 = 5
        transfer = 0.4 + 0.2j
        phase = 2 * np.pi * osc_f * (time - osc_t0)
        response = np.full_like(time, 5, dtype=float)
        mask = time >= osc_t0
        response[mask] += (
            osc_amp * transfer.real * np.sin(phase[mask]) +
            osc_amp * transfer.imag * np.cos(phase[mask])
        )
        values = response.reshape(1, 1, 1, 1, 1, -1)
        rates = xr.DataArray(
            values,
            dims=[
                'seed_main',
                'pop_pre',
                'osc_f',
                'osc_amp',
                'pop',
                'time',
            ],
            coords={
                'seed_main': [1000],
                'pop_pre': ['IT2'],
                'osc_f': [osc_f],
                'osc_amp': [osc_amp],
                'pop': ['IT2'],
                'time': time,
            },
            attrs={'OSC_T0': 5000},
        )
        fitted = self.rr.fit_transfer_dataset(rates, [1, 2])
        recovered = complex(
            fitted['transfer_real'].sel(harmonic=1).item(),
            fitted['transfer_imag'].sel(harmonic=1).item(),
        )
        self.assertAlmostEqual(recovered.real, transfer.real, places=5)
        self.assertAlmostEqual(recovered.imag, transfer.imag, places=5)
        self.assertAlmostEqual(fitted['baseline_rate'].item(), 5, places=5)

    def _make_rr_plot_rates(self):
        """Create a compact labeled RR array for plotting tests."""
        time = np.arange(0, 4, 0.01)
        osc_f = 5
        osc_amp = 15
        osc_t0 = 2
        pop_pre_values = ['IT2', 'PV2']
        pop_values = ['IT2', 'PV2', 'IT2frz', 'PV2frz']
        values = np.full(
            (
                1,
                len(pop_pre_values),
                1,
                1,
                len(pop_values),
                len(time),
            ),
            5,
            dtype=float,
        )
        mask = time >= osc_t0
        phase = 2 * np.pi * osc_f * (time - osc_t0)

        # Give every active output and driven input a recoverable sinusoid
        for n_pre, pop_pre in enumerate(pop_pre_values):
            for n_pop in range(2):
                values[0, n_pre, 0, 0, n_pop, mask] += (
                    (2 + n_pop) * np.sin(phase[mask]) +
                    (1 + n_pre) * np.cos(phase[mask])
                )
            n_input = pop_values.index(f'{pop_pre}frz')
            values[0, n_pre, 0, 0, n_input, mask] += (
                osc_amp * np.sin(phase[mask])
            )

        return xr.DataArray(
            values,
            dims=[
                'seed_main',
                'pop_pre',
                'osc_f',
                'osc_amp',
                'pop',
                'time',
            ],
            coords={
                'seed_main': [1000],
                'pop_pre': pop_pre_values,
                'osc_f': [osc_f],
                'osc_amp': [osc_amp],
                'pop': pop_values,
                'time': time,
            },
            attrs={'OSC_T0': 2000},
        )

    def test_sinusoid_evaluation_reconstructs_fit(self):
        time = np.arange(0, 3, 0.005)
        z_out = 2 + 3j
        offset = 7
        values = self.rr.evaluate_fitted_sinusoid(
            time,
            z_out,
            offset,
            osc_f=5,
            osc_t0=1,
        )
        rr = xr.DataArray(values, coords={'time': time}, dims=['time'])
        fitted, fitted_offset = self.rr.fit_sinusoid_fixed_freq(
            rr,
            osc_f=5,
            osc_t0=1,
        )
        self.assertAlmostEqual(fitted.real, z_out.real, places=5)
        self.assertAlmostEqual(fitted.imag, z_out.imag, places=5)
        self.assertAlmostEqual(fitted_offset, offset, places=5)

    def test_psd_uses_only_post_oscillation_interval(self):
        time = np.arange(0, 4, 0.002)
        values = np.sin(2 * np.pi * 20 * time)
        mask = time >= 2
        values[mask] = np.sin(2 * np.pi * 5 * time[mask])
        rr = xr.DataArray(values, coords={'time': time}, dims=['time'])
        freq, power = self.rr.calc_welch_psd(
            rr,
            osc_t0=2,
            window_sec=1,
            fmax=30,
        )
        self.assertAlmostEqual(freq[np.argmax(power)], 5, places=5)

    def test_optional_rr_plots_are_disabled_by_default(self):
        rates = self._make_rr_plot_rates()
        transfer_ds = self.rr.fit_transfer_dataset(rates, [1, 2])
        with tempfile.TemporaryDirectory() as tmp:
            outputs = self.rr._create_diagnostic_plots(
                rates,
                transfer_ds,
                Path(tmp),
                {
                    'iteration': 0,
                    'experiment_overrides': {},
                },
                False,
                False,
                False,
                1,
                50,
                1,
                50,
            )
            self.assertEqual(outputs, [])
            self.assertFalse((Path(tmp) / 'processed').exists())

    def test_rr_diagnostic_plot_grouping_and_outputs(self):
        rates = self._make_rr_plot_rates()
        transfer_ds = self.rr.fit_transfer_dataset(rates, [1, 2])
        stage_spec = {
            'iteration': 1,
            'experiment_overrides': {
                'wmat_multipliers': [
                    {'pre': 'IT2', 'post': 'IT2', 'mult': 3},
                ],
            },
        }
        setup_counts = []
        setup_axes = self.rr._setup_axes

        # Capture subplot counts while preserving real plot generation
        def capture_setup(nplots, *args, **kwargs):
            setup_counts.append(nplots)
            return setup_axes(nplots, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                self.rr,
                '_setup_axes',
                side_effect=capture_setup,
            ):
                outputs = self.rr._create_diagnostic_plots(
                    rates,
                    transfer_ds,
                    Path(tmp),
                    stage_spec,
                    True,
                    True,
                    True,
                    1,
                    30,
                    1,
                    50,
                )

            # Two jobs, one matrix group, and one PSD group are expected
            self.assertEqual(len(outputs), 4)
            self.assertEqual(setup_counts, [3, 3, 2])
            for relpath in outputs:
                self.assertTrue((Path(tmp) / relpath).is_file())
            self.assertIn(
                'Iteration 1; IT2->IT2 x3',
                self.rr._get_weight_title(stage_spec),
            )

    def test_transfer_plot_matrix_orientation(self):
        rates = self._make_rr_plot_rates()
        transfer_ds = self.rr.fit_transfer_dataset(rates, [1, 2])
        magnitude, phase = self.rr._select_transfer_matrix(
            transfer_ds,
            {
                'seed_main': 1000,
                'osc_f': 5,
                'osc_amp': 15,
            },
            harmonic=1,
        )
        self.assertEqual(magnitude.dims, ('pop_post', 'pop_pre'))
        self.assertEqual(phase.dims, ('pop_post', 'pop_pre'))
        self.assertEqual(
            list(magnitude.coords['pop_pre'].values),
            ['IT2', 'PV2'],
        )
        self.assertEqual(
            list(magnitude.coords['pop_post'].values),
            ['IT2', 'PV2'],
        )

    def test_processor_uses_load_result_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            dirpath_workflow = dirpath / 'workflow'
            dirpath_stage = dirpath / 'stage'
            dirpath_workflow.mkdir()
            (dirpath_stage / 'processed').mkdir(parents=True)
            processor_source = """
from pathlib import Path


def process_stage(stage_dir, stage_spec):
    count_path = Path(stage_dir) / 'processed' / 'count.txt'
    count = int(count_path.read_text()) + 1 if count_path.exists() else 1
    count_path.write_text(str(count))
    output = Path(stage_dir) / 'processed' / 'value.txt'
    output.write_text(f'processed-{count}')
    return output.read_text(), ['processed/value.txt']


def load_stage_result(stage_dir, stage_spec):
    output = Path(stage_dir) / 'processed' / 'value.txt'
    return f'loaded-{output.read_text()}'
"""
            (dirpath_workflow / 'processor.py').write_text(processor_source)
            stage_spec = {
                'processor': 'processor.py',
                'processor_params': {},
                'stage_spec_hash': 'abc',
            }

            first = run_workflow._process_stage(
                dirpath_stage,
                stage_spec,
                dirpath_workflow,
            )
            second = run_workflow._process_stage(
                dirpath_stage,
                stage_spec,
                dirpath_workflow,
            )
            self.assertEqual(first, 'processed-1')
            self.assertEqual(second, 'loaded-processed-1')

            # Missing declared output invalidates the processing manifest
            (dirpath_stage / 'processed' / 'value.txt').unlink()
            third = run_workflow._process_stage(
                dirpath_stage,
                stage_spec,
                dirpath_workflow,
            )
            self.assertEqual(third, 'processed-2')


class WorkflowConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_WORKFLOW / 'workflow_cfg.py',
            'workflow_cfg_test',
        )

    def test_stage_order_accepts_arbitrary_names(self):
        stages = [
            {'name': 'alpha'},
            {'name': 'beta'},
            {'name': 'gamma'},
        ]
        resolved = run_workflow._get_stage_configs({'stages': stages})
        self.assertEqual(
            [stage['name'] for stage in resolved],
            ['alpha', 'beta', 'gamma'],
        )

    def test_default_run_id_uses_iterations_and_initial_weights(self):
        params = self.cfg.get_workflow_params()
        self.assertEqual(
            self.cfg.get_run_id(params),
            'exp_wmat_transfer_niter_1_w_IT2_IT2_2',
        )

        # Scientific naming parameters should select another result directory
        params['max_iterations'] = 3
        params['initial_context']['wmat_multipliers'][0]['mult'] = 4
        self.assertEqual(
            self.cfg.get_run_id(params),
            'exp_wmat_transfer_niter_3_w_IT2_IT2_4',
        )

    def test_dynamic_rr_overrides_use_dw_result(self):
        context = {
            'wmat_multipliers': [
                {'pre': 'IT2', 'post': 'IT2', 'mult': 2},
            ],
        }
        corrections = {'IT2': -0.01}
        overrides = self.cfg.get_stage_overrides(
            'rr',
            0,
            context,
            {'dw': corrections},
            [],
        )
        self.assertEqual(
            overrides['experiment_overrides']['ibkg_corrections'],
            corrections,
        )
        self.assertEqual(
            overrides['experiment_overrides']['wmat_multipliers'],
            context['wmat_multipliers'],
        )

    def test_dynamic_batch_and_experiment_overrides_are_merged(self):
        params = self.cfg.get_workflow_params()
        stage_cfg = params['stages'][0]
        dynamic = {
            'batch_param_overrides': {
                'seed_main': [42],
            },
            'experiment_overrides': {
                'wmat_multipliers': [
                    {'pre': 'IT2', 'post': 'IT2', 'mult': 3},
                ],
            },
        }
        spec, _ = run_workflow._resolve_stage_spec(
            params,
            stage_cfg,
            0,
            'test',
            dynamic,
        )
        self.assertEqual(spec['batch_params']['seed_main'], [42])
        self.assertEqual(
            spec['experiment_overrides']['wmat_multipliers'][0]['mult'],
            3,
        )


class WorkflowListRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_WORKFLOW_LIST / 'workflow_cfg.py',
            'workflow_list_cfg_test',
        )

    def test_dw_failure_advances_variant_context(self):
        context = self.cfg._make_context(1)
        outcome = self.cfg.handle_stage_failure(
            'dw',
            1,
            context,
            {},
            [],
            ValueError('bad fit'),
        )
        self.assertEqual(outcome['next_context']['wmult_id'], 2)
        self.assertEqual(outcome['result']['failed_stage'], 'dw')
        self.assertIn('bad fit', outcome['result']['error'])

    def test_fullsim_failure_is_not_recoverable(self):
        with self.assertRaises(RuntimeError):
            self.cfg.handle_stage_failure(
                'fullsim',
                1,
                self.cfg._make_context(1),
                {},
                [],
                RuntimeError('fullsim failed'),
            )


class WorkflowResumeTests(unittest.TestCase):
    def _write_complete_stage(self, dirpath_stage, stage_name, stage_hash):
        """Write one minimal valid batch and processing stage."""
        output = dirpath_stage / 'sim_results' / 'result.json'
        output.parent.mkdir(parents=True)
        output.write_text('{}')
        processed = dirpath_stage / 'processed' / 'result.json'
        processed.parent.mkdir(parents=True)
        processed.write_text('{}')
        record = make_job_record(
            {
                'workflow_name': 'test',
                'run_id': 'run',
                'iteration': 0,
                'stage': stage_name,
                'stage_spec_hash': stage_hash,
            },
            'experiment_00000',
            0,
            {'seed': 1},
            ['sim_results/result.json'],
        )
        write_json_atomic(
            dirpath_stage / 'job_meta' / 'experiment_00000.json',
            record,
        )
        stage_spec = {
            'stage': stage_name,
            'batch_params': {'seed': [1]},
            'stage_spec_hash': stage_hash,
        }
        write_json_atomic(
            dirpath_stage / 'meta' / 'stage_spec.json',
            stage_spec,
        )
        write_json_atomic(
            dirpath_stage / 'meta' / 'stage_complete.json',
            {'stage_spec_hash': stage_hash},
        )
        write_json_atomic(
            dirpath_stage / 'meta' / 'processing_complete.json',
            {
                'stage_spec_hash': stage_hash,
                'outputs': ['processed/result.json'],
            },
        )
        return stage_spec

    def test_stage_resume_requires_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_stage = Path(tmp)
            spec = self._write_complete_stage(
                dirpath_stage,
                'alpha',
                'abc',
            )
            self.assertTrue(
                run_workflow._stage_is_complete(dirpath_stage, spec)
            )
            (dirpath_stage / 'sim_results' / 'result.json').unlink()
            self.assertFalse(
                run_workflow._stage_is_complete(dirpath_stage, spec)
            )

    def test_history_uses_declared_stage_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_run = Path(tmp)
            dirpath_iter = dirpath_run / 'iterations' / 'iter_000'
            hashes = {'alpha': 'aaa', 'beta': 'bbb'}
            for name, stage_hash in hashes.items():
                self._write_complete_stage(
                    dirpath_iter / name,
                    name,
                    stage_hash,
                )
            write_json_atomic(
                dirpath_iter / 'meta' / 'iteration.json',
                {
                    'status': 'complete',
                    'iteration': 0,
                    'stage_spec_hashes': hashes,
                    'context': {},
                    'result': {},
                    'next_context': {},
                    'stop_reason': None,
                },
            )
            history = run_workflow._load_history(
                dirpath_run,
                [{'name': 'alpha'}, {'name': 'beta'}],
            )
            self.assertEqual(len(history), 1)

    def test_history_accepts_failed_continue_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_run = Path(tmp)
            dirpath_iter = dirpath_run / 'iterations' / 'iter_000'
            write_json_atomic(
                dirpath_iter / 'meta' / 'iteration.json',
                {
                    'status': 'failed_continue',
                    'iteration': 0,
                    'stage_spec_hashes': {'dw': 'aaa'},
                    'context': {'wmult_id': 0},
                    'failed_stage': 'dw',
                    'error': "ValueError('bad fit')",
                    'result': {},
                    'next_context': {'wmult_id': 1},
                    'stop_reason': None,
                },
            )
            history = run_workflow._load_history(
                dirpath_run,
                [{'name': 'dw'}, {'name': 'fullsim'}],
            )
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]['status'], 'failed_continue')

    def test_workflow_continues_after_recoverable_stage_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_configs = run_workflow.DIR_WORKFLOW_CONFIGS
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_CONFIGS = Path(tmp) / 'configs'
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp) / 'results'
            dirpath_cfg = (
                run_workflow.DIR_WORKFLOW_CONFIGS /
                'fake_recovery'
            )
            dirpath_cfg.mkdir(parents=True)
            (dirpath_cfg / 'workflow_cfg.py').write_text("""
def get_workflow_params():
    return {
        'workflow_name': 'fake_recovery',
        'max_iterations': 2,
        'initial_context': {'idx': 0},
        'retention': {},
        'batch_run_defaults': {},
        'stages': [
            {'name': 'dw', 'experiment': 'dummy', 'processor': 'p.py'},
            {'name': 'fullsim', 'experiment': 'dummy', 'processor': 'p.py'},
        ],
    }


def get_run_id(params):
    return 'run'


def get_stage_overrides(stage_name, iteration, context, stage_results, history):
    return {}


def handle_stage_failure(stage_name, iteration, context, stage_results,
                         history, error):
    if stage_name != 'dw':
        raise error
    return {
        'result': {'failed_stage': stage_name},
        'next_context': {'idx': context['idx'] + 1},
        'stop_reason': None,
    }


def finish_iteration(iteration, context, stage_results, history):
    return {
        'result': {'stages': sorted(stage_results)},
        'next_context': {'idx': context['idx'] + 1},
        'stop_reason': None,
    }
""")
            calls = []

            def fake_resolve(params, stage_cfg, iteration, run_id, dynamic):
                stage_name = stage_cfg['name']
                spec = {
                    'stage': stage_name,
                    'iteration': iteration,
                    'batch_params': {},
                    'processor': 'p.py',
                    'processor_params': {},
                    'stage_spec_hash': f'{iteration}-{stage_name}',
                }
                return spec, {'name': 'dummy', 'subdir': None}

            def fake_process(dirpath_stage, stage_spec, dirpath_workflow):
                key = (stage_spec['iteration'], stage_spec['stage'])
                calls.append(key)
                if key == (0, 'dw'):
                    raise ValueError('bad fit')
                return stage_spec['stage']

            try:
                with patch.object(
                    run_workflow,
                    '_resolve_stage_spec',
                    side_effect=fake_resolve,
                ), patch.object(
                    run_workflow,
                    '_run_stage',
                ), patch.object(
                    run_workflow,
                    '_process_stage',
                    side_effect=fake_process,
                ):
                    run_workflow.run_workflow('fake_recovery')
                dirpath_run = (
                    run_workflow.DIR_WORKFLOW_RESULTS /
                    'fake_recovery' /
                    'run'
                )
                iter0 = run_workflow.read_json(
                    dirpath_run / 'iterations' /
                    'iter_000' / 'meta' / 'iteration.json'
                )
                iter1 = run_workflow.read_json(
                    dirpath_run / 'iterations' /
                    'iter_001' / 'meta' / 'iteration.json'
                )
                self.assertEqual(iter0['status'], 'failed_continue')
                self.assertEqual(iter0['failed_stage'], 'dw')
                self.assertEqual(iter1['status'], 'complete')
                self.assertNotIn((0, 'fullsim'), calls)
                self.assertIn((1, 'fullsim'), calls)
            finally:
                run_workflow.DIR_WORKFLOW_CONFIGS = old_configs
                run_workflow.DIR_WORKFLOW_RESULTS = old_results

    def test_run_id_parameter_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp) / 'results'
            try:
                dirpath_cfg = Path(tmp) / 'workflow'
                dirpath_cfg.mkdir()
                (dirpath_cfg / 'workflow_cfg.py').write_text('VALUE = 1\n')
                cfg_first = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 1,
                    },
                )
                run_workflow._prepare_run(
                    cfg_first,
                    dirpath_cfg,
                    'same-id',
                )
                cfg_changed = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 2,
                    },
                )
                with self.assertRaises(ValueError):
                    run_workflow._prepare_run(
                        cfg_changed,
                        dirpath_cfg,
                        'same-id',
                    )
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results

    def test_tuple_params_match_saved_json_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp) / 'results'
            try:
                dirpath_cfg = Path(tmp) / 'workflow'
                dirpath_cfg.mkdir()
                (dirpath_cfg / 'workflow_cfg.py').write_text('VALUE = 1\n')
                cfg = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'wmult_conns': [('IT2', 'IT2')],
                    },
                )
                dirpath_run, params_first = run_workflow._prepare_run(
                    cfg,
                    dirpath_cfg,
                    'same-id',
                )
                dirpath_run_again, params_again = run_workflow._prepare_run(
                    cfg,
                    dirpath_cfg,
                    'same-id',
                )
                self.assertEqual(dirpath_run_again, dirpath_run)
                self.assertEqual(
                    params_first['wmult_conns'],
                    [['IT2', 'IT2']],
                )
                self.assertEqual(params_again, params_first)
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results

    def test_generated_run_id_collision_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp) / 'results'
            try:
                dirpath_cfg = Path(tmp) / 'workflow'
                dirpath_cfg.mkdir()
                (dirpath_cfg / 'workflow_cfg.py').write_text('VALUE = 1\n')
                cfg_first = SimpleNamespace(
                    get_run_id=lambda params: 'generated',
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 1,
                    },
                )
                params_first = cfg_first.get_workflow_params()
                run_id = run_workflow._resolve_run_id(
                    cfg_first,
                    params_first,
                )
                run_workflow._prepare_run(
                    cfg_first,
                    dirpath_cfg,
                    run_id,
                    workflow_params=params_first,
                )

                # The generated name does not bypass immutable run metadata
                cfg_changed = SimpleNamespace(
                    get_run_id=lambda params: 'generated',
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 2,
                    },
                )
                params_changed = cfg_changed.get_workflow_params()
                with self.assertRaises(ValueError):
                    run_workflow._prepare_run(
                        cfg_changed,
                        dirpath_cfg,
                        cfg_changed.get_run_id(params_changed),
                        workflow_params=params_changed,
                    )
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results

    def test_any_workflow_source_change_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp) / 'results'
            try:
                dirpath_cfg = Path(tmp) / 'workflow'
                dirpath_cfg.mkdir()
                (dirpath_cfg / 'workflow_cfg.py').write_text('VALUE = 1\n')
                fpath_processor = dirpath_cfg / 'processor.py'
                fpath_processor.write_text('VALUE = 1\n')
                cfg = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 1,
                    },
                )
                dirpath_run, _ = run_workflow._prepare_run(
                    cfg,
                    dirpath_cfg,
                    'same-id',
                )
                self.assertTrue(
                    (
                        dirpath_run / 'meta' / 'workflow_source' /
                        'processor.py'
                    ).is_file()
                )

                fpath_processor.write_text('VALUE = 2\n')
                with self.assertRaises(ValueError):
                    run_workflow._prepare_run(
                        cfg,
                        dirpath_cfg,
                        'same-id',
                    )
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results


class DwFitDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dw = load_module_unique(
            DIR_WORKFLOW_LIST / 'process_dw.py',
            'workflow_list_process_dw_test',
        )

    def test_plot_fits_keeps_points_when_fit_crossing_fails(self):
        ibkg = np.linspace(-0.5, 0.1, 10)
        values = np.zeros((1, ibkg.size, 2), dtype=float)
        values[0, :, 0] = np.linspace(0, 2, ibkg.size)
        values[0, :, 1] = 0
        rates_xr = xr.Dataset({
            'avg_rate': (
                ('seed_main', 'ibkg_dw_adj', 'pop'),
                values,
            ),
        }, coords={
            'seed_main': [1000],
            'ibkg_dw_adj': ibkg,
            'pop': ['IT2', 'PV2'],
        })
        fig, table = self.dw.plot_fits(
            rates_xr,
            {'IT2': 1, 'PV2': 1},
            required_pops=['IT2', 'PV2'],
        )
        try:
            self.assertTrue(np.isfinite(table.loc['IT2', 'median_ibkg']))
            self.assertTrue(np.isnan(table.loc['PV2', 'median_ibkg']))
            self.assertEqual(table.loc['PV2', 'status'], 'failed')
            self.assertIn('does not cross', table.loc['PV2', 'fit_error'])
        finally:
            self.dw.plt.close(fig)


class WorkflowRunIdTests(unittest.TestCase):
    def setUp(self):
        self.cfg = SimpleNamespace(
            get_run_id=lambda params: 'configured-name',
        )
        self.params = {'workflow_name': 'test'}

    def test_configured_default_is_used(self):
        with patch.dict('os.environ', {}, clear=True):
            run_id = run_workflow._resolve_run_id(
                self.cfg,
                self.params,
            )
        self.assertEqual(run_id, 'configured-name')

    def test_explicit_and_environment_precedence(self):
        with patch.dict(
            'os.environ',
            {'A1_WORKFLOW_RUN_ID': 'environment-name'},
            clear=True,
        ):
            self.assertEqual(
                run_workflow._resolve_run_id(
                    self.cfg,
                    self.params,
                ),
                'environment-name',
            )
            self.assertEqual(
                run_workflow._resolve_run_id(
                    self.cfg,
                    self.params,
                    run_id='explicit-name',
                ),
                'explicit-name',
            )

    def test_invalid_run_ids_are_rejected(self):
        invalid = ['', '   ', '.', '..', 'parent/child', r'parent\child']
        for run_id in invalid:
            with self.subTest(run_id=run_id):
                with self.assertRaises(ValueError):
                    run_workflow._validate_run_id(run_id)


if __name__ == '__main__':
    unittest.main()
