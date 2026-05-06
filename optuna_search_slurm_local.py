import os
from pathlib import Path

from batchtk.runtk import Template
from batchtk.runtk.dispatchers import LocalDispatcher
from netpyne.batchtools.search import search
from netpyne.batchtools.submits import SlurmSubmit

from load_module import load_module


class LocalSlurmSubmit(SlurmSubmit):
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
            'env', 'custom', 'project_dir', 'command'
        },
    )


def _split_exp_name(exp_name):
    if '/' in exp_name:
        exp_subdir, exp_name_main = exp_name.rsplit('/', 1)
        subdir_str = f'--subdir {exp_subdir}'
    else:
        exp_subdir = None
        exp_name_main = exp_name
        subdir_str = ''
    return exp_subdir, exp_name_main, subdir_str


def _load_optuna_config(batch_params_mod):
    if not hasattr(batch_params_mod, 'get_optuna_config'):
        raise ValueError("batch_params.py must define get_optuna_config() for Optuna runs")

    optuna_cfg = batch_params_mod.get_optuna_config()
    if not isinstance(optuna_cfg, dict):
        raise TypeError("get_optuna_config() must return a dict")

    required_keys = {'params', 'metric', 'mode', 'num_samples'}
    missing_keys = required_keys - set(optuna_cfg)
    if missing_keys:
        missing = ', '.join(sorted(missing_keys))
        raise ValueError(f"get_optuna_config() is missing required keys: {missing}")

    if not isinstance(optuna_cfg['params'], dict):
        raise TypeError("get_optuna_config()['params'] must be a dict")
    if not optuna_cfg['params']:
        raise ValueError("get_optuna_config()['params'] must not be empty")
    if not isinstance(optuna_cfg['metric'], str) or not optuna_cfg['metric']:
        raise TypeError("get_optuna_config()['metric'] must be a non-empty string")
    if optuna_cfg['mode'] not in {'min', 'max'}:
        raise ValueError("get_optuna_config()['mode'] must be either 'min' or 'max'")
    if not isinstance(optuna_cfg['num_samples'], int) or optuna_cfg['num_samples'] <= 0:
        raise ValueError("get_optuna_config()['num_samples'] must be a positive integer")

    max_concurrent = optuna_cfg.get('max_concurrent')
    if max_concurrent is not None:
        if not isinstance(max_concurrent, int) or max_concurrent <= 0:
            raise ValueError("get_optuna_config()['max_concurrent'] must be a positive integer")

    algorithm_config = optuna_cfg.get('algorithm_config')
    if algorithm_config is not None and not isinstance(algorithm_config, dict):
        raise TypeError("get_optuna_config()['algorithm_config'] must be a dict")

    return optuna_cfg


def main():
    exp_name = os.environ.get(
        'A1_OPTUNA_EXP_NAME',
        'batch_rxbkg_state1_mech1/net_newsec_ibkg_corr_optuna',
    )

    partition = 'cpu.q'
    n_cores = 60
    mem_sz = 256

    dirpath_repo = Path(__file__).resolve().parent
    dirname_exp_configs = 'exp_configs'

    _, exp_name_main, subdir_str = _split_exp_name(exp_name)

    dirpath_exp = dirpath_repo / dirname_exp_configs / exp_name
    fpath_batch_params = dirpath_exp / 'batch_params.py'
    fpath_exp_cfg = dirpath_exp / 'exp_cfg.py'

    batch_params_mod = load_module(fpath_batch_params)
    exp_cfg_mod = load_module(fpath_exp_cfg)

    if not hasattr(exp_cfg_mod, 'get_batch_metrics'):
        raise ValueError(
            f"{fpath_exp_cfg} must define get_batch_metrics(sim) for Optuna runs"
        )

    optuna_cfg = _load_optuna_config(batch_params_mod)

    params = dict(optuna_cfg['params'])
    metric = optuna_cfg['metric']
    #params.setdefault('optuna_metric_name', metric)

    slurm_config = {
        'partition': partition,
        'realtime': '5:00:00',
        'nodes': 1,
        'coresPerNode': n_cores,
        'mem': f'{mem_sz}G',
        'custom': '\n'.join([
            'source ~/.bashrc',
            'conda activate netpyne_batch_slurm',
            'export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH',
            'export MKL_THREADING_LAYER=GNU',
        ]),
        'command': (
            f'srun --mpi=pmi2 -n {n_cores} nrniv -python -mpi '
            f'run_exp.py --batch --job_id_len 9 {subdir_str}'
        ),
    }

    ray_config = optuna_cfg.get('ray_config', {
        'runtime_env': {
            'working_dir': '.',
            'excludes': [
                '**/*.pkl',
                '**/*.out',
                '/.git/',
                '**/__pycache__/',
                '/exp_results/',
                '/exp_logs_old/',
                '/OLD/'
            ]
        }
    })

    search(
        dispatcher_constructor=LocalDispatcher,
        submit_constructor=LocalSlurmSubmit,
        label=exp_name_main,
        params=params,
        output_path=f'./exp_results/{exp_name}',
        checkpoint_path=f'./exp_logs/{exp_name}/ray',
        run_config=slurm_config,
        metric=metric,
        mode=optuna_cfg['mode'],
        sample_interval=optuna_cfg.get('sample_interval', 1),
        num_samples=optuna_cfg['num_samples'],
        max_concurrent=optuna_cfg.get('max_concurrent', 1),
        batch=optuna_cfg.get('batch', True),
        ray_config=ray_config,
        algorithm='optuna',
        algorithm_config=optuna_cfg.get('algorithm_config', {}),
        remote_dir=dirpath_repo.as_posix(),
        advanced_logging=optuna_cfg.get('advanced_logging', False),
        attempt_restore=optuna_cfg.get('attempt_restore', False),
    )


if __name__ == '__main__':
    main()
