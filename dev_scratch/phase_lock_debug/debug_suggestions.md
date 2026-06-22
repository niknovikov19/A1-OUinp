# Phase-Locking Debug Suggestions

## Main Concern
- Amp `0` is a valid near-null condition: netParams use actual pulse weight `1e-6`.
- If amp `0` and non-zero amps show similar phase concentration, epoch averages, and power peaks, the analysis is likely dominated by the event grid and periodic mask.
- Current pulse masking removes a fixed phase sector every 200 ms, so the estimator sees a strong 5 Hz missing-data comb.

## Priority Diagnostics
- Run the full phase/power pipeline on synthetic white noise with the exact same time axis, pulse intervals, and mask.
- Run the same synthetic test on a flat constant signal and a slow non-5 Hz sinusoid.
- Plot raw signal, masked signal, and mask-valid samples folded over the 200 ms pulse period.
- Plot valid-sample fraction inside each local fit window at every pulse start.
- Report the expected random ITC floor `1 / sqrt(n_valid_phase)` next to each measured ITC.

## Null-Corrected Metrics
- Use amp `0` as the empirical null for each trace and seed.
- For power, plot `power(amp) - power(amp=0)` and `power(amp) / power(amp=0)`.
- For ITC, compare complex vectors, not only magnitudes: `mean(exp(1j * phase_amp)) - mean(exp(1j * phase_amp0))`.
- Keep raw amp `0` plots visible as controls, but avoid interpreting raw non-zero plots without the amp-zero correction.

## Phase Histogram Checks
- Plot phase histograms per seed before any seed averaging.
- Pool phases across seeds as samples in a diagnostic plot.
- Avoid circular-averaging phase arrays pulse-by-pulse before histogramming, because it can sharpen weak or noisy structure.
- Separate even and odd pulses to test whether apparent two-peak structure is an alternating-cycle artifact.
- Compare true pulse starts against jittered starts and random starts with the same count.

## Power Spectrum Checks
- Add a plot showing the actual frequency grid. With `target_f=5`, current `_get_power_fband()` clamps the band to `2.5`, so the grid spans `2.5..7.5 Hz`.
- Plot the mask-only/synthetic-noise power spectrum to expose peaks introduced by periodic missing data.
- Add baseline-subtracted power, because the current power plot is absolute fitted oscillatory power.
- Compare `METHOD='fit'` and `METHOD='morlet'` on the same masked synthetic controls.

## Epoch Average Checks
- Plot pulse-triggered averages of both `x_raw` and `x_masked`.
- Add amp-minus-amp0 epoch averages.
- Mark the exact masked region and extend it for CSD diagnostics, because CSD tails can persist beyond `PULSE_PAD=0.02`.
- Consider separate pre-pulse and post-pulse epoch panels so evoked responses are not confused with ongoing phase.

## Estimator Geometry Checks
- Warn when clean inter-pulse interval is shorter than one target cycle.
- For `f=5`, one cycle is 200 ms, but after masking there is only about 110 ms of clean data per pulse period.
- Report local fit support size. With `N_CYCLES=3`, the current half-width is about 0.382 s, so each phase estimate spans several periodically masked pulses.
- Test whether increasing `PULSE_PAD` changes raw ITC/power in amp `0`; strong sensitivity would confirm mask-dominated estimates.

## Possible Script Changes
- Add `RUN_MASK_NULL = 1` to generate synthetic null plots in the same output layout.
- Add `RUN_AMP0_CORRECTION = 1` for delta/ratio plots relative to amp `0`.
- Add per-seed combined plots before `AVG_OVER_SEEDS` aggregation.
- Save diagnostic CSV columns: random ITC floor, valid fit mass, mask fraction, clean inter-pulse interval, and local fit half-width.
- Add an explicit warning in the console when periodic masking makes the target-frequency phase estimate poorly conditioned.
