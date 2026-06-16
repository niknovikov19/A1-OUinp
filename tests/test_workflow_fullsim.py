import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import xarray as xr

import run_workflow
from workflow_utils import make_job_record, write_json_atomic


DIR_REPO = Path(__file__).resolve().parents[1]
DIR_WORKFLOW = (
    DIR_REPO / 'workflow_configs' /
    'ibkg_adj__fullsim__var_wmult_1d'
)
FPATH_FULLSIM_CFG = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1' /
    'net_newsec_var_seed' / 'exp_cfg.py'
)


def load_module_unique(fpath, name):
    """Load one source file without reusing its repository module name."""
    spec = importlib.util.spec_from_file_location(name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_module(name, **attrs):
    """Create one lightweight import stub."""
    module = ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(module, attr_name, value)
    return module


def load_fullsim_exp_cfg():
    """Load fullsim experiment helpers without NEURON or NetPyNE."""
    fake_modules = {
        'neuron': _make_module(
            'neuron',
            h=SimpleNamespace(),
        ),
        'analysis.model_utils.net_utils': _make_module(
            'analysis.model_utils.net_utils',
            get_2pop_conns=lambda *args, **kwargs: [],
        ),
        'analysis.ou_tuning.sim_res_proc_utils': _make_module(
            'analysis.ou_tuning.sim_res_proc_utils',
            calc_rates_and_cvs=lambda *args, **kwargs: {},
            calc_v_stats=lambda *args, **kwargs: {},
            calc_rate_dynamics=lambda *args, **kwargs: {},
        ),
        'analysis.ou_tuning.netpyne_res_parse_utils': _make_module(
            'analysis.ou_tuning.netpyne_res_parse_utils',
            prepare_sim_result=lambda sim: {},
        ),
        'batch_params': _make_module(
            'batch_params',
            N_SEEDS=1,
        ),
        'conn_fader': _make_module(
            'conn_fader',
            ConnFader=object,
        ),
        'diagnostics': _make_module('diagnostics'),
        'external.sim_data_analyzer.xr_adapters': _make_module(
            'external.sim_data_analyzer.xr_adapters',
            get_net_rate_dynamics_xr=lambda *args, **kwargs: None,
        ),
        'syn_mech_relabel': _make_module(
            'syn_mech_relabel',
            _rule_kind_and_base_pops=lambda conn: (None, [], []),
            _relabel_conn_synmech=lambda *args, **kwargs: None,
        ),
    }
    with patch.dict(sys.modules, fake_modules):
        return load_module_unique(
            FPATH_FULLSIM_CFG,
            'workflow_fullsim_exp_cfg_test',
        )


class FullsimWorkflowConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_module_unique(
            DIR_WORKFLOW / 'workflow_cfg.py',
            'workflow_fullsim_cfg_test',
        )

    def test_files_are_physical_and_stages_are_ordered(self):
        fnames = [
            'workflow_cfg.py',
            'process_dw.py',
            'process_fullsim_psd.py',
        ]
        for fname in fnames:
            with self.subTest(fname=fname):
                fpath = DIR_WORKFLOW / fname
                self.assertTrue(fpath.is_file())
                self.assertFalse(fpath.is_symlink())

        params = self.cfg.get_workflow_params()
        self.assertEqual(
            [stage['name'] for stage in params['stages']],
            ['dw', 'fullsim'],
        )

    def test_scalar_sweep_expands_across_configured_connections(self):
        with patch.object(
            self.cfg,
            'WMULT_CONNS',
            [('IT2', 'IT2'), ('IT2', 'PV2')],
        ):
            weights = self.cfg._make_wmat_multipliers(1.5)
        self.assertEqual(weights, [
            {'pre': 'IT2', 'post': 'IT2', 'mult': 1.5},
            {'pre': 'IT2', 'post': 'PV2', 'mult': 1.5},
        ])

    def test_context_advances_through_explicit_sweep(self):
        params = self.cfg.get_workflow_params()
        context = params['initial_context']
        current_values = []
        next_values = []

        # Advance the context using compact fake stage results
        for iteration in range(params['max_iterations']):
            current_values.append(context['wmult_val'])
            outcome = self.cfg.finish_iteration(
                iteration,
                context,
                {
                    'dw': {'IT2': -0.01},
                    'fullsim': SimpleNamespace(
                        sizes={'seed_main': 3, 'pop': 5, 'freq': 51},
                    ),
                },
                [],
            )
            next_values.append(
                outcome['result']['next_wmult_val']
            )
            context = outcome['next_context']

        self.assertEqual(current_values, [1, 1.5, 2, 3])
        self.assertEqual(next_values, [1.5, 2, 3, None])

    def test_fullsim_overrides_include_dw_corrections(self):
        params = self.cfg.get_workflow_params()
        context = params['initial_context']
        corrections = {
            pop: -0.01
            for pop in self.cfg.POPS_USED
        }
        overrides = self.cfg.get_stage_overrides(
            'fullsim',
            0,
            context,
            {'dw': corrections},
            [],
        )
        self.assertEqual(
            overrides['experiment_overrides']['runtime_params']['conn'][
                'wmat_multipliers'
            ],
            context['wmat_multipliers'],
        )
        self.assertEqual(
            overrides['experiment_overrides']['runtime_params']['inp'][
                'ibkg_corrections'
            ],
            corrections,
        )
        self.assertEqual(
            overrides['experiment_overrides']['runtime_params']['time'][
                't0_calc'
            ],
            5000,
        )

    def test_stage_specs_resolve_expected_grids(self):
        params = self.cfg.get_workflow_params()
        context = params['initial_context']
        corrections = {
            pop: -0.01
            for pop in self.cfg.POPS_USED
        }
        stage_results = {'dw': corrections}
        resolved = {}

        # Resolve both real experiment grids without launching BatchTools
        for stage in params['stages']:
            dynamic = self.cfg.get_stage_overrides(
                stage['name'],
                0,
                context,
                stage_results,
                [],
            )
            resolved[stage['name']], _ = (
                run_workflow._resolve_stage_spec(
                    params,
                    stage,
                    0,
                    'test',
                    dynamic,
                )
            )

        self.assertEqual(
            resolved['dw']['batch_params']['seed_main'],
            [1000, 1001, 1002],
        )
        self.assertEqual(
            len(resolved['dw']['batch_params']['ibkg_dw_adj']),
            10,
        )
        self.assertEqual(
            resolved['fullsim']['batch_params']['seed_main'],
            [1000, 1001, 1002],
        )
        self.assertEqual(
            resolved['fullsim']['experiment_overrides']['runtime_params'][
                'time'
            ]['t0_calc'],
            5000,
        )

    def test_run_id_describes_weight_and_fullsim_grids(self):
        run_id = self.cfg.get_run_id(
            self.cfg.get_workflow_params()
        )
        self.assertIn('ibkg_adj__fullsim__var_wmult_1d', run_id)
        self.assertIn('wconn_IT2_IT2', run_id)
        self.assertIn('wvals_1_1.5_2_3', run_id)
        self.assertIn('dw_nseed_3_nibkg_10_t_5_15', run_id)
        self.assertIn('fullsim_nseed_3_t_5_10', run_id)


class FullsimExperimentOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp_cfg = load_fullsim_exp_cfg()

    def _make_cfg(self):
        """Create a prepared fullsim config for override tests."""
        cfg = SimpleNamespace(
            seeds={},
            analysis={
                'plotRaster': {},
                'plotSpikeStats': {},
                'plotTraces': {},
            },
        )
        self.exp_cfg.apply_exp_cfg(cfg)
        return cfg

    def test_deep_runtime_update_preserves_unpatched_values(self):
        base = self.exp_cfg._get_default_runtime_params()
        merged = self.exp_cfg._deep_update_runtime_params(
            base,
            {
                'time': {'t0_calc': 5000},
                'out': {'save_rate_xr': True},
            },
        )

        self.assertEqual(base['time']['t0_calc'], self.exp_cfg.T0_CALC)
        self.assertEqual(merged['time']['duration'], base['time']['duration'])
        self.assertEqual(merged['time']['t0_calc'], 5000)
        self.assertTrue(merged['out']['save_rate_xr'])
        with self.assertRaisesRegex(KeyError, 'Unknown runtime_params'):
            self.exp_cfg._deep_update_runtime_params(
                base,
                {'bad': 1},
            )

    def test_runtime_overrides_filter_and_append_currents(self):
        cfg = self._make_cfg()
        corrections = {
            pop: -0.01
            for pop in self.exp_cfg.L2_POPS
        }
        self.exp_cfg.apply_runtime_overrides(cfg, {
            'runtime_params': {
                'time': {
                    'duration': 10000,
                    't0_calc': 5000,
                },
                'pops_used': self.exp_cfg.L2_POPS,
                'conn': {
                    'fader_pts': [
                        (0, 0),
                        (3000, 0),
                        (5000, 1),
                        (10000, 1),
                    ],
                    'wmat_multipliers': [
                        {'pre': 'IT2', 'post': 'IT2', 'mult': 1.5},
                    ],
                },
                'inp': {
                    'ibkg_corrections': corrections,
                    'add_pulses': False,
                },
                'rec': {
                    'traces': False,
                    'lfp': False,
                },
                'out': {
                    'plot_traces': False,
                    'plot_csd': False,
                    'plot_rate_dynamics': False,
                },
            },
        })

        self.assertEqual(cfg.pops_used, self.exp_cfg.L2_POPS)
        self.assertEqual(cfg.subnet_params['pops_active'], self.exp_cfg.L2_POPS)
        self.assertEqual(set(cfg.bkg_spike_inputs), set(self.exp_cfg.L2_POPS))
        self.assertEqual(cfg.t0_calc, 5000)
        self.assertEqual(cfg.recordLFP, [])
        self.assertEqual(cfg.recordCells, [])
        self.assertNotIn('plotCSD', cfg.analysis)
        self.assertEqual(cfg.add_pulses, 0)
        self.assertEqual(
            cfg.runtime_params['conn']['wmat_multipliers'],
            [{'pre': 'IT2', 'post': 'IT2', 'mult': 1.5}],
        )
        for pop in self.exp_cfg.L2_POPS:
            entries = cfg.IClamp[pop]
            if isinstance(entries, dict):
                entries = [entries]
            self.assertEqual(entries[-1]['amp'], -0.01)

    def test_runtime_overrides_validate_corrections(self):
        cfg = self._make_cfg()
        with self.assertRaisesRegex(ValueError, 'Missing ibkg'):
            self.exp_cfg.apply_runtime_overrides(cfg, {
                'runtime_params': {
                    'pops_used': self.exp_cfg.L2_POPS,
                    'inp': {'ibkg_corrections': {'IT2': 0}},
                },
            })

    def test_runtime_overrides_reject_flat_roots(self):
        cfg = self._make_cfg()
        with self.assertRaisesRegex(KeyError, 'Unknown experiment'):
            self.exp_cfg.apply_runtime_overrides(cfg, {
                'pops_used': self.exp_cfg.L2_POPS,
            })

    def test_pairwise_weight_application(self):
        params = SimpleNamespace(connParams={
            'ee': {
                'preConds': {'pop': ['IT2']},
                'postConds': {'pop': ['IT2']},
                'weight': 0.2,
            },
            'ei': {
                'preConds': {'pop': 'IT2'},
                'postConds': {'pop': 'PV2'},
                'weight': 0.3,
            },
            'broad': {
                'preConds': {'pop': ['IT2', 'IT3']},
                'postConds': {'pop': ['PV2']},
                'weight': 0.4,
            },
        })
        self.exp_cfg._apply_wmat_multipliers(params, [
            {'pre': 'IT2', 'post': 'IT2', 'mult': 3},
            {'pre': 'IT2', 'post': 'PV2', 'mult': 2},
        ])
        self.assertAlmostEqual(params.connParams['ee']['weight'], 0.6)
        self.assertAlmostEqual(params.connParams['ei']['weight'], 0.6)
        self.assertAlmostEqual(params.connParams['broad']['weight'], 0.4)

    def test_broad_weight_rules_do_not_satisfy_exact_pairs(self):
        params = SimpleNamespace(connParams={
            'broad': {
                'preConds': {'pop': ['IT2', 'IT3']},
                'postConds': {'pop': ['PV2']},
                'weight': 0.4,
            },
        })
        with self.assertRaisesRegex(ValueError, 'No connParams found'):
            self.exp_cfg._apply_wmat_multipliers(params, [
                {'pre': 'IT2', 'post': 'PV2', 'mult': 2},
            ])

    def test_apply_exp_cfg_keeps_standalone_defaults(self):
        cfg = SimpleNamespace(
            seeds={},
            analysis={
                'plotRaster': {},
                'plotSpikeStats': {},
                'plotTraces': {},
            },
        )
        self.exp_cfg.apply_exp_cfg(cfg)
        self.assertEqual(cfg.pops_used, self.exp_cfg.POPS_USED)
        self.assertEqual(cfg.t0_calc, self.exp_cfg.T0_CALC)
        self.assertEqual(cfg.duration, self.exp_cfg.SIM_DURATION)
        self.assertEqual(cfg.add_pulses, self.exp_cfg.ADD_PULSES)
        self.assertEqual(cfg.rec_lfp, bool(self.exp_cfg.REC_LFP))
        self.assertEqual(cfg.plot_csd, bool(self.exp_cfg.PLOT_CSD))
        self.assertEqual(cfg.runtime_params['pops_used'], self.exp_cfg.POPS_USED)
        self.assertEqual(
            cfg.runtime_params['conn']['ee_fader_on'],
            self.exp_cfg.EE_FADER_ON,
        )

    def test_post_run_declares_result_json_and_rate_xr(self):
        cfg = self._make_cfg()
        self.exp_cfg.apply_runtime_overrides(cfg, {
            'runtime_params': {
                'pops_used': self.exp_cfg.L2_POPS,
                'conn': {'ee_fader_on': False},
                'rec': {
                    'traces': False,
                    'lfp': False,
                },
                'out': {
                    'plot_rate_dynamics': False,
                    'save_rate_xr': True,
                },
                'proc': {
                    'rate_t_limits': [5, 10],
                    'rate_dt_bin': 0.005,
                    'rate_tau_smooth': 0.02,
                },
            },
        })

        # Fake one compact rate DataArray without touching NetPyNE
        rate_xr = xr.DataArray(
            np.zeros((len(self.exp_cfg.L2_POPS), 3)),
            dims=['pop', 'time'],
            coords={
                'pop': self.exp_cfg.L2_POPS,
                'time': [5, 5.005, 5.01],
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg.saveFolder = tmp
            cfg.simLabel = 'fullsim_00000'
            cfg.seed_main = 1000
            cfg.workflow_result_subdir = 'sim_results'
            for suffix in ('raster.png', 'data.pkl', 'cfg.json',
                           'netParams.json', 'CSD.png'):
                (Path(tmp) / f'fullsim_00000_{suffix}').touch()
            sim = SimpleNamespace(cfg=cfg, timingData={})
            with patch.object(
                self.exp_cfg,
                'get_net_rate_dynamics_xr',
                return_value=rate_xr,
            ):
                outputs = self.exp_cfg.post_run(sim)

            self.assertIn(
                'sim_results/results/result_00000_seed_1000.json',
                outputs,
            )
            self.assertIn(
                'sim_results/rvec_xr/rvec_00000_seed_1000.nc',
                outputs,
            )
            for relpath in outputs:
                self.assertTrue((Path(tmp) / relpath).is_file())


class FullsimProcessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.processor = load_module_unique(
            DIR_WORKFLOW / 'process_fullsim_psd.py',
            'workflow_fullsim_processor_test',
        )

    def _make_rate(self, seed):
        """Create one five-population rate array with a 5 Hz peak."""
        time = np.arange(5, 10, 0.005)
        values = np.zeros((5, len(time)))
        for n_pop in range(5):
            values[n_pop] = (
                5 +
                (n_pop + 1) *
                np.sin(2 * np.pi * 5 * time)
            )
        return xr.DataArray(
            values,
            dims=['pop', 'time'],
            coords={
                'pop': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
                'time': time,
            },
            attrs={'seed_main': seed},
        )

    def _write_stage(self, dirpath):
        """Write compact job records and per-job rate NetCDF files."""
        stage_hash = 'fullsim-test'
        dirpath_meta = dirpath / 'job_meta'
        dirpath_rates = dirpath / 'sim_results' / 'rvec_xr'
        dirpath_meta.mkdir(parents=True)
        dirpath_rates.mkdir(parents=True)

        # Keep filenames compatible with the production processor pattern
        for job_id, seed in enumerate([1000, 1001]):
            fpath_rate = (
                dirpath_rates /
                f'rvec_{job_id:05d}_seed_{seed}.nc'
            )
            self.processor.save_xr(
                self._make_rate(seed),
                fpath_rate,
            )
            context = {
                'workflow_name': 'test',
                'run_id': 'run',
                'iteration': 0,
                'stage': 'fullsim',
                'stage_spec_hash': stage_hash,
            }
            record = make_job_record(
                context,
                f'fullsim_{job_id:05d}',
                job_id,
                {'seed_main': seed},
                [
                    fpath_rate.relative_to(dirpath).as_posix(),
                ],
            )
            write_json_atomic(
                dirpath_meta / f'fullsim_{job_id:05d}.json',
                record,
            )
        return {
            'iteration': 0,
            'stage_spec_hash': stage_hash,
            'batch_params': {
                'seed_main': [1000, 1001],
            },
            'experiment_overrides': {
                'runtime_params': {
                    'conn': {
                        'wmat_multipliers': [
                            {'pre': 'IT2', 'post': 'IT2', 'mult': 1.5},
                        ],
                    },
                },
            },
        }

    def test_process_stage_collects_rates_and_recovers_psd(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            stage_spec = self._write_stage(dirpath)
            psd, outputs = self.processor.process_stage(
                dirpath,
                stage_spec,
                pop_names=['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
                plot_dpi=50,
            )
            peak_freq = psd.sel(
                seed_main=1000,
                pop='IT2',
            ).idxmax('freq').item()

            self.assertEqual(
                psd.dims,
                ('seed_main', 'pop', 'freq'),
            )
            self.assertAlmostEqual(peak_freq, 5)
            self.assertEqual(len(outputs), 4)
            for relpath in outputs:
                self.assertTrue((dirpath / relpath).is_file())

            loaded = self.processor.load_stage_result(
                dirpath,
                stage_spec,
            )
            xr.testing.assert_allclose(loaded, psd)


if __name__ == '__main__':
    unittest.main()
