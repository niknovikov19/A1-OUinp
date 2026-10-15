import unittest

import numpy as np
import xarray as xr

from analyze_j_refit import solve_response, zero_missing_gains


class JPredictionTests(unittest.TestCase):
    """Check labelled input-first prediction and strict missing-value handling. """

    def test_prediction_aligns_and_transposes_both_matrices(self):
        """Preserve physical meaning when matrix coordinate orders differ. """
        pops = ['A', 'B']
        j = xr.DataArray([[0, 0.5], [-0.2, 0]], dims=('pop_pre', 'pop_post'),
                         coords={'pop_pre': pops, 'pop_post': pops})
        q = xr.DataArray(np.diag([2, 3]), dims=('pop_h', 'pop_post'),
                         coords={'pop_h': pops, 'pop_post': pops})
        q = q.sel(pop_h=['B', 'A'], pop_post=['B', 'A'])
        prediction, direct, _ = solve_response(j, q, {'A': 0.1, 'B': 0})
        self.assertAlmostEqual(prediction['A'], 0.2 / 1.1)
        self.assertAlmostEqual(prediction['B'], 0.1 / 1.1)
        self.assertAlmostEqual(direct['A'], 0.2)
        self.assertEqual(direct['B'], 0)

    def test_missing_j_is_not_treated_as_zero(self):
        """Reject a missing gain instead of silently manufacturing a prediction. """
        j = xr.DataArray([[np.nan]], dims=('pop_pre', 'pop_post'),
                         coords={'pop_pre': ['A'], 'pop_post': ['A']})
        q = xr.DataArray([[1]], dims=('pop_h', 'pop_post'),
                         coords={'pop_h': ['A'], 'pop_post': ['A']})
        with self.assertRaises(ValueError):
            solve_response(j, q, {'A': 0.1})


    def test_explicit_zero_filling_preserves_original_and_finite_gains(self):
        """Record missing coordinates and change only the explicitly filled copy. """
        pops = ['A', 'B']
        original = xr.DataArray([[np.nan, 0.5], [-0.2, np.nan]], dims=('pop_pre', 'pop_post'),
                                coords={'pop_pre': pops, 'pop_post': pops})
        filled, entries = zero_missing_gains(original)
        np.testing.assert_equal(filled.values, [[0, 0.5], [-0.2, 0]])
        self.assertTrue(np.isnan(original.values[0, 0]))
        self.assertTrue(np.isnan(original.values[1, 1]))
        self.assertEqual(entries, [{'pop_pre': 'A', 'pop_post': 'A'}, {'pop_pre': 'B', 'pop_post': 'B'}])


if __name__ == '__main__':
    unittest.main()
