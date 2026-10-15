import json
from pathlib import Path
import stat
from types import SimpleNamespace
import tempfile
import unittest

from hpc_batch_jobs import (
    HpcBatchJobError,
    append_child_record,
    build_child_record,
    decode_batch_parameters,
    parse_child_sbatch_result,
)


class HpcBatchJobTests(unittest.TestCase):
    def test_batchtools_coordinates_are_decoded(self):
        """Decode only the declared axes from BatchTools environment values. """
        environment = {
            'INTRUNTK0': 'stim_seed*=1301',
            'STRRUNTK1': 'mode*=short',
            'STRRUNTK2': 'simLabel*=ignored',
        }
        self.assertEqual(
            decode_batch_parameters(environment, ('stim_seed', 'mode')),
            {'stim_seed': 1301, 'mode': 'short'},
        )

    def test_sbatch_receipt_is_parsed_or_rejected(self):
        """Accept one parsable Slurm ID and reject scheduler failure. """
        completed = SimpleNamespace(returncode=0, stdout='117900;cluster\n', stderr='')
        self.assertEqual(parse_child_sbatch_result(completed), 117900)
        failed = SimpleNamespace(returncode=1, stdout='', stderr='denied')
        with self.assertRaises(HpcBatchJobError):
            parse_child_sbatch_result(failed)

    def test_child_records_append_once_as_jsonl(self):
        """Persist unique child identities and refuse a duplicate append. """
        record = build_child_record(
            'b2-child-discovery-001',
            'b2_child_discovery_00000',
            117900,
            {'stim_seed': 1301},
            'exp_results/batch/example/jobs',
            ['exp_results/batch/example/results/child.json'],
        )
        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / 'index.jsonl'
            append_child_record(fpath, record)
            stored = json.loads(fpath.read_text())
            mode = stat.S_IMODE(fpath.stat().st_mode)
            with self.assertRaises(HpcBatchJobError):
                append_child_record(fpath, record)
        self.assertEqual(stored['slurm_job_id'], 117900)
        self.assertEqual(stored['parameters'], {'stim_seed': 1301})
        self.assertEqual(mode, 0o600)

    def test_sixty_long_child_records_fit_the_shared_index_budget(self):
        """Keep the controller writer aligned with the protected one-MiB index readers. """
        root = 'exp_results/batch_fixture/' + 'long_result_name_' * 12
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'index.jsonl'
            for index in range(60):
                outputs = [f'{root}/{directory}/job_{index:05d}.{suffix}'
                           for directory, suffix in (('cfg', 'json'), ('results', 'json'),
                                                     ('rvec_xr', 'nc'), ('hvec_xr', 'nc'))]
                record = build_child_record('sixty-child-fixture', f'child_{index:05d}', 120000 + index,
                                            {'seed_main': 1000 + index % 5}, f'{root}/jobs', outputs)
                append_child_record(path, record)
            self.assertGreater(path.stat().st_size, 65536)
            self.assertEqual(len(path.read_text().splitlines()), 60)


if __name__ == '__main__':
    unittest.main()
