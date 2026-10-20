# Missing thalamic fading experiments: proposed run plan

Prepared 2026-10-20 for discussion. No experiment configurations changed and no
jobs prepared or submitted.

## Scientific conditions

Use the existing `net_newsec_ee_fade_var_seed` experiment for both parameter
variants: IREM→TI fading and IREM→IRE fading. Do not create experiment folders or
duplicate implementation for these parameter-only differences. Set the existing
parameter block and `EXP_LABEL` for each condition, preserving its exact settings
and code revision with the run. Both start
with only the selected projection replaced by target-rate surrogate input and end
with full thalamic recurrence. Other thalamic projections remain recurrent
throughout. Use new result names so archived experiments are not overwritten.

- All seven thalamic populations; inputs from excluded cortex remain surrogate.
- Preserve archived background input, baseline currents, target sections,
  mechanisms, synaptic gains, and seed mapping. Keep second-stage corrections off.
- `CONNS_FROZEN=[]`, `EE_FADER_ON=1`; split exactly one pair:
  `[('IREM', 'TI')]` or `[('IREM', 'IRE')]`.
- Proposed explicit protocol: 0–3 s selected input entirely surrogate, 3–5 s
  linear transition to recurrence, 5–10 s fully recurrent; summary over 7–10 s.
- `FADER_PTS=[(0, 0), (3000, 0), (5000, 1), (10000, 1)]`, with time in ms and
  the second coordinate the recurrent fraction; the surrogate fraction is 1−a.
- Fifteen seeds, 1000–1014, per condition; 30 scientific realizations total.

This schedule is consistent with the inspected historical all-thalamus fade PNG,
but its exact points were not serialized in the archived cfg. Document the new
schedule explicitly rather than claiming unverified identity with every old run.
The current source defaults are full A1, a permanent IREM→IRE freeze, 15 s total,
and a 6–8 s fade schedule. They are unsuitable unchanged. Its functions read
module-level settings, so ordinary cfg JSON overrides alone will not switch the
fader's selected projections and schedule.

## Preparation and pilot

The user clarified that parameter-only variants belong to the existing experiment;
the earlier suggestion to create two new experiment folders was withdrawn.

Compare each candidate saved cfg/input signature with the historical representative
cfg before running: population set, seed mapping, section selection, background,
baseline currents, mechanisms, gains, and duration/window. Record unavoidable code
or construction-path differences. Use the repository's tracked job requests and
HPC preflight/preparation mechanism, with scientific settings in `exp_configs/`,
new result paths, and a pinned Git revision.

Run seed 1000 for each new condition first. Check finite rates, positive/recurrent
and negative/surrogate projection selection, complementary modulation from 0/1
to 1/0, and the actual terminal recurrent state. Inspect all-population rate time
courses and the raster. Starting rates need only agree in distribution with the
archived frozen condition; static versus split construction can realize different
networks/noise despite matching numeric seeds. If the implementation has changed,
reproduce an uncorrected fully recurrent control before relying on historical
comparisons; one control seed is a troubleshooting check, not cohort validation.

Use pilot memory/runtime measurements to choose resources and bounded concurrency
for the remaining seeds. Successful pilot seeds can be included in the final
15-seed cohorts if no scientific configuration changes follow. If changes are
needed, distinguish pilot outputs and rerun those seeds under the final settings.

## Outputs and completion

Keep raw spikes, cfgs, and rasters on HPC. Add compact numerical population-rate
time courses over the entire 0–10 s interval, endpoint rate/CV JSONs, and explicit
fade schedule/projection/seed/input/code metadata. Use `sim_data_analyzer` for rate
extraction. A conductance PNG alone is not evidence of the numerical fade
coefficient: existing `ConnFader.setup_recording()` records synaptic g despite
the old pmod labeling. Save a(t) separately if recording it numerically.

Once all 15 seeds per condition are complete, retrieve only compact summaries and
time courses, plus one representative raster per condition. Validate targets,
window, exact restored projection, and absence of corrections, then add verified
sources to the table generator and replace its two blank columns. Compare the
seven-population endpoint patterns and pre/during/post-fade time courses with
the existing frozen and fully recurrent conditions.

If rates are still drifting at 10 s, extend the hold and use a common later
evaluation window with appropriate reference runs. Do not silently pool later
windows with the historical 7–10 s values. The result tests these restoration
routes; it does not prove unique-attractor behavior for every initial condition.
