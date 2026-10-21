# Full IREM→TI fading run

## Task

Run IREM→TI fading with the full duration and seed cohort of archived
`thal_all_fade`. Change existing experiment parameter values only. Submit one
batch, start the installed local watcher, and wait for its report without
parallel task work, extra status queries, or local-state checks.

## Settings and provenance

- Existing experiment: `batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed`.
- Fifteen seeds: 1000–1014; 10 s duration; 7–10 s rate summary.
- Population order matches `thal_all_fade`: TC, HTC, TCM, TI, TIM, IRE, IREM.
  This intentionally differs from the pilot order and restores the reference's
  per-population background-seed assignment.
- Only IREM→TI is split and faded; no permanent thalamic freeze or second-stage
  current correction. Background inputs, currents, mechanisms, gains, target
  sections, and numeric seed mapping must match the archived reference.
- Fade schedule: surrogate through 3 s, linear restoration at 3–5 s, recurrence
  through 10 s. The historical image supports 3–5 s fading, but its cfg does not
  serialize the schedule; exact historical timing is not independently verified.
- Label: `thal_irem_ti_fade`; expected result directory:
  `exp_thal_irem_ti_fade_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`.
- Keep two concurrent simulations within this single batch, each 8 MPI ranks,
  32 GiB, and 60 min. Batch main: 2 cores, 16 GiB, 120 min.
- Request completion evidence includes the child index and all 15 cfgs, result
  JSONs, and rasters. Compact retrieval excludes large raw files and PNGs.
- No experiment function or compatibility helper will change. No numerical
  coefficient or time-course export will be added.

## Progress

- Read the assessment and the existing local `thal_all_fade` cfg. Confirmed the
  duration, summary window, 15-seed cohort, population order, and lack of
  serialized fade points. The pilot order must change to match this reference.
- Local preflight passed exactly 15 seed-only children and 46 unique requested
  completion files. AST comparison against `a8b1603` permits only the four
  intended parameter assignments; every experiment function is unchanged.
- All inspected scientific cfg fields match the archived reference. Resolved
  three pre-construction differences: network construction assigns the modulated
  GABAB mechanism labels and scales the base weight matrix by `wmult`; those
  resolved values match the saved reference exactly. Remaining cfg differences
  are the intended split-projection selection and run-specific paths/labels.
  Evidence: `../data/inventories/thalamus_irem_ti_full_preflight.json`.
