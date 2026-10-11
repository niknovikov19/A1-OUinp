import argparse
from pathlib import Path

from hpc_batch_jobs import (
    append_child_record,
    build_child_record,
    decode_batch_parameters,
    parse_child_sbatch_result,
)
from hpc_job import (
    get_batchtools_resource_config,
    validate_positive_int,
    validate_repo_path,
)
from hpc_preflight import preflight_request, read_tracked_request
from load_module import load_module


DEFAULT_EXPERIMENT = 'batch_rxbkg_state1_mech1/net_newsec_var_seed'
DEFAULT_RESOURCES = {
    'partition': 'cpu.q',
    'nodes': 1,
    'cores': 60,
    'memory_gb': 256,
    'wall_time_min': 7 * 60,
}
DEFAULT_MAX_CONCURRENT = 6
DIR_REPO = Path(__file__).resolve().parent


def _resolve_child_outputs(exp_config_path, expected_result_path,
                           child_key, parameters):
    """Resolve experiment-owned child outputs beneath one result root. """
    exp_mod = load_module(DIR_REPO / exp_config_path)
    outputs = exp_mod.get_batch_completion_files(child_key, parameters)
    if not isinstance(outputs, list) or not outputs:
        raise ValueError('Batch completion files must be a non-empty list')
    outputs = [
        validate_repo_path(path, 'batch completion file')
        for path in outputs
    ]
    return [f'{expected_result_path}/{path}' for path in outputs]


def _build_local_slurm_submit(child_recorder=None):
    """Build the local Slurm submitter with optional child recording. """
    from batchtk import runtk
    from batchtk.runtk import Submit, Template

    class LocalSlurmSubmit(Submit):
        """Submit BatchTools simulation jobs through local Slurm. """

        def __init__(self, **kwargs):
            """Initialize fixed Slurm templates and BatchTools handles. """
            submit_template = Template(
                template='/usr/bin/sbatch --parsable {job_path}/{label}.sh',
                key_args={'job_path', 'label'},
            )
            script_template = Template(
                template="""\
#!/bin/bash
#SBATCH --job-name={label}
#SBATCH -t {realtime}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={coresPerNode}
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem}
#SBATCH --partition={partition}
#SBATCH -o {job_path}/{label}.run
#SBATCH -e {job_path}/{label}.err
#SBATCH --export=ALL
export JOBID=$SLURM_JOB_ID
export MSGFILE="{job_path}/{label}.out"
export SGLFILE="{job_path}/{label}.sgl"
{env}
{custom}
cd {project_path}
{command}
wait
""",
                key_args={
                    'label', 'realtime', 'nodes', 'coresPerNode', 'mem',
                    'partition', 'job_path', 'env', 'custom',
                    'project_path', 'command',
                },
            )
            handles = {
                runtk.SUBMIT: '{job_path}/{label}.sh',
                runtk.STDOUT: '{job_path}/{label}.run',
                runtk.MSGOUT: '{job_path}/{label}.out',
                runtk.SGLOUT: '{job_path}/{label}.sgl',
            }
            super().__init__(
                submit_template=submit_template,
                script_template=script_template,
                handles=handles,
            )
            self.batch_parameters = None

        def create_job(self, **kwargs):
            """Capture parameters before rendering the child script. """
            if child_recorder is not None:
                self.batch_parameters = decode_batch_parameters(
                    kwargs['env'],
                    child_recorder['parameter_names'],
                )
            super().create_job(**kwargs)

        def submit_job(self, **kwargs):
            """Submit once and persist the exact scheduler receipt. """
            completed = super().submit_job(**kwargs)
            slurm_job_id = parse_child_sbatch_result(completed)
            if child_recorder is None:
                return slurm_job_id
            child_key = Path(self.path).stem
            outputs = _resolve_child_outputs(
                child_recorder['exp_config_path'],
                child_recorder['expected_result_path'],
                child_key,
                self.batch_parameters,
            )
            record = build_child_record(
                child_recorder['run_id'],
                child_key,
                slurm_job_id,
                self.batch_parameters,
                child_recorder['job_dir'],
                outputs,
            )
            append_child_record(child_recorder['index_path'], record)
            return slurm_job_id

    return LocalSlurmSubmit


def _load_batchtools(child_recorder=None):
    """Load BatchTools and Ray only when a batch is actually launched. """
    from batchtk.runtk.dispatchers import LocalDispatcher
    from netpyne.batchtools.search import search

    submitter = _build_local_slurm_submit(child_recorder)
    return search, LocalDispatcher, submitter


def _split_experiment(experiment):
    """Split one validated experiment into subdirectory and label values."""
    if '/' not in experiment:
        return None, experiment
    return experiment.rsplit('/', 1)


def _build_slurm_config(resources, experiment_subdir):
    """Build existing BatchTools Slurm settings from validated resources."""
    config = get_batchtools_resource_config(resources)
    subdir_arg = ''
    if experiment_subdir is not None:
        subdir_arg = f' --subdir {experiment_subdir}'
    n_tasks = resources['nodes'] * resources['cores']
    config.update({
        'custom': '\n'.join([
            'source ~/.bashrc',
            'conda activate netpyne_batch_slurm',
            'export LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
            'export MKL_THREADING_LAYER=GNU',
        ]),
        'command': (
            f'srun --mpi=pmi2 -n {n_tasks} nrniv -python -mpi '
            f'run_exp.py --batch{subdir_arg}'
        ),
    })
    return config


def _get_run_settings(args):
    """Resolve either legacy manual defaults or one tracked HPC request."""
    if args.hpc_request is None:
        if args.hpc_run_id is not None:
            raise ValueError('--hpc-run-id requires --hpc-request')
        resources = dict(DEFAULT_RESOURCES)
        if args.partition is not None:
            resources['partition'] = args.partition
        if args.nodes is not None:
            resources['nodes'] = args.nodes
        if args.cores is not None:
            resources['cores'] = args.cores
        if args.memory_gb is not None:
            resources['memory_gb'] = args.memory_gb
        if args.wall_time_min is not None:
            resources['wall_time_min'] = args.wall_time_min
        return {
            'experiment': args.experiment or DEFAULT_EXPERIMENT,
            'resources': resources,
            'max_concurrent': (
                args.max_concurrent
                if args.max_concurrent is not None
                else DEFAULT_MAX_CONCURRENT
            ),
            'hpc_run_id': None,
            'expected_result_path': None,
        }

    manual_values = (
        args.experiment,
        args.partition,
        args.nodes,
        args.cores,
        args.memory_gb,
        args.wall_time_min,
        args.max_concurrent,
    )
    if any(value is not None for value in manual_values):
        raise ValueError('An HPC request cannot be combined with manual settings')
    request = read_tracked_request(DIR_REPO, args.hpc_request)
    if request['job_kind'] != 'batch':
        raise ValueError('grid_search_slurm_local.py requires a batch request')
    if args.hpc_run_id is None:
        raise ValueError('An HPC batch request requires --hpc-run-id')
    preflight_request(DIR_REPO, request)
    return {
        'experiment': request['target'],
        'resources': request['simulation_job_resources'],
        'max_concurrent': request['max_concurrent_simulation_jobs'],
        'hpc_run_id': args.hpc_run_id,
        'expected_result_path': request['expected_result_path'],
    }


def run_batch(experiment, resources, max_concurrent, hpc_run_id=None,
              expected_result_path=None):
    """Run one BatchTools parameter grid with resolved operational settings."""
    max_concurrent = validate_positive_int(
        max_concurrent,
        'concurrent simulation-job limit',
    )
    experiment_subdir, experiment_name = _split_experiment(experiment)
    fpath_batch = DIR_REPO / 'exp_configs' / experiment / 'batch_params.py'
    fpath_exp = DIR_REPO / 'exp_configs' / experiment / 'exp_cfg.py'
    batch_mod = load_module(fpath_batch)
    exp_mod = load_module(fpath_exp)
    params = batch_mod.get_batch_params()
    if not params:
        print('Parameter list is empty - exit')
        return
    child_recorder = None
    if hpc_run_id is not None:
        if not hasattr(exp_mod, 'get_batch_completion_files'):
            raise ValueError(
                'HPC batch experiment requires get_batch_completion_files()'
            )
        job_dir = f'{expected_result_path}/jobs'

        child_recorder = {
            'run_id': hpc_run_id,
            'parameter_names': tuple(params),
            'job_dir': job_dir,
            'job_path': (DIR_REPO / job_dir).as_posix(),
            'index_path': DIR_REPO / job_dir / 'index.jsonl',
            'exp_config_path': fpath_exp.relative_to(DIR_REPO).as_posix(),
            'expected_result_path': expected_result_path,
        }
    search, dispatcher, submitter = _load_batchtools(child_recorder)
    slurm_config = _build_slurm_config(resources, experiment_subdir)
    if child_recorder is not None:
        slurm_config['job_path'] = child_recorder['job_path']
    ray_config = {
        'runtime_env': {
            'working_dir': '.',
            'excludes': [
                '**/*.pkl',
                '**/*.out',
                '/.git/',
                '**/__pycache__/',
                '/exp_results/',
                '/exp_logs_old/',
                '/OLD/',
            ],
        },
    }

    # Keep the established BatchTools output and checkpoint locations
    search(
        dispatcher_constructor=dispatcher,
        submit_constructor=submitter,
        label=experiment_name,
        params=params,
        output_path=f'./exp_results/{experiment}',
        checkpoint_path=f'./exp_logs/{experiment}/ray',
        run_config=slurm_config,
        metric='done',
        mode='max',
        sample_interval=1,
        num_samples=1,
        max_concurrent=max_concurrent,
        batch=True,
        ray_config=ray_config,
        algorithm='variant_generator',
        remote_dir=DIR_REPO.as_posix(),
        advanced_logging=False,
        attempt_restore=False,
    )


def main_cli():
    """Parse manual or tracked-request settings and start BatchTools."""
    parser = argparse.ArgumentParser(description='Run one BatchTools sweep.')
    parser.add_argument('--hpc-request')
    parser.add_argument('--hpc-run-id')
    parser.add_argument('--experiment')
    parser.add_argument('--partition')
    parser.add_argument('--nodes', type=int)
    parser.add_argument('--cores', type=int)
    parser.add_argument('--memory-gb', type=int)
    parser.add_argument('--wall-time-min', type=int)
    parser.add_argument('--max-concurrent', type=int)
    args = parser.parse_args()
    settings = _get_run_settings(args)
    run_batch(
        settings['experiment'],
        settings['resources'],
        settings['max_concurrent'],
        settings['hpc_run_id'],
        settings['expected_result_path'],
    )


if __name__ == '__main__':
    main_cli()
