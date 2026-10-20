# Historical reference: presynaptic rate-sweep extraction and fitting commands

HISTORICAL REPRODUCTION REFERENCE — not a launch, extraction, or fitting request.
This preserves the earlier procedure, including its command-oriented wording.
The selected local inputs/results already exist; the
[short processing description](../processing/rate_sweep_hpc_to_local.md) is sufficient
for orientation. The commands below are not part of the current hand-off.
For the selected L2 J, use [the completed refit record](../results/l2_rate_sweep_j.md)
and [frozen prediction contract](../contracts/static_prediction.md), not a fresh
run of the historical fitter. No fitting is requested by this document.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Run simulations and spike extraction on HPC. Copy the rate cache locally and
do the exploratory curve fitting locally, where plots and fit changes are
easy to inspect.

```text
HPC simulation: cfg + pkl
  -> extract_rates_batch.py
  -> spike NPZ cache -> rate NetCDF
  -> copy rate NetCDF + one cfg locally
  -> analyze_rate_io.py
  -> Richards coefficients + static gain matrix
```

Run all commands from the repository root.

## 1. Run the batch on HPC

Configure
[`batch_params.py`](../../../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/batch_params.py)
and
[`exp_cfg.py`](../../../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/exp_cfg.py),
then launch through the BatchTools/Slurm entry point:

```bash
python grid_search_slurm_local.py \
  --experiment batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre
```

Check that each expected job produced one `cfg/*.json` and one `pkl/*.pkl`.
The transfer analysis uses these files, not the per-job `results/*.json`.

## 2. Build the rate cache on HPC

In
[`analysis/batch/extract_rates_batch.py`](../../../../analysis/batch/extract_rates_batch.py),
set `EXP_LABEL` to the complete path below `exp_results/` and check the time
range, bin size, smoothing, and batch-coordinate fields. Use `spikes` mode for
a reusable spike cache, or `direct` mode to skip that cache.

```bash
python analysis/batch/extract_rates_batch.py
```

This uses `sim_data_analyzer` and writes `combined/data_proc/rates_*.nc` plus,
in `spikes` mode, `combined/data_proc/spikes_*/`.

## 3. Copy the fitting inputs locally

From the HPC experiment directory below, copy the rate NetCDF and the first
job configuration to the same relative path under local `exp_results/`:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/
net_inpsur_rsweep_newsec_var_seed_pre/<experiment-label>/
```

Required files are:

```text
combined/data_proc/rates_*.nc
cfg/cfg_00000_*.json
```

Leave `pkl/` and `combined/data_proc/spikes_*/` on HPC. Preserve the result
tree because the current fitting script uses hard-coded relative paths.

## 4. Fit the transfer matrix locally

In
[`analysis/batch/analyze_rate_io.py`](../../../../analysis/batch/analyze_rate_io.py),
set the experiment label, match the rate-cache time/bin/smoothing values, and
choose the fitting interval and additional rolling window. Use
`NEED_PLOT = 1` in the primary local workflow so the per-pair fit figures are
saved for inspection.

```bash
python analysis/batch/analyze_rate_io.py
```

For every `pop_pre -> pop_post` pair, this fits a Richards curve and evaluates
its derivative at the target presynaptic rate. It writes:

```text
combined/results/
├── richards_coeffs_tau_<window>.json
├── wmat_tau_<window>.json
├── wmat_tau_<window>.nc
└── fit_pngs_tau_<window>/        # Optional
```

Check the fit count, matrix dimensions, and `NaN` count.

## Optional HPC fitting

Direct HPC fitting is suitable only for a small circuit and normally with
`NEED_PLOT = 0`:

```bash
python analysis/batch/analyze_rate_io.py
```

Large-circuit fitting on HPC should be submitted as a scheduled job rather
than run directly. After it completes, copy `combined/results/` locally. A
job-submission wrapper for this analysis has not yet been added here.

The three historical scripts listed here are provenance snapshots in code/;
extract_rates_batch.py still assumes its original analysis/batch/ file depth.
This does not describe the newer executable local scripts: refit_rate_io.py,
analyze_h_io.py, and connected-step analysis live and run in step_resp/code/.
