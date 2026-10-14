# Connected L2 first-test status

## Reviewed first-test configuration

The user revised the initial test on 2026-10-14:

- All five L2 populations remain connected and active.
- Input groups: `IT2`, `PV2`, and the ordinary empty `control` group.
- Seeds: 1000 and 1001; amplitudes: -0.005 and +0.005 nA.
- Twelve jobs, including four redundant empty-group jobs.
- Duration: 40 s; step onset: 20 s; response measurement start: 30 s.
- Derived windows: baseline 10–20 s, response 30–40 s, early 30–35 s,
  late 35–40 s.
- Planned child resources: 30 ranks and 128 GB; concurrency five.

The tracked request is
[`hstep-l2-first-pilot.json`](../../hpc_jobs/requests/hstep-l2-first-pilot.json).
Its planned HPC result directory is:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
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
- Three tests in [`code/test_hstep_exp.py`](code/test_hstep_exp.py) passed:
  matched baseline/seed streams, arbitrary empty/weighted groups, and
  half-open spike-count/current boundaries.
- Repository scientific preflight resolved twelve jobs and the intended path.
- Forty-five request/preflight/lifecycle regression tests passed.
- Read Ray's grid enumeration on Lethe to bind the 48 per-child completion
  files to the actual trial indices; the job index gives 49 required files.
- The two Gate-B promotion scripts passed shell syntax checks.

## HPC launch pending promotion

The installed helper permits ten children per batch. The test has twelve.
Prepared promotion scripts raise only the child ceiling to twelve, retaining
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

Under the user's Gate-B procedure, the user runs the promotion scripts and
reports `HPC_CHILD_LIMIT_RESULT=PASS`. No simulation has been submitted yet.
After promotion, prepare and submit `hstep-l2-first-pilot-001`, monitor all
children, validate the declared artifacts, and inspect matched controls and
late-window settling before interpreting prediction accuracy.
