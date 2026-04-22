#!/bin/bash
#SBATCH --job-name=OUsim
#SBATCH --partition=cpu.q
#SBATCH --nodes=1
#SBATCH --ntasks=60
#SBATCH --mem=256G
#SBATCH --time=24:00:00
#SBATCH --output=/ddn/niknovikov19/repo/A1_OUinp/single_sl_1.out
#SBATCH --error=/ddn/niknovikov19/repo/A1_OUinp/single_sl_1.out
#SBATCH --export=ALL

#EXP_NAME="single_rxbkg_unconn_state1_mech1/pops_inpsur_newsec"
EXP_NAME="single_rxbkg_state1_mech1/net_newsec_ctrl"
#EXP_NAME="single_unconn/fi_tuning_inpsur"

source ~/.bashrc
conda activate netpyne_batch_slurm
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
export MKL_THREADING_LAYER=GNU

cd /ddn/niknovikov19/repo/A1_OUinp
srun --mpi=pmi2 nrniv -python -mpi run_exp.py --name "$EXP_NAME"