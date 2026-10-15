import unittest

import numpy as np
import xarray as xr

from analyze_hstep import analyze_trials, central_slopes, summarize_responses, validate_trial


def make_trial(name, group, amp, bump_pre=False, post_offset=0):
    """Make a small raw-trace fixture with consistent counts and current metadata. """
    pops = ['A', 'B']
    times = np.arange(8)
    values = np.ones((2, 8))
    if bump_pre:
        values[0, 1] += 1
    values[0, 6:8] += post_offset
    rates = xr.DataArray(values, dims=('pop', 'time'), coords={'pop': pops, 'time': times})
    rates.attrs = {'units': 'Hz', 'tau_smooth_s': 0, 'dt_bin_s': 1, 'h_step_t0_ms': 4000}
    current_by_pop = {'A': amp if group == 'probe' else 0, 'B': 0}
    current_values = np.asarray([current_by_pop[pop] * (times >= 4) for pop in pops])
    current = xr.DataArray(current_values, dims=rates.dims, coords=rates.coords)
    current.attrs = {'units': 'nA'}

    # Derive exact window counts from the fixture's raw bins
    windows = {'baseline': [2, 4], 'response': [6, 8],
               'response_early': [6, 7], 'response_late': [7, 8]}
    stats = {}
    for window, (start, stop) in windows.items():
        stats[window] = {}
        for index, pop in enumerate(pops):
            count = int(values[index, start:stop].sum() * 10)
            stats[window][pop] = {'n_cells': 10, 'n_spikes': count,
                                  'rate_hz': count / (10 * (stop - start))}
    cfg = {
        'step_groups': {'probe': {'A': 1}, 'idle': {}},
        'h_step_t0': 4000, 'duration': 8000,
        'seeds': {'stim': 1000}, 'IClamp': {}, 'bkg_spike_inputs': {},
        'subnet_params': {}, 'mech_changes': {},
    }
    result = {
        'parameters': {'seed_main': 1000, 'step_group': group, 'amp': amp},
        'h_step_nA': current_by_pop, 'h_clamp_count_by_pop': {'A': 10, 'B': 10},
        'rate_windows_s': windows, 'window_stats': stats, 'timing': {'totalTime': 1},
    }
    return {'id': name, 'result': result, 'rates': rates, 'h': current, 'cfg': cfg}


class HStepAnalysisTests(unittest.TestCase):
    """Check zero-vector matching and distinguish protocol from reproducibility. """

    def test_matching_uses_zero_vector_not_reserved_name(self):
        """Accept arbitrary zero-input group names and reproducible controls. """
        trials = [make_trial('idle_minus', 'idle', -0.1),
                  make_trial('idle_plus', 'idle', 0.1),
                  make_trial('probe_plus', 'probe', 0.1)]
        summary, windows, contrasts = analyze_trials(trials)
        self.assertTrue(summary['protocol_checks_passed'])
        self.assertTrue(summary['matched_response_comparison_ready'])
        self.assertEqual(summary['n_zero_input_trials'], 2)
        self.assertEqual(len(windows), 24)
        self.assertEqual(len(contrasts), 8)

    def test_pre_step_mismatch_blocks_paired_comparison(self):
        """Catch changed pre-step bins even outside the baseline mean window. """
        trials = [make_trial('idle_minus', 'idle', -0.1),
                  make_trial('idle_plus', 'idle', 0.1, bump_pre=True),
                  make_trial('probe_plus', 'probe', 0.1)]
        summary, _, _ = analyze_trials(trials)
        self.assertTrue(summary['protocol_checks_passed'])
        self.assertFalse(summary['matched_pre_step_identical'])
        self.assertFalse(summary['zero_input_repeats_identical'])
        self.assertFalse(summary['matched_response_comparison_ready'])
        self.assertEqual(summary['matched_pairs'][0]['pre_step_changed_bins'], 1)

    def test_wrong_current_and_counts_are_rejected(self):
        """Reject an incorrect waveform or inconsistent raw-count rate. """
        trial = make_trial('probe_plus', 'probe', 0.1)
        trial['h'].values[0, 5] = 0
        with self.assertRaises(AssertionError):
            validate_trial(trial)
        trial = make_trial('probe_plus', 'probe', 0.1)
        trial['result']['window_stats']['response']['A']['n_spikes'] += 1
        with self.assertRaises(AssertionError):
            validate_trial(trial)

    def test_descriptive_estimands_keep_control_drift_separate(self):
        """Retain by-amplitude, pooled, and drift-adjusted response definitions. """
        trials = [make_trial('idle_minus', 'idle', -0.1),
                  make_trial('idle_plus', 'idle', 0.1, post_offset=2),
                  make_trial('probe_minus', 'probe', -0.1, post_offset=1),
                  make_trial('probe_plus', 'probe', 0.1, post_offset=3)]
        _, windows, contrasts = analyze_trials(trials)
        _, _, responses, summary = summarize_responses(windows, contrasts)
        plus = responses[(responses.amp == 0.1) & (responses['pop'] == 'A')].iloc[0]
        self.assertEqual(plus.matched_post_hz, 1)
        self.assertEqual(plus.pooled_post_hz, 2)
        self.assertEqual(plus.drift_adjusted_hz, 2)
        self.assertEqual(plus.control_drift_hz, 1)
        self.assertTrue((summary.drift_adjusted_hz_count == 1).all())
        slopes = central_slopes(responses).set_index('pop')
        self.assertAlmostEqual(slopes.loc['A', 'drift_adjusted_hz_slope_hz_per_nA'], 10)


if __name__ == '__main__':
    unittest.main()
