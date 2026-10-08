# A6.1 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Capability and boundary

A6.1 adds:

```text
hpc-log RUN_ID controller
```

The caller supplies only a validated run ID and the literal target
`controller`. The lethe helper derives the controller job ID and exact stdout
and stderr paths from the protected `run.json` and `submission.json`. It does
not accept paths, offsets, byte limits, line limits, shell text, or job IDs.

Each stream returns at most 64 KiB and 200 new lines. The local helper stores
only file identity, byte offset, size, and nanosecond modification time under
`/opt/a1-hpc/state/log-cursors.json`. An unchanged file returns no new output;
replacement or truncation resets the offset to zero with an explicit notice.
If a cap is reached, the cursor advances only through returned bytes, so later
calls can drain remaining content without skipping it.

A6.1 first proves reading an existing completed A5 log and then reading no new
content. A6.2 will use a separately approved fixed probe to prove real appended
content over time.

Reviewed candidate SHA256 values:

```text
58840c04606f72071184688aedc6c12449851da9d1235768b910466ef7b7fee1  hpc-log
3a530d2642c802c56a1f87ed621e2a022a87d976183a1f2ec51d14476557cdc3  hpc_common.py
fe5cb43eb133fcf1749620e2a9e421b36e1b0bdabc278d7ab5fa7dc90169bff3  hpc-lethe-log
66ddc07b2ee57a6063bc6c9e6bf0e562fbc760092998fd6c95d573053e8ec034  remote-hpc-log.json.example
c753d732b59f335cd4b322af5673ef528673232f228a10cc18756d779e30b929  a6_log_cases.json
a8ba0c96003c974370c139e9b340dcf8f4a5802638f5c25b63a4b6d319c380b4  remote-hpc-log-config.schema.json
e347a74947d70c64c6422c25b343bac3e11cdfc5e421d69761c73989dc18997a  log-cursor-state.schema.json
10e02d67326b32d1fa331138ec6058a7f71672f8de459069d6e6efbb7127d7b2  log-read-result.schema.json
```

The expected installed local bundle version is `0.7.0-a6`, with SHA256:

```text
ce7488da6de975fb22fa93cdc39dbe893cfefb3b4ecc67abfb022d1477c5fb2a
```

## Commit and checkout prerequisite

Codex will commit and push the reviewed A6.1 source and report the exact full
commit as `A6_COMMIT`. The protected A2 updater must move the automation
checkout to that commit before remote promotion. Confirm a clean `codex-hpc`
checkout with no active run or update lock.

## Local promotion

Run under `sudo`:

```bash
A6_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_a6_local.sh \
    "$A6_COMMIT"
```

The script installs only the local log helper, updated shared module, and A6
schemas. It leaves ownership and modes of `/opt/a1-hpc/state` and
`actions.jsonl` unchanged. Cursor and lock files are created later by the
installed helper as the normal user with mode `0600`.

## Remote promotion

Run on lethe without `sudo`:

```bash
A6_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_a6_lethe.sh \
    "$A6_COMMIT"
```

The script installs the lethe-only log reader, its non-secret configuration,
and hash-bound fixtures. It does not install a grid helper because the Slurm
logs reside on the shared filesystem and bounded reading is a lethe operation.

## Handoff and protected test order

Copy both complete files printed as `A6_REPORT`. After both pass, Codex will:

1. verify installed bundle, hashes, modes, and exact clean commit;
2. reject missing, traversal, wildcard, unknown-target, and extra arguments;
3. run `hpc-log --json --self-test` and require nine cases to pass;
4. read `a5-lifecycle-probe controller` once and require only its known
   stdout/stderr paths, bounded content, and initial-reset metadata;
5. repeat the same read and require empty content with unchanged identities and
   offsets;
6. verify cursor/lock modes `0600` and bounded redacted audit entries.

No Slurm submission or mutation occurs in A6.1.
