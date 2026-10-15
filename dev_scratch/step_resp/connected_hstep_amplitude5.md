# Connected L2 amplitude-scaling experiment

Protocol: [amplitude-test specification](connected_hstep_amplitude_test.md).
Request: [`hstep-l2-amplitude5.json`](../../hpc_jobs/requests/hstep-l2-amplitude5.json).
Run ID: `hstep-l2-amplitude5-001`. Local dataset: `data/l2_hstep_amplitude5/`.

## Configuration and preflight

- Five seeds: 1000–1004; groups IT2, PV2, and ordinary empty control.
- Signed amplitudes: −0.03, −0.015, +0.015, +0.03 nA.
- Sixty fresh trials: 40 current-step trials and 20 zero-input controls.
- Duration 100 s; step onset 40 s; baseline 10–40 s; response 60–100 s,
  with early/late halves 60–80 and 80–100 s.
- Thirty ranks and 128 GB per child; concurrency ten. Controller: two cores
  and 16 GB. No baseline calibration, connectivity, or identification fits change.
- Scientific preflight resolves the correct folder and all 60 jobs. Three
  experiment tests pass; four controller-index tests pass, including a 60-job
  index larger than 64 KiB. The writer now uses the same 1-MiB index budget
  as the protected readers; no protected-helper promotion is required for
  this repository controller change.

Expected HPC result directory:

```text
/ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/exp_L2_pilot3_nseed_5_ngroup_3_namp_4_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5/
```

## Execution

Submission is pending the committed revision, protected checkout update,
preparation, and submission. Preserve the actual commit, controller ID,
timestamps, and finalization/release evidence here as execution proceeds.

## Processing

After successful finalization, use the installed archive helper to download
and verify the 241 compact outputs once. Keep large simulation files on HPC.
Process locally using the existing NetPyNE environment and `sim_data_analyzer`
rate caches; retain both control-subtracted response definitions and all seeds.

Keep exactly the prior pooled J (with its two requested provisional zeros)
and the slow symmetric Q. Record their byte hashes and compare them with the
second-pilot prediction manifest before calculating the new-amplitude
predictions. No refitting or parameter tuning against these new responses.
Produce signed-amplitude summaries, per-seed central slopes and sign symmetry,
half-amplitude/full-amplitude comparisons, early/late diagnostics, and smoothed
rate dynamics with seed overlays and static prediction levels. All figures
have grids disabled and omit the initial transient from rate-trace scaling.
