import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load_signal_helper():
    """Load the signaling helper without importing the simulation module. """
    source = Path('run_exp.py').read_text()
    start = source.index('def _ensure_batchtools_file_signal():')
    end = source.index('\n\ndef _get_workflow_job_id', start)
    namespace = {'os': os, 'Path': Path}
    exec(source[start:end], namespace)
    return namespace['_ensure_batchtools_file_signal']


class RunExpBatchSignalTests(unittest.TestCase):
    def setUp(self):
        """Load the standalone repository signaling helper. """
        self.ensure_signal = load_signal_helper()

    def test_signal_is_created_after_message(self):
        """Publish completion only after the BatchTools message exists. """
        with tempfile.TemporaryDirectory() as tmp:
            message = Path(tmp) / 'trial.out'
            signal = Path(tmp) / 'trial.sgl'
            message.write_text('{"done": 1}')
            env = {'MSGFILE': str(message), 'SGLFILE': str(signal)}
            with patch.dict(os.environ, env, clear=True):
                self.ensure_signal()
            self.assertTrue(signal.is_file())

    def test_missing_message_is_rejected(self):
        """Do not mark a trial complete without its result message. """
        with tempfile.TemporaryDirectory() as tmp:
            message = Path(tmp) / 'trial.out'
            signal = Path(tmp) / 'trial.sgl'
            env = {'MSGFILE': str(message), 'SGLFILE': str(signal)}
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(FileNotFoundError):
                    self.ensure_signal()
            self.assertFalse(signal.exists())

    def test_non_batch_execution_is_unchanged(self):
        """Ignore runs without the BatchTools file-signaling environment. """
        with patch.dict(os.environ, {}, clear=True):
            self.ensure_signal()


if __name__ == '__main__':
    unittest.main()
