from pathlib import Path
from types import SimpleNamespace
import unittest

from hpc_preflight import preflight_request, read_tracked_request
from load_module import load_module


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = 'hpc_jobs/requests/b3-tiny-batch.json'
EXPECTED_RESULT_PATH = (
    'exp_results/batch_hpc_prototype/b3_tiny_batch/'
    'exp_hpc_b3_tiny_batch_nseed_4_t_0.5_1.0_'
    'rx_10000_100_wx_0.1_0.05_n_1_attempt_3'
)


def make_cfg():
    """Return the minimal base-config shape needed by the B3 experiment. """
    return SimpleNamespace(
        analysis={
            'plotRaster': {},
            'plotSpikeStats': {},
            'plotTraces': {},
        },
        seeds={'stim': 1},
    )


class HpcB3BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the tracked request and prototype modules once. """
        cls.request = read_tracked_request(REPO_ROOT, REQUEST_PATH)
        dirpath = REPO_ROOT / 'exp_configs/batch_hpc_prototype/b3_tiny_batch'
        cls.exp_mod = load_module(dirpath / 'exp_cfg.py')
        cls.batch_mod = load_module(dirpath / 'batch_params.py')

    def test_request_resolves_four_children_and_one_result_root(self):
        """Bind four seed values to one descriptive scientific result. """
        result = preflight_request(
            REPO_ROOT,
            self.request,
            cfg_factory=make_cfg,
            module_loader=load_module,
        )
        self.assertEqual(result['resolved_result_path'], EXPECTED_RESULT_PATH)
        self.assertEqual(result['planned_jobs'], 4)
        self.assertEqual(result['parameter_axis_sizes'], {'stim_seed': 4})

    def test_request_limits_concurrency_to_two(self):
        """Run no more than two of the four simulation jobs concurrently. """
        self.assertEqual(self.request['max_simulation_jobs'], 4)
        self.assertEqual(self.request['max_concurrent_simulation_jobs'], 2)
        self.assertEqual(self.request['simulation_job_resources']['cores'], 1)
        self.assertEqual(self.request['simulation_job_resources']['memory_gb'], 2)

    def test_each_child_has_one_deterministic_completion_file(self):
        """Map all four BatchTools labels to distinct result records. """
        outputs = []
        seeds = self.batch_mod.get_batch_params()['stim_seed']
        for index, seed in enumerate(seeds):
            label = f'b3_tiny_batch_{index:05d}'
            outputs.extend(
                self.exp_mod.get_batch_completion_files(
                    label,
                    {'stim_seed': seed},
                )
            )
        expected = [
            f'results/b3_tiny_batch_{index:05d}.json'
            for index in range(4)
        ]
        self.assertEqual(outputs, expected)


if __name__ == '__main__':
    unittest.main()
