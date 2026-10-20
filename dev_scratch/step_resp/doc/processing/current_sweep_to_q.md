# Current-sweep fitting: code and optional reproduction

This describes the completed Q analysis. Its inputs, fits, and figures already
exist; no simulation, transfer, or fitting is requested by this page.

The [registry](../../data/registry.md) identifies the selected Q dataset,
data/l2_current_sweep_5seeds_pm100pa_t40s/. HPC post-processing used sim_data_analyzer;
compact hvec/rvec NetCDFs were copied once, leaving PKLs on HPC. Fitting and
curve inspection were local. The [short Q record](../results/l2_current_sweep_q.md)
is sufficient for interpreting the selected estimate.

## Optional reproduction — regenerates fitted outputs

The code below documents how to reproduce the existing fit; it is not a task
to execute. It uses the repository root and existing NetPyNE environment.
If a refit is separately requested, this command may replace generated fits,
matrices, and figures. Viewing or collecting saved figures does not require it.

```bash
# Optional fit reproduction only; not requested by this document
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/analyze_h_io.py \
  --data-dir dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s
```

## What the code does

[analyze_h_io.py](../../code/analyze_h_io.py) discovers
one h/r pair per seed under input/hvec_xr/ and input/rvec_xr/, reads actual current
per population (unequal ranges supported), combines seed × pop × time, applies
declared smoothing, selects triangle samples excluding turn margins, pools seeds,
fits Richards curves, and differentiates at h = 0. Rising/falling fits are separate.

Options: --smooth-win, --fit-start, --fit-stop, --turn-margin, --no-plot.
Outputs: processed/h_rate.nc and processed/tau_<window>/ with richards_coeffs.json,
qmat.json, input-first qmat.nc, and fits/<population>.png. Off-diagonal zeros
reflect decoupled topology; failed own-population gains are not silently zeroed.

[Selected-Q result](../results/l2_current_sweep_q.md) gives the current estimate;
[development history](../archive/current_sweep_development.md) holds superseded
diagnostics, not equally preferred alternatives.
