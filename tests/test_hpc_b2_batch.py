from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from hpc_job import (
    TEMPLATE_TOKENS,
    build_prepared_job_context,
    build_template_values,
    render_template,
)
from hpc_preflight import preflight_request, read_tracked_request
from load_module import load_module


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = 'hpc_jobs/requests/b2-child-discovery.json'
EXPECTED_RESULT_PATH = (
    'exp_results/batch_hpc_prototype/b2_child_discovery/'
    'exp_hpc_b2_child_discovery_nseed_2_t_0.5_1.0_'
    'rx_10000_100_wx_0.1_0.05_n_1'
)


def make_cfg():
    """Return the minimal base-config shape needed by the B2 experiment. """
    return SimpleNamespace(
        analysis={
            'plotRaster': {},
            'plotSpikeStats': {},
            'plotTraces': {},
        },
        seeds={'stim': 1},
    )


class HpcB2BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the tracked request and prototype modules once. """
        cls.request = read_tracked_request(REPO_ROOT, REQUEST_PATH)
        dirpath = REPO_ROOT / 'exp_configs/batch_hpc_prototype/b2_child_discovery'
        cls.exp_mod = load_module(dirpath / 'exp_cfg.py')
        cls.batch_mod = load_module(dirpath / 'batch_params.py')

    def test_request_resolves_two_children_and_one_result_root(self):
        """Bind the two-axis values to the shared scientific result path. """
        result = preflight_request(
            REPO_ROOT,
            self.request,
            cfg_factory=make_cfg,
            module_loader=load_module,
        )
        self.assertEqual(result['resolved_result_path'], EXPECTED_RESULT_PATH)
        self.assertEqual(result['planned_jobs'], 2)
        self.assertEqual(result['parameter_axis_sizes'], {'stim_seed': 2})

    def test_each_child_has_one_deterministic_completion_file(self):
        """Map both BatchTools labels to non-colliding result records. """
        outputs = []
        for index, seed in enumerate(self.batch_mod.get_batch_params()['stim_seed']):
            label = f'b2_child_discovery_{index:05d}'
            outputs.extend(
                self.exp_mod.get_batch_completion_files(
                    label,
                    {'stim_seed': seed},
                )
            )
        self.assertEqual(
            outputs,
            [
                'results/b2_child_discovery_00000.json',
                'results/b2_child_discovery_00001.json',
            ],
        )

    def test_batch_template_binds_the_prepared_run_id(self):
        """Pass the protected run identity into the child recorder. """
        checkout = Path('/ddn/niknovikov19/repo/A1_OUinp_codex')
        context = build_prepared_job_context(
            self.request,
            'b2-child-discovery-001',
            checkout,
            'a' * 40,
        )
        values = build_template_values(context, checkout)
        template = (REPO_ROOT / self.request['template_path']).read_text()
        rendered = render_template(
            template,
            values,
            TEMPLATE_TOKENS['batch'],
        )
        self.assertIn('--hpc-run-id b2-child-discovery-001', rendered)
        self.assertNotIn('@@', rendered)


if __name__ == '__main__':
    unittest.main()
