# Connected L2 first-pilot analysis

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

The twelve simulations completed and all declared outputs passed protected
finalization. The current steps and saved rate/count data are internally
consistent. Responses can be analyzed descriptively, but the small probe,
two-seed sample, baseline offsets, and response-window variation do not yet
give a precise test of static J-Q predictions.

The [same-seed reproducibility issue](../issues/same_seed_reproducibility.md) is
documented separately; its fix is deferred. No simulation or calibrated
baseline component was changed during this analysis.

## Dataset and processing

Run: `hstep-l2-first-pilot-002`, controller `118061`, simulation commit
`2431fe2a4faea65df7164748398c60baba3d6a26`. Two seeds (1000 and 1001),
`IT2` / `PV2` / empty-group inputs, and -0.005 / +0.005 nA give twelve trials.
All five L2 populations are active and recurrent, including within-population
connections; outside-L2 inputs remain frozen surrogates.

The trial phase took 6 min 24 s, excluding controller initialization and
queueing. Saved NetPyNE `totalTime` ranges from 93.93 to 165.22 s per trial.
Children requested 30 ranks and 128 GB, with concurrency five. The protected
helper verified twelve completed children, a completed controller, and all 49
required files before releasing the active-run marker.

The actual HPC directory is in the automation checkout, not the manual
`A1_OUinp` checkout:

```text
/ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/
batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
exp_L2_pilot1_nseed_2_ngroup_3_namp_2_dur_40_step_t0_20_tresp_30_gset_1pop_v1_amin_-0.005_amax_0.005_ictrl_wmult_0.25_ee_0.5/
```

The ignored local dataset is `data/_old/l2_connected_steps_2seeds_5pa_40s/`:

```text
input/
    cfg/                 # Twelve job configurations
    results/             # Twelve compact count/rate summaries
    rvec_xr/             # Twelve unsmoothed population-rate traces
    hvec_xr/             # Twelve declared current traces
    rvec_figs/           # Original twelve HPC figures
    jobs_index.jsonl     # Child IDs and parameters
analysis/
    input_manifest.json
    validation.json
    window_rates.csv
    trial_window_summary.csv
    seed_control_summary.csv
    matched_contrasts.csv
    response_estimates.csv
    response_summary.csv
    central_slopes.csv
    q_reference.json
    j_audit.json
    zero_input_repeats.png
    rate_overview.png
    static_response_contrasts.png
```

The 61 inputs total 12,007,256 bytes and were copied once through the read-only
mount and checked against source SHA256 hashes. PKLs, network parameters,
rasters, and logs were not bulk-copied. The manifest records actual HPC paths;
subsequent analysis uses local files only.

HPC `post_run()` used `sim_data_analyzer` to extract raw 5-ms rate bins and
population spike counts. Local [`code/analyze_hstep.py`](../../code/analyze_hstep.py)
validates currents, instantiated-clamp counts, raw bin means versus saved
spike-count means, and early/late count additivity. All checks pass. Cell
counts are IT2 338, PV2 13, SOM2 5, VIP2 16, and NGF2 11. Four local analysis
tests pass. Figures have no axes grid and use 0.5-s display-only smoothing;
none of the estimates use that smoothing.

## Response definitions

The simulation lasts 40 s, the step starts at 20 s, and measurement windows
are baseline 10–20 s and response 30–40 s. Early/late windows are 30–35 s and
35–40 s. All endpoints are half-open.

Three descriptive contrasts are retained:

1. **Specified post-rate contrast:** treatment response minus the
   same-seed/amplitude zero-input response, as proposed before running.
   Because traces are not matched, this has no demonstrated common-noise
   cancellation.
2. **Pooled-control post-rate contrast:** treatment response minus the mean
   of both physical zero-input responses within that seed. The controls'
   amplitude coordinates do not change their applied currents.
3. **Drift-adjusted pre/post contrast:** treatment's own response-minus-baseline
   change, minus the mean zero-input response-minus-baseline change within
   that seed. This is a sensitivity analysis, not a replacement for the
   specified estimand or a correction to the simulation baseline.

Means and SDs are computed across the two seed-level estimates. The four
controls are first pooled within their two seed blocks; they are not treated
as four independent network seeds. SD error bars are descriptive, not
confidence intervals. Smoothed time samples are not independent replicates.

## Connected baseline operating point

Means across seed-pooled zero-input controls, in Hz:

| Population | Identification target | Baseline 10–20 s | Response 30–40 s | Control pre/post change |
| --- | ---: | ---: | ---: | ---: |
| IT2 | 2 | 1.971 | 1.867 | -0.104 |
| PV2 | 12 | 10.058 | 8.865 | -1.192 |
| SOM2 | 6 | 5.070 | 4.355 | -0.715 |
| VIP2 | 7 | 6.298 | 6.039 | -0.259 |
| NGF2 | 1 | 1.016 | 1.039 | +0.023 |

The connected zero-input operating point is not exactly the frozen-rate
identification point: late PV2 and SOM2 rates are about 26% and 27% below
their targets. Control drift is also substantial relative to this probe's
direct expected effects. Its cause is not inferred from two seeds. Existing
J/Q derivatives are not automatically relocated to these measured rates, and
no background/current/surrogate retuning was performed.

## Same-population responses and sensitivity to baseline handling

Mean rate changes, in Hz. The final column is mean ± SD across two seeds:

| Input | h (nA) | Direct Qh reference | Specified post contrast | Pooled post contrast | Drift-adjusted pre/post |
| --- | ---: | ---: | ---: | ---: | ---: |
| IT2 | -0.005 | -0.104 | -0.072 | -0.002 | +0.070 ± 0.166 |
| IT2 | +0.005 | +0.104 | +0.215 | +0.145 | +0.166 ± 0.029 |
| PV2 | -0.005 | -0.941 | +2.181 | +1.873 | -0.254 ± 1.751 |
| PV2 | +0.005 | +0.941 | +1.708 | +2.015 | +1.288 ± 2.127 |

The positive IT2 response is of the same order as Qh. The PV2 direct effect
is roughly 0.94 Hz, whereas baseline offsets, control differences, and drift
can be several Hz. For the negative PV2 step, the positive post-only contrast
changes sign under drift adjustment. This is not sufficient evidence of a
paradoxical connected response or of a failed Q estimate.

The positive PV2 specified contrast happens to have a small seed SD, but its
mean changes from 1.708 to 2.015 to 1.288 Hz across the three definitions; the
small SD of one contrast alone is not a robust precision claim.

## Full population response vectors

Drift-adjusted mean changes, in Hz; seed-level values and SDs are retained in
the CSVs and [contrast figure](../../data/_old/l2_connected_steps_2seeds_5pa_40s/analysis/static_response_contrasts.png):

| Input | h (nA) | IT2 | PV2 | SOM2 | VIP2 | NGF2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| IT2 | -0.005 | +0.070 | +1.004 | -0.205 | +0.975 | +0.018 |
| IT2 | +0.005 | +0.166 | +0.523 | +0.665 | +0.356 | +0.009 |
| PV2 | -0.005 | +0.058 | -0.254 | +0.185 | +0.428 | -0.032 |
| PV2 | +0.005 | +0.136 | +1.288 | -0.255 | +0.475 | +0.041 |

Some responses do not reverse between negative and positive input. With only
two seeds and unmatched baselines, the even component can include drift and
sampling variation as well as nonlinearity; it is not a clean feedback
signature. Do not interpret these means as a fitted connected gain matrix.

## Early/late response-window comparison

The [rate overview](../../data/_old/l2_connected_steps_2seeds_5pa_40s/analysis/rate_overview.png) shows all
traces from 10–40 s, with step onset and the response interval marked.
For negative PV2 input, PV2 falls from 12.60 to 9.31 Hz between early and late
response windows for seed 1000, and from 12.23 to 8.82 Hz for seed 1001.
The late-minus-early differences are -3.29 and -3.42 Hz, averaging -3.35 Hz.
Positive PV2 input also has a mean PV2 late-minus-early difference of -1.70 Hz.

These differences exceed the direct Qh scale of this probe. A uniform settled
endpoint is not demonstrated by the current 40-s pilot. The checks do not
separate remaining adaptation/settling from finite-window stochastic
variation; no dynamic model or oscillatory analysis was fitted.

Symmetric plus/minus slopes are saved only as exploratory diagnostics. For
the PV2-to-PV2 slope they are -47.31, +14.23, and +154.23 Hz/nA under the
specified, pooled, and drift-adjusted definitions, respectively. That
estimator sensitivity prevents treating one of them as a precise transfer
gain. The drift-adjusted IT2-to-IT2 slope is 9.60 ± 19.48 Hz/nA, also poorly
constrained by two seeds.

## Prediction references and remaining limitation

The declared Q reference is
`data/l2_current_sweep_5seeds_pm100pa_t40s/processed/tau_0.2/qmat.nc`, aligned by population labels.
Its input-first matrix is transposed before computing `Q_saved.T @ h`.
`q_reference.json` records the file hash and orientation. Grey crosses in the
contrast figure show this open-loop reference, not connected predictions.

No numerical `solve(I - J, Q @ h)` comparison was performed. The audited L2
J candidates still have three non-finite entries each:

- `exp_pre_L2_post_L2/combined/results/wmat_tau_0.3.nc`: PV2 → NGF2,
  VIP2 → SOM2, VIP2 → NGF2.
- `ctx/wmat_tau_0.2.nc`, restricted to L2: PV2 → NGF2, SOM2 → IT2,
  NGF2 → VIP2.

Their common root is
`exp_results/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/`.
`j_audit.json` records exact paths, hashes, and missing entries. No values were
filled with zero, combined across candidates, or refitted to this pilot.

## Reproduce locally

From the repository root, with no new dependencies and no remote reads:

```bash
MPLCONFIGDIR=.mplcache /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_hstep.py \
  --input-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_5pa_40s/input \
  --output-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_5pa_40s/analysis \
  --qmat dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s/processed/tau_0.2/qmat.nc \
  --audit-jmat exp_results/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/exp_pre_L2_post_L2/combined/results/wmat_tau_0.3.nc \
  --audit-jmat exp_results/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/ctx/wmat_tau_0.2.nc
```

The initial copy used `--verify-source` and `--hpc-root` once to create the
input manifest. Omit those flags when reprocessing the verified local copy.
