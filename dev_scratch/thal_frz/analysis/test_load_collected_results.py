#!/home/nnovikov/conda_env/netpyne/bin/python
"""Test that every collected experiment can be loaded and inspected."""

import sys
import unittest
from pathlib import Path


# Set repository import paths
DIR_ANALYSIS = Path(__file__).resolve().parent
DIR_REPO = DIR_ANALYSIS.parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.xr_io import load_xr


DIR_EXPERIMENTS = DIR_ANALYSIS / 'experiments'
DIR_COLLECTED = DIR_ANALYSIS / 'collected'


class TestCollectedResults(unittest.TestCase):
    """Validate the collected experiment datasets."""

    def test_load_all_experiments(self):
        """Load every dataset and verify its core schema and seed count."""
        exp_dirs = sorted(path for path in DIR_EXPERIMENTS.glob('exp_*') if path.is_dir())
        collected_files = sorted(DIR_COLLECTED.glob('exp_*.nc'))
        self.assertEqual(len(collected_files), len(exp_dirs))

        for dirpath_exp in exp_dirs:
            fpath = DIR_COLLECTED / f'{dirpath_exp.name}.nc'
            self.assertTrue(fpath.is_file(), fpath)

            result_xr = load_xr(fpath, data_type='dataset', load=True)
            with self.subTest(experiment=dirpath_exp.name):
                self.assertEqual(set(result_xr.data_vars), {'rate', 'cv'})
                self.assertEqual(result_xr['rate'].dims, ('seed_main', 'pop'))
                self.assertEqual(result_xr['cv'].dims, ('seed_main', 'pop'))
                self.assertEqual(
                    result_xr.sizes['seed_main'],
                    len(list((dirpath_exp / 'results').glob('result_*.json'))),
                )
                self.assertGreater(result_xr.sizes['pop'], 0)
            result_xr.close()


if __name__ == '__main__':
    unittest.main()
