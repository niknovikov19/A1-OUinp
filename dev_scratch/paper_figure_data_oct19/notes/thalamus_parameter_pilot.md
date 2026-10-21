# Thalamic fading pilot with parameter-only experiment changes

## Task and limits

Run the IREM→TI and IREM→IRE pilots sequentially in the existing
`net_newsec_ee_fade_var_seed` experiment. Change existing parameter values only;
retain the existing `get_batch_completion_files()` compatibility function.
Do not add batch axes, diagnostics, simulation hooks, or experiment folders.
Finish, analyze, finalize, and release the first batch before preparing the
second. Use installed HPC-Codex helpers and the local watcher.

## Protocol

- Two seeds per batch: 1000 and 1001; the only batch axis is `seed_main`.
- Seven thalamic populations, in archived branch-freeze population order.
- Duration 10 s (reduced from the restored 15 s default), summary 7–10 s.
- Selected projection surrogate at 0–3 s, fading at 3–5 s, recurrent at 5–10 s.
- No permanently frozen thalamic projection; no second-stage corrections.
- Retain existing inputs, mechanisms, gains, seed mapping, and simulation code.
- Each condition has a unique result label and a pinned Git revision.
- Request two concurrent simulations within the sole active batch: 8 ranks and
  32 GiB per simulation; 2 cores and 16 GiB for the batch main.
- Retrieve compact results, saved cfgs, and child index. Keep large raw files
  on HPC. The unchanged experiment does not export numerical fade coefficients;
  document that limitation rather than restoring the removed diagnostics.

## Findings and progress

- The earlier pilot's simulations completed, but they used the subsequently
  rolled-back implementation. Their analysis remains historical evidence and
  does not replace this parameter-only pilot.
- The restored experiment already supports each projection through
  `CONNS_SPLIT`; changing conditions requires sequential pinned revisions.
- The existing completion helper needs no change. The request can additionally
  require the existing saved cfg files for compact archive retrieval.
- The 10 s pilot retains the 3–5 s fade and gives five seconds after restoration;
  its 7–10 s summary window matches the historical table. Two-seed results will
  remain separate from the 15-seed paper table.
- IREM→TI local preflight passed: exactly two seed-only children, the intended
  unique result directory, and seven completion paths (index, two JSONs, two
  rasters, two cfgs). An AST comparison against restored commit `e7e109d`
  confirms that all experiment functions and other statements are unchanged.
  Only eight existing `exp_cfg.py` assignments and `N_SEEDS` differ. Archived
  seed-1000 background inputs, currents, mechanisms, gains, targets, sections,
  and seeds match. Evidence: `data/inventories/thalamus_param_pilot_ti_preflight.json`.
- Committed IREM→TI parameters as `08e301a744634c5f210c6a2ff46e3c62b92d4408`,
  pushed, and updated lethe with the installed helper. Prepared and submitted
  run `thal-ti-param-pilot-20261020`, main Slurm job **118859**, at
  `2026-10-21T02:09:57.784774+00:00` (October 20, 22:09 EDT).
  Request SHA256: `1b9e37b279147519022960e8d834957e2037937e32d4055b860158a1b1369873`.
  Only this batch is active; IREM→IRE has not been prepared or submitted.
- IREM→TI main 118859 and children 118860/118861 completed with exit `0:0`.
  The normal finalizer verified all seven requested files and returned complete.
  Retrieved the compact five-file archive: 12,358 compressed bytes / 134,977
  uncompressed bytes, containing two cfgs, two result JSONs, and the child index.
  No raw pickle or raster was transferred.
- Local analysis passed both saved-cfg/input/seed checks and finite-rate checks.
  TC/HTC rates over 7–10 s were **29.98/28.11 Hz** (seed 1000) and
  **7.34/10.15 Hz** (seed 1001), against 8/8 Hz targets. This remains a strong
  seed difference; the pilot does not establish universal return to high rates.
  Per-population results: `data/tables/thalamus_param_pilot_ti_rates.csv`;
  provenance/checks: `data/inventories/thalamus_param_pilot_ti_analysis.json`.
- The installed release helper released IREM→TI at
  `2026-10-21T02:30:41.353018+00:00` (October 20, 22:30 EDT).
  Only after that release will the projection and label change for IREM→IRE.
- IREM→IRE preflight passed the same seed-only grid, baseline-input comparison,
  completion list, and AST check. Relative to the IREM→TI experiment revision,
  only `EXP_LABEL` and `CONNS_SPLIT` changed; every function is unchanged.
  Evidence: `data/inventories/thalamus_param_pilot_ire_preflight.json`.
