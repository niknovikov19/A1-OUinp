import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from hpc_preflight import preflight_request, read_tracked_request
from hpc_job import (
    TEMPLATE_TOKENS,
    build_prepared_job_context,
    build_template_values,
    render_template,
)
from load_module import load_module


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = 'hpc_jobs/requests/b1-single-smoke.json'
EXPECTED_RESULT_PATH = (
    'exp_results/single_hpc_prototype/b1_smoke/'
    'exp_hpc_b1_smoke_seed_1201_t_0.5_1.0_rx_10000_100_wx_0.1_0.05_n_1'
)
EXPECTED_SCRIPT_SHA256 = (
    '1988abfe912bc5f4ba517a7245491ff2e583b721ced7e423575ed04432d9441d'
)


def make_cfg():
    """Return the minimal base-config shape needed by the B1 experiment."""
    return SimpleNamespace(
        analysis={
            'plotRaster': {},
            'plotSpikeStats': {},
            'plotTraces': {},
        },
        seeds={'stim': 1},
    )


class FakeAnalysis:
    """Return deterministic rate data without running a simulation."""

    def popAvgRates(self, tranges, show):
        """Return one fixed population rate after checking the time window."""
        self.tranges = tranges
        self.show = show
        return {'IT2': 4}


class HpcB1SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the tracked request and experiment module once."""
        cls.request = read_tracked_request(REPO_ROOT, REQUEST_PATH)
        cls.exp_mod = load_module(
            REPO_ROOT /
            'exp_configs/single_hpc_prototype/b1_smoke/exp_cfg.py'
        )

    def test_request_resolves_from_the_experiment_configuration(self):
        """Derive the declared scientific result path from exp_cfg.py."""
        result = preflight_request(
            REPO_ROOT,
            self.request,
            cfg_factory=make_cfg,
            module_loader=load_module,
        )
        self.assertEqual(result['resolved_result_path'], EXPECTED_RESULT_PATH)
        self.assertEqual(result['planned_jobs'], 1)

    def test_configuration_is_one_short_unconnected_cell(self):
        """Keep the B1 simulation deliberately small and reproducible."""
        cfg = make_cfg()
        self.exp_mod.apply_exp_cfg(cfg)
        self.assertEqual(cfg.duration, 1000)
        self.assertEqual(cfg.t0_calc, 500)
        self.assertEqual(cfg.pops_active, ['IT2'])
        self.assertEqual(cfg.singleCellPops, 1)
        self.assertEqual(cfg.addConn, 0)
        self.assertEqual(cfg.addSubConn, 0)
        self.assertEqual(cfg.seeds['stim'], 1201)

    def test_post_run_writes_the_declared_completion_file(self):
        """Write the completion record at the request-declared path."""
        cfg = make_cfg()
        self.exp_mod.apply_exp_cfg(cfg)
        analysis = FakeAnalysis()
        with tempfile.TemporaryDirectory() as tmp:
            cfg.saveFolder = tmp
            cfg.simLabel = 'b1-single-smoke'
            generic = Path(tmp) / f'{cfg.simLabel}_result.json'
            generic.write_text('{}\n')
            outputs = self.exp_mod.post_run(
                SimpleNamespace(cfg=cfg, analysis=analysis)
            )
            result_dir = Path(tmp) / self.exp_mod.gen_exp_name_sub(cfg)
            completion = result_dir / self.request['completion_files'][0]
            result = json.loads(completion.read_text())
            generic_moved = (result_dir / generic.name).exists()

        self.assertEqual(outputs, self.request['completion_files'])
        self.assertEqual(result['rates_hz'], {'IT2': 4})
        self.assertEqual(analysis.tranges, [500, 1000])
        self.assertTrue(generic_moved)

    def test_reviewed_template_renders_to_the_expected_script_hash(self):
        """Bind the B1 request to one reviewed prepared-script rendering."""
        checkout = Path('/ddn/niknovikov19/repo/A1_OUinp_codex')
        context = build_prepared_job_context(
            self.request,
            'b1-single-smoke-001',
            checkout,
            'a' * 40,
        )
        values = build_template_values(context, checkout)
        template = (REPO_ROOT / self.request['template_path']).read_text()
        rendered = render_template(
            template,
            values,
            TEMPLATE_TOKENS['single'],
        )
        digest = hashlib.sha256(rendered.encode()).hexdigest()
        self.assertEqual(digest, EXPECTED_SCRIPT_SHA256)


if __name__ == '__main__':
    unittest.main()
