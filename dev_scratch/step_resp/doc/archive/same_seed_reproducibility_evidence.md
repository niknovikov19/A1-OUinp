# Evidence log: same-seed activity mismatch

HISTORICAL EVIDENCE — observations and investigation notes, not a repair request.
The [current issue summary](../issues/same_seed_reproducibility.md) states what
is known and what remains deferred.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

The user deferred the fix on 2026-10-14. Descriptive pilot analysis subsequently
continued without changing the subnet builder or rerunning simulations.

## Observed issue

The connected pilot `hstep-l2-first-pilot-002` contains twelve trials: two
seeds, `IT2` / `PV2` / an empty group, and amplitudes -0.005 / +0.005 nA.
Each empty-group trial applies exactly zero additional current regardless of
its amplitude coordinate.

The two zero-current repetitions for each seed have different raw rate
traces. All eight treatments also differ from their same-seed/amplitude
control before step onset. This concerns matching within a seed, not expected
differences between distinct seeds.

For seed 1000, the two controls share all saved baseline settings and seed
values (`cell=1`, `loc=1`, `stim=1000`, `conn=2000`, surrogate base seed 3000).
Nevertheless, their traces first differ at 0.06 s, before the 20-s step onset.
PV2's 10–20 s baseline rate is 8.95385 versus 12.62308 Hz.

At least one population differs in 3875 of the 4000 pre-step bins between
the seed-1000 controls, and in 3861 bins between the seed-1001 controls. These
are 5-ms unsmoothed bins, not independent statistical observations. The saved
currents, cell/clamp counts, and window-count arithmetic pass validation.

## Identified construction-order concern

The local companion subnet builder uses `list(set(...))` to deduplicate
frozen population names in `subnet_par_builder_2.py`. Python set iteration
order can vary between processes. The pilot's saved topology metadata confirms
different frozen-population insertion orders; for the seed-1000 controls the
first names are:

```text
trial 00008: IT5Bfrz, SOM5Bfrz, CT5Afrz, NGF1frz, SOM5Afrz, ...
trial 00009: PV5Bfrz, IT3frz, TCMfrz, PV4frz, ITP4frz, ...
```

The inspected NetPyNE implementation creates populations/cells in parameter
insertion order and initializes NetStim randomness with the cell GID as well
as the numerical seed. Changing the population order can therefore change
GID assignments, stochastic inputs, and connections despite unchanged seed
numbers and calibrated input parameters.

This is a concrete ordering concern and a strong explanation for the observed
mismatch. It has not yet been established as the sole cause by a controlled
fixed-order rerun. Actual stored GID maps have not been compared; the large
simulation PKLs were left on HPC.

## Relationship to earlier experiments

The h-r identification batch has only the seed coordinate, with one job per
seed. It has no same-seed duplicate controls within that batch. Its successful
multi-seed fitting does not establish exact rerun reproducibility, but neither
does this pilot demonstrate that those earlier estimates are invalid.

If earlier exact same-seed repetitions were verified to match, compare their
population order, builder and NetPyNE versions, and process environment before
generalizing this issue. No retrospective claim about all prior experiments
is supported by the checks done here.

## Analysis while the fix is deferred

- Treat same-seed treatment/control contrasts as descriptive comparisons,
  not noise-cancelled paired measurements.
- Retain the originally specified same-seed/amplitude post-rate contrast.
- Also pool physically zero-current controls within each seed, and show a
  drift-adjusted within-trial pre/post contrast as a sensitivity analysis.
- Report individual seeds, control variability, pre-step offsets, and
  early/late response-window differences. Smoothed time samples are not
  independent replicates, and two seeds cannot establish precise uncertainty.
- Do not adjust rx, surrogate rates, background-current corrections, or other
  calibrated baseline components to compensate for the mismatch.

## Previously proposed verification — still deferred, not authorized

1. Compare realized GID maps and source-stream initialization in saved
   same-seed controls, and compare any known reproducible older experiment.
2. Review deterministic ordering of populations and relevant stimulus rules;
   preserve numerical calibration and explicit seed mappings. Do not edit the
   companion repository without permission.
3. Run a small exact-repeat check before a new treatment batch. Compare raw
   pre-step traces, metadata, and full zero-input trajectories.
4. Preserve this pilot and use a new attempt/result folder for any rerun.

Evidence is in the ignored local dataset `data/_old/l2_connected_steps_2seeds_5pa_40s/`, including
`analysis/validation.json`, `analysis/zero_input_repeats.png`, copied result
summaries/configurations, and `analysis/input_manifest.json`. The manifest
records exact HPC paths and verified input hashes. The analysis entry point
is [`code/analyze_hstep.py`](../../code/analyze_hstep.py).
