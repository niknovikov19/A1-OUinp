# Quick L2 J-Q prediction

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Completed on 2026-10-14 using existing local data. Further fitting improvements
are stopped at the user's request; no simulation or baseline component changed.

## Matrices and calculation

- J: five-seed L2 r-r refit, pooled triangle branches, 0.2-s smoothing,
  `data/l2_rate_sweep_j_5seeds/processed/tau_0.2_bins_64/jmat_pooled.nc`.
- Set only the two missing gains, SOM2 → SOM2 and NGF2 → NGF2, to zero in
  `data/l2_rate_sweep_j_5seeds/analysis/jmat_pooled_zero_filled.nc`. Preserve every finite
  gain and the original matrix. These zeros are provisional assumptions,
  not evidence of absent connections.
- Q: `data/l2_current_sweep_5seeds_pm100pa_t40s/processed/tau_0.2/qmat.nc`, unchanged.
- Align populations by labels, transpose both saved input-first matrices,
  then calculate `delta_r = solve(I - J, Q @ h)`.
- Use the actual step vectors saved in the connected pilot results. No fit
  or model setting was chosen by agreement with those results.

The condition number of `I - J` is 51.69. This is a provisional point
prediction, not a validated J or a confidence interval.

## Predicted rate changes

All values below are Hz for +0.005 nA to the named group. Negative steps
have exactly the opposite prediction in this linear model.

| Input group | IT2 | PV2 | SOM2 | VIP2 | NGF2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| IT2 | 0.10175 | 0.69266 | 0.16760 | 0.05246 | 0.00610 |
| PV2 | -0.00308 | 0.92017 | -0.00960 | -0.02332 | -0.00068 |

The Q-only own-population predictions are +0.10384 Hz for IT2 input and
+0.94064 Hz for PV2 input. The main predicted recurrent effect here is the
IT2-driven response in PV2, rather than a large change in own-population gain.

## Comparison with the first pilot

The pilot has two seeds and ±0.005-nA steps. Selected seed-mean contrasts:

| Input | Output | Prediction | Specified post contrast | Drift-adjusted contrast |
| --- | --- | ---: | ---: | ---: |
| IT2 +0.005 | IT2 | 0.102 | 0.215 | 0.166 |
| IT2 +0.005 | PV2 | 0.693 | 1.192 | 0.523 |
| PV2 +0.005 | PV2 | 0.920 | 1.708 | 1.288 |
| IT2 -0.005 | PV2 | -0.693 | 2.073 | 1.004 |
| PV2 -0.005 | PV2 | -0.920 | 2.181 | -0.254 |

The positive IT2-driven PV2 response is compatible with the predicted scale,
but negative-step responses are not a clean sign-symmetric check. Control
variation, unmatched pre-step activity, and incomplete settling remain large
relative to the signals. See [the pilot analysis](connected_steps_2seeds_5pa_results.md)
and [the deferred reproducibility issue](../issues/same_seed_reproducibility.md).

Mean per-seed/condition five-population RMSE is 1.070 Hz for J-Q versus
1.031 Hz for Q-only using specified post contrasts, and 0.722 versus 0.670 Hz
using drift-adjusted contrasts. This noisy pilot does not demonstrate a J-Q
improvement; it also does not provide a decisive rejection of the predictor.
No uncertainty/significance claim is made from two seeds.

## Files and repeat command

All outputs are local under `data/l2_rate_sweep_j_5seeds/analysis/`:

- `jmat_pooled_zero_filled.nc`: the primary prediction matrix.
- `pilot_comparison.csv`: predictions and measured contrasts for each seed.
- `comparison_errors.csv`: per-seed/condition vector errors against Q-only.
- `conditional_predictions.csv`: primary and already available complete
  alternative matrices, explicitly labelled by model.
- `prediction_vs_pilot.png`: grid-free comparison; observation bars are seed
  SD, and the model-sensitivity range is not a confidence interval.
- `manifest.json`: exact zeroed coordinates, input/script hashes, and caveats.

```bash
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_j_refit.py --zero-missing
```

Three prediction tests pass: matrix label alignment/transposition, strict
non-finite rejection, and explicit zero filling without modifying the source.

## Next simulation

Update: the user selected ±0.03 nA rather than the initial ±0.02-nA proposal
below, retaining the 100-s timings and twelve-trial grid. That configuration
has been applied and submitted; see [the second-pilot run note](connected_steps_2seeds_30pa_execution.md).
The following paragraph records the original proposal, not the active settings.

Move to a measurement-quality connected pilot, without more fitting. A
concrete small next run would use 100 s total, step onset at 40 s, baseline
10–40 s, response 60–100 s, and early/late response halves of 60–80/80–100 s.
Keep the two seeds and IT2/PV2/control groups, but use ±0.02 nA: still 12
trials under the current child limit. Retain the ordinary redundant control
runs across amplitudes and existing HPC resource/concurrency settings.

The provisional model then predicts IT2 input → IT2/PV2 changes of
±0.407/±2.771 Hz and PV2 input → PV2 changes of ±3.681 Hz. This is a fourfold
signal increase, at the cost of a less local linearity test. The longer
baseline, 20-s post-step settling, and 40-s averaging should improve the
measurement but cannot guarantee stationarity or repair same-seed matching.
The final agreed amplitude and launch status are recorded in the run note above.
