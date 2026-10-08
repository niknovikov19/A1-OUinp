# A5.1 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Capability and boundary

A5.1 adds compact scheduler monitoring for runs that already contain recorded
Slurm IDs. It does not accept scheduler IDs, paths, hosts, commands, or query
options from the caller. `hpc-status RUN_ID` resolves the fixed run directory,
loads IDs only from `run.json`, and makes at most one `squeue` and one `sacct`
query through the installed two-hop helper chain.

The helper preserves raw state, reason, and exit code while normalizing states
to `pending`, `running`, `completed`, `failed`, `cancelled`, `timeout`,
`out-of-memory`, or `unknown`. A job absent from both queries becomes
`unknown` with a 120-second accounting-grace recommendation; it is never
treated as failed.

For a successful known observation, the lethe helper writes `status.json`
atomically and reconciles `run.json.status`. Unknown or unavailable scheduler
state does not overwrite `run.json`. This increment first tests the completed
A4 job through `sacct`; it does not submit a new job. A later A5.2 increment
will add the separately approved slow lifecycle probe.

Reviewed candidate SHA256 values:

```text
dde49bb7b565adb96fb38b559e0cbbaa5eb8abbf5fc7353e5f72634871543cd0  hpc-status
e4b894a3b7e92585974d48ab6c4de87b77b3646665c20f6b9b730fa713432423  hpc_common.py
5f5f7ed374d35f9dd1e7d8dc163b276a84d8b86544b3f603d917f977e7171f83  hpc-lethe-status
12cc75cf5355d8544cfba35e54dcc45e95c8043a4c401c7f8fa58679dfd82c9d  hpc-grid-status
3ccd72366ce7c3809edea0ed15b8acd87b5af8e1dcf856662798bacc76cac905  remote-hpc-status.json.example
d0d9b5b2ffaa36b779ba78c8b42f825c57cbef42299acaa9de552de37b0b6840  a5_status_cases.json
fff824437f4b755b8fad896346c9ad53eae101add4b87a82031389551a189c75  remote-hpc-status-config.schema.json
e29da82aa81c9cb62d9bb5f52f4b9201c3aae40c60eb9abe3672086e6a2e7ade  status-record.schema.json
```

The expected installed local bundle version is `0.6.0-a5`, with SHA256:

```text
ed3200ad97205464f86120ed0daf116cb73bb669b7d7c0c9615ce83c55f55d76
```

## Commit and checkout prerequisite

Codex will commit and push the reviewed A5.1 source and report the full commit
as `A5_COMMIT`. Update the automation checkout through the protected A2 helper
before remote promotion:

```bash
/opt/a1-hpc/bin/hpc-code-update --json "$A5_COMMIT"
```

Do not promote remote files until `hpc-code-status --json` reports a clean
`codex-hpc` checkout whose local and remote commits both equal `A5_COMMIT`.

## Local promotion

Run the reviewed local promotion script under `sudo`:

```bash
A5_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_a5_local.sh \
    "$A5_COMMIT"
```

The script checks the exact commit and reviewed hashes, installs only
`hpc-status`, `hpc_common.py`, and the two A5 schemas, restores protected
directory modes on failure, verifies bundle identity and permissions, and
writes a report under `/tmp`.

It must leave `/opt/a1-hpc/state` and `actions.jsonl` ownership and modes
unchanged.

## Remote promotion

Log in to lethe as `niknovikov19`; do not use `sudo`:

```bash
A5_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_a5_lethe.sh \
    "$A5_COMMIT"
```

The script checks the exact clean checkout, expected owner/group, reviewed
hashes, non-secret configuration, and fixture binding. It installs the lethe
and grid status helpers, status configuration, and fixed parser fixtures. It
restores helper/configuration directories to `0555`, installs helpers as
`0555`, configurations as `0444`, and writes its report beneath
`hpc_codex/state/A1_OUinp/reports/promotion`.

## Handoff to Codex

Copy and paste both complete files printed as `A5_REPORT`. They must show
`A5_RESULT=PASS`, all reviewed and installed hashes, bundle `0.6.0-a5`, and
the required modes.

After the reports pass, Codex will request permission for the protected A5.1
checks. No Slurm submission approval is needed because A5.1 only queries the
already-completed A4 job. A successful status check will write `status.json`
and change that run's `run.json.status` from `submitted` to `complete`.

## Protected test order

Codex will:

1. verify installed identities, modes, exact commit, and clean checkout;
2. reject missing, unknown, traversal, and extra-argument run selections
   locally or on lethe before querying Slurm;
3. run `hpc-status --json --self-test` and require all 16 fixed normalization,
   parser, and malformed-output cases to pass;
4. run `hpc-status --json a4-slurm-probe-v2` and require one `squeue` plus one
   `sacct` query, raw `COMPLETED`, normalized `completed`, and job `117706`;
5. repeat the status call and require the same scheduler classification with
   `run.json.status` reconciled to `complete`;
6. inspect the bounded local audit tail and ask the user for the exact
   `status.json` and reconciled `run.json` if needed.

Passing A5.1 proves completed-job accounting fallback and parser behavior.
A5 remains incomplete until A5.2 observes a fixed probe while active, handles
any measured `squeue`-to-`sacct` gap, and reaches terminal state without
per-job SSH connections or log reads.
