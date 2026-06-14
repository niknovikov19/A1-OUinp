import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np
import xarray as xr

import run_workflow
from workflow_result_utils import (
    organize_standard_outputs,
)
from workflow_utils import (
    make_job_record,
    merge_batch_params,
    poll_job_records,
    sort_batchtools_files,
    write_json_atomic,
)


DIR_REPO = Path(__file__).resolve().parents[1]


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
                'stage': 'dw',
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


class WorkflowCleanupTests(unittest.TestCase):
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
                'experiment_00000_extra.txt': 'extra',
                'experiment_00000.sh': 'batchtools',
            }
            for name, value in files.items():
                (dirpath_stage / name).write_text(value)

            dirpath_result = organize_standard_outputs(
                cfg,
                'sim_results',
                '00000',
            )
            sort_batchtools_files(dirpath_stage)

            self.assertTrue(
                (dirpath_result / 'cfg' / 'cfg_00000.json').is_file()
            )
            self.assertTrue(
                (
                    dirpath_result / 'results_last' /
                    'result_last_00000.json'
                ).is_file()
            )
            self.assertTrue(
                (
                    dirpath_stage / 'batchtools' / 'comm' /
                    'experiment_00000_extra.txt'
                ).is_file()
            )
            self.assertFalse((dirpath_stage / 'experiment_00000_data.pkl').exists())
            self.assertFalse((dirpath_stage / 'experiment_00000_netParams.json').exists())
            self.assertFalse((dirpath_stage / 'experiment_00000_params.json').exists())
            self.assertTrue(
                (
                    dirpath_stage / 'batchtools' / 'scripts' /
                    'experiment_00000.sh'
                ).is_file()
            )


class WorkflowProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dirpath_dw = (
            DIR_REPO / 'exp_configs' /
            'batch_rxbkg_unconn_state1_mech1' /
            'net_inpsur_dw_var_seed_ibkg'
        )
        dirpath_rr = (
            DIR_REPO / 'exp_configs' /
            'batch_rxbkg_unconn_state1_mech1' /
            'net_inpsur_rr_osc_var_seed_pre_f_amp'
        )
        cls.dw = load_module_unique(
            dirpath_dw / 'explore_results.py',
            'workflow_dw_processor_test',
        )
        cls.rr = load_module_unique(
            dirpath_rr / 'process_results.py',
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


class WorkflowResumeTests(unittest.TestCase):
    def test_stage_resume_requires_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath_stage = Path(tmp)
            spec = {
                'batch_params': {'seed': [1]},
                'stage_spec_hash': 'abc',
            }
            output = dirpath_stage / 'sim_results' / 'result.json'
            output.parent.mkdir(parents=True)
            output.write_text('{}')
            record = make_job_record(
                {
                    'workflow_name': 'test',
                    'run_id': 'run',
                    'iteration': 0,
                    'stage': 'dw',
                    'stage_spec_hash': 'abc',
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
            write_json_atomic(
                dirpath_stage / 'meta' / 'stage_complete.json',
                {'stage_spec_hash': 'abc'},
            )
            self.assertTrue(run_workflow._stage_is_complete(dirpath_stage, spec))
            output.unlink()
            self.assertFalse(run_workflow._stage_is_complete(dirpath_stage, spec))

    def test_run_id_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp)
            try:
                fpath_cfg = Path(tmp) / 'workflow_cfg.py'
                fpath_cfg.write_text('VALUE = 1\n')
                cfg_first = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 1,
                    },
                )
                run_workflow._prepare_run(
                    cfg_first,
                    fpath_cfg,
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
                        fpath_cfg,
                        'same-id',
                    )
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results

    def test_run_id_source_change_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_results = run_workflow.DIR_WORKFLOW_RESULTS
            run_workflow.DIR_WORKFLOW_RESULTS = Path(tmp)
            try:
                fpath_cfg = Path(tmp) / 'workflow_cfg.py'
                fpath_cfg.write_text('VALUE = 1\n')
                cfg = SimpleNamespace(
                    get_workflow_params=lambda: {
                        'workflow_name': 'test',
                        'value': 1,
                    },
                )
                run_workflow._prepare_run(cfg, fpath_cfg, 'same-id')
                fpath_cfg.write_text('VALUE = 2\n')
                with self.assertRaises(ValueError):
                    run_workflow._prepare_run(cfg, fpath_cfg, 'same-id')
            finally:
                run_workflow.DIR_WORKFLOW_RESULTS = old_results


if __name__ == '__main__':
    unittest.main()
