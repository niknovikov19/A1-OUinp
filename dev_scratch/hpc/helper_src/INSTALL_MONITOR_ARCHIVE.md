# Chunked monitoring and compact result archives

Status: initial Gate-B installation and live status/log/archive checks passed.
An additional compatibility correction for `hpc-status` reply validation is
awaiting remote re-promotion; local helpers need no reinstall. See the
[acceptance report](../monitor_archive_testing.md) for results and the remaining
gate. Do not invoke candidate helper executables in place. No simulation
submission limits are raised by this work.

## Monitoring

The existing `hpc-job status RUN_ID` observes the recorded controller and
children. One user-scoped `squeue` query is followed by `sacct` requests for
IDs missing from that observation, in chunks of **at most 25 IDs**. For 61
recorded jobs, a completely finished tree takes one `squeue` plus three
`sacct` calls, not one accounting request containing all 61 IDs and not one
request per job. Returned JSON includes normalized state counts.

Each scheduler command has a 30 s timeout, and the entire grid observation
has a 180 s budget. SSH/job-helper deadlines allow that observation to return.
Subprocess streams are drained with live byte limits, rather than checked
only after unrestricted capture. Missing accounting records remain unknown;
a failed chunk or expired observation fails explicitly rather than reporting
partial coverage as completion. Calls are sequential and the observation is
not an atomic snapshot. Poll once per run, roughly once a minute; no sleep is
inserted between chunks and no automatic retry or submission is introduced.

Incremental log retrieval is separate and makes **no scheduler calls**:

```bash
/opt/a1-hpc/bin/hpc-job log RUN_ID
/opt/a1-hpc/bin/hpc-job --json logs RUN_ID --offset 0
/opt/a1-hpc/bin/hpc-job --json logs RUN_ID --offset 5
```

`log` retains the existing controller or `--child CHILD_KEY` behavior. New
`logs` reads five children from the recorded index per call, at most 8 KiB
and 40 lines from each child's stdout and stderr. Follow `next_offset` until
it is null; a 60-child tree takes twelve pages. Each child's byte/inode cursor
is retained locally, so repeating a page reads new content rather than the
old prefix. `more_available` inside a stream indicates a backlog: revisit
the page to drain it. A poll can read the controller plus selected pages;
reading every page every minute is not required.

The index is read once per page. It grows by appending children during a
run, so return to offset zero on a later sweep to see both updates and new
children. Page cursors advance only after a successful response; rotation,
truncation, and missing logs retain the existing stream-reader behavior.

## Archive and local handoff

After successful protected finalization:

```bash
/opt/a1-hpc/bin/hpc-result --json archive RUN_ID --unpack
```

This creates a `.tar.gz` on Lethe from **only the run's finalized declared
compact outputs**: `cfg/*.json`, `results/*.json`, `rvec_xr/*.nc`,
`hvec_xr/*.nc`, and `jobs/index.jsonl`. It does not recursively scan results
or include raw PKLs, saved networks, or figures. Large files remain on HPC.
This fixed profile is appropriate for the current connected-step experiment;
other experiments expose only matching files that their completion contract
actually declares. An empty profile is rejected.

Sources are hashed while packing, with size/identity/timestamp checks against
changes during the read. The embedded `archive_manifest.json` records original
HPC paths, per-file SHA256, sizes, run ID, commit, and result-root binding.
Archive metadata is stored under protected state. Later archive calls reuse
the stored bundle and do not reopen all simulation files.

One metadata call is followed by **one binary SSH stream**. The payload is
written to a private temporary local file, not encoded as base64 JSON or
loaded wholly into memory. A 600 s transfer timeout and 1 GiB compressed and
uncompressed byte ceilings apply; the profile is also capped at 4096 files.
The archive and individual member checksums are verified before acceptance.

The fixed cache layout is:

```text
exp_results_local/hpc_codex/RUN_ID/
  compact.tar.gz
  compact/                  # Created by --unpack
    cfg/
    results/
    rvec_xr/
    hvec_xr/
    jobs/index.jsonl
    archive_manifest.json
```

Unpacking accepts only unique regular files in the fixed profile. It rejects
links, path traversal, wrong checksums, and oversized contents, and stages
extraction in a fresh directory before publishing it. Repeated calls report
`cache-hit`; existing unpacked files are checked and user changes are preserved
by rejecting a mismatch. Interrupted downloads leave no accepted partial
archive. A corrupt existing cache is not silently overwritten. Omitting
`--unpack` downloads and verifies just the archive. A failed transfer can be
retried without creating another remote archive.

The compact directory can be supplied directly as the local analyzer's
`--input-dir`; alternatively copy its files locally into the project dataset
once. The embedded manifest uses real HPC paths, never mount paths.

## Bounds and remaining work

- Total recorded scheduler IDs remain capped at 100 by installed policy after
  promotion; accounting chunk size is independently 25. Total-child submission
  authority stays at 12 and concurrency stays five until separately promoted.
- Shared lifecycle/index byte bounds increase from 64 KiB to 1 MiB, and
  declared completion files from 64 to 256, supporting the planned 241-file
  handoff. The request JSON schema is synchronized with the runtime bound.
- Existing 1 MiB job-helper response limits and 100-child log-cursor limit
  remain. This is sufficient headroom for the planned 60-child run, not a
  claim of end-to-end support for thousands of jobs.
- Whole-tree status still returns recorded child detail; terminal-state
  caching, compact paginated status responses, and a manifest-based replacement
  for per-file completion declarations remain future work. Finalization's
  existing lifecycle contract is preserved, not redesigned here.

The 60-child authorization increase is a separate future policy promotion.
There is no need to raise the 100-ID status limit for that batch.

## Gate-B promotion

The user runs the promotion scripts after these changes are committed and
pushed and the idle HPC automation checkout is updated to the same commit:

```bash
sudo bash dev_scratch/hpc/helper_src/promotion/promote_monitor_archive_local.sh FULL_COMMIT

ssh lethe bash -s -- FULL_COMMIT \
  < dev_scratch/hpc/helper_src/promotion/promote_monitor_archive_lethe.sh
```

Both reports must end with `MONITOR_ARCHIVE_RESULT=PASS`. Local reports go to
`/tmp`; remote reports go under protected `state/A1_OUinp/reports/promotion/`.
The installer verifies exact committed source hashes against
`promotion/monitor_archive_hashes.json`, known installed predecessors or the
already-promoted version, branch/commit, and immutable directory restoration.
Unexpected predecessor hashes stop the promotion before installation. The
remote promotion requires no active run because shared lifecycle code changes.
It creates only the private archive-state directory and replaces reviewed
helper code/status policy; it does not fetch, submit, cancel, or remove data.

After installation, verify the protected commands against the completed
`hstep-l2-long-pilot-001`: status, two adjacent log pages and an unchanged
repeat, then archive/unpack and a cache-hit repeat. Compare the twelve-trial
archive's 49 compact source files and hashes with the existing local handoff.
No simulation rerun is needed. Report installed identities and saved promotion
transcripts before using the capability for the next experiment.

## Tests

Use the existing NetPyNE environment, with no dependency installation:

```bash
/home/nnovikov/conda_env/netpyne/bin/python -m unittest discover -s tests -p 'test_hpc*.py'
```

Candidate modules are imported only into isolated fixture tests with scheduler
and network calls mocked. Synthetic scheduler sizes include 1, 13, 25, 26,
61, 101, and 1000 IDs; failures, missing accounting, and observation expiry
are checked. Other cases cover bounded subprocess output, streaming/timeouts,
log pages and cursor reuse, 241-file archive roundtrips, checksum/source
failures, unsafe tar entries, cache reuse, and preservation of modified data.
