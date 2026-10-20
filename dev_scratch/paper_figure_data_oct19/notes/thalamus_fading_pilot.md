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
contacts, seven-population rate dynamics exported with `sim_data_analyzer`, and
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
