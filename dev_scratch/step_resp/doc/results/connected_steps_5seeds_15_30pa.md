# Connected L2 step prediction: essential hand-off

**Completed experiment and analysis.** This page summarizes saved results;
it does not request a new run, reanalysis, fitting, or file transfer.

## What was tested

The connected five-population L2 model received additional somatic current in
IT2 or PV2. Seeds 1000–1004, amplitudes ±0.015/±0.03 nA, and an ordinary empty
control group gave 60 trials. All L2 recurrence remained active; baseline
currents, surrogate inputs, and calibration were unchanged.

Each simulation lasted 100 s: step onset 40 s, baseline 10–40 s, response
60–100 s, early/late checks 60–80/80–100 s. Rates came from raw spike counts;
all trials passed current-delivery and count-consistency checks.

The prediction used the previously selected five-seed pooled J and Q, not a
fit to these connected results: `dr = solve(I - J, Q @ h)`. Saved matrices are
input-first and are transposed after label alignment. J retains the two
user-requested provisional zero self-gains, SOM2 and NGF2.
[Exact matrix selection and measurement definitions](../contracts/static_prediction.md).

## Main findings

The following PV2 changes subtract the controls' average before/after change
from the step run's before/after change. Values are mean ± seed SD, in Hz.

| Current into IT2 (nA) | Measured PV2 change | J–Q prediction |
| --- | ---: | ---: |
| −0.030 | −2.666 ± 0.291 | −4.156 |
| −0.015 | −2.150 ± 0.384 | −2.078 |
| +0.015 | +1.655 ± 0.751 | +2.078 |
| +0.030 | +3.618 ± 1.014 | +4.156 |

Mean five-population prediction error across 40 seed/condition vectors:

| Measured response definition | J–Q RMSE | Q-only RMSE |
| --- | ---: | ---: |
| Before/after changes, control change subtracted | 0.403 Hz | 0.799 Hz |
| Post-step rates, control rate subtracted | 1.273 Hz | 1.322 Hz |

These are averages of per-vector errors, not errors of the mean response or
significance tests. The feedback benefit is mainly in IT2-driven responses.
The negative IT2→PV2 response is weaker than predicted and does not scale
proportionally between the two amplitudes.

## Limitations that remain relevant

Same-seed control/treatment traces are not identical, so their subtraction
does not cancel shared stochastic noise. Both response definitions remain
informative; neither is automatically the true effect. The connected operating
point differs from the open-loop identification point. Slow variation,
uncertain J entries, and NGF2 branch dependence limit interpretation. This is
useful evidence for static prediction, not complete validation. No next
scientific experiment has been selected.

## Where the saved results are

Dataset: [l2_connected_steps_5seeds_15_30pa_100s/](../../data/l2_connected_steps_5seeds_15_30pa_100s).

- [Signed-amplitude figure](../../data/l2_connected_steps_5seeds_15_30pa_100s/analysis/jq/amplitude_summary/drift_adjusted_hz.png):
  individual seeds; dashed line is fixed prediction, not a fit.
- [Absolute-rate overlays](../../data/l2_connected_steps_5seeds_15_30pa_100s/analysis/jq/rate_dynamics):
  0.5-s display smoothing; dashed lines are each trial's measured baseline
  plus pooled predicted change, not predictions of transients.
- [Numerical comparisons](../../data/l2_connected_steps_5seeds_15_30pa_100s/analysis/jq/pilot_comparison.csv).
- [Five selected slide figures](../../data/slide_assets/jq_prediction/README.md).

[Analysis code and optional reproduction](../processing/connected_step_analysis.md)
explain how the saved outputs were produced. The
[full historical log](../archive/connected_steps_5seeds_15_30pa_log.md) retains
execution dates, job IDs, resources, transfer checksums, detailed tables, and
reproduction commands; it is not needed for the basic hand-off.
