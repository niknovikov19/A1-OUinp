import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


DIR_REPO = Path(__file__).resolve().parents[1]
DIR_EXP = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1' /
    'net_pulse_var_seed_f_amp'
)


def _make_module(name, **attrs):
    """Create one lightweight import stub."""
    module = ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(module, attr_name, value)
    return module


def _load_module(fpath, name):
    """Load one source file without reusing its repository module name."""
    spec = importlib.util.spec_from_file_location(name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_batch_params():
    """Load the pulse batch params as an isolated module."""
    return _load_module(DIR_EXP / 'batch_params.py', 'pulse_batch_params_test')


def load_exp_cfg():
    """Load the pulse experiment config without NEURON or NetPyNE."""
    batch_params = load_batch_params()
    fake_modules = {
        'neuron': _make_module('neuron', h=SimpleNamespace()),
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
        'batch_params': batch_params,
        'conn_fader': _make_module('conn_fader', ConnFader=object),
        'diagnostics': _make_module('diagnostics'),
        'external.sim_data_analyzer.xr_adapters': _make_module(
            'external.sim_data_analyzer.xr_adapters',
            get_net_rate_dynamics_xr=lambda *args, **kwargs: None,
            get_lfp_xr=lambda *args, **kwargs: None,
        ),
        'syn_mech_relabel': _make_module(
            'syn_mech_relabel',
            _rule_kind_and_base_pops=lambda conn: (None, [], []),
            _relabel_conn_synmech=lambda *args, **kwargs: None,
        ),
    }
    with patch.dict(sys.modules, fake_modules):
        return _load_module(DIR_EXP / 'exp_cfg.py', 'pulse_exp_cfg_test')


class PulseBatchParamTests(unittest.TestCase):
    def setUp(self):
        self.batch = load_batch_params()

    def _make_cfg(self, rates):
        """Create a minimal cfg for post_update()."""
        return SimpleNamespace(
            seed_main=1000,
            seeds={},
            subnet_params={},
            bkg_spike_inputs={'IT2': {'exc': {}, 'inh': {}}},
            add_pulses=1,
            duration=6000,
            f=2,
            amp=0.3,
            pulse_seq_params={
                't0': 5000,
                't_last': None,
                'rates': rates,
            },
        )

    def test_post_update_repeats_scalar_rates(self):
        cfg = self._make_cfg(1250)

        # Derive pulse fields from batch frequency and amplitude
        self.batch.post_update(cfg)

        self.assertEqual(cfg.pulse_seq_params['period'], 500)
        self.assertEqual(cfg.pulse_seq_params['weight'], 0.3)
        self.assertEqual(cfg.pulse_seq_params['n_pulses'], 3)
        self.assertEqual(cfg.pulse_seq_params['rates'], [1250, 1250, 1250])

    def test_post_update_uses_tiny_weight_for_public_zero_amp(self):
        cfg = self._make_cfg(1250)
        cfg.amp = 0

        # Keep public amp zero while avoiding an exactly zero NetPyNE weight
        self.batch.post_update(cfg)

        self.assertEqual(cfg.amp, 0)
        self.assertEqual(
            cfg.pulse_seq_params['weight'],
            self.batch.PULSE_ZERO_WEIGHT,
        )

    def test_post_update_cycles_list_rates(self):
        cfg = self._make_cfg([100, 5000])
        cfg.duration = 7200

        # Cycle the user-provided rate pattern over all pulses
        self.batch.post_update(cfg)

        self.assertEqual(cfg.pulse_seq_params['n_pulses'], 5)
        self.assertEqual(
            cfg.pulse_seq_params['rates'],
            [100, 5000, 100, 5000, 100],
        )

    def test_post_update_respects_explicit_last_pulse_time(self):
        cfg = self._make_cfg([100, 5000])
        cfg.duration = 7200
        cfg.pulse_seq_params['t_last'] = 6000

        # Include a pulse whose start equals t_last
        self.batch.post_update(cfg)

        self.assertEqual(cfg.pulse_seq_params['n_pulses'], 3)
        self.assertEqual(cfg.pulse_seq_params['rates'], [100, 5000, 100])

    def test_post_update_rejects_bad_pulse_grid(self):
        cfg = self._make_cfg(1250)
        cfg.f = 0
        with self.assertRaisesRegex(ValueError, 'frequency'):
            self.batch.post_update(cfg)

        cfg = self._make_cfg([])
        with self.assertRaisesRegex(ValueError, 'rates'):
            self.batch.post_update(cfg)

        cfg = self._make_cfg(1250)
        cfg.pulse_seq_params['t0'] = 6000
        with self.assertRaisesRegex(ValueError, 't0'):
            self.batch.post_update(cfg)

        cfg = self._make_cfg(1250)
        cfg.pulse_seq_params['t_last'] = 4999
        with self.assertRaisesRegex(ValueError, 't_last'):
            self.batch.post_update(cfg)

        cfg = self._make_cfg(1250)
        cfg.pulse_seq_params['t_last'] = 6001
        with self.assertRaisesRegex(ValueError, 't_last'):
            self.batch.post_update(cfg)


class PulseExperimentConfigTests(unittest.TestCase):
    def setUp(self):
        self.exp_cfg = load_exp_cfg()

    def test_exp_name_excludes_batch_derived_pulse_fields(self):
        cfg = SimpleNamespace(
            t0_calc=7000,
            duration=10000,
            wmult=0.25,
            EEGain=0.5,
            pulse_seq_params={
                'pop': ['TC'],
                't0': 5000,
                't_last': None,
                'width': 150,
                'period': 500,
                'n_pulses': 10,
                'rates': [100, 5000],
                'weight': 0.1,
                'convergence': 25,
                'jitter': 0,
            },
            runtime_params=self.exp_cfg._get_default_runtime_params(),
        )
        self.exp_cfg.WMAT_MULT_LABEL = 'IT2_IT2_x2'

        # Batch-specific pulse period and weight stay out of exp_name_sub
        exp_name = self.exp_cfg.gen_exp_name_sub(cfg)

        self.assertIn('_nseed_1_f_2_5_amp_0.01_0.03_3_', exp_name)
        self.assertIn('_IT2_IT2_x2_', exp_name)
        self.assertIn('_pulse_TC_d_150_c_25_r_100_4900_t0_5000_jit_0', exp_name)
        self.assertNotIn('_tlast_', exp_name)
        self.assertNotIn('_T_500', exp_name)
        self.assertNotIn('_w_0.1', exp_name)

    def test_exp_name_includes_explicit_last_pulse_time(self):
        cfg = SimpleNamespace(
            t0_calc=7000,
            duration=10000,
            wmult=0.25,
            EEGain=0.5,
            pulse_seq_params={
                'pop': ['TC'],
                't0': 5000,
                't_last': 8000,
                'width': 150,
                'period': 500,
                'n_pulses': 10,
                'rates': [100],
                'weight': 0.1,
                'convergence': 25,
                'jitter': 0,
            },
            runtime_params=self.exp_cfg._get_default_runtime_params(),
        )

        # Explicit t_last participates in the experiment directory name
        exp_name = self.exp_cfg.gen_exp_name_sub(cfg)

        self.assertIn('_tlast_8000', exp_name)

    def test_default_wmat_multipliers_feed_runtime_params(self):
        self.exp_cfg.WMAT_MULTIPLIERS = [
            {'pre': 'IT2', 'post': 'IT2', 'mult': 2},
        ]

        # Defaults are copied into the generic runtime override surface
        runtime_params = self.exp_cfg._get_default_runtime_params()

        self.assertEqual(
            runtime_params['conn']['wmat_multipliers'],
            [{'pre': 'IT2', 'post': 'IT2', 'mult': 2}],
        )
        self.exp_cfg.WMAT_MULTIPLIERS[0]['mult'] = 3
        self.assertEqual(
            runtime_params['conn']['wmat_multipliers'][0]['mult'],
            2,
        )

    def test_job_postfix_includes_batch_coordinates(self):
        cfg = SimpleNamespace(seed_main=1000, f=5, amp=0.3)

        # Job-local outputs carry the actual f/amp values
        postfix = self.exp_cfg._get_job_postfix(cfg, 'net_pulse_000001')

        self.assertEqual(postfix, '000001_seed_1000_f_5_amp_0.3')

    def test_job_postfix_keeps_public_zero_amp(self):
        cfg = SimpleNamespace(seed_main=1000, f=5, amp=0)

        # Output labels stay on the public batch coordinate
        postfix = self.exp_cfg._get_job_postfix(cfg, 'net_pulse_000001')

        self.assertEqual(postfix, '000001_seed_1000_f_5_amp_0')

    def test_ibkg_wcorr_json_appends_before_runtime_corrections(self):
        runtime_params = self.exp_cfg._get_default_runtime_params()
        runtime_params['pops_used'] = ['IT2', 'PV2']
        runtime_params['time']['duration'] = 1000
        runtime_params['inp']['ibkg_corrections'] = {
            'IT2': 0.003,
            'PV2': 0.004,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / 'wcorr.json'
            with open(fpath, 'w') as fid:
                json.dump({'IT2': 0.001, 'PV2': 0.002}, fid)

            # Isolate correction composition from base and control currents
            self.exp_cfg.dirpath_self = Path(tmpdir)
            self.exp_cfg.USE_IBKG = 0
            self.exp_cfg.USE_IBKG_CTRL = 0
            self.exp_cfg.IBKG_WCORR_JSON_NAME = 'wcorr'
            iclamp = self.exp_cfg._build_iclamp(runtime_params)

        self.assertEqual(iclamp['IT2'], [
            {'amp': 0.001, 'dur': 1000},
            {'amp': 0.003, 'dur': 1000},
        ])
        self.assertEqual(iclamp['PV2'], [
            {'amp': 0.002, 'dur': 1000},
            {'amp': 0.004, 'dur': 1000},
        ])

    def test_wmat_multipliers_apply_to_exact_pairs(self):
        conn = {
            'preConds': {'pop': 'IT2'},
            'postConds': {'pop': ['IT2']},
            'weight': 0.5,
        }
        params = SimpleNamespace(connParams={'IT2_IT2': conn})

        # Pair multipliers work with scalar or singleton-list pop conditions
        self.exp_cfg._apply_wmat_multipliers(
            params,
            [{'pre': 'IT2', 'post': 'IT2', 'mult': 3}],
        )

        self.assertEqual(conn['weight'], 1.5)


if __name__ == '__main__':
    unittest.main()
