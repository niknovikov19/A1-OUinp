# B2 BatchTools-main resource retry

Run `b2-child-discovery-001` reached Slurm as job `117831`, but Ray startup
consumed the complete 2 GB main-job allocation. Slurm recorded 21 OOM kills,
the job timed out, and no child job was submitted. The run was finalized as
`TIMEOUT` and released; never submit that run ID again.

The retry uses the established `submit_batch_slurm_local.sh` allocation for
the BatchTools main job: 1 node, 2 CPUs, 16 GB, and 24 hours. The two B2
simulation jobs remain at 1 CPU, 2 GB, and 10 minutes each.

## Local promotion

After Codex reports the exact commit, run locally under `sudo`:

```bash
B2_RETRY_COMMIT='<full 40-character commit>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_b2_retry_local.sh \
    "$B2_RETRY_COMMIT"
```

## Remote promotion

First update the automation checkout through `hpc-code-update`. Then run on
lethe without `sudo`:

```bash
B2_RETRY_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_b2_retry_lethe.sh \
    "$B2_RETRY_COMMIT"
```

That promotion passed and run 004 proved that Ray returns on `node03`. Its
child scripts failed during BatchTools formatting, and recovery continues in
`INSTALL_B2_FINALIZE_RECOVERY.md`.

Both reports must end in `B2_RETRY_RESULT=PASS`. Promotion changes only the
reviewed preparation ceilings and does not submit a job. Codex will then
preflight and prepare fresh run `b2-child-discovery-002`, show its rendered
script, and obtain separate approval before submission.

Run `b2-child-discovery-002` proved that the established memory allocation was
sufficient, but Ray stalled while installing a 115.79 MiB repository package.
It was explicitly cancelled, finalized, and released with no children. The
tracked follow-up removes unnecessary repository packaging for local Ray and
uses fresh run `b2-child-discovery-003`; no additional protected promotion is
required for that repository-code change.

Run `b2-child-discovery-003` removed repository packaging, and Ray reported a
successful local startup, but `ray.init()` again did not return. All three B2
attempts ran on `node10`; the same environment previously completed a large
BatchTools run on the cluster. After explicit approval, job `117833` was
cancelled, finalized, and released with no children. The next tracked retry
adds `#SBATCH --exclude=node10` to the canonical batch main-job template and
uses fresh run `b2-child-discovery-004`. Simulation-job settings are unchanged.

The changed template hash requires only the remote preparation policy to be
promoted again; the local protected installation and helper code are unchanged.
After updating the automation checkout to the reported commit, run on lethe:

```bash
B2_RETRY_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_b2_retry_lethe.sh \
    "$B2_RETRY_COMMIT"
```
