# Connected L2 second pilot

Authorized on 2026-10-14. Status: local checks passed; preparing HPC submission.
The user selected ±0.03 nA after the provisional J-Q comparison; no further
fitting is part of this run.

## Protocol

- Connected populations: IT2, PV2, SOM2, VIP2, NGF2, including within-population
  feedback. Outside-L2 surrogates and all baseline calibration remain unchanged.
- Seeds: 1000 and 1001. Groups: IT2, PV2, ordinary empty control.
- Amplitudes: -0.03 and +0.03 nA. Twelve trials, including four redundant
  zero-input trials; no special treatment of the control group.
- Duration: 100 s. Step onset: 40 s; step persists to simulation end.
- Windows: baseline 10–40 s, response 60–100 s, early 60–80 s, late 80–100 s.
- Resources: 30 ranks and 128 GB per trial, concurrency five. Controller:
  two cores and 16 GB. Existing 1440-minute wall-time ceilings are unchanged.
- Raw 5-ms rate bins and grid-free figures; window rates use raw spike counts.
- Same-seed matching issue remains deferred. Do not assume treatment/control
  noise cancellation; retain ordinary and drift-adjusted contrasts.

The provisional linear prediction for +0.03 nA is IT2 input → IT2/PV2 changes
of +0.610/+4.156 Hz, and PV2 input → PV2 +5.521 Hz. Negative steps reverse
these signs in the linear predictor, not necessarily in the simulation.

## Request and paths

Tracked request: [`hstep-l2-long-pilot.json`](../../hpc_jobs/requests/hstep-l2-long-pilot.json).
Planned run ID: `hstep-l2-long-pilot-001`.

Expected HPC result path:

```text
/ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/
batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
exp_L2_pilot2_nseed_2_ngroup_3_namp_2_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5/
```

The existing read-only mount of the experiment parent should expose this new
sibling result folder without a new mount. Preserve the first pilot outputs.
Use installed HPC helpers for checkout update, preparation, submission,
bounded log/status monitoring, finalization, and explicit release.

## Checks

The three experiment tests passed in the existing local NetPyNE environment.
Scientific preflight resolved exactly twelve trials and the expected new path.
Only amplitude, pilot-attempt label, duration, onset, and response-start
constants changed in the simulation configuration; calibration assets,
connection rules, group definitions, seeds, and resources are unchanged.
