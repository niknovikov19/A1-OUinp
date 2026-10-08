# A6.2 fixed append-probe promotion and handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Capability and boundary

A6.2 adds one fixed request ID:

```text
a6-incremental-log-probe
```

The request uses `cpu.q`, one node, one core, 1 GB, and a two-minute wall-time.
Its protected payload emits:

1. one immediate `log_probe_phase=initial` line;
2. 205 short lines after 35 seconds;
3. one 70,000-byte line after another 35 seconds;
4. the existing fixed completion marker and four summary lines.

This proves new-content-only reads, the 200-line cap with continuation, and the
64 KiB cap with continuation. The payload writes only beneath its fresh fixed
run directory. Promotion does not submit the request. Submission remains one
separate, explicitly approved operation and is never retried automatically.

Reviewed candidate SHA256 values:

```text
9628ae9fdf027107bd4371ee1a6c969932a92097ee9dcc5065689d16300b2722  preview-requests.json.example
df473859c40126158e6c0a569bd21dc41e634de7a845f6ed85c3a337d3e43610  hpc-grid-probe-job
fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665  hpc-grid-probe-job.sh
14330c9e7af7d061aaef434b6e8eb14a328af86fc399e913ed1bab14e936e270  remote-hpc-submit.json.example
```

The installed local A6 bundle remains version `0.7.0-a6`, with SHA256:

```text
ce7488da6de975fb22fa93cdc39dbe893cfefb3b4ecc67abfb022d1477c5fb2a
```

## Commit and checkout prerequisite

Codex will commit and push the reviewed A6.2 source and report the exact full
commit as `A6_2_COMMIT`. The protected A2 updater must move the automation
checkout to that commit before remote promotion. Confirm a clean `codex-hpc`
checkout with no active run or update lock.

## Local promotion

Run under `sudo`:

```bash
A6_2_COMMIT='<full 40-character commit reported by Codex>'
sudo bash /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_a6_log_probe_local.sh \
    "$A6_2_COMMIT"
```

The script changes only the protected request registry. It regenerates every
normal request entry with the exact commit and leaves the A6 helper bundle and
state files unchanged.

## Remote promotion

Run on lethe without `sudo`:

```bash
A6_2_COMMIT='<same full 40-character commit>'
bash /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_a6_log_probe_lethe.sh \
    "$A6_2_COMMIT"
```

The script changes only the grid probe payload and submission configuration.
It also verifies the unchanged submission wrapper and A6 lethe log reader.

## Handoff and protected test order

Copy both complete files printed as `A6_2_REPORT`. After both pass, Codex will:

1. verify installed hashes, modes, exact clean commit, and fresh run ID;
2. preview the fixed request and show the exact commit/resources;
3. request explicit approval for one submission;
4. submit once, record the Slurm ID, and never automatically retry;
5. read the initial line while the controller is alive;
6. read 200 newly appended lines and require a line-cap notice;
7. read the five-line remainder and require no skipped bytes;
8. after completion, read 64 KiB of the large line and require a byte-cap
   notice, then read only its remainder and fixed completion lines;
9. repeat once more and require no new output;
10. verify terminal Slurm state, completion marker, cursors, and audit entries.

The only approval-bearing action is step 4.
