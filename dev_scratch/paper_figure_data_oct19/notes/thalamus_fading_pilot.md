# Thalamic single-projection fading pilot

Task: prepare and push parameter changes within the existing experiment, run a
short two-seed pilot for each missing projection with the HPC-Codex utilities,
retrieve bounded evidence, and analyze it before proposing full runs.

## Design

- Existing experiment: `batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed`.
- One batch: `fade_post=[TI, IRE]` × `seed_main=[1000,1001]`, four child runs.
- All seven thalamic populations; baseline inputs/currents/gains retained,
  second-stage corrections absent, no permanently frozen thalamic projections.
- Only IREM→the selected target starts surrogate and is restored to recurrence.
- Duration 6 s (reduced from 10 s); fade remains at 3–5 s, endpoint window 5–6 s.
- This short pilot tests construction, modulation, and immediate post-fade
  behavior. It is not a substitute for 15-seed, 7–10 s table results. The two
  production-table columns remain blank.
- Child request: 8 MPI ranks, 32 GiB, 60 min; at most two concurrent children.
  Controller request: 2 cores, 16 GiB, 120 min.

## Implementation and evidence

The existing experiment previously used module-level split pairs in both network
hooks. These now read the saved per-child split-pair cfg, allowing both parameter
variants in the same batch without copying experiment code. The batch still
uses the archived seed mapping; the saved cfg now also retains the fade points.

Each child declares one result JSON and raster to the existing HPC completion
contract. Its compact JSON additionally contains actual modulation-coefficient
samples, rank-wise terminal coefficients, counts of instantiated modulated
contacts, seven-population rate dynamics exported with the existing repository
rate-processing helper, and
pre/during/post-fade rate summaries. Existing synaptic-g plots have a corrected
axis label; g and the dimensionless fade coefficient are separate quantities.

No raw pickle retrieval is needed. Raw spikes and full cfgs remain on HPC.
Per-population time courses use 20 ms bins and Gaussian smoothing sigma 50 ms,
computed over the full 0–6 s record; endpoint/phase rates are separate unsmoothed
window summaries.

## Execution log

- Inspected the protected helper configuration: the automation checkout is clean
  and has no active run. Existing limits permit the four-child, concurrency-two
  request. Pilot parameters and outputs prepared locally; no job submitted yet.
- Local preflight resolves exactly four children and the new shared result path.
  Initial comparison caught the archived all-thalamus fade versus branch-freeze
  population-order difference, which changes per-population background seeds.
  The pilot now uses `CORE_POPS + MATX_POPS`, matching both archived branch-freeze
  cfgs. Background weights/rates/sections, baseline currents, mechanisms, targets,
  gains, and seed assignment are checked against the archived branch cfg.
- All four combinations passed the archived-baseline comparison; the eight child
  artifact paths are unique. Twelve HPC preflight/batch/interface tests passed.
- Pushed documentation commit `0612925` and pilot commit
  `e135ab7ef3fd0cd86bfdbdd916e0236a1bf524c6` to `origin/codex-hpc`.
- Updated the clean automation checkout with `hpc-code-update`; prepared and
  submitted `thal-irem-fade-pilot-20261020a` with `hpc-job-prepare` / `hpc-job`.
  Controller Slurm job **118798**, submitted 2026-10-20 18:11:21 UTC (14:11 EDT).
  Scientific result folder:
  `exp_results/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/exp_thal_irem_branch_fade_pilot_nseed_2_t_5.0_6.0_wmult_0.25_ee_0.5`.
- First controller failed before child submission because `external/` is a local,
  ignored dependency absent from the automation checkout. Removed that new remote
  dependency: rate dynamics now use the existing repository helper with the same
  requested bins/smoothing; local analysis uses `sim_data_analyzer` for archived
  reference data. No simulations ran in attempt A.
- Finalized and released failed attempt A with the protected utilities. Pushed
  correction `a1d5bb23de7c6e934b44b3948193e4f7737556db`, updated and prepared
  attempt B, and submitted controller **118799** at 18:15:19 UTC (14:15 EDT),
  run ID `thal-irem-fade-pilot-20261020b`. Same four-run request and scientific
  parameters; only the rate-export dependency changed.
- Attempt B controller and all four children completed with scheduler exit 0.
  Protected finalization nevertheless marked the run failed: the top-level
  request declared only `jobs/index.jsonl`, whereas its child records also
  declared the four result JSONs and four rasters. The helper requires every
  child output to be included in the top-level completion list. This was a
  request-definition error, not evidence of a failed simulation. It blocks the
  result-inventory utility for attempt B. Corrected the nine-file manifest and
  selected a fresh `_pilot_v2` result name for a clean rerun; old files and the
  failed finalization record are preserved. Child logs confirm correct projection
  labels and 6 s simulations (~18 s integration, ~32 s total per child).
