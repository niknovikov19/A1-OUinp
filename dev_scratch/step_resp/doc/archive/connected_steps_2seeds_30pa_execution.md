# Connected L2 second pilot

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Authorized and completed on 2026-10-14. All twelve children and controller
`118074` completed successfully; protected finalization verified all 49
required files, and the checkout lock was explicitly released.
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

Tracked request: [`hstep-l2-long-pilot.json`](../../../../hpc_jobs/requests/hstep-l2-long-pilot.json).
Run ID: `hstep-l2-long-pilot-001`.
Simulation commit: `ba7022adb012d4b0b3c67fa2c1ba1c51bdd8b3d2`.
Submission time: 2026-10-14 21:24:17 America/New_York
(2026-10-15 01:24:17 UTC). The installed helpers fast-forwarded the clean
automation checkout, prepared the reviewed request, and submitted once.
No new helper promotion was required.

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

The first five child jobs, `118075`–`118079`, completed successfully and the
next five, `118080`–`118084`, started. Sampled logs confirm 30 MPI ranks and
integration for 100000 ms. Controller startup emitted only the known display,
rxdmath, and Ray deprecation warnings; no new dependency changes were needed.

## Completion and local handoff

All twelve children, Slurm IDs `118075`–`118086`, completed. The final trial
finished at 21:41:27 America/New_York: 16 min 36 s for the trial phase, or
17 min 10 s after controller submission including startup. Saved NetPyNE
total times range from 297.36 to 321.41 s per child.

Protected finalization passed at 21:41:42 and release passed at 21:42:06.
Subsequent checkout status was clean with no active-run marker.

Copied only the 49 compact files once to
`data/_old/l2_connected_steps_2seeds_30pa_100s/input/`: configurations, result JSONs, rate/current
NetCDFs, and the child index (locally named `jobs_index.jsonl`). Total size
is 23,958,898 bytes. `input_manifest.json` records HPC paths and verified
source/local SHA256 hashes. Large PKLs, saved network parameters, and remote
figures were not copied.

Existing `code/analyze_hstep.py` checks passed for all twelve local trials:
finite raw traces, waveform amplitudes/onset, clamp counts, spike-count
arithmetic, and agreement between raw rate means and saved window rates.
The saved windows are exactly 10–40, 60–100, 60–80, and 80–100 s.
`validation.json` records these checks and the unchanged same-seed limitation:
pre-step treatment/control traces and duplicate zero-input traces are not
identical. This is reported, not repaired or treated as matched noise.

The descriptive response analysis and J-Q comparison are now complete in
`data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/`, with feedback predictions under `analysis/jq/`.
See [the analysis note](connected_steps_2seeds_30pa_results.md) for findings,
figures, output files, and repeat commands. No additional fitting or baseline
tuning was performed.
