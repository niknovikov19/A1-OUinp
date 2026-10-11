# B2 child-job recording promotion and handoff

These instructions are for the user. Codex must not execute candidate files
from `helper_src` or write into either protected installation.

## Capability and boundary

B2 extends the proven prepared-job lifecycle from a single top-level
simulation to one BatchTools main job with exactly two simulation jobs. The
main job calls `/usr/bin/sbatch --parsable` for each child and immediately
records the returned Slurm ID, BatchTools label, parameter coordinates, exact
log paths, and declared scientific output in:

```text
exp_results/batch_hpc_prototype/b2_child_discovery/<result>/jobs/index.jsonl
```

The protected finalizer ingests that bounded index. A completed B2 batch is
not accepted unless both child records and all three request-declared files
exist. Promotion does not submit or run a job.

## Commit and checkout prerequisite

Codex will commit and push the candidate and report `B2_COMMIT`. Update the
automation checkout through the approved A2 helper:

```bash
B2_COMMIT='<full 40-character commit reported by Codex>'
/opt/a1-hpc/bin/hpc-code-update --json "$B2_COMMIT"
```

Require status `ok`, commit equal to `B2_COMMIT`, branch `codex-hpc`, a clean
checkout, and no active run.

## Local promotion

Run locally under `sudo`:

```bash
B2_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_b2_job_local.sh \
    "$B2_COMMIT"
```

The final lines must include:

```text
B2_JOB_RESULT=PASS
B2_JOB_REPORT=/tmp/b2-job-local-promotion.<suffix>.txt
```

## Remote promotion

Run on lethe as `niknovikov19`, without `sudo`:

```bash
B2_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_b2_job_lethe.sh \
    "$B2_COMMIT"
```

The final lines must include:

```text
B2_JOB_RESULT=PASS
B2_JOB_REPORT=/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/b2-job-remote-promotion.<suffix>.txt
```

On lattice, verify that the established simulation environment also contains
the BatchTools main-job dependency:

```bash
source ~/.bashrc
conda activate netpyne_batch_slurm
python -c 'import ray; import netpyne.batchtools.search; print(ray.__version__)'
```

This imports software only; it does not submit or allocate a job.

## Post-promotion order

After both promotions pass, Codex will:

1. verify the exact clean automation checkout;
2. run read-only B2 preflight and prepare `b2-child-discovery-001`;
3. show the commit, resources, two seed coordinates, result path, and rendered top-level script;
4. request explicit approval for the real `hpc-job submit` call;
5. submit once, monitor the recorded main-job ID and bounded top-level logs;
6. inspect `jobs/index.jsonl` and the two recorded child IDs;
7. finalize only after Slurm and all declared output evidence agree;
8. explicitly release the checkout lock.
