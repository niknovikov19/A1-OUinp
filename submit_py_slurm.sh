#!/bin/bash
#SBATCH --job-name=PY
#SBATCH --partition=cpu.q
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=256G
#SBATCH --time=24:00:00
#SBATCH --output=/ddn/niknovikov19/repo/A1_OUinp/single_sl_1.out
#SBATCH --error=/ddn/niknovikov19/repo/A1_OUinp/single_sl_1.out
#SBATCH --export=ALL

source ~/.bashrc
conda activate netpyne_batch_slurm2
export PYTHONPATH="$PWD/external:$PYTHONPATH"

cd /ddn/niknovikov19/repo/A1_OUinp
srun python -u ./analysis/batch/extract_rates_batch.py