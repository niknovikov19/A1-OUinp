import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr

from predict_hstep_static import checked_matrix_copy, predict_dataset
from summarize_hstep_amplitudes import half_amplitude_checks


class FixedPredictionTests(unittest.TestCase):
    def test_half_amplitude_check_distinguishes_linear_and_quadratic_changes(self):
        """Check signed amplitude scaling without dividing by noisy responses. """
        rows = [{'seed_main': 1000, 'step_group': 'A', 'pop': 'A', 'amp': amp,
                 'matched_post_hz': 3 * amp, 'drift_adjusted_hz': 3 * amp + 100 * amp ** 2}
                for amp in (-0.03, -0.015, 0.015, 0.03)]
        result = half_amplitude_checks(pd.DataFrame(rows))
        self.assertEqual(len(result), 4)
        for _, row in result.iterrows():
            expected = 0 if row.response_definition == 'matched_post_hz' else -100 * row.small_amp_nA ** 2
            self.assertAlmostEqual(row.half_minus_half_full_hz, expected)

    def test_five_seed_two_amplitude_prediction_uses_frozen_bytes(self):
        """Keep fixed labelled matrices unchanged regardless of observed response values. """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, data = root / 'reference', root / 'data'
            reference.mkdir()
            (data / 'input/results').mkdir(parents=True)
            (data / 'input/cfg').mkdir()
            (data / 'analysis').mkdir()
            pops = ['A', 'B']
            j = xr.DataArray([[0.1, 0.2], [-0.1, 0.05]], dims=['pop_pre', 'pop_post'],
                             coords={'pop_pre': pops, 'pop_post': pops})
            q = xr.DataArray([[3, 0], [0, 4]], dims=['pop_h', 'pop_post'],
                             coords={'pop_h': pops, 'pop_post': pops})
            jpath, qpath = reference / 'j.nc', reference / 'q.nc'
            j.to_netcdf(jpath)
            q.to_netcdf(qpath)
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {'primary': 'reference/j', 'j_inputs': [
                {'label': 'reference/j', 'path': str(jpath), 'sha256': digest(jpath)}],
                'q_path': str(qpath), 'q_sha256': digest(qpath),
                'zero_filled_entries': [], 'missing_gain_policy': 'Reference already finite'}
            (reference / 'manifest.json').write_text(json.dumps(manifest))
            cfg = {'simConfig': {'subnet_params': {'pops_active': pops}}}
            (data / 'input/cfg/cfg_00000.json').write_text(json.dumps(cfg))

            # Generate every new condition independently from the fake measurements
            rows = []
            for seed in range(1000, 1005):
                for group in pops:
                    for amp in (-0.03, -0.015, 0.015, 0.03):
                        trial = f'{seed}_{group}_{amp}'
                        result = {'parameters': {'seed_main': seed, 'step_group': group, 'amp': amp},
                                  'h_step_nA': {pop: amp if pop == group else 0 for pop in pops}}
                        (data / f'input/results/result_{trial}.json').write_text(json.dumps(result))
                        rows += [{'trial': trial, 'seed_main': seed, 'step_group': group,
                                  'amp': amp, 'pop': pop, 'matched_post_hz': 100, 'drift_adjusted_hz': -100}
                                 for pop in pops]
            observations = data / 'analysis/response_estimates.csv'
            pd.DataFrame(rows).to_csv(observations, index=False)
            with patch('predict_hstep_static.plot_prediction_comparison'):
                result = predict_dataset(data, reference)
            predicted = pd.read_csv(data / 'analysis/jq/conditional_predictions.csv')
            self.assertEqual(len(predicted), 16)
            self.assertEqual(len(pd.read_csv(data / 'analysis/jq/pilot_comparison.csv')), 80)
            self.assertEqual(digest(data / 'analysis/jq/jmat_fixed.nc'), manifest['j_inputs'][0]['sha256'])
            self.assertEqual(digest(data / 'analysis/jq/qmat_fixed.nc'), manifest['q_sha256'])
            for _, row in predicted.iterrows():
                h = np.asarray([row.amp if pop == row.step_group else 0 for pop in pops])
                expected = np.linalg.solve(np.eye(2) - j.values.T, q.values.T @ h)
                self.assertAlmostEqual(row.predicted_hz, expected[pops.index(row['pop'])])

            # Changing measured rates must never tune the fixed predictor
            changed = pd.DataFrame(rows)
            changed['matched_post_hz'] = 0
            changed['drift_adjusted_hz'] = 0
            changed.to_csv(observations, index=False)
            with patch('predict_hstep_static.plot_prediction_comparison'):
                predict_dataset(data, reference)
            pd.testing.assert_frame_equal(predicted, pd.read_csv(data / 'analysis/jq/conditional_predictions.csv'))

    def test_changed_source_or_existing_copy_is_rejected(self):
        """Reject a changed source or destination without overwriting existing data. """
        with tempfile.TemporaryDirectory() as temporary:
            source, destination = Path(temporary) / 'source', Path(temporary) / 'copy'
            source.write_bytes(b'fixed')
            checksum = hashlib.sha256(b'fixed').hexdigest()
            checked_matrix_copy(source, destination, checksum)
            destination.write_bytes(b'user change')
            with self.assertRaises(ValueError):
                checked_matrix_copy(source, destination, checksum)
            self.assertEqual(destination.read_bytes(), b'user change')
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                checked_matrix_copy(source, destination, checksum)


if __name__ == '__main__':
    unittest.main()
