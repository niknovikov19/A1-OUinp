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
