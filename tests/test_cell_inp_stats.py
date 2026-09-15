import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import xarray as xr

from utils.cell_inp_ratio import (
    merge_ratio_summaries,
    update_ratio_summary,
    validate_ratio_summaries,
)
from utils.cell_inp_stats import _get_pop_names, calc_cell_inp_stats


DIR_REPO = Path(__file__).resolve().parents[1]
FPATH_COLLECTOR = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1' /
    'net_newsec_var_seed' / 'collect_batch_results.py'
)


def _load_module(fpath, name):
    """Load one source file under an isolated module name."""
    spec = importlib.util.spec_from_file_location(name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _conn(pre_gid, weight, syn_mech):
    """Create one minimal instantiated connection record."""
    return {'preGid': pre_gid, 'weight': weight, 'synMech': syn_mech}


def _cell(gid, pop, conns=None):
    """Create one minimal NetPyNE-like cell."""
    return SimpleNamespace(gid=gid, tags={'pop': pop}, conns=conns or [])


def _make_sim(include_frozen_conn=True):
    """Create a single-rank simulation stub with noncontiguous GIDs."""
    conns_10 = [
        _conn(101, 0.2, 'AMPA'),
        _conn(101, 0.8, 'NMDA'),
        _conn(101, 0.1, 'AMPA'),
        _conn(101, 0.4, 'NMDA'),
        _conn(103, 0.4, 'AMPA'),
        _conn(103, 1.6, 'NMDA'),
        _conn('NetStim', 99, 'AMPA'),
        _conn(901, 5, 'AMPA'),
    ]
    if include_frozen_conn:
        conns_10.extend([
            _conn(501, 0.5, 'AMPA'),
            _conn(501, 2, 'NMDA'),
        ])
    cells = [
        _cell(10, 'P2', conns_10),
        _cell(42, 'P2', [_conn(101, 0, 'AMPA'), _conn(101, 0, 'NMDA')]),
        _cell(77, 'P2'),
        _cell(101, 'P1'),
        _cell(103, 'P1'),
        _cell(501, 'P1frz'),
        _cell(901, 'other'),
    ]
    spkid = [101, 101, 101, 103, 103, 10, 10, 10, 77, 501, 501, 501]
    spkt = [1000, 2000, 3000, 1000, 2500, 1000, 2000, 4000,
            2000, 1000, 2000, 3000]
    return SimpleNamespace(
        rank=0,
        nhosts=1,
        cfg=SimpleNamespace(
            pops_used=['P1', 'P2'],
            t0_calc=1000,
            duration=4000,
            seed_main=123,
            runtime_params={'example': 1},
        ),
        net=SimpleNamespace(
            cells=cells,
            pops={'P1': None, 'P2': None, 'P1frz': None, 'other': None},
        ),
        simData={'spkid': spkid, 'spkt': spkt},
    )


class CellInputStatsTests(unittest.TestCase):
    def test_population_names_use_declared_netpyne_populations(self):
        sim = SimpleNamespace(
            cfg=SimpleNamespace(pops_used=['P1', 'P2']),
            net=SimpleNamespace(
                pops={
                    'P1': None,
                    'P2': None,
                    'P1frz': None,
                    'P3frz': None,
                },
            ),
        )

        self.assertEqual(
            _get_pop_names(sim, include_frz=False),
            (['P1', 'P2'], ['P1', 'P2']),
        )
        self.assertEqual(
            _get_pop_names(sim, include_frz=True),
            (['P1', 'P2'], ['P1', 'P2', 'P1frz']),
        )

    def test_metrics_contacts_empty_cells_and_activity(self):
        dataset = calc_cell_inp_stats(_make_sim(), include_frz=False)

        # Preserve global GIDs and aggregate all records from each cell pair
        self.assertEqual(dataset.gid.values.tolist(), [10, 42, 77, 101, 103])
        self.assertEqual(dataset.pop_pre.values.tolist(), ['P1', 'P2'])
        self.assertEqual(dataset.pop_post.sel(gid=10).item(), 'P2')
        self.assertEqual(dataset.n_pre.sel(gid=10, pop_pre='P1').item(), 2)
        self.assertAlmostEqual(
            dataset.r_pre_mean.sel(gid=10, pop_pre='P1').item(), 5 / 6
        )
        self.assertAlmostEqual(
            dataset.w_sum.sel(gid=10, pop_pre='P1').item(), 3.5
        )
        self.assertAlmostEqual(
            dataset.wr_sum.sel(gid=10, pop_pre='P1').item(), 17 / 6
        )
        self.assertAlmostEqual(
            dataset.r_pre_wmean.sel(gid=10, pop_pre='P1').item(), 17 / 21
        )

        # Keep connected zero-weight pairs but leave their weighted mean undefined
        self.assertEqual(dataset.n_pre.sel(gid=42, pop_pre='P1').item(), 1)
        self.assertEqual(dataset.w_sum.sel(gid=42, pop_pre='P1').item(), 0)
        self.assertEqual(dataset.wr_sum.sel(gid=42, pop_pre='P1').item(), 0)
        self.assertTrue(np.isnan(
            dataset.r_pre_wmean.sel(gid=42, pop_pre='P1').item()
        ))

        # Fill genuinely absent population inputs with the specified defaults
        self.assertEqual(dataset.n_pre.sel(gid=77, pop_pre='P1').item(), 0)
        self.assertTrue(np.isnan(
            dataset.r_pre_mean.sel(gid=77, pop_pre='P1').item()
        ))
        self.assertEqual(dataset.rate.sel(gid=10).item(), 1)
        self.assertAlmostEqual(dataset.cv.sel(gid=10).item(), 1 / 3)
        self.assertEqual(dataset.rate.sel(gid=42).item(), 0)
        self.assertTrue(np.isnan(dataset.cv.sel(gid=42).item()))
        self.assertTrue(np.isnan(dataset.cv.sel(gid=77).item()))

        ratio_meta = json.loads(dataset.attrs['receptor_ratio_validation_json'])
        self.assertEqual(ratio_meta['status'], 'passed')
        self.assertEqual(ratio_meta['population_pairs_checked'], 1)
        self.assertEqual(ratio_meta['cell_pairs_checked'], 2)
        self.assertEqual(ratio_meta['zero_weight_cell_pairs_skipped'], 1)
        self.assertEqual(dataset.attrs['dynamic_modulation'], 'ignored')

    def test_frozen_population_flag(self):
        sim = _make_sim()
        without_frz = calc_cell_inp_stats(sim, include_frz=False)
        with_frz = calc_cell_inp_stats(sim, include_frz=True)

        self.assertNotIn('P1frz', without_frz.pop_pre.values)
        self.assertEqual(
            with_frz.pop_pre.values.tolist(), ['P1', 'P2', 'P1frz']
        )
        self.assertEqual(with_frz.n_pre.sel(gid=10, pop_pre='P1frz').item(), 1)
        self.assertEqual(with_frz.w_sum.sel(gid=10, pop_pre='P1frz').item(), 2.5)
        self.assertEqual(with_frz.attrs['include_frz'], 1)

    def test_receptor_ratio_violation_is_informative(self):
        sim = _make_sim(include_frozen_conn=False)
        target = next(cell for cell in sim.net.cells if cell.gid == 10)
        target.conns[-3]['weight'] = 0.6

        with self.assertRaisesRegex(
                ValueError, r'P1 -> P2, AMPA.*pairs \(101, 10\).*\(103, 10\)'):
            calc_cell_inp_stats(sim)

    def test_receptor_ratio_check_can_be_disabled(self):
        sim = _make_sim(include_frozen_conn=False)
        target = next(cell for cell in sim.net.cells if cell.gid == 10)
        target.conns[-3]['weight'] = 0.6
        for conn in target.conns:
            conn.pop('synMech')

        with patch('utils.cell_inp_stats.CHECK_RECEPTOR_WEIGHT_RATIOS', 0):
            dataset = calc_cell_inp_stats(sim)

        self.assertEqual(dataset.w_sum.sel(gid=10, pop_pre='P1').item(), 2.5)
        ratio_meta = json.loads(dataset.attrs['receptor_ratio_validation_json'])
        self.assertEqual(ratio_meta, {
            'status': 'skipped',
            'reason': 'disabled',
        })

    def test_unresolved_numeric_source_fails(self):
        sim = _make_sim(include_frozen_conn=False)
        target = next(cell for cell in sim.net.cells if cell.gid == 10)
        target.conns.append(_conn(999, 0.1, 'AMPA'))

        with self.assertRaisesRegex(ValueError, r'unresolved preGid 999'):
            calc_cell_inp_stats(sim)

    def test_netcdf_round_trip_preserves_schema(self):
        dataset = calc_cell_inp_stats(_make_sim(), include_frz=True)
        with tempfile.TemporaryDirectory() as dirname:
            fpath = Path(dirname) / 'cell_inp_stats.nc'
            dataset.to_netcdf(fpath)
            loaded = xr.load_dataset(fpath)

        xr.testing.assert_allclose(loaded, dataset)
        self.assertEqual(loaded.pop_pre.values.tolist(), ['P1', 'P2', 'P1frz'])
        self.assertEqual(loaded.attrs['weight_semantics'], dataset.attrs['weight_semantics'])


class ReceptorRatioSummaryTests(unittest.TestCase):
    def test_cross_rank_merge_preserves_constant_ratios(self):
        parts = [{}, {}]
        update_ratio_summary(
            parts[0], ('P1', 'P2'), (1, 10), {'AMPA': 0.2, 'NMDA': 0.8}
        )
        update_ratio_summary(
            parts[1], ('P1', 'P2'), (2, 11), {'AMPA': 0.4, 'NMDA': 1.6}
        )

        summary = validate_ratio_summaries(
            merge_ratio_summaries(parts),
            tolerance=1e-8,
        )

        self.assertEqual(summary['status'], 'passed')
        self.assertAlmostEqual(summary['max_ratio_range'], 0)

    def test_cross_rank_merge_detects_missing_receptor(self):
        parts = [{}, {}]
        update_ratio_summary(
            parts[0], ('P1', 'P2'), (1, 10), {'AMPA': 0.2, 'NMDA': 0.8}
        )
        update_ratio_summary(
            parts[1], ('P1', 'P2'), (2, 11), {'AMPA': 1}
        )

        with self.assertRaisesRegex(ValueError, r'P1 -> P2, AMPA|P1 -> P2, NMDA'):
            validate_ratio_summaries(
                merge_ratio_summaries(parts),
                tolerance=1e-8,
            )


class CellInputBatchCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collector = _load_module(FPATH_COLLECTOR, 'cell_inp_collector_test')

    def test_collects_synthetic_job_datasets(self):
        with tempfile.TemporaryDirectory() as dirname:
            dirpath_exp = Path(dirname)
            dirpath_data = dirpath_exp / 'cell_inp_stats'
            dirpath_data.mkdir()
            dataset = calc_cell_inp_stats(_make_sim(), include_frz=False)
            for job, scale in enumerate((1, 2)):
                job_dataset = dataset.copy(deep=True)
                job_dataset['w_sum'] *= scale
                job_dataset.to_netcdf(
                    dirpath_data / f'cell_inp_stats_{job:05d}_seed.nc'
                )
            job_idx = xr.DataArray(
                [0, 1],
                dims=['seed_main'],
                coords={'seed_main': [1000, 1001]},
                name='job_id',
            )
            cache_path = dirpath_exp / 'combined.nc'

            with patch.object(
                    self.collector, '_get_job_idx_xr', return_value=job_idx):
                combined = self.collector.collect_cell_inp_stats_from_nc(
                    dirpath_exp,
                    cache_path=cache_path,
                )

            self.assertEqual(combined.sizes['seed_main'], 2)
            self.assertEqual(combined.sizes['gid'], 5)
            self.assertAlmostEqual(
                combined.w_sum.sel(
                    seed_main=1001, gid=10, pop_pre='P1'
                ).item(),
                7,
            )
            self.assertTrue(cache_path.is_file())


if __name__ == '__main__':
    unittest.main()
