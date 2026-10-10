from pathlib import Path
import tempfile
import unittest

from hpc_job import (
    HpcJobValidationError,
    TEMPLATE_TOKENS,
    build_prepared_job_context,
    build_template_values,
    calculate_parameter_grid_size,
    format_slurm_time,
    get_batchtools_resource_config,
    get_job_run_layout,
    hash_data,
    render_template,
    validate_git_commit,
    validate_repo_path,
    validate_request,
    validate_resources,
    validate_result_destination,
    validate_run_id,
    validate_target,
)


def make_resources():
    """Return one small valid Slurm resource mapping."""
    return {
        'partition': 'cpu.q',
        'nodes': 1,
        'cores': 2,
        'memory_gb': 4,
        'wall_time_min': 10,
    }


def make_single_request():
    """Return one valid single-simulation request."""
    return {
        'schema_version': 1,
        'request_id': 'b1-single',
        'job_kind': 'single',
        'target': 'single_hpc_prototype/b1_smoke',
        'template_path': 'hpc_jobs/templates/single.sh',
        'expected_result_path': (
            'exp_results/single_hpc_prototype/b1_smoke/exp_b1_smoke'
        ),
        'completion_files': ['b1_smoke_result.json'],
        'top_level_resources': make_resources(),
    }


class HpcJobIdentifierTests(unittest.TestCase):
    def test_valid_identifiers_are_retained(self):
        self.assertEqual(validate_run_id('b1-single_001'), 'b1-single_001')
        self.assertEqual(
            validate_target('single_hpc_prototype/b1_smoke'),
            'single_hpc_prototype/b1_smoke',
        )
        self.assertEqual(
            validate_repo_path('hpc_jobs/templates/single.sh'),
            'hpc_jobs/templates/single.sh',
        )
        self.assertEqual(validate_git_commit('a' * 40), 'a' * 40)

    def test_unsafe_identifiers_and_paths_are_rejected(self):
        run_ids = ('', '.', '..', '../run', 'group/run', 'run*', 'run id')
        targets = ('', '.', '..', '../exp', 'group//exp', 'group\\exp', 'x*')
        paths = ('', '/absolute', '../file', 'dir//file', 'dir/./file', 'x*')
        for value in run_ids:
            with self.subTest(run_id=value):
                with self.assertRaises(HpcJobValidationError):
                    validate_run_id(value)
        for value in targets:
            with self.subTest(target=value):
                with self.assertRaises(HpcJobValidationError):
                    validate_target(value)
        for value in paths:
            with self.subTest(path=value):
                with self.assertRaises(HpcJobValidationError):
                    validate_repo_path(value)


class HpcJobResourceTests(unittest.TestCase):
    def test_resources_are_normalized(self):
        resources = make_resources()
        self.assertEqual(
            validate_resources(resources, 'simulation-job resources'),
            resources,
        )

    def test_resources_reject_unknown_and_nonpositive_values(self):
        resources = make_resources()
        with self.assertRaises(HpcJobValidationError):
            validate_resources({**resources, 'account': 'extra'}, 'resources')
        for value in (0, -1, True, 1.5, '1'):
            with self.subTest(value=value):
                with self.assertRaises(HpcJobValidationError):
                    validate_resources({**resources, 'cores': value}, 'resources')

    def test_parameter_count_comes_from_axes(self):
        axes = {'seed': [1, 2], 'weight': [0.1, 0.2, 0.3]}
        self.assertEqual(calculate_parameter_grid_size(axes), 6)
        with self.assertRaises(HpcJobValidationError):
            calculate_parameter_grid_size(axes, maximum=5)
        with self.assertRaises(HpcJobValidationError):
            calculate_parameter_grid_size({'seed': [1, 1]})

    def test_resources_map_exactly_to_batchtools_fields(self):
        resources = make_resources()
        self.assertEqual(format_slurm_time(10), '00:10:00')
        self.assertEqual(format_slurm_time(1500), '1-01:00:00')
        self.assertEqual(get_batchtools_resource_config(resources), {
            'partition': 'cpu.q',
            'realtime': '00:10:00',
            'nodes': 1,
            'coresPerNode': 2,
            'mem': '4G',
        })


class HpcJobRequestTests(unittest.TestCase):
    def test_single_request_uses_existing_result_correspondence(self):
        request = make_single_request()
        self.assertEqual(validate_request(request), request)
        changed = {
            **request,
            'expected_result_path': 'exp_results/automation/b1-single',
        }
        with self.assertRaises(HpcJobValidationError):
            validate_request(changed)

    def test_request_does_not_embed_its_own_commit(self):
        request = {**make_single_request(), 'expected_commit': 'a' * 40}
        with self.assertRaises(HpcJobValidationError):
            validate_request(request)

    def test_batch_request_separates_main_and_simulation_resources(self):
        request = {
            **make_single_request(),
            'request_id': 'b2-batch',
            'job_kind': 'batch',
            'target': 'batch_group/seed_sweep',
            'template_path': 'hpc_jobs/templates/batch.sh',
            'expected_result_path': (
                'exp_results/batch_group/seed_sweep/exp_nseed_3'
            ),
            'top_level_resources': {
                **make_resources(),
                'cores': 1,
            },
            'simulation_job_resources': make_resources(),
            'max_concurrent_simulation_jobs': 2,
            'max_simulation_jobs': 3,
        }
        normalized = validate_request(request)
        self.assertEqual(normalized['top_level_resources']['cores'], 1)
        self.assertEqual(normalized['simulation_job_resources']['cores'], 2)

    def test_workflow_request_has_explicit_stage_settings(self):
        request = {
            **make_single_request(),
            'request_id': 'b3-workflow',
            'job_kind': 'workflow',
            'target': 'wmat_transfer',
            'template_path': 'hpc_jobs/templates/workflow.sh',
            'expected_result_path': (
                'exp_results/workflows/wmat_transfer/exp_wmat_001'
            ),
            'stage_jobs': {
                'dw': {
                    'resources': make_resources(),
                    'max_concurrent_simulation_jobs': 2,
                },
                'rr': {
                    'resources': make_resources(),
                    'max_concurrent_simulation_jobs': 1,
                },
            },
            'max_simulation_jobs': 6,
        }
        self.assertEqual(set(validate_request(request)['stage_jobs']), {'dw', 'rr'})


class HpcJobLayoutTests(unittest.TestCase):
    def test_job_records_are_separate_from_scientific_results(self):
        layout = get_job_run_layout(Path('/repo/A1_OUinp'), 'b1-single-001')
        run_dir = Path('/repo/A1_OUinp/hpc_jobs/runs/b1-single-001')
        self.assertEqual(layout['run_dir'], run_dir)
        self.assertEqual(layout['submit_script'], run_dir / 'submit.sh')
        self.assertEqual(layout['stdout'], run_dir / 'slurm-%j.out')

    def test_result_collision_policy_allows_only_absent_or_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            result = repo_root / 'exp_results/group/experiment/exp_1'
            self.assertEqual(
                validate_result_destination(
                    repo_root,
                    'exp_results/group/experiment/exp_1',
                ),
                result,
            )
            result.mkdir(parents=True)
            validate_result_destination(
                repo_root,
                'exp_results/group/experiment/exp_1',
            )
            (result / 'existing.json').write_text('{}')
            with self.assertRaises(HpcJobValidationError):
                validate_result_destination(
                    repo_root,
                    'exp_results/group/experiment/exp_1',
                )

    def test_result_destination_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / 'exp_results').mkdir()
            (repo_root / 'outside').mkdir()
            (repo_root / 'exp_results/group').symlink_to(repo_root / 'outside')
            with self.assertRaises(HpcJobValidationError):
                validate_result_destination(
                    repo_root,
                    'exp_results/group/experiment/exp_1',
                )


class HpcJobContextTests(unittest.TestCase):
    def test_context_binds_external_commit_without_running_scientific_code(self):
        request = make_single_request()
        with tempfile.TemporaryDirectory() as tmp:
            context = build_prepared_job_context(
                request,
                'b1-single-001',
                Path(tmp),
                'a' * 40,
            )
        self.assertEqual(context['git_commit'], 'a' * 40)
        self.assertEqual(context['simulation_job_limit'], 1)
        self.assertIn('/hpc_jobs/runs/b1-single-001', context['job_run_dir'])

        values = build_template_values(context, '/repo/A1_OUinp')
        self.assertEqual(set(values), TEMPLATE_TOKENS['single'])
        self.assertEqual(values['TASKS'], '2')
        self.assertEqual(values['REQUEST_PATH'], 'hpc_jobs/requests/b1-single.json')

    def test_context_records_batch_limit_and_rejects_result_collision(self):
        request = {
            **make_single_request(),
            'request_id': 'b2-batch',
            'job_kind': 'batch',
            'target': 'batch_group/seed_sweep',
            'template_path': 'hpc_jobs/templates/batch.sh',
            'expected_result_path': (
                'exp_results/batch_group/seed_sweep/exp_nseed_3'
            ),
            'simulation_job_resources': make_resources(),
            'max_concurrent_simulation_jobs': 2,
            'max_simulation_jobs': 3,
        }
        with tempfile.TemporaryDirectory() as tmp:
            context = build_prepared_job_context(
                request,
                'b2-batch-001',
                Path(tmp),
                'a' * 40,
            )
            self.assertEqual(context['simulation_job_limit'], 3)
            result_dir = Path(tmp) / request['expected_result_path']
            result_dir.mkdir(parents=True)
            (result_dir / 'old.json').write_text('{}')
            with self.assertRaises(HpcJobValidationError):
                build_prepared_job_context(
                    request,
                    'b2-batch-001',
                    Path(tmp),
                    'a' * 40,
                )


class HpcJobRenderTests(unittest.TestCase):
    def setUp(self):
        self.template = (
            '#!/bin/bash\n'
            '#SBATCH --job-name=@@JOB_NAME@@\n'
            '#SBATCH --cpus-per-task=@@CORES@@\n'
            '#SBATCH --output=@@STDOUT@@\n'
            'cd @@CHECKOUT@@\n'
        )
        self.tokens = {'JOB_NAME', 'CORES', 'STDOUT', 'CHECKOUT'}
        self.values = {
            'JOB_NAME': 'a1-b1-single',
            'CORES': '2',
            'STDOUT': '/repo/hpc_jobs/runs/b1/slurm-%j.out',
            'CHECKOUT': '/ddn/user/repo/A1_OUinp_codex',
        }

    def test_template_is_rendered_exactly(self):
        rendered = render_template(self.template, self.values, self.tokens)
        self.assertIn('#SBATCH --job-name=a1-b1-single', rendered)
        self.assertIn('slurm-%j.out', rendered)
        self.assertNotIn('@@', rendered)

    def test_template_rejects_missing_unknown_and_duplicate_tokens(self):
        cases = (
            self.template.replace('@@CORES@@', '2'),
            self.template + 'echo @@UNKNOWN@@\n',
            self.template + 'echo @@CORES@@\n',
        )
        for template in cases:
            with self.subTest(template=template):
                with self.assertRaises(HpcJobValidationError):
                    render_template(template, self.values, self.tokens)

    def test_template_rejects_shell_active_values(self):
        invalid = ('two words', 'x;touch', 'x\n#SBATCH --nodes=2', '$(id)', '')
        for value in invalid:
            values = {**self.values, 'JOB_NAME': value}
            with self.subTest(value=value):
                with self.assertRaises(HpcJobValidationError):
                    render_template(self.template, values, self.tokens)

    def test_hashing_is_order_independent(self):
        self.assertEqual(hash_data({'a': 1, 'b': 2}), hash_data({'b': 2, 'a': 1}))

    def test_tracked_templates_match_fixed_token_contracts(self):
        dirpath_repo = Path(__file__).resolve().parents[1]
        for job_kind in ('single', 'batch', 'workflow'):
            with self.subTest(job_kind=job_kind):
                context = {
                    'job_kind': job_kind,
                    'request_id': f'b0-{job_kind}',
                    'run_id': f'b0-{job_kind}-001',
                    'top_level_resources': make_resources(),
                    'stdout_path': f'/repo/hpc_jobs/runs/{job_kind}/slurm-%j.out',
                    'stderr_path': f'/repo/hpc_jobs/runs/{job_kind}/slurm-%j.err',
                }
                values = build_template_values(context, '/repo/A1_OUinp')
                template = (
                    dirpath_repo / 'hpc_jobs' / 'templates' / f'{job_kind}.sh'
                ).read_text()
                rendered = render_template(
                    template,
                    values,
                    TEMPLATE_TOKENS[job_kind],
                )
                self.assertNotIn('@@', rendered)
                self.assertIn('sbatch', template.lower())


if __name__ == '__main__':
    unittest.main()
