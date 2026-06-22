import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np


DIR_REPO = Path(__file__).resolve().parents[1]
DIR_EXP = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1' /
    'net_2pulses_var_seed_f_amps_dt0'
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
    """Load the two-pulse batch params as an isolated module."""
    return _load_module(DIR_EXP / 'batch_params.py', 'two_pulse_batch_test')


def load_exp_cfg():
    """Load the two-pulse experiment config without NEURON or NetPyNE."""
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
        return _load_module(DIR_EXP / 'exp_cfg.py', 'two_pulse_exp_cfg_test')


def load_create_net_params():
    """Load create_net_params.py with a fake NetPyNE specs module."""
    specs = _make_module('netpyne.batchtools.specs', NetParams=object)
    fake_modules = {
        'netpyne': _make_module('netpyne'),
        'netpyne.batchtools': _make_module('netpyne.batchtools', specs=specs),
        'netpyne.batchtools.specs': specs,
    }
    with patch.dict(sys.modules, fake_modules):
        return _load_module(DIR_REPO / 'create_net_params.py',
                            'create_net_params_pulse_test')


def _make_pulse(name):
    """Create one minimal pulse parameter dict."""
    return {
        'name': name,
        'pop': ['NGF'],
        't0': None,
        't_last': None,
        'width': 50,
        'period': None,
        'n_pulses': None,
        'rates': [500],
        'weight': None,
        'n_cells': 100,
        'convergence': 25,
        'jitter': 0,
        'rand_type': 'norm',
    }


class TwoPulseBatchParamTests(unittest.TestCase):
    def setUp(self):
        self.batch = load_batch_params()

    def _make_cfg(self):
        """Create a minimal cfg for post_update()."""
        return SimpleNamespace(
            seed_main=1000,
            seeds={},
            subnet_params={},
            bkg_spike_inputs={'IT2': {'exc': {}, 'inh': {}}},
            add_pulses=1,
            duration=6000,
            f=2,
            amp1=0.1,
            amp2=0.2,
            dt0=25,
            pulse_seq_params=[
                _make_pulse('PulseSeq1'),
                _make_pulse('PulseSeq2'),
            ],
        )

    def test_get_batch_params_has_two_amp_axes_and_dt0(self):
        params = self.batch.get_batch_params()

        # Expose one independent axis for each public pulse coordinate
        self.assertEqual(
            list(params),
            ['seed_main', 'f', 'amp1', 'amp2', 'dt0'],
        )
        self.assertEqual(params['amp1'], [0.01, 0.02, 0.03])
        self.assertEqual(params['amp2'], [0.01, 0.02, 0.03])
        self.assertEqual(params['dt0'], [0, 25, 50])

    def test_post_update_derives_two_streams_from_batch_axes(self):
        cfg = self._make_cfg()

        # Derive paired pulse streams from f, amp1, amp2, and dt0
        self.batch.post_update(cfg)

        pulse1, pulse2 = cfg.pulse_seq_params
        self.assertEqual(pulse1['period'], 500)
        self.assertEqual(pulse2['period'], 500)
        self.assertEqual(pulse1['n_pulses'], 2)
        self.assertEqual(pulse2['n_pulses'], 2)
        self.assertEqual(pulse1['weight'], 0.1)
        self.assertEqual(pulse2['weight'], 0.2)
        self.assertEqual(pulse1['tpulse'], [5000, 5500])
        self.assertEqual(pulse2['tpulse'], [5025, 5525])
        self.assertEqual(pulse1['rates'], [500, 500])
        self.assertEqual(pulse2['rates'], [500, 500])

    def test_post_update_keeps_public_zero_amp_labels(self):
        cfg = self._make_cfg()
        cfg.amp1 = 0
        cfg.amp2 = 0

        # Avoid exactly zero NetPyNE weights without changing public coords
        self.batch.post_update(cfg)

        pulse1, pulse2 = cfg.pulse_seq_params
        self.assertEqual(cfg.amp1, 0)
        self.assertEqual(cfg.amp2, 0)
        self.assertEqual(pulse1['weight'], self.batch.PULSE_ZERO_WEIGHT)
        self.assertEqual(pulse2['weight'], self.batch.PULSE_ZERO_WEIGHT)

    def test_post_update_preserves_dt0_with_shared_jitter(self):
        cfg = self._make_cfg()
        cfg.duration = 8000
        cfg.pulse_seq_params[0]['jitter'] = 1
        cfg.pulse_seq_params[1]['jitter'] = 1

        # Shared offsets keep corresponding pulses separated by one dt0
        self.batch.post_update(cfg)

        starts1 = np.asarray(cfg.pulse_seq_params[0]['tpulse'])
        starts2 = np.asarray(cfg.pulse_seq_params[1]['tpulse'])
        self.assertEqual(starts1[0], self.batch.PULSE_T0)
        self.assertEqual(starts2[0], self.batch.PULSE_T0 + cfg.dt0)
        np.testing.assert_allclose(starts2 - starts1, cfg.dt0)

    def test_post_update_rejects_mismatched_jitter_params(self):
        cfg = self._make_cfg()
        cfg.pulse_seq_params[0]['jitter'] = 1
        cfg.pulse_seq_params[1]['jitter'] = 2

        # Mismatched jitter would make constant per-pulse dt0 ambiguous
        with self.assertRaisesRegex(ValueError, 'jitter'):
            self.batch.post_update(cfg)

    def test_post_update_stores_batch_metadata(self):
        cfg = self._make_cfg()

        # Downstream scripts can recover the five-dimensional batch grid
        self.batch.post_update(cfg)

        self.assertEqual(
            cfg.batch_par_info['batch_params'],
            ['seed_main', 'f', 'amp1', 'amp2', 'dt0'],
        )


class TwoPulseExperimentConfigTests(unittest.TestCase):
    def setUp(self):
        self.exp_cfg = load_exp_cfg()

    def _make_cfg(self):
        """Create one cfg-like object for naming helpers."""
        return SimpleNamespace(
            seed_main=1000,
            f=5,
            amp1=0.1,
            amp2=0.2,
            dt0=25,
            t0_calc=5000,
            duration=15000,
            wmult=0.25,
            EEGain=0.5,
            pulse_seq_params=[
                {
                    'pop': ['NGF'],
                    't0': 5000,
                    't_last': None,
                    'width': 50,
                    'period': 500,
                    'n_pulses': 10,
                    'rates': [500],
                    'weight': 0.1,
                    'convergence': 25,
                    'jitter': 0,
                },
                {
                    'pop': ['NGF'],
                    't0': 5025,
                    't_last': None,
                    'width': 50,
                    'period': 500,
                    'n_pulses': 10,
                    'rates': [500],
                    'weight': 0.2,
                    'convergence': 25,
                    'jitter': 0,
                },
            ],
            runtime_params=self.exp_cfg._get_default_runtime_params(),
        )

    def test_exp_name_includes_two_amp_axes_and_dt0_grid(self):
        cfg = self._make_cfg()

        # Batch-wide result folder names include ranges, not per-job coords
        exp_name = self.exp_cfg.gen_exp_name_sub(cfg)

        self.assertIn('_nseed_1_f_2_5_', exp_name)
        self.assertIn('_amp1_0.01_0.03_3_', exp_name)
        self.assertIn('_amp2_0.01_0.03_3_', exp_name)
        self.assertIn('_dt0_0_25_50_', exp_name)
        self.assertIn('_2pulse_NGF_d_50_c_25_r_500_0_t0_5000_jit_0',
                      exp_name)

    def test_job_postfix_includes_actual_two_pulse_coords(self):
        cfg = self._make_cfg()

        # Job-local outputs carry actual amp1, amp2, and dt0 values
        postfix = self.exp_cfg._get_job_postfix(cfg, 'net_2pulse_000001')

        self.assertEqual(
            postfix,
            '000001_seed_1000_f_5_amp1_0.1_amp2_0.2_dt0_25',
        )


class SharedPulseGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.net_mod = load_create_net_params()

    def test_pulse_param_list_keeps_single_dict_compatible(self):
        cfg = SimpleNamespace(pulse_seq_params={'name': 'PulseSeq'})

        # Existing single-pulse cfgs still normalize to one item
        self.assertEqual(
            self.net_mod._get_pulse_seq_param_list(cfg),
            [{'name': 'PulseSeq'}],
        )

    def test_add_pulse_sequence_uses_explicit_tpulse(self):
        net_params = SimpleNamespace(
            popParams={'NGF': {}},
            connParams={},
        )
        par = {
            'name': 'PulseSeq1',
            'pop': ['NGF'],
            'tpulse': [5000, 5500],
            'n_pulses': 2,
            'width': 50,
            'rates': [500, 600],
            'weight': 0.1,
            'n_cells': 100,
            'convergence': 25,
        }

        # Explicit starts let paired jitter be derived outside net construction
        self.net_mod._add_pulse_sequence(net_params, par)

        pulses = net_params.popParams['PulseSeq1']['params']['pulses']
        self.assertEqual(pulses[0]['start'], 5000)
        self.assertEqual(pulses[0]['end'], 5050)
        self.assertEqual(pulses[1]['start'], 5500)
        self.assertEqual(pulses[1]['rate'], 600)
        self.assertEqual(
            net_params.connParams['PulseSeq1->NGF']['postConds']['pop'],
            ['NGF'],
        )

    def test_add_pulse_sequence_keeps_regular_timing_compatible(self):
        net_params = SimpleNamespace(
            popParams={'NGF': {}},
            connParams={},
        )
        par = {
            'name': 'PulseSeq',
            'pop': 'NGF',
            't0': 5000,
            'period': 500,
            'n_pulses': 2,
            'width': 50,
            'rates': 500,
            'weight': 0.1,
            'n_cells': 100,
            'convergence': 25,
        }

        # Old regular timing fields still generate the same pulse windows
        self.net_mod._add_pulse_sequence(net_params, par)

        pulses = net_params.popParams['PulseSeq']['params']['pulses']
        self.assertEqual(
            [(pulse['start'], pulse['rate']) for pulse in pulses],
            [(5000, 500), (5500, 500)],
        )


if __name__ == '__main__':
    unittest.main()
