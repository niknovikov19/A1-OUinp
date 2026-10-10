import argparse
from pathlib import Path

from hpc_job import get_batchtools_resource_config, validate_positive_int
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


def _load_batchtools():
    """Load BatchTools only when a batch is actually launched."""
    from batchtk.runtk import Template
    from batchtk.runtk.dispatchers import LocalDispatcher
    from netpyne.batchtools.search import search
    from netpyne.batchtools.submits import SlurmSubmit

    class LocalSlurmSubmit(SlurmSubmit):
        """Submit BatchTools simulation jobs through local Slurm."""

        SUBMIT_TEMPLATE = Template(
            template='sbatch {output_dir}/{label}.sh',
            key_args={'output_dir', 'label'},
        )

        SCRIPT_TEMPLATE = Template(
            template="""\
#!/bin/bash
#SBATCH --job-name={label}
#SBATCH -t {realtime}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={coresPerNode}
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem}
#SBATCH --partition={partition}
#SBATCH -o {stdout}
#SBATCH -e {stderr}
#SBATCH --export=ALL
export JOBID=$SLURM_JOB_ID
{handles}
{env}
{custom}
cd {project_dir}
{command}
wait
""",
            key_args={
                'label', 'realtime', 'nodes', 'coresPerNode', 'mem',
                'partition', 'stdout', 'stderr', 'handles',
                'env', 'custom', 'project_dir', 'command',
            },
        )

    return search, LocalDispatcher, LocalSlurmSubmit


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
            'export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH',
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
    preflight_request(DIR_REPO, request)
    return {
        'experiment': request['target'],
        'resources': request['simulation_job_resources'],
        'max_concurrent': request['max_concurrent_simulation_jobs'],
    }


def run_batch(experiment, resources, max_concurrent):
    """Run one BatchTools parameter grid with resolved operational settings."""
    max_concurrent = validate_positive_int(
        max_concurrent,
        'concurrent simulation-job limit',
    )
    experiment_subdir, experiment_name = _split_experiment(experiment)
    fpath_batch = DIR_REPO / 'exp_configs' / experiment / 'batch_params.py'
    batch_mod = load_module(fpath_batch)
    params = batch_mod.get_batch_params()
    if not params:
        print('Parameter list is empty - exit')
        return
    search, dispatcher, submitter = _load_batchtools()
    slurm_config = _build_slurm_config(resources, experiment_subdir)
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
    )


if __name__ == '__main__':
    main_cli()
