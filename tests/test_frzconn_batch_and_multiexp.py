import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import xarray as xr

from utils.batch import collect_cell_rates_from_pkl_multiexp as multiexp


DIR_REPO = Path(__file__).resolve().parents[1]
FPATH_BATCH_PARAMS = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1'
    / 'net_newsec_var_seed_frzconns' / 'batch_params.py'
)
FPATH_CELL_INP_COLLECTOR = (
    FPATH_BATCH_PARAMS.parent / 'collect_batch_results.py'
)


def _load_frzconn_batch_params():
    """Load the new experiment batch module without package side effects. """
    spec = importlib.util.spec_from_file_location(
        'test_frzconn_batch_params', FPATH_BATCH_PARAMS
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cell_inp_collector():
    """Load the frozen-connection cell-input batch collector. """
    spec = importlib.util.spec_from_file_location(
        'test_frzconn_cell_inp_collector', FPATH_CELL_INP_COLLECTOR
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenConnectionBatchTests(unittest.TestCase):
    def test_batch_axes_and_post_update_select_connection_group(self):
        """Resolve all top-10 conditions and seeds without launching simulations. """
        batch = _load_frzconn_batch_params()
        params = batch.get_batch_params()

        # Pin the requested interventions independently of their implementation
        expected = {
            'none': [],
            'thal_irem': [(p, 'IREM') for p in
                          ['TC', 'HTC', 'TCM', 'TI', 'TIM', 'IRE', 'IREM']],
            'irem_ire_ti': [('IREM', 'IRE'), ('IREM', 'TI')],
            'irem_tim': [('IREM', 'TIM')],
            'ti_tc': [('TI', 'TC'), ('TI', 'HTC')],
            'tim_tc': [('TIM', 'TC'), ('TIM', 'HTC')],
            'irem_ire': [('IREM', 'IRE')],
            'irem_ti': [('IREM', 'TI')],
            'irem_core': [('IREM', p) for p in ['TC', 'HTC', 'TI', 'IRE']],
            'ti_tim_tc': [('TI', 'TC'), ('TI', 'HTC'),
                          ('TIM', 'TC'), ('TIM', 'HTC')],
        }
        self.assertEqual(params['frz_conn_group'], list(expected))
        self.assertEqual(params['seed_main'], list(range(1000, 1015)))
        self.assertEqual(batch.N_SEEDS, 15)

        cfg = SimpleNamespace(
            seed_main=None,
            frz_conn_group=None,
            seeds={'stim': None, 'conn': None},
            subnet_params={'global_seed': None, 'conns_frozen': [('stale', 'pair')]},
            bkg_spike_inputs={
                pop: {'exc': {'seed': None}, 'inh': {'seed': None}}
                for pop in batch.THAL_POPS
            },
        )

        # Reuse one cfg to catch stale frozen pairs and inconsistent seed mapping
        for seed in params['seed_main']:
            for name, conns in expected.items():
                with self.subTest(seed=seed, group=name):
                    cfg.seed_main = seed
                    cfg.frz_conn_group = name
                    batch.post_update(cfg)
                    self.assertEqual(cfg.subnet_params['conns_frozen'], conns)
                    self.assertEqual(cfg.seeds, {'stim': seed, 'conn': seed * 2})
                    self.assertEqual(cfg.subnet_params['global_seed'], seed * 3)
                    self.assertEqual(cfg.batch_par_info['n_seeds'], 15)
                    self.assertEqual(cfg.batch_par_info['frz_conn_groups'], list(expected))
                    self.assertEqual(
                        cfg.batch_par_info['batch_params'],
                        ['seed_main', 'frz_conn_group'],
                    )
                    for n, pop in enumerate(batch.THAL_POPS):
                        inputs = cfg.bkg_spike_inputs[pop]
                        self.assertEqual(inputs['exc']['seed'], seed + 10000 + n)
                        self.assertEqual(inputs['inh']['seed'], seed + 20000 + n)


class FrozenConnectionCellInputCollectorTests(unittest.TestCase):
    def test_collects_seed_and_frozen_group_axes(self):
        """Stack per-job input statistics over both batch dimensions. """
        collector = _load_cell_inp_collector()
        with tempfile.TemporaryDirectory() as dirname:
            dirpath_exp = Path(dirname)
            dirpath_cfg = dirpath_exp / 'cfg'
            dirpath_data = dirpath_exp / 'cell_inp_stats'
            dirpath_cfg.mkdir()
            dirpath_data.mkdir()

            # Create a complete two-seed by two-group synthetic batch
            job = 0
            for seed in (1000, 1001):
                for group in ('irem_ire', 'matx_ti'):
                    cfg = {
                        'simConfig': {
                            'seed_main': seed,
                            'frz_conn_group': group,
                        },
                    }
                    cfg_path = dirpath_cfg / f'cfg_{job:05d}_test.json'
                    cfg_path.write_text(json.dumps(cfg))
                    dataset = xr.Dataset(
                        {'n_pre': (('gid', 'pop_pre'), [[job]])},
                        coords={
                            'gid': [10],
                            'pop_pre': ['P1'],
                            'pop_post': ('gid', ['P2']),
                        },
                    )
                    dataset.to_netcdf(
                        dirpath_data / f'cell_inp_stats_{job:05d}_test.nc'
                    )
                    job += 1

            combined = collector.collect_cell_inp_stats_from_nc(dirpath_exp)

            self.assertEqual(combined.sizes['seed_main'], 2)
            self.assertEqual(combined.sizes['frz_conn_group'], 2)
            self.assertEqual(
                combined.n_pre.sel(
                    seed_main=1001,
                    frz_conn_group='matx_ti',
                    gid=10,
                    pop_pre='P1',
                ).item(),
                3,
            )


class MultiExperimentCollectorTests(unittest.TestCase):
    def test_routes_each_experiment_to_its_own_output_subfolder(self):
        """Route experiments under matching output subfolders. """
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            config_path = root / 'experiments.json'
            config_path.write_text(json.dumps({
                'dirpath_root': 'results',
                'experiments': ['exp_a', 'nested/exp_b'],
            }))
            output_path = root / 'output'

            with patch.object(
                    multiexp, 'collect_cell_rates_from_pkl',
                    side_effect=['data_a', 'data_b']) as collector:
                output_paths = multiexp.collect_cell_rates_from_pkl_multiexp(
                    config_path,
                    dirpath_out=output_path,
                    t_limits=(1, 2),
                    pop_names=['P1'],
                    job_ids=[3],
                )

            self.assertEqual(
                output_paths,
                {
                    'exp_a': output_path / 'exp_a/cell_rates_xr_combined.nc',
                    'nested/exp_b': (
                        output_path / 'nested/exp_b/cell_rates_xr_combined.nc'
                    ),
                },
            )
            calls = collector.call_args_list
            self.assertEqual(calls[0].kwargs['dirpath_exp'], root / 'results/exp_a')
            self.assertEqual(calls[0].kwargs['dirpath_out'], output_path / 'exp_a')
            self.assertEqual(
                calls[1].kwargs['dirpath_out'], output_path / 'nested/exp_b'
            )
            self.assertEqual(calls[0].kwargs['t_limits'], (1, 2))
            self.assertEqual(calls[0].kwargs['pop_names'], ['P1'])
            self.assertEqual(calls[0].kwargs['job_ids'], [3])

    def test_none_output_keeps_single_experiment_behavior(self):
        """Pass None through so the original output behavior is retained. """
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            config_path = root / 'experiments.json'
            config_path.write_text(json.dumps({
                'dirpath_root': str(root / 'results'),
                'experiments': ['exp_a'],
            }))

            with patch.object(
                    multiexp, 'collect_cell_rates_from_pkl',
                    return_value='data') as collector:
                multiexp.collect_cell_rates_from_pkl_multiexp(config_path)

            self.assertIsNone(collector.call_args.kwargs['dirpath_out'])


if __name__ == '__main__':
    unittest.main()
