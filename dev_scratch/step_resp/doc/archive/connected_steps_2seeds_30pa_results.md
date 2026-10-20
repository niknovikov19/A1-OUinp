# Historical results: connected L2, two seeds, ±30-pA steps

HISTORICAL RESULT — superseded experiment; not part of the current hand-off.
No simulation, analysis, or fitting is requested by this record.

Earlier comparison, superseded as main evidence by the
[five-seed amplitude test](../results/connected_steps_5seeds_15_30pa.md). Retained for
comparison and the frozen reference manifest, not pooled into the newer batch.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Analysis is complete using only `data/_old/l2_connected_steps_2seeds_30pa_100s/input/`. No remote reads,
new fitting, simulations, or baseline changes were needed. The source rates
were extracted with `sim_data_analyzer` during simulation post-processing.
All twelve local trials pass current-waveform, clamp-count, spike-count, and
raw-rate/window consistency checks. See [the run note](connected_steps_2seeds_30pa_execution.md)
for the protocol, HPC path, and verified input-copy manifest.

## Outputs

Everything is under [`data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis):

- [`rate_overview.png`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/rate_overview.png): all
  population traces and input conditions, with 0.5-s display smoothing.
- [`static_response_contrasts.png`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/static_response_contrasts.png):
  specified, control-pooled, and drift-adjusted response estimates.
- [`zero_input_repeats.png`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/zero_input_repeats.png):
  all four physically zero-input trials.
- `window_rates.csv`, `trial_window_summary.csv`, `response_estimates.csv`,
  and `response_summary.csv`: raw-count window means and descriptive contrasts.
- `central_slopes.csv`: symmetric positive/negative step differences per seed.
- [`jq/prediction_vs_pilot.png`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/jq/prediction_vs_pilot.png):
  J-Q and Q-only predictions against measured response contrasts.
- `jq/pilot_comparison.csv` and `jq/comparison_errors.csv`: per-seed numerical
  comparisons; `jq/manifest.json` records prediction provenance and assumptions.

All figures have axes grids disabled. Observation error bars are SD across
two seeds, not standard errors or confidence intervals. Alternative-J
predictions are retained in CSV files but are not shown in the main plot.

## How to read the J-Q plot

The plot compares **numbers measured in the new connected simulations** with
**numbers calculated from the previously estimated J and Q matrices**. The
prediction is not fitted to these new step simulations.

Each panel specifies where extra current was applied and its sign. The top
row applies current to IT2; the bottom row applies it to PV2. Left is negative
current, right is positive. The horizontal axis names the population whose
firing rate we read out. The vertical axis is a rate difference in Hz, not
the absolute firing rate. Panel vertical scales differ. Small horizontal
offsets between symbols just make them easier to see.

### What is measured in the simulations?

We run the connected circuit with an extra current switched on at 40 s.
We also run controls with **no extra current**. Baseline currents and all
other calibrated inputs remain present in both kinds of run. For each
population we count spikes and calculate its average firing rate:

- Before the step: 10–40 s.
- After the step, allowing 20 s to settle: 60–100 s.

We then calculate the response in two ways, shown as different circles:

| Symbol | What is calculated from the simulations? |
| --- | --- |
| Blue circle | Rate **after** the step in the step run, minus the rate over the same time in a control run |
| Orange circle | The step run's **after minus before** rate change, minus the controls' **after minus before** rate change |

For blue, use the control with the same seed and the same stored amplitude
label. Its actual extra current is still zero because its group is empty.
For orange, average the two control rate changes within that seed. Finally,
average each result across the two seeds to place its circle on the plot.

Example: suppose a step run goes from 10 to 13 Hz, while a control goes from
8 to 10 Hz. Blue is `13 - 10 = 3 Hz`. Orange is
`(13 - 10) - (10 - 8) = 1 Hz`. Orange subtracts the change that also happened
without the added current, instead of directly comparing the final rates.
This example uses one control for simplicity; the real orange calculation
uses the mean change of both controls for that seed.

These are **two ways to estimate the current's effect from simulations**,
not two different predictions. Blue and orange can disagree because runs
start at different activity levels or change over time even without added
current. Neither calculation is automatically the true effect. The old
labels "specified post contrast" and "drift-adjusted" referred to blue and
orange respectively; CSV column names retain those older labels for continuity.

The vertical bars on the circles show how much these estimates differ
between the two seeds (one standard deviation). They are not uncertainty
bounds proving that a prediction agrees or disagrees with the simulation.

### What is predicted from J and Q?

| Symbol | What is calculated without fitting the new simulations? |
| --- | --- |
| Green star | Rate change predicted from **J and Q together**, including the circuit's recurrent effects: `(I - J)^-1 Qh` |
| Grey cross | Rate change predicted from **Q alone**, ignoring recurrent effects: `Qh` |

Here `h` is the extra current vector in that panel. For example, in the
top-right panel it is +0.03 nA for IT2 and zero for every other population.
The green star uses the same primary J and Q as before, including the two
explicit provisional zero J entries. An earlier plot also had a grey bar for
the range of predictions from alternative J matrices. It was unrelated to
the grey Q-only cross and obscured markers, so it has been removed. Those
alternative predictions remain in `jq/conditional_predictions.csv` and their
minimum/maximum values in `jq/prediction_sensitivity.csv`. Their range is not
a measurement error bar or a confidence interval.

To assess the predictor, compare the **green star with the circles** for
the same output population. Comparing green stars with grey crosses shows
what adding recurrent effects changes. A large blue–orange difference warns
that the way we subtract the controls strongly affects the measured response.
For IT2 +0.03 nA → IT2, the prediction is +0.610 Hz and orange is +0.620 Hz.
For IT2 -0.03 nA → PV2, the prediction is -4.156 Hz and orange is -2.377 Hz:
the predicted suppression is stronger than the measured estimate.

## Fixed predictor and response definitions

Use exactly the primary 0.2-s pooled L2 J from the previous quick prediction,
with the same explicit provisional zeros for SOM2 → SOM2 and NGF2 → NGF2.
An array comparison confirms that the new prediction copy has unchanged J
values. Q is the unchanged slow symmetric h-r estimate at 0.2-s smoothing.
Both matrices are aligned by labels and transposed from their saved input-first
layout before `delta_r = solve(I - J, Q @ h)`. The condition number remains 51.69.

The three descriptive estimands remain separate:

- Specified post contrast: treatment response minus the same-seed,
  same-amplitude zero-input response.
- Pooled post contrast: treatment response minus the mean of both same-seed
  zero-input response rates.
- Drift-adjusted contrast: treatment `(response - baseline)` minus the mean
  zero-input `(response - baseline)` within seed.

Same-seed pre-step traces and duplicate controls still differ. Their pairing
does not provide common-noise cancellation. Drift adjustment is a sensitivity
analysis, not a proven correction for all baseline/operating-point differences.

## Main numerical results

All values are Hz. Measurements are means across two seeds; the last column
also gives seed SD.

| Input | Output | J-Q prediction | Specified post contrast | Drift-adjusted contrast |
| --- | --- | ---: | ---: | ---: |
| IT2 -0.03 nA | IT2 | -0.610 | -0.500 | -0.525 ± 0.018 |
| IT2 +0.03 nA | IT2 | +0.610 | +0.586 | +0.620 ± 0.214 |
| IT2 -0.03 nA | PV2 | -4.156 | -2.099 | -2.377 ± 0.037 |
| IT2 +0.03 nA | PV2 | +4.156 | +3.202 | +3.128 ± 2.514 |
| PV2 -0.03 nA | PV2 | -5.521 | -4.174 | -3.381 ± 0.256 |
| PV2 +0.03 nA | PV2 | +5.521 | +4.655 | +5.861 ± 0.384 |

The larger steps give interpretable signs and signal scales, unlike the
smaller first pilot. IT2's own response is close to prediction for both signs;
positive PV2 stimulation is also close under drift adjustment. The IT2-driven
PV2 response has the predicted sign and clear nonzero scale, but is weaker
than the primary J-Q prediction, especially for negative input. Negative PV2
stimulation also suppresses less than predicted. Weak indirect effects remain
sensitive to baseline handling; e.g. PV2 negative input → VIP2 is -1.665 Hz
with specified post subtraction but +0.295 Hz after drift adjustment.

Average per-seed/condition five-population vector RMSE:

| Response definition | J-Q | Q-only |
| --- | ---: | ---: |
| Specified post contrast | 0.967 Hz | 1.135 Hz |
| Drift-adjusted contrast | 0.712 Hz | 0.964 Hz |

Thus J-Q has lower descriptive error than Q-only in this pilot. This is not
a significance claim or a complete validation: there are two seeds, provisional
J entries, operating-point differences, and model sensitivity.

## Settling and interpretation

Longer averaging improves the measurement, but the response is not uniformly
stationary. For positive IT2 and PV2 inputs, mean PV2 rate falls by 1.237 and
1.238 Hz respectively between 60–80 and 80–100 s. The corresponding average
zero-input fall is 0.336 Hz, leaving about 0.90 Hz beyond that descriptive
control trend. These changes should not automatically be called step-induced
relaxation, because slow stochastic variability is also present.

The zero-input response averages are about 10.00 Hz for PV2, 4.83 Hz for SOM2,
6.21 Hz for VIP2, 1.91 Hz for IT2, and 1.01 Hz for NGF2; some differ from the
identification targets. No baseline retuning was performed. This pilot does
not isolate how much prediction error comes from nonlinearity, settling,
baseline mismatch, or uncertainty in J/Q.

The practical outcome is a useful first J-Q comparison, with promising direct
and IT2-to-interneuron responses but visible asymmetry and residual drift.
Further fitting remains stopped. Replication/settling and amplitude-scaling
tests can be discussed next; no additional simulations are launched here.

## Smoothed rate dynamics

The four figures in `data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/jq/rate_dynamics/` show one
condition per figure and one population per panel. Blue and orange identify
seeds 1000 and 1001. Solid traces show actual rates with 0.5 s centered
moving-average smoothing and transparency; time before 10 s is excluded from
the display and vertical scaling. The input strip and dotted onset markers
show the step at 40 s.

Each same-color dashed line is that trial's measured 10–40 s baseline plus
the pooled J–Q predicted change, `(I - J)^(-1) Q h`. These are static endpoints,
with no control drift correction or predicted transient dynamics. The two
seeds share the predicted change but have separate baseline offsets.
`prediction_levels.csv` records the 40 plotted baseline/prediction pairs,
checked against the existing response and prediction tables. All four
figures were visually inspected for spacing and visible prediction levels.

The following optional reproduction code regenerates saved figures; it is
not requested by this historical record. Its working directory is the repository root.

```bash
# Historical reproduction reference only; writes generated outputs
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/plot_hstep_dynamics.py \
  --data-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_30pa_100s
```

The script reuses the local `sim_data_analyzer` rate-file loader and raw
rate/window-count validation. Its default now selects the newer five-seed
dataset, so specify this dataset explicitly as above. Options include `--data-dir`,
`--smooth-win` (seconds), and `--start` (seconds).

## Optional reproduction reference — not a task

```bash
# Historical reproduction reference only; writes generated outputs
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_hstep.py \
  --input-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_30pa_100s/input \
  --output-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_30pa_100s/analysis \
  --qmat dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s/processed/tau_0.2/qmat.nc \
  --audit-jmat dev_scratch/step_resp/data/l2_rate_sweep_j_5seeds/analysis/jmat_pooled_zero_filled.nc

MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_j_refit.py \
  --hstep-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_30pa_100s \
  --output-dir dev_scratch/step_resp/data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/jq \
  --zero-missing
```

The new `--output-dir` isolates this comparison from the first pilot's outputs.
The descriptive script's validation flag `prediction_computed: false` refers
only to that script; the completed feedback prediction is recorded separately
in `jq/manifest.json`. Nine analysis tests pass in the existing NetPyNE
environment; no dependencies were installed.
