# B0.3 protected job-preparation promotion and handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Capability and boundary

B0.3 adds one operation:

```text
hpc-job-prepare REQUEST_ID RUN_ID EXPECTED_COMMIT
```

It reads one tracked request and one approved tracked shell template from the
exact clean automation checkout. It validates protected resource ceilings,
renders only fixed tokens, and writes this ignored repository directory:

```text
hpc_jobs/runs/<run-id>/
  request.json
  run.json
  submit.sh
```

It also writes a compact authoritative copy of `run.json` beneath
`hpc_codex/state/A1_OUinp/runs/`. The prepared files are hash-bound and
non-writable; repeating the same request, run ID, and commit is an idempotent
no-op.

Preparation does not run `sbatch`, contact lattice, import experiment Python,
run scientific preflight, create a scientific result directory, or start a
simulation. The tracked entry points run scientific preflight later, inside
the allocated top-level job.

## Reviewed identities

```text
8e5c4621ec622e09ab8dbf023f18691dae953a87407f3bb694e448bca4d9de20  local/hpc-job-prepare
166d9b783b50f90b9e7032be8397fbe8ea8f668be8e193b0736ccf9f71b566da  local/hpc_common.py
6221cc6f242c9561b00c9515ed0f79201049066d78de78c726a5be511d6ff4f5  hpc_jobs/job-request.schema.json
822f3ce58fa3efa9a3414494af6cc1d6803a874b5ac039c1d9bf0ec52ee2fa2a  schemas/remote-hpc-prepare-config.schema.json
e875b0522369b8b130fc15f365fc55f43724eef03a47402dda51934ff8859c2c  schemas/prepared-job-record.schema.json
4534cf3ef47f53d89319afafbce9f67206b6df315d5135cf98c7558cdfa37e23  remote_lethe/hpc-lethe-prepare
029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893  hpc_job.py
b90ecb9ea30fee7ba73f520f7ca14e4d6b834289fc7238e27d461b470b3a4484  config_examples/remote-hpc-prepare.json.example
a4b048d54db100915eb4eefb347588fe4c92096fc625c69a1a07f28008318eb9  test_fixtures/b0_prepare_cases.json
b0d153b166dd7b91be1a77462b805114b055cf3123b00f349c7c6e36202ef32a  hpc_jobs/requests/b0-prepare-single.json
```

The local protected bundle version is `0.8.0-b0`; its reviewed bundle SHA256
is:

```text
d64ff946c6832d0ee8f8f6fcd89b605f3c7c9b64b682e8fdb8145e9e1d95852f
```

## Commit and checkout prerequisite

Codex will commit and push these sources and report the exact full commit as
`B0_COMMIT`. Update the automation checkout through the installed A2 command:

```bash
B0_COMMIT='<full 40-character commit reported by Codex>'
/opt/a1-hpc/bin/hpc-code-update --json "$B0_COMMIT"
```

Require status `ok`, commit equal to `B0_COMMIT`, branch `codex-hpc`, and a
clean checkout before either promotion.

## Local promotion

Run locally under `sudo`:

```bash
B0_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_b0_prepare_local.sh \
    "$B0_COMMIT"
```

The script installs the local command, updated common module, and schemas. It
does not call the new command. Copy the complete file printed as
`B0_PREPARE_REPORT` if the final result is not `PASS`.

## Remote promotion

Run on lethe without `sudo`:

```bash
B0_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_b0_prepare_lethe.sh \
    "$B0_COMMIT"
```

The script installs the lethe command, a read-only copy of the repository job
contract, the fixed configuration, and fixtures. It creates only the ignored
job-run root, compact state root, and preparation lock. It does not prepare a
run. Copy the complete file printed as `B0_PREPARE_REPORT` if the final result
is not `PASS`.

## Protected test order

After both promotions pass, Codex will:

1. verify bundle identity, installed hashes, exact commit, and modes;
2. run the local scientific preflight for `b0-prepare-single` without a
   simulation;
3. invoke the installed command once with run ID
   `b0-prepare-single-001`;
4. verify the request, run record, rendered script, hashes, modes, and compact
   state copy;
5. repeat the same invocation and require `already-prepared`;
6. test rejected identifier and wrong-commit inputs without new files;
7. verify that no `submission.json`, Slurm ID, scientific result, or scheduler
   operation was created.

No step in B0.3 submits a job.

## Call chain

```text
Codex
  -> /opt/a1-hpc/bin/hpc-job-prepare REQUEST_ID RUN_ID EXPECTED_COMMIT
  -> validate identifiers and append the local audit event
  -> /usr/bin/ssh lethe
  -> hpc-lethe-prepare prepare REQUEST_ID RUN_ID EXPECTED_COMMIT
  -> lock preparation and require the exact clean codex-hpc checkout
  -> read the tracked request and approved template
  -> enforce protected resources and verify tracked target files
  -> render fixed tokens without importing repository Python
  -> atomically publish hpc_jobs/runs/RUN_ID
  -> write the compact external run record
  -> return bounded JSON and append the final local audit event
```
