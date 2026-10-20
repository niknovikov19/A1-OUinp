# Static J–Q prediction and measurement contract

CURRENT CONTRACT — matrices are frozen; further fitting is stopped.

## Frozen predictor

J: five-seed L2 presynaptic-rate refit, 0.2-s smoothing, 64 input bins, pooled
triangle branches. The original has 23 finite entries. Only SOM2→SOM2 and
NGF2→NGF2 are provisionally zero-filled in a separate prediction copy, by user
decision. These are not measured structural zeros; preserve the incomplete fit.

Q: five-seed symmetric ±0.1-nA current sweep, T = 40 s, 0.2-s smoothing.
Both matrices pool seeds; there is no seed-specific J/Q. Locations and original
names are in the [registry](../../data/registry.md).

| Frozen input | SHA256 |
| --- | --- |
| J prediction copy | `9c1f64bd1f71130d4ec1fe1cd34215979037d93f53c2f8528c81d4705bf7cdd3` |
| Q | `f575dc2f9c12100877196e1f62c3f2567fcd8ed8a5a8df6a435327fa0a73c97c` |

Align labels, then `dr_pred = solve(I - J_saved.T, Q_saved.T @ h)`.
Q-only predicts Q_saved.T @ h, ignoring feedback. Do not tune/splice/select
matrices or clip predictions to improve agreement. cond(I − J) ≈ 51.69 does
not itself establish dynamical stability.

## Measurements

Use raw spike-count window means, not display smoothing. Retain both definitions:

- Post-step subtraction (matched_post_hz): treatment response minus control
  response with the same seed and stored amplitude label.
- Before/after subtraction (drift_adjusted_hz): treatment (response − baseline)
  minus the average control (response − baseline) within seed.

The latter subtracts the change also observed without input. It does not fix
the baseline or relocate derivatives to the connected operating point. Controls
are not exact replicas. Pool duplicate controls within seed; they are not extra
network seeds. Show individual seeds and descriptive seed SD, not confidence
intervals inferred from smoothed time samples.

## Figures

Static comparison: rate changes in Hz; blue circles = post-step subtraction,
orange circles = before/after subtraction, green stars = J–Q, grey crosses =
Q-only. Bars are measured seed SD. No grey prediction band. Signed-amplitude
panels instead color dots by seed; the dashed line is fixed prediction, not a fit.

Dynamics: absolute rates from 10 s, centered 0.5-s display-only moving average,
seed colors at alpha 0.6. Each dashed line is that trial's raw pre-step baseline
plus pooled dr_pred, during the step only. No control drift is added; it is a
static endpoint, not a transient/noise prediction. Include aligned current strip,
onset markers, independent population y limits, compact spacing, and no grids.

Check settling, sign symmetry, half/full-amplitude scaling, operating-point
differences, and estimator sensitivity. Weak gains, NGF2 hysteresis, provisional
zeros, and unmatched controls prevent claiming complete validation.
