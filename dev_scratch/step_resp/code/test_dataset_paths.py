from pathlib import Path
import tempfile
import unittest

from dataset_paths import DATASET_RENAMES, resolve_dataset_path


class DatasetPathTests(unittest.TestCase):
    def test_all_moves_support_relative_and_absolute_manifest_paths(self):
        """Resolve every recorded dataset move including archived preliminary data. """
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            for old, new in DATASET_RENAMES.items():
                relative = Path('dev_scratch/step_resp/data') / old / 'analysis/manifest.json'
                expected = repo / 'dev_scratch/step_resp/data' / new / 'analysis/manifest.json'
                self.assertEqual(resolve_dataset_path(relative, repo), expected)
                self.assertEqual(resolve_dataset_path(repo / relative, repo), expected)

    def test_existing_sources_are_not_redirected(self):
        """Preserve an existing historical path so checksum rejection cannot be bypassed. """
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            source = repo / 'dev_scratch/step_resp/data/l2_sym_slow_pilot/q.nc'
            source.parent.mkdir(parents=True)
            source.touch()
            self.assertEqual(resolve_dataset_path(source, repo), source)

    def test_other_roots_and_similar_names_are_untouched(self):
        """Do not rewrite remote paths or similarly named unrelated datasets. """
        repo = Path('/example/repo')
        for source in ('/ddn/repo/data/l2_sym_slow_pilot/q.nc',
                       '/example/repo/dev_scratch/step_resp/data/l2_sym_slow_pilot_extra/q.nc'):
            self.assertEqual(resolve_dataset_path(source, repo), Path(source))


if __name__ == '__main__':
    unittest.main()
