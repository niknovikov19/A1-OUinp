# Weight-transfer workflow

`wmat_transfer` evaluates how recurrent weight changes affect oscillatory
rate transfer while compensating the affected populations' baseline rates.
It is a two-stage workflow driven by [`run_workflow.py`](../../run_workflow.py):

```text
initial wmat multipliers
        |
        v
DW: sweep compensation current -> median current at each target rate
        |
        v
RR: apply weights and DW currents -> fit oscillatory transfer coefficients
        |
        v
finish_iteration(): save results and choose the next weights or stop
```

## Files

- [`workflow_cfg.py`](workflow_cfg.py) defines the stages, runtime resources,
  initial weights, iteration policy, retention, and cross-stage overrides.
- [`process_dw.py`](process_dw.py) collects average rates, fits current-rate
  curves, and derives population-specific background-current corrections.
- [`process_rr.py`](process_rr.py) collects rate traces and fits complex
  response and transfer coefficients.
- [`__init__.py`](__init__.py) identifies the directory as a Python package.

The actual simulations are defined in these experiment directories:

- [`net_inpsur_dw_var_seed_ibkg`](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_dw_var_seed_ibkg)
- [`net_inpsur_rr_osc_var_seed_pre_f_amp`](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rr_osc_var_seed_pre_f_amp)

## Default configuration

The initial context multiplies the `IT2 -> IT2` connection weight by `2`.
The generated run ID is
`exp_wmat_transfer_niter_1_w_IT2_IT2_2`, and results are written under:

```text
exp_results/workflows/wmat_transfer/<run-id>/
```

The default run has one iteration and 55 simulations:

| Stage | Batch axes | Jobs | Purpose |
| --- | --- | ---: | --- |
| `dw` | 5 seeds x 10 `ibkg_dw_adj` values | 50 | Restore target baseline rates |
| `rr` | 1 seed x 5 input populations x 1 frequency x 1 amplitude | 5 | Measure the transfer matrix |

Each simulation requests one `cpu.q` node with 60 cores, 256 GB of memory,
and a seven-hour limit. At most six simulations run concurrently. Batch and
resource settings can be overridden in the stage dictionaries or by a
reviewed HPC request.

The workflow polls durable job records every 30 seconds with no timeout. It
keeps configuration JSON files but removes NetPyNE parameter JSON and pickle
outputs. Shared Ray checkpoints live in `exp_logs/workflows/ray`.

## Stage 1: DW baseline compensation

The DW stage receives the current iteration's `wmat_multipliers`. Its
experiment sweeps `ibkg_dw_adj` from `-0.1` to `0.1` across seeds 1000-1004
and records average population rates.

`process_dw.py` uses `sim_data_analyzer` to assemble the per-job JSON results
into an xarray dataset. For each required L2 population (`IT2`, `PV2`,
`SOM2`, `VIP2`, and `NGF2`) and each seed, it:

1. Fits a five-parameter increasing Richards curve to rate versus current.
2. Finds the current where the fit crosses the target rate from
   [`target_state_1.csv`](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_dw_var_seed_ibkg/target_state_1.csv).
3. Uses the median crossing across seeds as that population's correction.

Every seed fit must have at least six finite samples, and its fitted curve
must cross the target inside the sampled current interval. A missing
population or crossing fails processing instead of silently extrapolating.

The stage returns a dictionary shaped like
`{"IT2": current, "PV2": current, ...}` and writes:

```text
dw/processed/
├── avg_rates.nc
├── ibkg_intersections.csv
└── fits.png
```

## Stage 2: RR transfer measurement

The RR stage cannot run until DW succeeds. It receives both the iteration's
`wmat_multipliers` and the DW correction dictionary. The experiment applies
those currents as population IClamps, then drives each L2 frozen input
population with a sinusoidal rate. The default grid uses seed 1000, 5 Hz,
and amplitude 15.

`process_rr.py` uses `sim_data_analyzer` to combine the saved rate-vector
NetCDF files. After the configured oscillation onset (`OSC_T0`), it fits each
active output population with sine, cosine, and constant terms at harmonics
1 and 2. If the fitted complex response is `z_out`, the transfer coefficient
is:

```text
z_out / (-i * osc_amp)
```

The resulting dataset retains the batch coordinates (`seed_main`, `pop_pre`,
`osc_f`, and `osc_amp`) and adds `pop_post` and `harmonic`. It contains real
and imaginary response and transfer components, transfer magnitude and
phase, and the first-harmonic baseline rate.

The stage returns the in-memory xarray dataset and writes:

```text
rr/processed/
├── combined_rates.nc
├── transfer_matrix.nc
└── transfer_matrix.csv
```

Rate-dynamics, transfer-matrix, and Welch-PSD plots are implemented but off
by default. Enable them through the RR stage's `processor_params`, using
`plot_rate_dynamics`, `plot_transfer_matrix`, and `plot_psd`.

## Iteration policy

After both stages complete, `finish_iteration()` stores the DW corrections
and the candidate next weight multipliers. The current `get_next_wmat()` is a
placeholder: it returns the existing weights and a stop reason, so the
workflow intentionally stops after the first iteration. Increasing
`MAX_ITERATIONS` alone does not create an update loop; implement the
scientific weight-update rule in `get_next_wmat()` and omit `stop_reason`
when another iteration should run.

## Running and resuming

From the repository root:

```bash
python run_workflow.py --workflow wmat_transfer
```

Use `--run-id <name>` to select a different result directory. The runner can
also read `A1_WORKFLOW_RUN_ID`; the CLI value takes precedence. Re-running
the same command resumes completed stages and processing outputs when their
manifests and hashes are valid.

At run creation, the runner saves resolved parameters and snapshots every
Python file in this directory. A reused run ID must have identical resolved
parameters and workflow-source hashes, so configuration or processor changes
require a new run ID. Each iteration contains immutable stage specifications,
job records, completion manifests, processed artifacts, and a compact
iteration summary:

```text
<run-id>/
├── meta/
│   ├── resolved_params.json
│   ├── state.json
│   └── workflow_source/
└── iterations/iter_000/
    ├── meta/iteration.json
    ├── dw/
    │   ├── meta/
    │   ├── job_meta/
    │   ├── sim_results/
    │   └── processed/
    └── rr/
        ├── meta/
        ├── job_meta/
        ├── sim_results/
        └── processed/
```

Processing is considered resumable only when
`meta/processing_complete.json` has the current stage hash and every declared
output still exists. Deleting a declared processed output causes that stage's
processor to run again on the next invocation.
