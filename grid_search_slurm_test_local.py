from batchtk.runtk import Template
from batchtk.runtk.dispatchers import LocalDispatcher
from netpyne.batchtools.search import search, LocalGridDispatcher
from netpyne.batchtools.submits import SlurmSubmit
import numpy as np


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


project_dir = '/ddn/niknovikov19/repo/A1_OUinp'

slurm_config = {
    'partition': 'bigmem.q',
    'realtime': '1:00:00',
    'nodes': 1,
    'coresPerNode': 4,
    'mem': '2G',
    'custom': '\n'.join([
        'source ~/.bashrc',
        'conda activate netpyne_batch_slurm',
        'export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH',
        'export MKL_THREADING_LAYER=GNU',
    ]),
    'command': 'srun --mpi=pmi2 -n 4 nrniv -python -mpi job_test_local.py',
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

params = {'batch_par': np.arange(10).tolist()}

search(
    #dispatcher_constructor=LocalGridDispatcher,
    dispatcher_constructor=LocalDispatcher,
    submit_constructor=LocalSlurmSubmit,
    label='SLURM_BATCH_3',
    params=params,
    output_path='./temp_local/slurm_test',
    checkpoint_path='./exp_logs/slurm_test/ray',
    run_config=slurm_config,
    metric='done',
    mode='max',
    sample_interval=1,
    num_samples=1,
    max_concurrent=3,
    batch=True,
    ray_config=ray_config,
    algorithm='variant_generator',
    remote_dir=project_dir,
    advanced_logging=False,
    attempt_restore=False
)
