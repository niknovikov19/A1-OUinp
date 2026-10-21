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
- Pushed and updated lethe to `0bdf1a5be351ab7b18d6b60e980b836f83130fd4`.
  Prepared and submitted run `thal-irem-ti-fade-20261020`, main Slurm job
  **118869**, at `2026-10-21T02:53:47.763315+00:00` (October 20, 22:53 EDT).
  Request SHA256: `0a10d51f40d2b05c14ed00f714e77eb68b354cd8246a3135c8a61aff724b6042`.
  Rendered script SHA256: `86d943937786c4f05ea8c1c9a6d454182ca0547e672ef2279f4e05c1238ab64d`.
- Starting the watcher with a 30-minute reporting interval. No parallel task
  work, local-state checks, or additional HPC queries will run during its wait.

## Restart requested by the user

- The user stopped the concurrency-two run and requested concurrency 10,
  32 cores, and 128 GiB per simulation. Cancelled main 118869 and all six recorded
  children (118870–118875). The watcher returned cancellation and exited: four
  children completed, two were cancelled, and nine seeds were never submitted.
- Normal finalization recorded the cancelled run as failed; normal release
  succeeded at `2026-10-21T03:04:11.942072+00:00` (October 20, 23:04 EDT).
  Partial results remain untouched and will not be pooled into the restart.
- Restart all 15 seeds in a fresh `thal_irem_ti_fade_r2` result directory.
  Scientific settings remain unchanged. Only the existing experiment label and
  operational request resources change: 10 concurrent simulations, each 32 MPI
  ranks and 128 GiB. Batch-main resources remain 2 cores and 16 GiB.
- After submission, start the watcher and wait without other task work or checks.
- Protected preparation rejected the 32-core restart because the installed
  per-simulation ceiling is 30 cores. No replacement job was submitted.
  The user then selected **30 cores**, retaining concurrency **10** and
  **128 GiB per simulation**. Discarded the uncommitted policy-update candidates;
  no protected configuration or helper changed. The restart uses the same
  fresh result label and unchanged scientific settings.
