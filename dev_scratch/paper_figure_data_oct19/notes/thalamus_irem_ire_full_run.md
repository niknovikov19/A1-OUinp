# Full IREM→IRE fading run

## Task and settings

Run IREM→IRE with the completed full IREM→TI run's scientific and operational
settings, changing only the existing projection and result-label values.
Keep the generic modulation legend unchanged, as requested. After the watcher
starts, wait for its report without background checks or parallel task work.

- Existing experiment: `batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed`.
- Seeds 1000–1014; duration 10 s; summary window 7–10 s.
- Population order: TC, HTC, TCM, TI, TIM, IRE, IREM, matching `thal_all_fade`.
- Only IREM→IRE starts surrogate and fades into recurrence at 3–5 s.
  No permanent thalamic freeze or second-stage current correction.
- Inputs, currents, mechanisms, gains, and seed mapping remain unchanged.
- Concurrency 10; each simulation 30 MPI ranks, 128 GiB, 60 min.
  Batch main: 2 cores, 16 GiB, 120 min. Only one batch is active at a time.
- Label: `thal_irem_ire_fade`; all 15 seeds run in a new result directory.
- Existing simulation functions and HPC compatibility helper remain unchanged.
- Retrieve only compact cfgs, result JSONs, and the child index after completion.

## Progress

- Prepared parameter-only projection/label changes and a separate operational
  request. Preserve the completed IREM→TI run and its result files.
- Preflight passed exactly 15 seed-only children and the new result path. AST
  comparison with the completed IREM→TI revision confirms that only
  `EXP_LABEL` and `CONNS_SPLIT` changed. Every experiment function is unchanged;
  resources and all 46 completion filenames match the previous full run.
  Evidence: `../data/inventories/thalamus_irem_ire_full_preflight.json`.
- Pushed and updated lethe to `093736d432fc243c6ce440e9c4ef122eae7c8c14`.
  Protected preparation accepted the 15-child request. Submitted run
  `thal-irem-ire-fade-20261020`, main Slurm job **118897**, at
  `2026-10-21T03:28:19.104703+00:00` (October 20, 23:28 EDT).
  Request SHA256: `3c47baf3fc38d612555b7862a3f8bf3d869efc1ca323980a62569a07360d3338`.
- Start the watcher with a 30-minute reporting interval and wait without other
  task work, additional HPC queries, or local-state checks until it returns.

## Completion

- Waited for the watcher; it returned scheduler-terminal at
  `2026-10-21T03:42:32.186310+00:00` (October 20, 23:42 EDT), reporting
  main 118897 and all 15 simulations completed, without failures.
- The normal finalizer recorded complete status and verified all 46 requested
  files. Retrieved the compact archive only: 84,953 compressed bytes,
  1,011,797 uncompressed bytes, 31 files (15 cfgs, 15 JSONs, child index).
  Raw pickles and PNGs remain on HPC.
- All 31 compact-file hashes passed. For every seed, the saved cfg equals the
  corresponding completed full IREM→TI cfg after replacing only
  `conns_split` with `{'IREM, IRE': 0.5}`. This checks the complete saved
  configuration, including population order, input seeds, currents, and weights.
  All 105 population rates are finite and nonnegative, with the 7–10 s window.
- Normal release succeeded at `2026-10-21T03:43:47.845735+00:00`
  (October 20, 23:43 EDT). No job or watcher remains active for this run.
- [Run record and unrounded rates](../data/inventories/thalamus_irem_ire_full_run.json)
  preserve source commit, child IDs, compact checksums, and all endpoint rates.
  Both full single-projection fading cohorts are now complete; the paper table
  has not been regenerated in this task.
