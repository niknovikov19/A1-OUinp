import json
import pickle
from pathlib import Path
import tempfile
import unittest

import numpy as np
import xarray as xr

from utils.batch.collect_cell_rates_from_pkl import (
    _infer_batch_param_fields,
    collect_cell_rates_from_pkl,
)
from utils.cell_xr import get_batch_dims, get_pop_gids, select_pop


def _make_cfg(job_id, seed, amp, t_limits=(1, 5), metadata=True):
    """Create one minimal saved simulation config. """
    cfg = {
        'seed_main': seed,
        'amp': amp,
        'simLabel': f'test_{job_id:05d}',
        'duration': 5000,
        't0_calc': 1000,
        'pops_used': ['P1', 'P2'],
        'runtime_params': {
            'proc': {'rate_t_limits': list(t_limits)},
        },
    }
    if metadata:
        cfg['batch_par_info'] = {
            'batch_params': ['seed_main', 'amp'],
        }
    return cfg


def _make_result(gid_p2=20):
    """Create one minimal NetPyNE pickle result. """
    return {
        'net': {
            'pops': {
                'P1': {'cellGids': [10, 11]},
                'P2': {'cellGids': [gid_p2]},
                'P1frz': {'cellGids': [100]},
            },
        },
        'simData': {
            'spkid': [10, 10, 10, 10, gid_p2, gid_p2, 100],
            'spkt': [1000, 2000, 3000, 5000, 1000, 2000, 3000],
        },
    }


def _write_job(root, job_id, seed, amp, t_limits=(1, 5), metadata=True,
               gid_p2=20, write_pickle=True):
    """Write one synthetic config and simulation pickle. """
    cfg = _make_cfg(job_id, seed, amp, t_limits=t_limits, metadata=metadata)
    cfg_path = root / 'cfg' / f'cfg_{job_id:05d}_seed_{seed}.json'
    cfg_path.write_text(json.dumps({'simConfig': cfg}))
    if not write_pickle:
        return
    pkl_path = root / 'pkl' / f'data_{job_id:05d}_seed_{seed}.pkl'
    with pkl_path.open('wb') as file:
        pickle.dump(_make_result(gid_p2=gid_p2), file)


def _make_batch(root):
    """Write a three-job batch with one missing Cartesian combination. """
    (root / 'cfg').mkdir()
    (root / 'pkl').mkdir()
    _write_job(root, 0, seed=1, amp=0.1)
    _write_job(root, 1, seed=2, amp=0.1)
    _write_job(root, 2, seed=1, amp=0.2)


class CellRateCollectorTests(unittest.TestCase):
    def test_collects_rates_cvs_and_batch_coordinates(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / 'batch'
            root.mkdir()
            _make_batch(root)
            output_dir = Path(dirname) / 'output'

            dataset = collect_cell_rates_from_pkl(root, dirpath_out=output_dir)

            self.assertEqual(
                dict(dataset.sizes),
                {'seed_main': 2, 'amp': 2, 'gid': 3},
            )
            self.assertEqual(dataset.gid.values.tolist(), [10, 11, 20])
            self.assertEqual(dataset['pop'].values.tolist(), ['P1', 'P1', 'P2'])
            self.assertAlmostEqual(
                dataset.rate.sel(seed_main=1, amp=0.1, gid=10).item(), 1
            )
            self.assertAlmostEqual(
                dataset.cv.sel(seed_main=1, amp=0.1, gid=10).item(),
                np.std([1, 1, 2]) / np.mean([1, 1, 2]),
            )
            self.assertEqual(
                dataset.rate.sel(seed_main=1, amp=0.1, gid=11).item(), 0
            )
            self.assertTrue(
                np.isnan(dataset.cv.sel(seed_main=1, amp=0.1, gid=20))
            )
            self.assertTrue(
                dataset.rate.sel(seed_main=2, amp=0.2).isnull().all()
            )
            self.assertEqual(
                dataset.job_id.sel(seed_main=1, amp=0.2).item(), 2
            )
            output_path = output_dir / 'cell_rates_xr_combined.nc'
            self.assertTrue(output_path.is_file())
            with xr.open_dataset(output_path) as saved:
                self.assertEqual(saved['pop'].values.tolist(), ['P1', 'P1', 'P2'])
                self.assertEqual(saved.rate.attrs['units'], 'Hz')

    def test_job_filter_and_explicit_batch_fields(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / 'batch'
            root.mkdir()
            (root / 'cfg').mkdir()
            (root / 'pkl').mkdir()
            _write_job(root, 0, seed=7, amp=0.1, metadata=False)
            output_dir = Path(dirname) / 'output'

            dataset = collect_cell_rates_from_pkl(
                root,
                dirpath_out=output_dir,
                batch_param_fields={
                    'seed': 'seed_main',
                    'pulse_amp': 'amp',
                },
                job_ids=[0],
            )

            self.assertEqual(dataset.sizes['seed'], 1)
            self.assertEqual(dataset.sizes['pulse_amp'], 1)
            self.assertEqual(dataset.seed.item(), 7)

    def test_missing_pickle_remains_on_config_grid(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / 'batch'
            root.mkdir()
            (root / 'cfg').mkdir()
            (root / 'pkl').mkdir()
            _write_job(root, 0, seed=1, amp=0.1)
            _write_job(
                root, 1, seed=2, amp=0.1, write_pickle=False
            )

            dataset = collect_cell_rates_from_pkl(
                root, dirpath_out=Path(dirname) / 'output'
            )

            self.assertEqual(dataset.sizes['seed_main'], 2)
            self.assertEqual(dataset.job_id.sel(seed_main=2, amp=0.1).item(), 1)
            self.assertTrue(dataset.rate.sel(seed_main=2, amp=0.1).isnull().all())

    def test_fallback_inference_and_ambiguous_failure(self):
        cfgs = {
            0: _make_cfg(0, seed=10, amp=0.1, metadata=False),
            1: _make_cfg(1, seed=11, amp=0.1, metadata=False),
        }
        self.assertEqual(
            _infer_batch_param_fields(cfgs),
            {'seed_main': 'seed_main'},
        )
        with self.assertRaisesRegex(ValueError, 'BATCH_PARAM_FIELDS'):
            _infer_batch_param_fields({0: cfgs[0]})

    def test_rejects_inconsistent_time_and_cell_mapping(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / 'batch'
            root.mkdir()
            (root / 'cfg').mkdir()
            (root / 'pkl').mkdir()
            _write_job(root, 0, seed=1, amp=0.1)
            _write_job(root, 1, seed=2, amp=0.1, t_limits=(2, 5))
            with self.assertRaisesRegex(ValueError, 'time limits'):
                collect_cell_rates_from_pkl(
                    root, dirpath_out=Path(dirname) / 'out_time'
                )

            # Make the configs consistent, then expose a changed population map
            _write_job(root, 1, seed=2, amp=0.1, gid_p2=21)
            with self.assertRaisesRegex(ValueError, "coordinate values for 'gid'"):
                collect_cell_rates_from_pkl(
                    root, dirpath_out=Path(dirname) / 'out_mapping'
                )

    def test_rejects_duplicate_parameter_tuple_and_existing_output(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / 'batch'
            root.mkdir()
            (root / 'cfg').mkdir()
            (root / 'pkl').mkdir()
            _write_job(root, 0, seed=1, amp=0.1)
            _write_job(root, 1, seed=1, amp=0.1)
            with self.assertRaisesRegex(ValueError, 'non-unique MultiIndex'):
                collect_cell_rates_from_pkl(
                    root, dirpath_out=Path(dirname) / 'out_duplicate'
                )

            output_dir = Path(dirname) / 'out_existing'
            output_dir.mkdir()
            (output_dir / 'cell_rates_xr_combined.nc').write_bytes(b'existing')
            with self.assertRaises(FileExistsError):
                collect_cell_rates_from_pkl(
                    root,
                    dirpath_out=output_dir,
                    overwrite=False,
                )


class CellXrTests(unittest.TestCase):
    def test_population_helpers_support_new_and_legacy_coordinates(self):
        dataset = xr.Dataset(
            {'rate': (('seed', 'gid'), [[1, 2, 3]])},
            coords={
                'seed': [1],
                'gid': [10, 11, 20],
                'pop': ('gid', ['P1', 'P1', 'P2']),
            },
        )
        self.assertEqual(get_pop_gids(dataset, 'P1').tolist(), [10, 11])
        self.assertEqual(select_pop(dataset, 'P2').gid.values.tolist(), [20])
        self.assertEqual(get_batch_dims(dataset), ('seed',))

        legacy = dataset.rename({'pop': 'pop_post'})
        legacy = legacy.assign_coords(pop_pre=['P1', 'P2'])
        legacy['inputs'] = (('seed', 'gid', 'pop_pre'), np.ones((1, 3, 2)))
        self.assertEqual(get_pop_gids(legacy, 'P2').tolist(), [20])
        self.assertEqual(get_batch_dims(legacy), ('seed',))
        with self.assertRaises(KeyError):
            select_pop(dataset, 'missing')


if __name__ == '__main__':
    unittest.main()
