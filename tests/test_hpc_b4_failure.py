from pathlib import Path
from types import SimpleNamespace
import unittest

from hpc_preflight import preflight_request, read_tracked_request
from load_module import load_module


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = 'hpc_jobs/requests/b4-controlled-failure.json'
EXPECTED_RESULT_PATH = (
    'exp_results/batch_hpc_prototype/b4_controlled_failure/'
    'exp_hpc_b4_controlled_failure_nseed_2_t_0.5_1.0_'
    'rx_10000_100_wx_0.1_0.05_n_1_attempt_1'
)


def make_cfg():
    """Return the minimal base-config shape needed by the B4 experiment. """
    return SimpleNamespace(
        analysis={
            'plotRaster': {},
            'plotSpikeStats': {},
            'plotTraces': {},
        },
        seeds={'stim': 1},
    )


class HpcB4FailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the tracked request and controlled-failure modules once. """
        cls.request = read_tracked_request(REPO_ROOT, REQUEST_PATH)
        dirpath = REPO_ROOT / 'exp_configs/batch_hpc_prototype/b4_controlled_failure'
        cls.exp_mod = load_module(dirpath / 'exp_cfg.py')
        cls.batch_mod = load_module(dirpath / 'batch_params.py')

    def test_request_resolves_two_children_and_one_result_root(self):
        """Bind both reviewed coordinates to one fresh result directory. """
        result = preflight_request(
            REPO_ROOT,
            self.request,
            cfg_factory=make_cfg,
            module_loader=load_module,
        )
        self.assertEqual(result['resolved_result_path'], EXPECTED_RESULT_PATH)
        self.assertEqual(result['planned_jobs'], 2)
        self.assertEqual(result['parameter_axis_sizes'], {'stim_seed': 2})

    def test_failure_coordinate_is_exact(self):
        """Fail only the reviewed seed after the short simulation. """
        seeds = self.batch_mod.get_batch_params()['stim_seed']
        self.assertEqual(seeds, [1501, 1502])
        self.assertEqual(self.exp_mod.FAIL_STIM_SEED, 1502)
        sim = SimpleNamespace(cfg=SimpleNamespace(stim_seed=1502))
        with self.assertRaisesRegex(RuntimeError, 'stim_seed 1502'):
            self.exp_mod.post_run(sim)


if __name__ == '__main__':
    unittest.main()
