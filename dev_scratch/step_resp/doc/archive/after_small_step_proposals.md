# Next steps after the first connected L2 pilot

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Current follow-up: [L2 amplitude-scaling test](step_scaling_batch_design.md)
supersedes this historical plan after completion of the second pilot. It
keeps J/Q fixed and records the 60-child batch and resource/copy estimates.

Status: implementation started on 2026-10-14. The current pilot is a useful
setup test, but is not a precise validation or refutation of static J-Q
prediction. Its signals are small relative to variation, its response window
is not uniformly stationary, and numerical feedback prediction still lacks a
complete validated J.

Update: the user requested stopping fitting improvements and using provisional
zeros for the two remaining missing J entries. This overrides the original
no-filling gate below. The quick prediction is completed in
[the J-Q result note](connected_steps_2seeds_5pa_prediction.md); move next to choosing
the follow-up simulation parameters, not further fitting. The user subsequently
selected ±0.03 nA with the proposed 100-s protocol; see
[the second-pilot run note](connected_steps_2seeds_30pa_execution.md) for the active run.

## Fixed boundaries

- Keep rx, external surrogate inputs, ibkg/rate-control corrections, membrane
  calibration, and other baseline components unchanged.
- Keep the same-seed reproducibility fix deferred as described in
  [the issue note](../issues/same_seed_reproducibility.md). Do not edit the
  companion subnet-builder repository.
- Work locally in `code/` using the existing NetPyNE environment; install no
  dependencies. Use existing compact rate caches rather than re-extracting
  large simulation PKLs.
- Preserve historical matrices, coefficients, and simulation output. Put
  revised fitting inputs/results under a new ignored `data/` dataset and
  record their provenance.
- For the quick prediction, explicitly set missing SOM2 → SOM2 and NGF2 → NGF2
  gains to zero in a separate matrix, as requested. These are provisional
  assumptions, not structural zeros. Preserve original fits and do not tune
  fitting choices to improve agreement with the connected pilot.

## 1. Resolve J's missing entries using existing r-r data

This investigation is finished for now; no more fitting improvements are planned.

1. Trace the local L2 and full-cortex candidates to rate caches,
   configurations, and coefficient files. Distinguish absent fits, failed
   derivatives, numerical failures, and genuinely uninformative curves.
2. Inspect the problematic input-output curves, target-rate coverage,
   smoothing, seed variability, and rising/falling branches.
3. Implement a reproducible local r-r refit in `code/`, semantically parallel
   to the h-r fitter. Use numerically stable evaluations and justified fitting
   constraints/initializations where appropriate; retain explicit failure and
   uncertainty diagnostics.
4. Refit one consistent L2 dataset, not just substitute missing entries from
   another candidate. Save labelled matrices, all pair diagnostics, grid-free
   figures, settings, input hashes, and code identity separately from history.
5. Check finite values, signs, target-rate interpolation, parameter-bound
   effects, fitting/branch sensitivity, and reproducibility on synthetic and
   actual data. A finite matrix is not sufficient evidence of reliable gains.
6. Completed under the user's revised instruction: evaluate the declared Q
   with `solve(I - J, Q @ h)` using the explicitly zero-filled primary J.
   Record substitutions, conditioning, and operating-point limitations.

## 2. Design a small measurement-quality follow-up pilot

After inspecting the provisional J-Q prediction and its signal scale:

- Consider 80–120 s simulations with a longer pre-step baseline, a longer
  post-step settling interval, and roughly 30–40 s response averaging.
- Consider signed steps around ±0.01 or ±0.02 nA, provided the identification
  curves support an adequately local approximation. These are candidate
  values, not finalized experiment parameters.
- Retain zero-input controls and both signs. Compare early/late response
  intervals and preserve individual seed results.
- Keep the connected zero-input operating-point mismatch visible; do not
  retune the baseline to force it to the identification target.
- While reproducibility repair is deferred, do not assume same-seed controls
  cancel stochastic noise. Retain seed blocks and report descriptive
  contrasts/control variation explicitly.

Do not launch a new simulation merely as part of the local J investigation.
Settle timings, amplitudes, and the bounded pilot grid after reviewing that
investigation; retain existing HPC resource/concurrency policy unless changed
through the established Gate-B procedure.

## 3. Replication and amplitude scaling

Once a usable endpoint is demonstrated, increase to at least five seeds and
compare more than one amplitude under a common protocol. Examine the response
divided by amplitude, positive/negative symmetry, and estimator sensitivity
before scaling to more populations. Do not treat smoothed time bins as
independent observations or claim narrow uncertainty from two seeds.

The large-batch helper refactor remains postponed. Its plan is separate in
[`../hpc/status_scaling_refactor_plan.md`](../../../hpc/status_scaling_refactor_plan.md).
