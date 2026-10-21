import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_hpc_job_control import load_script_module


PROMOTION = load_script_module(
    'completion_recovery_promotion',
    'dev_scratch/hpc/helper_src/promotion/promote_completion_recovery.py',
)


class CompletionPromotionTests(unittest.TestCase):
    def test_destinations_are_fixed_and_do_not_include_run_records(self):
        """Limit this installation to two local and six remote code files. """
        local = PROMOTION.targets('local')
        remote = PROMOTION.targets('lethe')
        self.assertEqual(len(local), 2)
        self.assertEqual(len(remote), 6)
        self.assertTrue(all(path.parent == Path('/opt/a1-hpc/bin') for _, path, _ in local))
        self.assertTrue(all('helpers' in path.parts for _, path, _ in remote))
        self.assertEqual({mode for _, _, mode in local + remote}, {0o444, 0o555})

    def test_unreviewed_predecessors_and_symlinks_are_rejected(self):
        """Prevent replacement of unknown installed code or linked destinations. """
        hashes = {name: hashlib.sha256(payload).hexdigest() for name, payload in (
            ('old', b'old'), ('new', b'new'),
        )}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'installed.py'
            for payload in (b'old', b'new'):
                path.write_bytes(payload)
                self.assertEqual(PROMOTION.validate_target(path, hashes), payload)
            path.write_bytes(b'unreviewed')
            with self.assertRaises(ValueError):
                PROMOTION.validate_target(path, hashes)
            link = path.with_name('linked.py')
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                PROMOTION.validate_target(link, hashes)

    def test_manifest_matches_all_reviewed_sources(self):
        """Pin the exact replacement bytes for every installation destination. """
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / PROMOTION.MANIFEST).read_text())
        names = {name for site in ('local', 'lethe') for name, _, _ in PROMOTION.targets(site)}
        self.assertEqual(set(manifest), names)
        for name in names:
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), manifest[name]['new'])


if __name__ == '__main__':
    unittest.main()
