from pathlib import Path
import time

from batchtk.runtk import Template
from batchtk.runtk.dispatchers import LocalDispatcher
from netpyne.batchtools.search import search
from netpyne.batchtools.submits import SlurmSubmit
import numpy as np

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


# Experiment name
#exp_name = 'batch_rxbkg_state1_mech1/net_newsec_var_seed'
#exp_name = 'batch_rxbkg_unconn_state1_mech1/net_newsec_var_seed_pre_post'
#exp_name = 'batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre'
#exp_name = 'batch_rxbkg_unconn_state1_mech1/net_inpsur_hr_osc_var_seed_f_amp'
#exp_name = 'batch_rxbkg_unconn_state1_mech1/net_inpsur_rr_osc_var_seed_pre_f_amp'batch_rxbkg_unconn_state1_mech1/net_inpsur_rr_osc_var_seed_pre_f_amp'
exp_name = 'batch_rxbkg_unconn_state1_mech1/net_inpsur_dw_var_seed_ibkg'
#exp_name = 'batch_rxbkg_unconn_state1_mech1/pops_inpsur_newsec_var_drxe_rxi'
#exp_name = 'batch_unconn/fi_tuning'

# HPC partition
#PARTITION = 'bigmem.q'
PARTITION = 'cpu.q'

# Resources to allocate
#N_CORES = 28
#MEM_SZ = 128
N_CORES = 60
MEM_SZ = 256


# Repository folder
dirpath_repo = Path(__file__).resolve().parent

# Folder name for experiment configs
DIRNAME_EXP_CONFIGS = 'exp_configs'

# Split exp_name into the main name and the containing subfolder
if '/' in exp_name:
    exp_subdir, exp_name_main = exp_name.rsplit('/', 1)
    subdir_str = f'--subdir {exp_subdir}'
else:
    exp_name_main = exp_name
    subdir_str = ''

# Import experiment-specific batch_params.py and get batch params
fpath_batch_params = (dirpath_repo / DIRNAME_EXP_CONFIGS / 
                      exp_name / 'batch_params.py')
batch_params_mod = load_module(fpath_batch_params)
params = batch_params_mod.get_batch_params()

slurm_config = {
    'partition': PARTITION,
    'realtime': '7:00:00',
    'nodes': 1,
    'coresPerNode': N_CORES,
    'mem': f'{MEM_SZ}G',
    'custom': '\n'.join([
        'source ~/.bashrc',
        'conda activate netpyne_batch_slurm',
        'export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH',
        'export MKL_THREADING_LAYER=GNU',
    ]),
    'command': f'srun --mpi=pmi2 -n {N_CORES} nrniv -python -mpi run_exp.py --batch {subdir_str}'
}

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
            '/OLD/'
        ]
    }
}

if params:
    search(
        dispatcher_constructor=LocalDispatcher,
        submit_constructor=LocalSlurmSubmit,
        label=exp_name_main,
        params=params,
        output_path=f'./exp_results/{exp_name}',
        checkpoint_path=f'./exp_logs/{exp_name}/ray',
        run_config=slurm_config,
        metric='done',
        mode='max',
        sample_interval=1,
        num_samples=1,
        max_concurrent=6,
        batch=True,
        ray_config=ray_config,
        algorithm='variant_generator',
        remote_dir=dirpath_repo.as_posix(),
        advanced_logging=False,
        attempt_restore=False
    )
else:
    print('Parameter list is empty - exit')

