#!/bin/bash
#SBATCH --job-name=OUGrid
#SBATCH --partition=cpu.q
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=/ddn/niknovikov19/repo/A1_OUinp/batch_sl_1.out
#SBATCH --error=/ddn/niknovikov19/repo/A1_OUinp/batch_sl_1.err
#SBATCH --export=ALL

source ~/.bashrc
conda activate netpyne_batch_slurm
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
export MKL_THREADING_LAYER=GNU

cd /ddn/niknovikov19/repo/A1_OUinp
python -u grid_search_slurm_local.py
