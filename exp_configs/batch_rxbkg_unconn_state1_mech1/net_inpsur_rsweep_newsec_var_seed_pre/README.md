# Presynaptic rate-sweep experiment

This experiment estimates a static population-level transfer matrix: the
local change in each postsynaptic population's firing rate caused by a change
in one presynaptic population's firing rate. It is an effective-connectivity
measurement around the configured target-rate operating point, rather than a
direct summary of anatomical connection weights.

## Relevant files

- [`batch_params.py`](batch_params.py) selects the presynaptic populations and
  random seeds.
- [`exp_cfg.py`](exp_cfg.py) configures the network, creates the dynamic
  surrogate input, and saves each simulation's results.
- [`target_state_1.csv`](target_state_1.csv) supplies the baseline population
  rates at which transfer-curve derivatives are evaluated.
- [`pops_sz.csv`](pops_sz.csv) supplies the number of independent surrogate
  cells used for each driven population.

The main analysis script is
[`analysis/batch/analyze_rate_io.py`](../../../analysis/batch/analyze_rate_io.py).
Its required rate-dynamics cache is created by
[`analysis/batch/extract_rates_batch.py`](../../../analysis/batch/extract_rates_batch.py).
Exploratory versions of the analysis also exist in
[`analysis/batch/analyze_rate_io.ipynb`](../../../analysis/batch/analyze_rate_io.ipynb)
and
[`analysis/batch/analyze_rate_io_2.ipynb`](../../../analysis/batch/analyze_rate_io_2.ipynb).

## Experiment design

The current batch varies two axes:

| Axis | Current values |
| --- | --- |
| `seed_main` | 1000-1004 |
| `pop_pre` | All 36 cortical populations |

For each job, all cortical populations remain active and their incoming
network connections are represented by frozen surrogate populations. The
surrogate corresponding to `pop_pre` is replaced by a VecStim population
whose cells emit independent inhomogeneous-Poisson spike trains. This changes
one presynaptic population's rate while retaining the rest of the model and
allows all active postsynaptic populations to be measured simultaneously.
Because `conns_frozen = 'all'`, active populations do not form a recurrent
feedback network in this experiment.

The simulation lasts 20 seconds. The driven rate remains at its target value
until 5 seconds, then follows the configured rate sweep. The current settings
use a triangular sweep with a 7.5-second period. Its upper rate is computed
separately for each population as:

```text
min(500 Hz, 10 * target presynaptic rate)
```

The triangle starts at the target rate and traverses a range from zero to the
effective upper rate. Thus the input levels are sampled continuously in time,
not as an explicit batch axis. The slow sweep is used to estimate a static
input-output curve; this is distinct from the sinusoidal transfer experiment
in `net_inpsur_rr_osc_var_seed_pre_f_amp`.

The experiment supports `ramp`, `osc`, and `tri` rate dynamics through
`RPRE_DYN_TYPE`, although `tri` is the current setting. Network-wide scaling
defaults to `wmult = 0.25` and `EEGain = 0.5`, and the configured background
and current-control inputs are enabled.

## Saved simulation data

`post_run()` organizes each batch job under:

```text
exp_results/batch_rxbkg_unconn_state1_mech1/
└── net_inpsur_rsweep_newsec_var_seed_pre/<experiment-label>/
    ├── cfg/
    ├── pkl/
    ├── results/
    ├── rasters/
    ├── netpar/
    └── rvec_figs/
```

The pickle files contain the spike data used by the transfer analysis. The
compact result JSON files contain rates, CVs, and timings, while `rvec_figs`
contains per-job rate-dynamics diagnostics.

## Processing pipeline

Run the following from the repository root after setting `EXP_LABEL` in both
scripts to the desired result directory:

```bash
python analysis/batch/extract_rates_batch.py
python analysis/batch/analyze_rate_io.py
```

### 1. Extract population-rate dynamics

`extract_rates_batch.py` uses `sim_data_analyzer` to reconstruct the batch
grid from job configuration files and collect population firing-rate traces.
Its current `spikes` mode performs two steps:

1. Extract each job's population spikes from its pickle into a reusable NPZ
   cache.
2. Bin and smooth the spikes into one labeled xarray DataArray.

The default bin width is 2 ms, the initial smoothing time constant is 10 ms,
and the extraction interval is 1-20 seconds. The resulting cache is named:

```text
combined/data_proc/rates_dt_0.002_tau_0.01_t_1_20.0.nc
```

The script also supports a `direct` mode that computes the same rate cache
straight from the pickle files.

### 2. Fit transfer curves

`analyze_rate_io.py` loads the rate cache and restricts fitting to data from
5 seconds onward. It then applies a centered 200 ms rolling mean. For every
`pop_pre -> pop_post` pair, it:

1. Uses the measured rate of `pop_prefrz` as the input, rather than assuming
   that the requested surrogate rate was realized exactly.
2. Uses the active `pop_post` rate as the output.
3. Pools valid time samples across all seeds.
4. Fits a five-parameter Richards input-output curve.
5. Evaluates the fitted derivative at `pop_pre`'s target firing rate.
6. Stores that derivative in `W[pop_pre, pop_post]`.

In notation, each matrix element is:

```text
W[pre, post] = d r_post / d r_pre evaluated at r_pre = target_rate[pre]
```

The curve fit is global over the collected sweep samples; the effective
connectivity value is local because it is the derivative at the target-rate
operating point. Setting `NEED_PLOT = 1` also saves the fitted curves and
tangent lines.

## Analysis outputs

The processor writes the following under `combined/results/`:

```text
richards_coeffs_tau_<window>.json
wmat_tau_<window>.json
wmat_tau_<window>.nc
fit_pngs_tau_<window>/        # Only when NEED_PLOT is enabled
```

- `richards_coeffs_*.json` contains `A`, `K`, `B`, `M`, `nu`, and the sample
  count for every successful population-pair fit.
- `wmat_*.nc` is the labeled `pop_pre x pop_post` effective-connectivity
  matrix.
- `wmat_*.json` contains the same matrix in an inspection-friendly form.

Existing derived examples are available in the corresponding result folder,
including `ctx/wmat_tau_0.2.nc` and the older L2 analysis under
`exp_pre_L2_post_L2/combined/results/`.

## Interpretation notes

- Matrix entries are dimensionless rate gains in Hz/Hz.
- Positive and negative derivatives represent excitatory and suppressive
  effective responses, respectively; they need not match the sign or size of
  an anatomical weight because they combine the realized surrogate input,
  projection convergence and synaptic properties, postsynaptic response, and
  operating state. Active recurrent feedback is excluded by the fully frozen
  connection configuration.
- The estimate is local to the target-rate operating point even though the
  fitted Richards curve uses the complete sampled sweep.
- Failed fits remain `NaN` in the matrix. The analysis script currently
  catches all fit exceptions without recording their cause, so fit counts and
  optional diagnostic plots should be checked before using a matrix.
- The current analysis collapses seeds before fitting and does not report
  uncertainty across seeds.
