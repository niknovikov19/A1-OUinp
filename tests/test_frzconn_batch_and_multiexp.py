import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from utils.batch import collect_cell_rates_from_pkl_multiexp as multiexp


DIR_REPO = Path(__file__).resolve().parents[1]
FPATH_BATCH_PARAMS = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1'
    / 'net_newsec_var_seed_frzconns' / 'batch_params.py'
)


def _load_frzconn_batch_params():
    """Load the new experiment batch module without package side effects. """
    spec = importlib.util.spec_from_file_location(
        'test_frzconn_batch_params', FPATH_BATCH_PARAMS
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenConnectionBatchTests(unittest.TestCase):
    def test_batch_axes_and_post_update_select_connection_group(self):
        """Apply the selected frozen group after batch parameter updates. """
        batch = _load_frzconn_batch_params()
        params = batch.get_batch_params()
        self.assertEqual(params['frz_conn_group'], ['irem_ire', 'matx_ti'])
        self.assertEqual(len(params['seed_main']), batch.N_SEEDS)

        cfg = SimpleNamespace(
            seed_main=1002,
            frz_conn_group='matx_ti',
            seeds={'stim': None, 'conn': None},
            subnet_params={'global_seed': None, 'conns_frozen': []},
            bkg_spike_inputs={
                'P1': {'exc': {'seed': None}, 'inh': {'seed': None}},
            },
        )
        batch.post_update(cfg)

        self.assertEqual(
            cfg.subnet_params['conns_frozen'], batch.CONNS_MATX_TI
        )
        self.assertEqual(cfg.seeds, {'stim': 1002, 'conn': 2004})
        self.assertEqual(cfg.subnet_params['global_seed'], 3006)
        self.assertEqual(
            cfg.batch_par_info['batch_params'],
            ['seed_main', 'frz_conn_group'],
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
