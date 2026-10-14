from itertools import product
import unittest
from unittest.mock import patch

import numpy as np
import xarray as xr

from create_base_cfg import create_base_cfg
from exp_configs.batch_rxbkg_state1_mech1.net_hstep_newsec_var_seed_group_amp import batch_params as batch
from exp_configs.batch_rxbkg_state1_mech1.net_hstep_newsec_var_seed_group_amp import exp_cfg as exp


def make_cfg(seed, group, amp):
    """Apply one real batch condition to the calibrated base configuration. """
    cfg = create_base_cfg()
    exp.apply_exp_cfg(cfg)
    cfg.seed_main = seed
    cfg.step_group = group
    cfg.amp = amp
    batch.post_update(cfg)
    return cfg


class HStepExperimentTests(unittest.TestCase):
    """Check additive inputs, matched random streams, and window boundaries. """

    def test_grid_preserves_baseline_and_random_streams(self):
        """Keep baseline inputs and all seed streams identical across conditions. """
        axes = batch.get_batch_params()
        reference = {}
        for seed, group, amp in product(*axes.values()):
            cfg = make_cfg(seed, group, amp)
            baseline = (cfg.IClamp, cfg.bkg_spike_inputs, cfg.seeds,
                        cfg.subnet_params, cfg.mech_changes)
            if seed in reference:
                self.assertEqual(baseline, reference[seed])
            else:
                reference[seed] = baseline
            expected = {
                pop: amp * cfg.step_groups[group].get(pop, 0)
                for pop in cfg.pops_used
            }
            self.assertEqual(cfg.h_step, expected)
            self.assertEqual(cfg.subnet_params['conns_frozen'], [])

    def test_empty_and_weighted_groups_have_no_name_specific_behavior(self):
        """Resolve arbitrary empty and weighted groups through the same grid. """
        groups = {'rest': [], 'scaled': {'IT2': 1, 'PV2': 0.5}}
        with patch.dict(batch.STEP_GROUPS, groups, clear=True):
            with patch.object(batch, 'GROUPS_SUBSET', ['rest', 'scaled']):
                seed = batch.get_batch_params()['seed_main'][0]
                for amp in batch.get_batch_params()['amp']:
                    rest = make_cfg(seed, 'rest', amp)
                    scaled = make_cfg(seed, 'scaled', amp)
                    self.assertTrue(all(value == 0 for value in rest.h_step.values()))
                    self.assertEqual(rest.step_pops, [])
                    self.assertEqual(scaled.h_step['IT2'], amp)
                    self.assertEqual(scaled.h_step['PV2'], amp / 2)
                    self.assertEqual(scaled.h_step['NGF2'], 0)
                    self.assertEqual(rest.seeds, scaled.seeds)

    def test_counts_and_current_use_half_open_boundaries(self):
        """Count boundary spikes once and hold the step only during its duration. """
        axes = batch.get_batch_params()
        cfg = make_cfg(axes['seed_main'][0], 'IT2', axes['amp'][0])
        baseline_start, baseline_stop = cfg.rate_windows['baseline']
        response_start, response_stop = cfg.rate_windows['response']
        response_mid = cfg.rate_windows['response_early'][1]
        spikes = [baseline_start, baseline_stop - 0.001, baseline_stop,
                  response_start, response_mid - 0.001, response_mid,
                  response_stop - 0.001, response_stop]
        sim_result = {
            'simConfig': {'duration': cfg.duration},
            'net': {'pops': {
                pop: {'cellGids': [index]}
                for index, pop in enumerate(cfg.pops_used)
            }},
            'simData': {'spkt': np.asarray(spikes) * 1000, 'spkid': [0] * len(spikes)},
        }
        stats = exp._get_window_stats(sim_result, cfg)
        self.assertEqual(stats['baseline']['IT2']['n_spikes'], 2)
        self.assertEqual(stats['response']['IT2']['n_spikes'], 4)
        self.assertEqual(stats['response_early']['IT2']['n_spikes'], 2)
        self.assertEqual(stats['response_late']['IT2']['n_spikes'], 2)
        self.assertEqual(stats['response']['PV2']['rate_hz'], 0)
        expected_rate = 4 / (response_stop - response_start)
        self.assertEqual(stats['response']['IT2']['rate_hz'], expected_rate)

        # Probe the current immediately around onset and simulation end
        onset = cfg.h_step_t0 / 1000
        end = cfg.duration / 1000
        times = [onset - 0.001, onset, end - 0.001, end]
        rates = xr.DataArray(
            np.zeros((len(cfg.pops_used), len(times))),
            dims=('pop', 'time'),
            coords={'pop': cfg.pops_used, 'time': times},
        )
        current = exp._build_hvec_xr(rates, cfg)
        np.testing.assert_array_equal(current.sel(pop='IT2'), [0, cfg.amp, cfg.amp, 0])
        np.testing.assert_array_equal(current.sel(pop='PV2'), np.zeros(4))


if __name__ == '__main__':
    unittest.main()
