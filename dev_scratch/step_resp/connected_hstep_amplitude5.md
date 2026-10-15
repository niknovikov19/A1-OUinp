# Connected L2 amplitude-scaling experiment

Protocol: [amplitude-test specification](connected_hstep_amplitude_test.md).
Request: [`hstep-l2-amplitude5.json`](../../hpc_jobs/requests/hstep-l2-amplitude5.json).
Run ID: `hstep-l2-amplitude5-001`. Local dataset: `data/l2_hstep_amplitude5/`.

## Configuration and preflight

- Five seeds: 1000–1004; groups IT2, PV2, and ordinary empty control.
- Signed amplitudes: −0.03, −0.015, +0.015, +0.03 nA.
- Sixty fresh trials: 40 current-step trials and 20 zero-input controls.
- Duration 100 s; step onset 40 s; baseline 10–40 s; response 60–100 s,
  with early/late halves 60–80 and 80–100 s.
- Thirty ranks and 128 GB per child; concurrency ten. Controller: two cores
  and 16 GB. No baseline calibration, connectivity, or identification fits change.
- Scientific preflight resolves the correct folder and all 60 jobs. Three
  experiment tests pass; four controller-index tests pass, including a 60-job
  index larger than 64 KiB. The writer now uses the same 1-MiB index budget
  as the protected readers; no protected-helper promotion is required for
  this repository controller change.

HPC result directory:

```text
/ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/exp_L2_pilot3_nseed_5_ngroup_3_namp_4_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5/
```

## Execution

Submitted through the protected helpers as controller **118098**, run
`hstep-l2-amplitude5-001`, from simulation commit
`62ca1df1af4bd32b25081e6c43b5bbaa58924397`.
Submission time: 2026-10-15 00:37:04 America/New_York
(2026-10-15 04:37:04 UTC). Protected preparation accepted the 60-child request
and its exact output contract. All 60 children (118099–118158) and the controller
were observed **COMPLETED at 05:13:34 UTC**, about **36 min 30 s** after
submission. This is elapsed time to the completed observation, not an exact
Slurm finish timestamp. Saved simulation `totalTime` averages 297 s per trial
(range 251–327 s), excluding controller scheduling/launch overhead.
Sampled child stdout confirms `numprocs=30`. Finalization passed at 05:13:47 UTC
with all 241 required files verified; the checkout lock was released at
05:13:53 UTC. No failed or cancelled children were observed.

Chunked status/log monitoring and archive handoff worked on the full 60-job
batch. The archive helper transferred **8,505,762 bytes** (8.51 MB), containing
**119,808,046 bytes** (119.81 MB) in 241 compact outputs. It verified the archive
checksum and per-file manifest while unpacking. Archive SHA256:
`a31e6b21a494a37ac711d102e59b25ff4ff6512254070e1965185807555aa7e7`.
The remote archive is
`/ddn/niknovikov19/hpc_codex/state/A1_OUinp/result-archives/hstep-l2-amplitude5-001.tar.gz`.
Raw simulation files remain on HPC.

## Processing

Completed locally using the existing NetPyNE environment and saved
`sim_data_analyzer` rate caches, retaining both control-subtracted response
definitions and all seeds. The input symlink points to the verified helper
cache at `exp_results_local/hpc_codex/hstep-l2-amplitude5-001/compact/`.
Its `archive_manifest.json` records original HPC paths and individual hashes.

Keep exactly the prior pooled J (with its two requested provisional zeros)
and the slow symmetric Q. Record their byte hashes and compare them with the
second-pilot prediction manifest before calculating the new-amplitude
predictions. No refitting or parameter tuning against these new responses.
Produce signed-amplitude summaries, per-seed central slopes and sign symmetry,
half-amplitude/full-amplitude comparisons, early/late diagnostics, and smoothed
rate dynamics with seed overlays and static prediction levels. All figures
have grids disabled and omit the initial transient from rate-trace scaling.

## Local repeat commands

After the archive helper creates its verified local `compact/` cache, expose
that directory as `data/l2_hstep_amplitude5/input/` with a local symlink.
This avoids a second physical copy of the 120-MB input set. Source paths in
the embedded archive manifest remain real HPC paths.

Run these commands from the repository root in the existing NetPyNE environment:

```bash
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/analyze_hstep.py \
  --input-dir dev_scratch/step_resp/data/l2_hstep_amplitude5/input \
  --output-dir dev_scratch/step_resp/data/l2_hstep_amplitude5/analysis \
  --qmat dev_scratch/step_resp/data/l2_sym_slow_pilot/processed/tau_0.2/qmat.nc

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/predict_hstep_static.py \
  --data-dir dev_scratch/step_resp/data/l2_hstep_amplitude5

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/summarize_hstep_amplitudes.py \
  --data-dir dev_scratch/step_resp/data/l2_hstep_amplitude5

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python dev_scratch/step_resp/code/plot_hstep_dynamics.py \
  --data-dir dev_scratch/step_resp/data/l2_hstep_amplitude5
```

The frozen matrix hashes, verified before submission, are:

- J: `9c1f64bd1f71130d4ec1fe1cd34215979037d93f53c2f8528c81d4705bf7cdd3`.
- Q: `f575dc2f9c12100877196e1f62c3f2567fcd8ed8a5a8df6a435327fa0a73c97c`.

The fixed-matrix predictor checks these against the prior pilot manifest,
preserves byte-identical copies in the new analysis directory, and rejects
unexpected changes. Plot captions derive the seed count from the data.

## Validation and where to look

All 60 trials pass waveform, units, finite-rate, clamp-count, spike-count,
window, and within-seed baseline-configuration checks. There are 20 physically
zero-input controls and 200 nonzero-trial/population observations. As in the
earlier pilots, same-seed pre-step traces and zero-input repeats are **not
identical**. Exact paired-noise cancellation is therefore unavailable; this
known reproducibility issue remains deferred, not fixed by the new batch.

Outputs under [`data/l2_hstep_amplitude5/analysis/`](data/l2_hstep_amplitude5/analysis/):

- `validation.json`: protocol checks and same-seed mismatch diagnostics.
- `response_estimates.csv`: raw window means and both response definitions.
- `jq/manifest.json`: unchanged J/Q provenance and provisional zero entries.
- [`jq/prediction_vs_pilot.png`](data/l2_hstep_amplitude5/analysis/jq/prediction_vs_pilot.png):
  circles are seed means, error bars are seed SD, green stars are J–Q predictions,
  grey crosses are Q-only predictions. Blue circles subtract post-step control
  rates; orange circles subtract the controls' before/after changes from the
  step runs' before/after changes. All are **changes**, not absolute rates.
- [`jq/amplitude_summary/drift_adjusted_hz.png`](data/l2_hstep_amplitude5/analysis/jq/amplitude_summary/drift_adjusted_hz.png):
  each colored dot is one seed's before/after change minus the average
  before/after control change for that seed. Dashed lines are the fixed J–Q
  prediction, not fits to these dots. `matched_post_hz.png` instead subtracts
  the post-step control with the same seed and amplitude label.
- `jq/amplitude_summary/half_amplitude_checks.csv`: per-seed
  `response(A/2) - response(A)/2`, separately for positive/negative input;
  zero is the linear-scaling expectation. The summary reports seed mean/SD.
- [`jq/rate_dynamics/`](data/l2_hstep_amplitude5/analysis/jq/rate_dynamics/):
  eight figures, one per stimulated group/amplitude, five population panels,
  five seed overlays and the actual applied current. Traces are **absolute
  rates** smoothed with a centered 0.5-s moving average for display only,
  shown from 10 s. Blue/orange/green/red/purple denote seeds 1000–1004.
  Matching dashed lines show each trial's raw 10–40 s baseline plus the same
  pooled static predicted change, from 40–100 s. They are static endpoints,
  not predictions of the transient or of the noise. No control correction
  is added to these line heights. Exact levels are in `prediction_levels.csv`.

Independent checks confirm all 40 predicted condition/population values match
`solve(I - J_saved.T, Q_saved.T @ h)`, and all 200 dynamics-line baselines
match their own trial's saved baseline. Output tables have the expected
counts and finite numeric values. All eight dynamics figures and the summary
figures were inspected for step timing, prediction placement, vertical ranges,
legends, compact spacing, and disabled grids. The local analysis suite passes
20 tests. Display smoothing is never used to calculate window means or errors.

## Findings

Measured changes below use before/after differences with the average control
change subtracted, in Hz; ± is SD across five seeds, not confidence intervals.
J and Q were not refitted to this batch.

| Input group | Current (nA) | Measured IT2 | Predicted IT2 | Measured PV2 | Predicted PV2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| IT2 | −0.030 | −0.497 ± 0.062 | −0.610 | −2.666 ± 0.291 | −4.156 |
| IT2 | −0.015 | −0.370 ± 0.073 | −0.305 | −2.150 ± 0.384 | −2.078 |
| IT2 | +0.015 | +0.331 ± 0.081 | +0.305 | +1.655 ± 0.751 | +2.078 |
| IT2 | +0.030 | +0.581 ± 0.147 | +0.610 | +3.618 ± 1.014 | +4.156 |
| PV2 | −0.030 | −0.024 ± 0.060 | +0.018 | −4.623 ± 0.549 | −5.521 |
| PV2 | −0.015 | +0.032 ± 0.052 | +0.009 | −2.356 ± 0.704 | −2.761 |
| PV2 | +0.015 | −0.021 ± 0.061 | −0.009 | +2.603 ± 0.437 | +2.761 |
| PV2 | +0.030 | −0.034 ± 0.073 | −0.018 | +6.207 ± 1.211 | +5.521 |

Across the 40 seed/condition vectors, mean five-population RMSE is **0.403 Hz
for J–Q versus 0.799 Hz for Q-only** with before/after control subtraction.
With post-step control subtraction it is **1.273 versus 1.322 Hz**. These are
descriptive averages of per-vector RMSE, not RMSE of the mean response or
formal validation scores. The feedback benefit is mainly the IT2-driven
responses; PV2-driven J–Q and Q-only predictions are already quite similar.

Half amplitude improves agreement for negative IT2→PV2, but the measured curve
is not simply proportional: at −0.015 nA the response is −2.150 Hz, whereas
half the −0.03-nA response is −1.333 Hz. Their per-seed difference is
**−0.817 ± 0.331 Hz**. The direct IT2 response shows the same direction of
departure (**−0.121 ± 0.071 Hz** for that scaling check). PV2's own negative
response scales much more closely (**−0.045 ± 0.805 Hz**); its positive
scaling difference is **−0.500 ± 0.872 Hz**. This suggests amplitude-dependent
gain, particularly on the negative IT2 branch, without resolving its cause.

Positive IT2 input also produces the expected SOM2 increase: +0.644 ± 0.247 Hz
at +0.015 nA and +1.048 ± 0.474 Hz at +0.03 nA, versus +0.503 and +1.006 Hz
predicted. VIP2/NGF2 and PV2-driven cross-population changes are generally
small relative to seed variation, so agreement there is weak evidence.

There is no consistent large late PV2 ramp across these five seeds: after
subtracting the controls' late-minus-early change, condition means range
−0.294 to +0.363 Hz, with seed SD 0.344–1.179 Hz. This is not proof of a fully
settled endpoint; slow variability remains visible, including modest SOM2
early/late differences. Keep both response definitions and the controls visible.

Overall: a useful independent static-prediction test, with a clear feedback
signal but a reproducible large-negative-IT2 discrepancy. Inspect these results
before choosing another batch; no further simulations or fitting are launched.
