# Connected L2 first-test status

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Completed: twelve children and controller `118061` finished successfully;
protected finalization verified all 49 required files. Descriptive results are
in [the analysis report](connected_steps_2seeds_5pa_results.md). The same-seed mismatch
is [documented separately](../issues/same_seed_reproducibility.md), with its fix
deferred by the user.

## Reviewed first-test configuration

The user revised the initial test on 2026-10-14:

- All five L2 populations remain connected and active.
- Input groups: `IT2`, `PV2`, and the ordinary empty `control` group.
- Seeds: 1000 and 1001; amplitudes: -0.005 and +0.005 nA.
- Twelve jobs, including four redundant empty-group jobs.
- Duration: 40 s; step onset: 20 s; response measurement start: 30 s.
- Derived windows: baseline 10–20 s, response 30–40 s, early 30–35 s,
  late 35–40 s.
- Child requests: 30 ranks and 128 GB; concurrency five. A child log confirmed
  integration on 30 MPI ranks.

The tracked request is
[`hstep-l2-first-pilot.json`](../../../../hpc_jobs/requests/hstep-l2-first-pilot.json).
Its actual HPC result directory is in the automation checkout:

```text
/ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/
batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
exp_L2_pilot1_nseed_2_ngroup_3_namp_2_dur_40_step_t0_20_tresp_30_gset_1pop_v1_amin_-0.005_amax_0.005_ictrl_wmult_0.25_ee_0.5/
```

## Local checks completed

The existing local NetPyNE environment was used; no dependencies were installed.

- Applied and resolved every one of the twelve batch conditions.
- Constructed actual full-model NetPyNE parameters, applied the experiment
  changes, and built the connected L2 subnet with `SubnetParamBuilder2`.
- Verified that all 25 L2 projection pairs retain their original rules,
  including the five within-population pairs. The summary has 175 rules;
  this is not a count of instantiated synapses.
- Verified that the connected subnet has no L2-origin surrogate populations,
  retains external surrogate rates, and declares the correct additive clamps.
- Three tests in [`code/test_hstep_exp.py`](../../code/test_hstep_exp.py) passed:
  matched baseline/seed streams, arbitrary empty/weighted groups, and
  half-open spike-count/current boundaries.
- Repository scientific preflight resolved twelve jobs and the intended path.
- Forty-five request/preflight/lifecycle regression tests passed.
- Read Ray's grid enumeration on Lethe to bind the 48 per-child completion
  files to the actual trial indices; the job index gives 49 required files.
- The two Gate-B promotion scripts passed shell syntax checks.

## HPC launch and initial import correction

Before promotion, the installed helper permitted ten children per batch. The
test has twelve. The promotion scripts raised the child ceiling to twelve, retaining
five concurrent children and the established per-child resources:

```text
dev_scratch/hpc/helper_src/promotion/promote_child_limit_12_local.sh
dev_scratch/hpc/helper_src/promotion/promote_child_limit_12_lethe.sh
```

The repository completion-manifest bound is raised from 32 to 64 so the
request can declare all 49 files. It remains bounded and has a regression
check rejecting oversized manifests. The remote promotion also updates the
protected request-contract copies on Lethe and grid; their old hashes were
checked directly before writing the promotion.

Both Gate-B promotions passed. Run `hstep-l2-first-pilot-001` was submitted
as controller job `118060` from commit `8850329`, but failed during experiment
import before launching children. The new configuration resolved companion
modules through `external/`, whereas the HPC dependency is a sibling
repository. Earlier experiments incidentally added that parent directory
through another analysis import. The corrected configuration explicitly adds
the repository parent to its import paths. No baseline parameters changed.

The failed controller was finalized and released. Retry
`hstep-l2-first-pilot-002` used the same still-unused scientific result path
and simulation commit `2431fe2a4faea65df7164748398c60baba3d6a26`.

## Successful retry and policy correction

All twelve child jobs and controller `118061` completed. The trial phase took
6 min 24 s, plus controller initialization/queueing; saved NetPyNE simulation
times are 93.93–165.22 s per child. The separate status-query policy still had
an eleven-ID ceiling, whereas twelve children plus their controller require
thirteen IDs. This blocked whole-tree status/finalization, not simulation.

The user promoted 100 IDs and a 30-second timeout per scheduler command:

```text
/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/hpc-status-limits-promotion.XcoupK.txt
```

The installed policy hash was verified as
`28f59366c6c05c86c1fb7fbdc3be143293c27fde67c624ced54f66bf20deee7c`.
`hpc-job status` then reported the controller and all children completed;
`hpc-job finalize` verified 49 files, and `hpc-job release` removed the
active-run marker. Submission/concurrency limits stayed twelve/five.

## Local analysis completed

Copied 61 compact inputs (~12 MB) once into `data/_old/l2_connected_steps_2seeds_5pa_40s/input/` and
verified source/local SHA256 hashes. All further analysis uses that local
copy. Saved spike-count means agree with raw rate-bin means, current traces
match the intended step vectors, and cell/clamp counts agree.

All eight same-seed treatment/control pre-step traces differ, and both
same-seed duplicate zero-input pairs differ. This limitation is retained in
the results; no builder modification or rerun was performed. The analysis
reports the specified post-only contrast, seed-pooled zero-input references,
and drift-adjusted pre/post sensitivity. Four analysis tests pass.

Plots and tables are in `data/_old/l2_connected_steps_2seeds_5pa_40s/analysis/`. The response window
is not uniformly settled, and the two existing J candidates still contain
non-finite entries. Qh is shown as an open-loop reference only; no complete
numerical J-Q prediction is claimed.
