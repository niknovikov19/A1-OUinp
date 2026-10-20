# Connected-step analysis: code and optional reproduction

This describes how the completed analysis was produced. All results already
exist; this page is not a request to submit jobs, download inputs, or rerun code.
The [short result hand-off](../results/connected_steps_5seeds_15_30pa.md) is
sufficient for interpreting the current results.

## How the inputs reached the local workspace

Installed hpc-codex helpers handled submission, monitoring, completion checks,
and release. PKLs/network files stayed on HPC. The compact files were downloaded
and verified as one archive. For a separately requested transfer, the helper
interface is shown below; it is not needed for the existing local dataset:

```bash
# Optional transfer reference; not requested and not needed for existing inputs
/opt/a1-hpc/bin/hpc-result --json archive <run-id> --unpack
```

The helper checks archive SHA256 and the per-file manifest. The latest dataset's
input/ already links to the verified local compact/ cache, avoiding a duplicate
copy. Its archive manifest records actual HPC paths. Dataset locations are in
the [registry](../../data/registry.md).

## Optional local reproduction — writes analysis outputs

The following is executable reproduction reference, not a pending analysis task.
It uses the repository root as working directory and the existing NetPyNE
environment. If reproduction is explicitly requested, these commands regenerate
files in the specified analysis directory and may replace existing generated
outputs. Reading results or collecting saved figures does not require them.

```bash
# Optional reproduction only; regenerates existing analysis outputs
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/analyze_hstep.py \
  --input-dir dev_scratch/step_resp/data/l2_connected_steps_5seeds_15_30pa_100s/input \
  --output-dir dev_scratch/step_resp/data/l2_connected_steps_5seeds_15_30pa_100s/analysis \
  --qmat dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s/processed/tau_0.2/qmat.nc

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/predict_hstep_static.py \
  --data-dir dev_scratch/step_resp/data/l2_connected_steps_5seeds_15_30pa_100s

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/summarize_hstep_amplitudes.py \
  --data-dir dev_scratch/step_resp/data/l2_connected_steps_5seeds_15_30pa_100s

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/plot_hstep_dynamics.py \
  --data-dir dev_scratch/step_resp/data/l2_connected_steps_5seeds_15_30pa_100s
```

## What the relevant code does

[analyze_hstep.py](../../code/analyze_hstep.py) validates waveform/units, finite raw rates, clamp counts,
spike-count arithmetic/windows, and unchanged baseline config within seed.
It saves raw window means, response contrasts, symmetric slopes, and repeat
diagnostics. Exact-repeat failure stays visible as a limitation.

[predict_hstep_static.py](../../code/predict_hstep_static.py) reads the fixed-predictor reference manifest, resolves
relocated local paths, verifies hashes, and copies byte-identical J/Q into
analysis/jq/. It never refits.
[summarize_hstep_amplitudes.py](../../code/summarize_hstep_amplitudes.py) adds
signed-amplitude, symmetry, and half/full-amplitude tables;
[plot_hstep_dynamics.py](../../code/plot_hstep_dynamics.py) makes rate overlays.
Definitions and symbols: [prediction contract](../contracts/static_prediction.md).
