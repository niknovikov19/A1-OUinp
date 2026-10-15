import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import refit_rate_io as refit
from refit_rate_io import fit_curve, richards, richards_derivative, scaled_model_and_jac, triangle_masks


class RateRefitTests(unittest.TestCase):
    """Check stable derivatives, scaled fitting, and experimental branch masks. """

    def test_historical_overflow_case_is_finite(self):
        """Evaluate the saved VIP2-to-NGF2 tail without inf divided by inf. """
        params = [0.9733471419786519, 0.716613715174314, 35.42235698150015,
                  65.63046165822381, 172.71976692023665]
        with np.errstate(over='raise', invalid='raise'):
            gain = richards_derivative(7, *params)
            value = richards(7, *params)
        self.assertTrue(np.isfinite(gain))
        self.assertTrue(np.isfinite(value))
        self.assertLess(gain, 0)

    def test_scaled_jacobian_matches_finite_differences(self):
        """Verify analytic derivatives for both monotone response directions. """
        x = np.linspace(0, 1, 30)
        params = np.asarray([0.1, 0.7, 4, 0.4, 0.8])
        for sign in (-1, 1):
            _, jac = scaled_model_and_jac(x, params, sign)
            for index in range(len(params)):
                offset = np.zeros_like(params)
                offset[index] = 1e-6
                plus, _ = scaled_model_and_jac(x, params + offset, sign)
                minus, _ = scaled_model_and_jac(x, params - offset, sign)
                np.testing.assert_allclose(jac[:, index], (plus - minus) / 2e-6, rtol=1e-5, atol=1e-7)

    def test_scaled_refit_recovers_signed_synthetic_gains(self):
        """Recover local gains from noiseless increasing and decreasing curves. """
        x = np.tile(np.linspace(0, 20, 400), (3, 1))
        for sign in (-1, 1):
            params = [1, 10, 0.3, 8, 0.8] if sign > 0 else [10, 1, 0.3, 8, 0.8]
            y = richards(x, *params)
            fit = fit_curve(x, y, sign, 4, n_bins=100, max_nfev=500)
            self.assertTrue(fit['success'])
            expected = richards_derivative(4, *params)
            self.assertAlmostEqual(fit['dR_dr_at_target'] / expected, 1, delta=0.02)
            self.assertGreater(fit['r_squared'], 0.999)

    def test_triangle_mask_matches_starting_phase(self):
        """Use the known target-rate phase instead of noisy rate gradients. """
        times = np.asarray([5, 8.375, 9, 12.125, 13])
        masks = triangle_masks(times, 12, 5, 7.5, 10, 500, 0.1)
        np.testing.assert_array_equal(masks['pooled'], [True, False, True, False, True])
        np.testing.assert_array_equal(masks['rising'], [True, False, False, False, True])

    def test_reduced_model_is_fitted_when_general_model_does_not_converge(self):
        """Fit a real nested logistic model instead of imputing a failed gain. """
        original = refit.least_squares

        def fail_general(fun, initial, **kwargs):
            """Simulate generalized-model nonconvergence but run actual reduced fitting. """
            if len(initial) == 5:
                return SimpleNamespace(success=False)
            return original(fun, initial, **kwargs)

        x = np.tile(np.linspace(0, 20, 300), (3, 1))
        params = [10, 1, 0.3, 8, 1]
        y = richards(x, *params)
        with patch('refit_rate_io.least_squares', side_effect=fail_general):
            fit = fit_curve(x, y, -1, 4, n_bins=100)
        self.assertTrue(fit['success'])
        self.assertEqual(fit['fit_family'], 'logistic4')
        self.assertLess(fit['dR_dr_at_target'], 0)
        self.assertAlmostEqual(fit['dR_dr_at_target'] / richards_derivative(4, *params), 1, delta=0.02)


if __name__ == '__main__':
    unittest.main()
