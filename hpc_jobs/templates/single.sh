#!/bin/bash
#SBATCH --job-name=@@JOB_NAME@@
#SBATCH --time=@@WALL_TIME@@
#SBATCH --nodes=@@NODES@@
#SBATCH --ntasks-per-node=@@CORES@@
#SBATCH --cpus-per-task=1
#SBATCH --mem=@@MEMORY@@
#SBATCH --partition=@@PARTITION@@
#SBATCH --output=@@STDOUT@@
#SBATCH --error=@@STDERR@@
#SBATCH --export=ALL

source ~/.bashrc
conda activate netpyne_batch_slurm
set -euo pipefail
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MKL_THREADING_LAYER=GNU
cd @@CHECKOUT@@
srun --mpi=pmi2 -n @@TASKS@@ nrniv -python -mpi run_exp.py --hpc-request @@REQUEST_PATH@@
