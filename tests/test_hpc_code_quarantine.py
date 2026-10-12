from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, (REPO_ROOT / 'dev_scratch/hpc/helper_src/local').as_posix())


def load_helper():
    """Load the reviewed lethe helper without invoking its entry point. """
    fpath = REPO_ROOT / 'dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-code'
    loader = SourceFileLoader('hpc_lethe_code_recovery_candidate', fpath.as_posix())
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


HELPER = load_helper()


def load_local_helper():
    """Load the local command wrapper for forwarding checks. """
    fpath = REPO_ROOT / 'dev_scratch/hpc/helper_src/local/hpc-code-update'
    loader = SourceFileLoader('hpc_code_update_recovery_candidate', fpath.as_posix())
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


LOCAL = load_local_helper()


def git(*arguments):
    """Run one isolated fixture Git command. """
    completed = subprocess.run(
        ['/usr/bin/git', *map(str, arguments)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


class HpcCodeQuarantineTests(unittest.TestCase):
    def setUp(self):
        """Create an isolated developer, bare, and automation repository. """
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.developer = self.root / 'developer'
        self.remote = self.root / 'remote.git'
        self.checkout = self.root / 'automation'
        self.state = self.root / 'state'
        self.developer.mkdir()
        git('init', '-b', 'codex-hpc', self.developer)
        git('-C', self.developer, 'config', 'user.name', 'Fixture User')
        git('-C', self.developer, 'config', 'user.email', 'fixture@example.test')
        (self.developer / '.gitignore').write_text('')
        result = self.developer / 'exp_results' / 'fixture'
        result.mkdir(parents=True)
        (result / '.keep').write_text('tracked\n')
        git('-C', self.developer, 'add', '.gitignore', 'exp_results/fixture/.keep')
        git('-C', self.developer, 'commit', '-m', 'Initial fixture')
        git('init', '--bare', self.remote)
        git('-C', self.developer, 'remote', 'add', 'origin', self.remote)
        git('-C', self.developer, 'push', '-u', 'origin', 'codex-hpc')
        git('clone', '-b', 'codex-hpc', self.remote, self.checkout)
        self.before = git('-C', self.checkout, 'rev-parse', 'HEAD')
        self.state.mkdir(mode=0o700)
        (self.state / 'code-update.lock').write_text('')
        self.quarantine = self.state / 'code-quarantine'
        self.quarantine.mkdir(mode=0o700)
        self.config = {
            'schema_version': 1,
            'deployment_id': 'fixture',
            'git': {
                'path': '/usr/bin/git',
                'automation_checkout': self.checkout.as_posix(),
                'branch': 'codex-hpc',
                'remote_name': 'origin',
            },
            'state': {
                'root': self.state.as_posix(),
                'quarantine_root': self.quarantine.as_posix(),
            },
            'quarantine': {
                'generated_roots': ['exp_results'],
                'max_files': 128,
            },
        }
        HELPER.validate_config(self.config)

    def tearDown(self):
        """Discard all isolated Git repositories and state. """
        self.temp.cleanup()

    def push_target(self, ignore_line='exp_results/**/*.trace\n'):
        """Publish one exact fast-forward commit with a chosen ignore rule. """
        (self.developer / '.gitignore').write_text(ignore_line)
        git('-C', self.developer, 'add', '.gitignore')
        git('-C', self.developer, 'commit', '-m', 'Update ignore policy')
        git('-C', self.developer, 'push', 'origin', 'codex-hpc')
        return git('-C', self.developer, 'rev-parse', 'HEAD')

    def untracked_result(self):
        """Create one generated output omitted by the old ignore rules. """
        fpath = self.checkout / 'exp_results/fixture/generated.trace'
        fpath.write_text('scientific result\n')
        return fpath

    def test_restores_file_ignored_by_new_commit(self):
        """Move one exact output and restore it after a clean fast-forward. """
        target = self.push_target()
        fpath = self.untracked_result()
        result, exit_code = HELPER.update_checkout(self.config, target, True)
        self.assertEqual(exit_code, 0)
        self.assertEqual(result['quarantined_file_count'], 1)
        self.assertEqual(result['restored_file_count'], 1)
        self.assertEqual(fpath.read_text(), 'scientific result\n')
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), target)
        self.assertEqual(git('-C', self.checkout, 'status', '--porcelain'), '')
        self.assertFalse((self.quarantine / 'active.json').exists())
        manifest = json.loads(Path(result['quarantine_manifest']).read_text())
        self.assertEqual(manifest['status'], 'restored')

    def test_rejects_tracked_or_outside_changes(self):
        """Keep unrelated work in place and leave the checkout unchanged. """
        target = self.push_target()
        fpath = self.untracked_result()
        (self.checkout / 'unrelated.txt').write_text('keep\n')
        with self.assertRaises(HELPER.CodeFailure):
            HELPER.update_checkout(self.config, target, True)
        self.assertTrue(fpath.exists())
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), self.before)
        (self.checkout / 'unrelated.txt').unlink()
        (self.checkout / '.gitignore').write_text('manual edit\n')
        with self.assertRaises(HELPER.CodeFailure):
            HELPER.update_checkout(self.config, target, True)
        self.assertTrue(fpath.exists())
        self.assertFalse((self.quarantine / 'active.json').exists())

    def test_normal_update_still_rejects_dirty_checkout(self):
        """Keep the ordinary updater's clean-checkout requirement. """
        target = self.push_target()
        fpath = self.untracked_result()
        with self.assertRaises(HELPER.CodeFailure):
            HELPER.update_checkout(self.config, target)
        self.assertTrue(fpath.exists())
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), self.before)

    def test_wrong_remote_head_does_not_move_generated_file(self):
        """Reject a stale target before creating any quarantine record. """
        self.push_target()
        fpath = self.untracked_result()
        result, exit_code = HELPER.update_checkout(
            self.config, 'a' * 40, True,
        )
        self.assertEqual(exit_code, HELPER.EXIT_REJECTED)
        self.assertEqual(result['reason'], 'expected-commit-is-not-remote-branch-head')
        self.assertEqual(fpath.read_text(), 'scientific result\n')
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), self.before)
        self.assertFalse((self.quarantine / 'active.json').exists())

    def test_rejects_file_count_above_fixed_limit(self):
        """Refuse a too-large dirty set without changing any file. """
        target = self.push_target()
        self.config['quarantine']['max_files'] = 1
        first = self.untracked_result()
        second = self.checkout / 'exp_results/fixture/second.trace'
        second.write_text('second result\n')
        with self.assertRaises(HELPER.CodeFailure):
            HELPER.update_checkout(self.config, target, True)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertFalse((self.quarantine / 'active.json').exists())

    def test_failed_merge_restores_original_file(self):
        """Restore the original untracked path if the merge fails. """
        target = self.push_target()
        fpath = self.untracked_result()
        original_run_git = HELPER.run_git

        def fail_merge(config, arguments, **kwargs):
            """Fail only the fixture fast-forward after quarantine. """
            if arguments[0] == 'merge':
                raise HELPER.CodeFailure('Fixture merge failure')
            return original_run_git(config, arguments, **kwargs)

        with patch.object(HELPER, 'run_git', side_effect=fail_merge):
            with self.assertRaises(HELPER.CodeFailure):
                HELPER.update_checkout(self.config, target, True)
        self.assertEqual(fpath.read_text(), 'scientific result\n')
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), self.before)
        self.assertFalse((self.quarantine / 'active.json').exists())

    def test_retains_file_not_ignored_by_new_commit(self):
        """Preserve an unignored file in quarantine for explicit review. """
        target = self.push_target('other-output/\n')
        fpath = self.untracked_result()
        result, exit_code = HELPER.update_checkout(self.config, target, True)
        self.assertEqual(exit_code, HELPER.EXIT_FAILED)
        self.assertEqual(result['reason'], 'quarantine-needs-review')
        self.assertEqual(result['pending_file_count'], 1)
        self.assertFalse(fpath.exists())
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), target)
        self.assertTrue((self.quarantine / 'active.json').exists())
        manifest = json.loads(Path(result['quarantine_manifest']).read_text())
        saved = self.quarantine / manifest['operation_id'] / 'items'
        self.assertEqual(
            (saved / 'exp_results/fixture/generated.trace').read_text(),
            'scientific result\n',
        )

    def test_refuses_symlinked_result(self):
        """Reject a symlink before moving anything or updating Git. """
        target = self.push_target()
        fpath = self.checkout / 'exp_results/fixture/generated.trace'
        fpath.symlink_to(self.developer / '.gitignore')
        with self.assertRaises(HELPER.CodeFailure):
            HELPER.update_checkout(self.config, target, True)
        self.assertTrue(fpath.is_symlink())
        self.assertEqual(git('-C', self.checkout, 'rev-parse', 'HEAD'), self.before)

    def test_local_flag_forwards_only_the_fixed_remote_operation(self):
        """Forward the recovery flag without accepting remote paths. """
        target = 'a' * 40
        args = LOCAL.build_parser().parse_args([
            '--quarantine-generated', target,
        ])
        self.assertTrue(args.quarantine_generated)
        command = LOCAL.build_ssh_command({
            'remote_helpers': {'lethe_dir': '/fixed/lethe'},
            'ssh': {'connect_timeout_sec': 15, 'lethe_host_alias': 'lethe'},
        }, target, args.quarantine_generated)
        self.assertEqual(
            command[-1],
            f'/fixed/lethe/hpc-lethe-code update --quarantine-generated {target}',
        )


if __name__ == '__main__':
    unittest.main()
