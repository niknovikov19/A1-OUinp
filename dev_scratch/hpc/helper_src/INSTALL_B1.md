# B1 prepared single-job lifecycle promotion and handoff

These instructions are for the user. Codex must not execute candidate files
from `helper_src` or write into either protected installation.

## Capability and boundary

B1 adds one local command with five fixed operations:

```text
hpc-job submit RUN_ID EXPECTED_COMMIT
hpc-job status RUN_ID
hpc-job log RUN_ID
hpc-job finalize RUN_ID
hpc-job release RUN_ID
```

Only `submit` calls `sbatch`, and it does so through the promoted lattice
helper with the exact script recorded by `hpc-job-prepare`. `status`, `log`,
`finalize`, and `release` derive their Slurm ID and paths from protected
records. There is no arbitrary command, path, scheduler option, retry,
cancellation, or resubmission interface.

Promotion itself installs files and creates fixed state directories and lock
files. It does not call `hpc-job`, SSH, `sbatch`, `squeue`, `sacct`, or any
simulation command.

## Reviewed identities

```text
8680486c21a5624e770b0abb12246ee642a80679956c56b40ad857d55d3ffe19  local/hpc-job
53fab445f36923bd892e0df1999c8713ac2c4bda458beba62b298892e61ec17c  local/hpc_common.py
2556cd22f3591189f63b21bbb6a46b3722ee7ca2045cd079110a314d76ef70d3  remote_lethe/hpc-lethe-job
70623d66bc717c3041118f3773466bd31ae3aa5c133080c2bb1ffbb82780d0a6  remote_grid/hpc-grid-job
029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893  hpc_job.py
ede38c3b8534e5c3c535b33263379dcc5804228be809e24c133a3163079b2d19  hpc_job_lifecycle.py
95a58889e3a7622282a95556e5e7aad44d9e4b1b5456b07398da73618f98de8d  hpc_job_control.py
b39c9a26daf5edf7b5833ce59e2001a0f844f662093ea156fe562d503a89b94c  config_examples/remote-hpc-job.json.example
b90ecb9ea30fee7ba73f520f7ca14e4d6b834289fc7238e27d461b470b3a4484  config_examples/remote-hpc-prepare.json.example
67d7131c8be99d4933702e08b9b9a8d29371a0d0fe47560b856939139ff40ec9  schemas/remote-hpc-job-config.schema.json
f096e453957cc94c25660093757b86ef536f1786e471cef1b36af0d43666506f  test_fixtures/b1_job_cases.json
```

These hashes are checked by the promotion scripts. The local protected bundle
version is `0.9.0-b1`; its reviewed bundle SHA256 is:

```text
ec8fc7a262fc3296f8b9f89a6db8a176eeb43a0acbe39e5a91ce68e6d1aee530
```

## Commit and checkout prerequisite

Codex will commit and push the candidate and report the full `B1_COMMIT`.
Update the automation checkout only through the approved A2 helper:

```bash
B1_COMMIT='<full 40-character commit reported by Codex>'
/opt/a1-hpc/bin/hpc-code-update --json "$B1_COMMIT"
```

Require status `ok`, commit equal to `B1_COMMIT`, branch `codex-hpc`, a clean
checkout, and no active run.

## Local promotion

Run locally under `sudo`:

```bash
B1_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_b1_job_local.sh \
    "$B1_COMMIT"
```

The script must finish with:

```text
B1_JOB_RESULT=PASS
```

## Remote promotion

Run on lethe as `niknovikov19`, without `sudo`:

```bash
B1_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_b1_job_lethe.sh \
    "$B1_COMMIT"
```

The script installs the lethe and lattice commands, protected copies of the
three repository contract modules, one read-only non-secret configuration,
the reviewed tracked-template policy, and the reviewed fixture. It also
creates mode-`0700` submission, final, and release record directories plus
mode-`0600` job and grid-submission locks.
It must finish with:

```text
B1_JOB_RESULT=PASS
```

Promotion reports remain beneath:

```text
/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/
```

## HPC runtime handoff before submission

On lattice, activate the established simulation environment and report these
read-only checks:

```bash
source ~/.bashrc
conda activate netpyne_batch_slurm
command -v srun
command -v nrniv
command -v python
srun --version
python --version
```

These commands verify the tracked single-job template's internal launch
convention. They do not allocate resources or run a simulation.

## Post-promotion order

After both promotion reports and the runtime handoff pass, Codex will:

1. verify the installed bundle and the clean exact automation checkout;
2. prepare a fresh run ID at the final commit;
3. verify the new prepared record and rendered-script hash;
4. show the exact request, commit, resources, result path, and command that
   would be submitted;
5. request explicit approval for the first real `hpc-job submit` call;
6. after approval, submit once, monitor the recorded ID and incremental logs,
   finalize against scheduler and completion-file evidence, and explicitly
   release the checkout lock.

The previously prepared `b1-single-smoke-001` remains B0 evidence and must not
be submitted because it is bound to an earlier commit.
