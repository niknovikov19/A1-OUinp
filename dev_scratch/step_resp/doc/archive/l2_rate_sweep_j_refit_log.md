# Historical log: L2 presynaptic-rate J investigation and refit

HISTORICAL LOG — completed investigation, not a fitting plan.
The [short J hand-off](../results/l2_rate_sweep_j.md) identifies the selected
artifacts and current limitations. Further fitting remains stopped.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

This completed the J investigation from the
[historical small-step follow-up](../archive/after_small_step_proposals.md).
Further fitting is stopped by user decision. The selected pooled estimate has
23/25 finite entries; a separate prediction copy provisionally zeros only the
two remaining self-gains. No simulations, baseline changes, or subnet-builder
fixes are involved. Historical artifacts remain unchanged.

## Inputs and provenance

The local input cache is copied once to
`data/l2_rate_sweep_j_5seeds/input/rates.nc`. It contains five presynaptic populations,
five seeds (1000–1004), five active plus five swept-frozen rate traces, and
9500 time bins over 1–20 s. These rates were originally extracted with
`sim_data_analyzer` using 2-ms bins and 10-ms smoothing.

The cache's embedded provenance identifies the HPC source:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/
exp_pre_L2_post_L2_nseed_5_npre_5_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5/
combined/data_proc/spikes_1_20.0/
```

The local original is
`exp_results/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/exp_pre_L2_post_L2/combined/data_proc/rates_dt_0.002_tau_0.01.nc`.
The copied file and original both have SHA256
`1643ba06fd8d6f571bbb9ba0b80677fee1baf8df5e531dd7d23510d8b8d0c955`.
The corresponding seed-1000 IT2 job configuration is copied as `input/cfg.json`;
both copies have SHA256
`189bbdeb1e5b80d53feea4d354c4d1426f3a1e3a4effad3071ddd097e75a8dca`.

Historical L2 and ctx matrices/coefficient files are copied into
`input/historical/l2/` and `input/historical/ctx/` for audit, not for splicing
their entries into a new matrix. No remote filesystem scan or spike
re-extraction was needed.

## Diagnosis of the old missing values

The historical local 0.3-s L2 matrix has three missing entries:

| Pair | Coefficient present? | Diagnosis |
| --- | --- | --- |
| PV2 → NGF2 | No | Unbounded historical optimizer failed or produced no saved fit |
| VIP2 → SOM2 | No | Unbounded historical optimizer failed or produced no saved fit |
| VIP2 → NGF2 | Yes | Derivative overflow, not an absent curve fit |

For VIP2 → NGF2, the saved slope/location parameters make the old expression
evaluate an exponential with exponent about 2077 at the target rate. Its
numerator and denominator overflow. Log-space evaluation of the same saved
curve gives the finite derivative **-3.1575e-7 Hz/Hz**. This repairs numerical
evaluation only; it does not establish that the fitted gain is identifiable.

The ctx candidate's three missing L2 entries all have absent coefficients:
PV2 → NGF2, SOM2 → IT2, and NGF2 → VIP2. The ctx rate cache is not the dataset
used for the new L2 refit.

All three old missing L2 pairs have declared nonzero projection rules in
`create_net_params`: seven rules per pair, with nonzero weights and
distance-dependent probability. They cannot be classified as structural
zeros merely because fitting failed. This rule check is not a measurement of
realized synapse counts.

## Refit method

[`code/refit_rate_io.py`](../../code/refit_rate_io.py) fits all 25 pairs from the
same L2 cache. It does not read connected response measurements or optimize
agreement with them.

- Fit from 5–20 s using the measured frozen-population rate as x, as in the
  historical branch; evaluate the derivative at the saved target rate.
- Apply the declared additional rolling window, with 0.2 s as the initial
  primary setting and 0.1/0.4 s as predetermined sensitivity checks.
- Evaluate the Richards curve and its derivative in log space to avoid
  overflow; normalize axes for fitting and use an analytic Jacobian.
- Constrain fitted rates to be nonnegative and monotone with presynaptic
  sign: IT2 increasing, the four inhibitory populations decreasing. This is
  an explicit model assumption, not evidence that a weak noisy curve has a
  nonzero or exactly zero gain.
- Use six initializations. Approximate the full-sample least-squares objective
  with count-weighted x-bin means separately within each seed, initially
  64 bins. These are computational summaries, not independent observations.
- If all five-parameter starts failed, the implementation fitted the nested
  four-parameter logistic model with nu fixed to one and two initializations. Record the reduced
  family explicitly. This is a real lower-complexity fit to the same data,
  not a zero substitution; it does not restore information absent from a
  weak curve.
- Check residuals/R² on all original selected samples, not just bin means.
- Use the known 7.5-s triangle phase to classify rising/falling legs, starting
  at the target rate on the rising leg at 5 s. Exclude 0.1 s around extrema.
- Save branch fits, active-bound diagnostics, near-optimal initialization
  gain ranges, and unconstrained per-seed local linear slopes within ±r0
  and ±2r0. Report local seed variation, not time-bin-based confidence limits.

Each smoothing setting has separate coefficients, diagnostics, figures,
labelled pooled/branch/local matrices, and a hash/settings manifest in
`data/l2_rate_sweep_j_5seeds/processed/`. A failed fit remains explicit; no missing value
is set to zero.

The initial five-parameter-only runs are preserved in
`processed/initial_richards5/`. That run converged for 23 of 25 pooled pairs at 0.2 s,
including the old three missing entries. SOM2 → SOM2 and NGF2 → NGF2 did not
converge. Runs with the reduced-model fallback have now finished at all three
smoothing settings. The primary 0.2-s pooled matrix still has these two missing
entries; its original three historical gaps have finite, weakly identified
estimates. The 0.1/0.2/0.4-s pooled matrices have 23/23/24 finite entries.

The user requested no further fitting improvements and provisional zero
substitution for the two primary gaps. The original matrices are unchanged;
`analysis/jmat_pooled_zero_filled.nc` contains the separate prediction copy.
The resulting quick J-Q comparison and exact substitutions are documented in
[the prediction note](../archive/connected_steps_2seeds_5pa_prediction.md). No claim of structural
absence or reliable gain identification follows from these substitutions.

## Optional reproduction reference — fitting remains stopped

The code below reproduces the completed refit, not merely the prediction.
It is retained for audit; no rerun is requested. Execution would regenerate
fit outputs and requires a separate user request despite its presence here.
The working directory would be the repository root, using the existing environment.

```bash
# Historical refit reproduction, not a pending task
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/refit_rate_io.py
```

The recorded sensitivity settings were `--smooth-win 0.1` and `--smooth-win 0.4`. No packages
are installed. Synthetic tests check stable evaluation of the historical
overflow case, the analytic Jacobian, signed derivative recovery, and
triangle-phase masks.

[`code/analyze_j_refit.py`](../../code/analyze_j_refit.py) audits the old artifacts
and implements strictly labelled `solve(I - J, Q @ h)` sensitivity analysis.
It rejects non-finite matrices, does not fill them, and labels any completed
model-conditioned predictions provisional. Input-first J and Q are both
transposed by coordinate names, with tests checking shuffled population
labels and rejection of missing values.

Passing `--zero-missing` explicitly creates the separate zero-filled primary
matrix before solving; it records changed coordinates and source hashes.
The solver itself still rejects any remaining non-finite input. A test checks
that explicit filling preserves the original matrix and every finite gain.
