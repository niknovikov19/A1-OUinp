#!/bin/bash
#SBATCH --partition=cpu.q
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
#SBATCH --export=NONE

set -euo pipefail

exec /ddn/niknovikov19/miniconda3/bin/python3 \
    /ddn/niknovikov19/hpc_codex/helpers/grid/hpc-grid-probe-job \
    "$@"
