import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import xarray as xr

from dev_scratch.step_resp.code import analyze_h_io as fitter


class AnalyzeHIOTests(unittest.TestCase):
    """Test h-r fitting over seeds and population-specific amplitudes."""

    def test_multiseed_population_amplitudes(self):
        """Recover diagonal gains with two seeds and unequal h amplitudes."""
        time = np.arange(2, 20, 0.01)
        phase = ((time - 5) / 7.5) % 1
        scale = np.zeros_like(time)
        active = time >= 5
        scale[active] = np.interp(
            phase[active],
            [0, 0.25, 0.5, 0.75, 1],
            [0, 1, 0, -1, 0],
        )

        pops = ['P1', 'P2']
        seeds = [1000, 1001]
        amps = {'P1': 0.04, 'P2': 0.1}
        params = {
            'P1': (1, 10, 30, 0.01, 1),
            'P2': (0.5, 20, 20, 0.02, 0.8),
        }
        rng = np.random.default_rng(12)
        current = np.empty((len(seeds), len(pops), time.size))
        rate = np.empty_like(current)
        for n_seed, _ in enumerate(seeds):
            for n_pop, pop in enumerate(pops):
                current[n_seed, n_pop] = amps[pop] * scale
                rate[n_seed, n_pop] = fitter.richards(
                    current[n_seed, n_pop],
                    *params[pop],
                )
                rate[n_seed, n_pop] += rng.normal(0, 0.02, time.size)

        coords = {'seed': seeds, 'pop': pops, 'time': time}
        dataset = xr.Dataset({
            'rate': (('seed', 'pop', 'time'), rate),
            'h': (('seed', 'pop', 'time'), current),
        }, coords=coords)
        coefficients, q_xr = fitter.fit_h_rate_curves(
            dataset,
            smooth_win_s=0.02,
            t_limits=(5, None),
            turn_margin_s=0.05,
        )

        expected = np.asarray([
            fitter.richards_derivative(0, *params[pop]) for pop in pops
        ])
        actual = np.diag(q_xr.values)
        np.testing.assert_allclose(actual, expected, rtol=0.05)
        np.testing.assert_array_equal(
            q_xr.values - np.diag(actual),
            np.zeros((2, 2)),
        )
        self.assertTrue(all(coefficients[pop][pop]['success'] for pop in pops))
        self.assertEqual(list(q_xr['pop_h'].values), pops)
        self.assertEqual(list(q_xr['pop_post'].values), pops)

    def test_collects_one_pair_per_seed(self):
        """Discover paired NetCDF files and retain seed/job coordinates."""
        time = np.asarray([2, 3, 4, 5, 6])
        pops = ['P1', 'P2']
        with TemporaryDirectory() as dirname:
            dirpath_data = Path(dirname)
            dirpath_rvec = dirpath_data / 'input' / 'rvec_xr'
            dirpath_hvec = dirpath_data / 'input' / 'hvec_xr'
            dirpath_rvec.mkdir(parents=True)
            dirpath_hvec.mkdir(parents=True)
            for job, seed, amp in ((0, 1000, 0.04), (1, 1001, 0.1)):
                values = np.full((len(pops), len(time)), amp)
                coords = {'pop': pops, 'time': time}
                rvec = xr.DataArray(values + 1, dims=('pop', 'time'),
                                    coords=coords, name='rate')
                hvec = xr.DataArray(values, dims=('pop', 'time'),
                                    coords=coords, name='h')
                postfix = f'{job:05d}_seed_{seed}.nc'
                rvec.to_netcdf(dirpath_rvec / f'rvec_{postfix}')
                hvec.to_netcdf(dirpath_hvec / f'hvec_{postfix}')

            dataset = fitter.collect_h_rate_data(dirpath_data)

        self.assertEqual(list(dataset['seed'].values), [1000, 1001])
        self.assertEqual(list(dataset['job'].values), [0, 1])
        self.assertEqual(dataset.sizes, {'seed': 2, 'pop': 2, 'time': 5})
        self.assertAlmostEqual(float(dataset['h'].sel(seed=1000).max()), 0.04)
        self.assertAlmostEqual(float(dataset['h'].sel(seed=1001).max()), 0.1)


if __name__ == '__main__':
    unittest.main()
