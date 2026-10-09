from pathlib import Path
import unittest

from automation_run import (
    AutomationValidationError,
    build_run_context,
    calculate_child_jobs,
    get_run_layout,
    hash_data,
    render_launcher,
    validate_experiment_id,
    validate_git_commit,
    validate_repo_path,
    validate_resources,
    validate_run_id,
)


class AutomationIdentifierTests(unittest.TestCase):
    def test_valid_identifiers_are_retained(self):
        self.assertEqual(validate_run_id('b1-single_001'), 'b1-single_001')
        self.assertEqual(
            validate_experiment_id('single_hpc_prototype/b1_smoke'),
            'single_hpc_prototype/b1_smoke',
        )
        self.assertEqual(
            validate_repo_path('hpc_launchers/submit_single.sh'),
            'hpc_launchers/submit_single.sh',
        )
        self.assertEqual(validate_git_commit('a' * 40), 'a' * 40)

    def test_unsafe_identifiers_are_rejected(self):
        values = ('', '.', '..', '../run', 'group/experiment', 'run*', 'run id')
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(AutomationValidationError):
                    validate_run_id(value)

    def test_unsafe_experiments_and_paths_are_rejected(self):
        experiments = ('', '.', '..', '../exp', 'group//exp', 'group\\exp', 'x*')
        paths = ('', '/absolute', '../file', 'dir//file', 'dir/./file', 'x*')
        for value in experiments:
            with self.subTest(experiment=value):
                with self.assertRaises(AutomationValidationError):
                    validate_experiment_id(value)
        for value in paths:
            with self.subTest(path=value):
                with self.assertRaises(AutomationValidationError):
                    validate_repo_path(value)


class AutomationResourceTests(unittest.TestCase):
    def setUp(self):
        self.resources = {
            'partition': 'cpu.q',
            'nodes': 1,
            'cores': 2,
            'memory_gb': 4,
            'wall_time_min': 10,
        }

    def test_resources_are_normalized(self):
        self.assertEqual(
            validate_resources(self.resources, 'controller'),
            self.resources,
        )

    def test_resources_reject_unknown_and_nonpositive_values(self):
        unknown = {**self.resources, 'account': 'extra'}
        with self.assertRaises(AutomationValidationError):
            validate_resources(unknown, 'controller')
        for value in (0, -1, True, 1.5, '1'):
            changed = {**self.resources, 'cores': value}
            with self.subTest(value=value):
                with self.assertRaises(AutomationValidationError):
                    validate_resources(changed, 'child')

    def test_single_and_batch_job_counts_are_separate(self):
        self.assertEqual(calculate_child_jobs('single', {}), 1)
        axes = {'seed': [1, 2], 'weight': [0.1, 0.2, 0.3]}
        self.assertEqual(calculate_child_jobs('batch', axes), 6)
        with self.assertRaises(AutomationValidationError):
            calculate_child_jobs('single', axes)
        with self.assertRaises(AutomationValidationError):
            calculate_child_jobs('batch', {})
        with self.assertRaises(AutomationValidationError):
            calculate_child_jobs('batch', axes, maximum=5)

    def test_duplicate_axis_values_are_rejected(self):
        with self.assertRaises(AutomationValidationError):
            calculate_child_jobs('batch', {'seed': [1, 1]})


class AutomationLayoutTests(unittest.TestCase):
    def test_layout_is_unique_and_beneath_automation_root(self):
        layout = get_run_layout(
            Path('/repo/A1_OUinp'),
            'single_hpc_prototype/b1_smoke',
            'b1-single-001',
        )
        run_dir = Path(
            '/repo/A1_OUinp/exp_results/automation/'
            'single_hpc_prototype/b1_smoke/b1-single-001'
        )
        self.assertEqual(layout['run_dir'], run_dir)
        self.assertEqual(
            layout['submit_script'],
            run_dir / 'controller' / 'submit.sh',
        )
        self.assertEqual(layout['job_index'], run_dir / 'jobs' / 'index.jsonl')

    def test_layout_requires_an_absolute_repository_root(self):
        with self.assertRaises(AutomationValidationError):
            get_run_layout('relative/repo', 'group/experiment', 'run')


class AutomationContextTests(unittest.TestCase):
    def setUp(self):
        self.resources = {
            'partition': 'cpu.q',
            'nodes': 1,
            'cores': 2,
            'memory_gb': 4,
            'wall_time_min': 10,
        }
        self.request = {
            'schema_version': 2,
            'request_id': 'b1-single',
            'run_type': 'single',
            'experiment': 'single_hpc_prototype/b1_smoke',
            'expected_commit': 'a' * 40,
            'launcher_path': 'hpc_launchers/submit_single.sh',
            'controller_resources': self.resources,
            'child_resources': None,
            'parameter_axes': {},
            'max_concurrent_jobs': 1,
        }

    def test_single_context_is_canonical_and_uses_unique_run_id(self):
        context = build_run_context(
            self.request,
            'b1-single-001',
            Path('/repo/A1_OUinp'),
            max_child_jobs=10,
        )
        self.assertEqual(context['request_id'], 'b1-single')
        self.assertEqual(context['run_id'], 'b1-single-001')
        self.assertEqual(context['calculated_child_jobs'], 1)
        self.assertEqual(
            context['result_dir'],
            '/repo/A1_OUinp/exp_results/automation/'
            'single_hpc_prototype/b1_smoke/b1-single-001',
        )

    def test_batch_context_requires_child_resources_and_obeys_limits(self):
        request = {
            **self.request,
            'run_type': 'batch',
            'child_resources': self.resources,
            'parameter_axes': {'seed': [1, 2], 'weight': [0.1, 0.2]},
            'max_concurrent_jobs': 2,
        }
        context = build_run_context(
            request,
            'b1-batch-001',
            Path('/repo/A1_OUinp'),
            max_child_jobs=4,
        )
        self.assertEqual(context['calculated_child_jobs'], 4)
        with self.assertRaises(AutomationValidationError):
            build_run_context(
                request,
                'b1-batch-002',
                Path('/repo/A1_OUinp'),
                max_child_jobs=3,
            )

    def test_context_rejects_cross_mode_and_unknown_fields(self):
        invalid = {**self.request, 'child_resources': self.resources}
        with self.assertRaises(AutomationValidationError):
            build_run_context(invalid, 'run-1', Path('/repo'), 10)
        invalid = {**self.request, 'unexpected': True}
        with self.assertRaises(AutomationValidationError):
            build_run_context(invalid, 'run-2', Path('/repo'), 10)

    def test_context_rejects_nonfinite_axis_values(self):
        request = {
            **self.request,
            'run_type': 'batch',
            'child_resources': self.resources,
            'parameter_axes': {'weight': [float('nan')]},
        }
        with self.assertRaises(AutomationValidationError):
            build_run_context(request, 'run-1', Path('/repo'), 10)


class AutomationRenderTests(unittest.TestCase):
    def setUp(self):
        self.template = (
            '#!/bin/bash\n'
            '#SBATCH --job-name=@@JOB_NAME@@\n'
            '#SBATCH --cpus-per-task=@@CORES@@\n'
            'cd @@CHECKOUT@@\n'
        )
        self.tokens = {'JOB_NAME', 'CORES', 'CHECKOUT'}
        self.values = {
            'JOB_NAME': 'a1-b1-single',
            'CORES': '2',
            'CHECKOUT': '/ddn/user/repo/A1_OUinp_codex',
        }

    def test_launcher_is_rendered_exactly(self):
        rendered = render_launcher(self.template, self.values, self.tokens)
        self.assertIn('#SBATCH --job-name=a1-b1-single', rendered)
        self.assertIn('#SBATCH --cpus-per-task=2', rendered)
        self.assertIn('cd /ddn/user/repo/A1_OUinp_codex', rendered)
        self.assertNotIn('@@', rendered)

    def test_launcher_rejects_missing_unknown_and_duplicate_tokens(self):
        cases = (
            self.template.replace('@@CORES@@', '2'),
            self.template + 'echo @@UNKNOWN@@\n',
            self.template + 'echo @@CORES@@\n',
        )
        for template in cases:
            with self.subTest(template=template):
                with self.assertRaises(AutomationValidationError):
                    render_launcher(template, self.values, self.tokens)

    def test_launcher_rejects_shell_active_values(self):
        invalid = ('two words', 'x;touch', 'x\n#SBATCH --nodes=2', '$(id)', '')
        for value in invalid:
            values = {**self.values, 'JOB_NAME': value}
            with self.subTest(value=value):
                with self.assertRaises(AutomationValidationError):
                    render_launcher(self.template, values, self.tokens)

    def test_hashing_is_order_independent(self):
        self.assertEqual(hash_data({'a': 1, 'b': 2}), hash_data({'b': 2, 'a': 1}))


if __name__ == '__main__':
    unittest.main()
