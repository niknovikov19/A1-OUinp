# HPC helper candidate sources

This directory contains reviewable source candidates for protected HPC helper commands. Files here are not the live security boundary and must never be invoked or sourced in place.

The [chunked monitoring/archive candidate](INSTALL_MONITOR_ARCHIVE.md) adds
25-ID accounting chunks, five-child incremental log pages, and one compact,
checksummed archive transfer per completed run. Protected installation and live
acceptance passed, including the `hpc-status` compatibility correction.

The [60-child / concurrency-ten policy](INSTALL_BATCH_60_CONCURRENCY_10.md)
is installed after both Gate-B promotions passed; per-job limits are unchanged.

The [completion recovery repair](INSTALL_COMPLETION_RECOVERY.md) is a new
candidate, pending installation. It checks request and child output files
together, preserves and repairs the old list-mismatch failure, and checks
recorded jobs before release. The B1/B2 descriptions below describe the older
installed behavior until that repair is promoted.

The future [large-batch status and lifecycle refactor plan](../status_scaling_refactor_plan.md)
separates scheduler-query bounds from total batch size and records temporary
policy recommendations for the current implementation.

## Promotion rule

For each capability:

1. Codex writes and reviews the candidate source here.
2. The user manually copies the required files to a protected directory outside Codex's write access.
3. The user reports the installed path and source hashes.
4. Codex tests only the protected installed command.

If a test fails, update the candidate, manually promote it again, and retest the installed copy. Never patch the installed copy through Codex.

## A0 contents

```text
local/hpc-helper-info
local/hpc_common.py
local/hpc_common.md
config_examples/hpc-helper.json.example
schemas/audit-event.schema.json
schemas/hpc-helper-config.schema.json
schemas/run.schema.json
test_fixtures/identifiers.json
INSTALL.md
```

`hpc-helper-info` has no SSH, Git mutation, Slurm, or file-transfer capability. It reports the installed source identity, validates the protected configuration, tests identifier validators, reads at most 20 prior audit events, and appends an audit event for every invocation.

## A1 contents

```text
local/hpc-probe
remote_lethe/hpc-lethe-probe
remote_grid/hpc-grid-probe
config_examples/remote-hpc-probe.json.example
schemas/remote-hpc-probe-config.schema.json
test_fixtures/a1_probe_cases.json
test_fixtures/slurm_probe_formats.json
INSTALL_A1.md
```

`hpc-probe` accepts only the logical targets `lethe` and `grid`. The lethe
probe checks the one configured automation checkout. The grid probe travels
through the fixed lethe helper and runs only version and bounded user queries
through the configured absolute `squeue` and `sacct` paths.

A1 does not fetch or modify Git state, submit or cancel Slurm jobs, read job
logs, or transfer files. Connectivity failures and malformed remote output are
reported as `unknown` with exit code `3`.

### A1 test scope

The protected A1 tests verify:

- lethe connectivity and visibility of the fixed automation checkout and its
  `.git` marker;
- lattice connectivity through the lethe helper;
- installed helper and remote-configuration identities;
- `squeue` and `sacct` availability and versions;
- fixed-format, user-scoped active and recent-accounting queries;
- local rejection of unsupported targets, traversal, punctuation, and extra
  arguments before SSH;
- normalization of timeouts, SSH errors, malformed JSON, and oversized output
  to `unknown` with exit code `3`;
- local audit events for successful, rejected, and unknown invocations.

### A1 call chains

Lethe probe:

```text
Codex
  -> /opt/a1-hpc/bin/hpc-probe lethe
  -> /usr/bin/ssh lethe
  -> hpc-lethe-probe lethe
  -> inspect the fixed A1_OUinp_codex checkout and .git marker
  -> return bounded JSON
  -> append the local audit event
```

Grid probe:

```text
Codex
  -> /opt/a1-hpc/bin/hpc-probe grid
  -> /usr/bin/ssh lethe
  -> hpc-lethe-probe grid
  -> /usr/bin/ssh lattice
  -> hpc-grid-probe probe
  -> run fixed read-only squeue and sacct queries
  -> return bounded JSON through lethe
  -> append the local audit event
```

Rejected input:

```text
Codex
  -> hpc-probe unsupported-input
  -> reject locally with exit code 2
  -> append the local audit event
  -> do not open an SSH connection
```

## A2 contents

```text
local/hpc-code-status
local/hpc-code-update
remote_lethe/hpc-lethe-code
config_examples/remote-hpc-code.json.example
schemas/remote-hpc-code-config.schema.json
schemas/code-update-record.schema.json
test_fixtures/a2_code_cases.json
INSTALL_A2.md
```

`hpc-code-status` reads only the fixed automation checkout and reports its
branch, local and remote-tracking commits, cleanliness, update-lock state, and
active-run marker. It does not fetch.

`hpc-code-update` accepts exactly one full lowercase commit hash. The remote
helper requires the configured branch, a clean checkout, no active run, and an
exclusive pre-created update lock. It fetches only the configured branch,
requires the requested hash to equal that branch's remote head, and permits
only a fast-forward or an idempotent no-op.

The helper never merges divergent history, resets a checkout, changes the
manual checkout, selects another branch/remote/path, or accepts Git arguments
from the caller. Fetch failures are `unknown`; policy and known checkout
failures do not trigger retries.

An optional `--quarantine-generated` recovery mode is documented in
`INSTALL_CODE_QUARANTINE.md`. It handles only bounded untracked regular files
under `exp_results`; the target commit must ignore them. A conflict leaves
the files in private protected state for explicit review. The default clean-
checkout rule and fixed branch/commit checks are unchanged.

### A2 call chains

Read-only status:

```text
Codex
  -> /opt/a1-hpc/bin/hpc-code-status
  -> /usr/bin/ssh lethe
  -> hpc-lethe-code status
  -> fixed read-only Git and state checks
  -> return bounded JSON
  -> append the local audit event
```

Approved update:

```text
Codex
  -> /opt/a1-hpc/bin/hpc-code-update EXPECTED_COMMIT
  -> validate the full hash and append local intent
  -> /usr/bin/ssh lethe
  -> hpc-lethe-code update EXPECTED_COMMIT
  -> acquire fixed exclusive lock and write pending record
  -> fetch only origin/codex-hpc
  -> require exact remote head and fast-forward ancestry
  -> fast-forward or return no-op
  -> verify exact commit, branch, and cleanliness
  -> finalize the remote record and local audit event
```

Rejected commit syntax is audited locally with exit code `2` and opens no SSH
connection. A validly formatted hash that is not the fetched branch head is
rejected remotely with exit code `2` and cannot move the checkout.

## A3 contents

```text
local/hpc-run-preview
remote_lethe/hpc-lethe-preview
config_examples/preview-requests.json.example
config_examples/remote-hpc-preview.json.example
schemas/run-request.schema.json
schemas/remote-hpc-preview-config.schema.json
test_fixtures/a3_preview_cases.json
INSTALL_A3.md
```

`hpc-run-preview` accepts only a request ID. It selects the matching entry from
the fixed protected local request registry, sends canonical JSON to the fixed
lethe helper, and verifies the returned request digest. It never accepts a request
file path, raw JSON, repository path, host, partition, or resource override.

The lethe helper independently validates the complete request and the remote
preview configuration. It requires the exact clean configured branch and
commit, resolves the experiment only below `exp_configs`, verifies every
declared repository dependency is a tracked regular file, and reports bounded
suspicious ignored files under the selected experiment.

The request contains parameter axes but no caller-supplied child count. The
helper calculates the Cartesian product, compares it and every requested
resource with protected limits, and returns a canonical request SHA256. A
limit violation is a rejected preview and cannot become a submission. A3
contains no Slurm invocation, run-directory creation, Git mutation, or file
transfer.

### A3 call chain

```text
Codex
  -> /opt/a1-hpc/bin/hpc-run-preview REQUEST_ID
  -> select one request from the fixed protected local request registry
  -> canonicalize and encode the request
  -> /usr/bin/ssh lethe
  -> hpc-lethe-preview preview ENCODED_REQUEST
  -> validate the fixed remote config and complete request
  -> inspect the exact clean Git checkout and selected experiment
  -> verify declared tracked files and report bounded ignored-path warnings
  -> calculate axis product and enforce protected limits
  -> return deterministic bounded JSON and request digest
  -> verify the digest and append the local audit event
```

Malformed or unknown request IDs are rejected locally before SSH. Malformed
protected request entries, changed commits, unknown experiments, empty axes,
unsupported partitions, excessive resources, and excessive job counts are
rejected by the lethe helper with exit code `2`.

## A4 contents

```text
local/hpc-submit
remote_lethe/hpc-lethe-submit
remote_grid/hpc-grid-submit
remote_grid/hpc-grid-probe-job
remote_grid/hpc-grid-probe-job.sh
config_examples/remote-hpc-submit.json.example
schemas/remote-hpc-submit-config.schema.json
schemas/submission-record.schema.json
test_fixtures/a4_submit_cases.json
promotion/promote_a4_local.sh
promotion/promote_a4_lethe.sh
INSTALL_A4.md
```

The two promotion scripts are user-run installation conveniences, not
protected runtime helpers. They enforce the reviewed hashes, restore directory
modes after errors, and save complete local and lethe verification reports.

`hpc-submit` accepts only a request ID from the protected request registry.
A4 permits only `a4-slurm-probe-v2`: one fixed marker-producing Slurm job using
`cpu.q`, one node, one core, 1 GB, and two minutes. It does not execute
repository simulation code or accept a host, command, path, partition,
resource, environment, or Slurm option from the caller.

The lethe helper first invokes the installed A3 preview helper. It requires a
successful exact-commit preview whose request type, output kind, job count,
concurrency, resources, digest, and result directory match the fixed A4
policy. It then creates `run.json` before contacting the grid helper.

The grid helper writes `submission.json` with status `pending` before calling
the fixed `/usr/bin/sbatch --parsable` command. It changes the receipt to
`submitted` immediately after obtaining a valid job ID. A retry returns that
existing ID. A `pending` or `unknown` receipt fails closed because an earlier
submission may have succeeded; A4 never guesses by submitting another job.

Slurm executes a copied shell wrapper from its spool directory. The wrapper
contains the fixed `#SBATCH` resource directives and invokes the protected
Python payload through its absolute shared path. The grid helper verifies both
file hashes and requires the wrapper directives to match protected policy.
The Python payload therefore retains its original shared-file `__file__`.

### A4 call chain

```text
Codex, after explicit submission approval
  -> /opt/a1-hpc/bin/hpc-submit --json a4-slurm-probe-v2
  -> select and hash the request from the protected local registry
  -> append the mandatory local submit-intent audit event
  -> /usr/bin/ssh lethe
  -> hpc-lethe-submit submit ENCODED_REQUEST
  -> hpc-lethe-preview preview ENCODED_REQUEST
  -> require the exact clean commit and fixed A4 policy
  -> create or validate runs/A1_OUinp/a4-slurm-probe-v2/run.json
  -> /usr/bin/ssh lattice
  -> hpc-grid-submit submit REQUEST_ID REQUEST_SHA256
  -> create pending submission.json under an exclusive per-run lock
  -> verify fixed wrapper directives and both installed file hashes
  -> /usr/bin/sbatch --parsable hpc-grid-probe-job.sh
  -> wrapper invokes the protected shared Python payload
  -> hpc-grid-probe-job writes probe-result.json on the compute node
  -> persist and return the Slurm job ID
  -> append the final local audit event
```

A4 proves protected submission and retry safety. Scheduler monitoring,
completion reconciliation, and log/result retrieval are separate later gates.

The promoted A4 wrapper is specific to the repository-independent probe. In
integrated experiment gates, single and batch launcher sources remain tracked
in the exact repository commit. Reviewed request definitions belong in
`hpc_jobs/requests/`, and reusable shell templates belong in
`hpc_jobs/templates/`. The planned protected run-preparation operation resolves
both from the exact commit and writes a hash-bound snapshot to
`hpc_jobs/runs/<run-id>/submit.sh`. A separate protected submission operation
rechecks the recorded hash before calling `sbatch`.

The ignored `hpc_jobs/runs/<run-id>/` directory contains only prepared job
records, the exact submitted script, and top-level Slurm logs. Scientific
results remain in the established `exp_results/<experiment>/<exp_name_sub>/`
or `exp_results/workflows/<workflow>/<run-id>/` layout. Compact authoritative
audit, job-ID, path, hash, cursor, and lock records remain outside the
repository in the protected HPC-Codex state root.

## A5.1 contents

```text
local/hpc-status
remote_lethe/hpc-lethe-status
remote_grid/hpc-grid-status
config_examples/remote-hpc-status.json.example
schemas/remote-hpc-status-config.schema.json
schemas/status-record.schema.json
test_fixtures/a5_status_cases.json
promotion/promote_a5_local.sh
promotion/promote_a5_lethe.sh
INSTALL_A5.md
```

`hpc-status RUN_ID` accepts only a validated run ID. The lethe helper resolves
that ID beneath the fixed run root and reads Slurm IDs only from `run.json`.
The grid helper makes one bounded user-scoped `squeue` query, retains only the
recorded IDs, and makes one allocation-only `sacct` query when recorded IDs
are absent. It never reads logs or accepts scheduler IDs and options from the
local caller.

Raw scheduler state, reason, and exit code are preserved beside a normalized
state. Missing accounting is `unknown`, not failure. A successful observation
is written atomically to `status.json`; known state also reconciles
`run.json.status`. The fixed `--self-test` path exercises protected parser
fixtures without calling Slurm.

### A5.1 call chain

```text
Codex
  -> /opt/a1-hpc/bin/hpc-status --json RUN_ID
  -> validate RUN_ID and append the local audit event
  -> /usr/bin/ssh lethe
  -> hpc-lethe-status status RUN_ID
  -> load only runs/A1_OUinp/RUN_ID/run.json
  -> extract the recorded controller and child Slurm IDs
  -> /usr/bin/ssh lattice
  -> hpc-grid-status status RECORDED_IDS
  -> one bounded user squeue query, filtered to the recorded IDs
  -> at most one bounded sacct query for IDs absent from squeue
  -> normalize states and return one compact response
  -> atomically write status.json and reconcile known run state
  -> append the final local audit event
```

## A5.2 lifecycle probe

`a5-lifecycle-probe` reuses the protected A4 submission chain with one fixed
difference: the hash-bound grid payload waits 45 seconds for this exact request
ID before writing its marker. The caller cannot select a duration. This gives
`hpc-status` time to observe the job through the normal `squeue` path, after
which the same ID should move through any accounting gap and into `sacct`.

Promotion changes only the protected request registry, submission
configuration, and probe payload. Submission remains a separate explicitly
approved operation.

## A6.1 incremental controller logs

```text
local/hpc-log
remote_lethe/hpc-lethe-log
config_examples/remote-hpc-log.json.example
schemas/remote-hpc-log-config.schema.json
schemas/log-cursor-state.schema.json
schemas/log-read-result.schema.json
test_fixtures/a6_log_cases.json
promotion/promote_a6_local.sh
promotion/promote_a6_lethe.sh
INSTALL_A6.md
```

`hpc-log RUN_ID controller` reads both controller stdout and stderr. The lethe
helper derives exact `slurm-JOB_ID.out` and `.err` paths from protected run and
submission records; it does not scan directories or accept paths from the
caller. The local helper stores per-stream byte cursors beneath protected local
state and advances them only through bytes actually returned.

### A6.1 call chain

```text
Codex
  -> /opt/a1-hpc/bin/hpc-log --json RUN_ID controller
  -> validate RUN_ID and acquire the fixed local cursor lock
  -> load only RUN_ID stdout/stderr cursors
  -> /usr/bin/ssh lethe
  -> hpc-lethe-log controller RUN_ID CURSOR_PAYLOAD
  -> load runs/A1_OUinp/RUN_ID/{run.json,submission.json}
  -> derive controller/slurm-CONTROLLER_ID.{out,err}
  -> reject symlinks and non-regular files
  -> read only new content, at most 64 KiB and 200 lines per stream
  -> return identity, size, mtime, offsets, reset and limit notices
  -> atomically advance local cursors and append the local audit event
```

## A6.2 fixed append-over-time probe

```text
promotion/promote_a6_log_probe_local.sh
promotion/promote_a6_log_probe_lethe.sh
INSTALL_A6_2.md
```

The fixed `a6-incremental-log-probe` request emits one immediate line, then 205
short lines, then one 70,000-byte line at protected intervals. It lets the
installed A6 reader prove appended-content-only transfer, line-cap
continuation, and byte-cap continuation against a real Slurm log. Promotion
only allowlists and installs the payload; submission still requires separate
explicit approval.

## B0.3 protected job preparation

```text
local/hpc-job-prepare
remote_lethe/hpc-lethe-prepare
config_examples/remote-hpc-prepare.json.example
schemas/remote-hpc-prepare-config.schema.json
schemas/prepared-job-record.schema.json
test_fixtures/b0_prepare_cases.json
promotion/promote_b0_prepare_local.sh
promotion/promote_b0_prepare_lethe.sh
INSTALL_B0_3.md
```

`hpc-job-prepare` accepts only a request ID, a fresh run ID, and one full Git
commit. The lethe helper requires the exact clean automation checkout, reads
the request only from `hpc_jobs/requests/`, and accepts only a template whose
path and SHA256 are fixed in protected configuration. It enforces protected
resource ceilings and verifies that the selected scientific configuration
files are tracked regular files.

The helper renders a fixed token set into
`hpc_jobs/runs/<run-id>/submit.sh`, stores read-only request and run snapshots,
and writes one compact mode-`0600` state copy. It does not execute repository
Python, run scientific preflight, call lattice or Slurm, or create scientific
results. A repeated identical invocation returns `already-prepared`; a reused
run ID with different immutable inputs is rejected.

### B0.3 call chain

```text
Codex
  -> /opt/a1-hpc/bin/hpc-job-prepare REQUEST_ID RUN_ID EXPECTED_COMMIT
  -> /usr/bin/ssh lethe
  -> hpc-lethe-prepare prepare REQUEST_ID RUN_ID EXPECTED_COMMIT
  -> require exact clean commit and acquire the fixed preparation lock
  -> validate the tracked request, target files, protected limits, and template
  -> render fixed tokens without importing repository Python
  -> publish the ignored job-run snapshot and compact external state record
  -> return bounded JSON and append the local audit event
```

## B1 prepared single-job lifecycle

```text
local/hpc-job
remote_lethe/hpc-lethe-job
remote_grid/hpc-grid-job
config_examples/remote-hpc-job.json.example
schemas/remote-hpc-job-config.schema.json
test_fixtures/b1_job_cases.json
promotion/promote_b1_job_local.sh
promotion/promote_b1_job_lethe.sh
INSTALL_B1.md
```

`hpc-job` accepts six operations over a prepared run ID: `submit`, `status`,
`log`, `cancel`, `finalize`, and `release`. Submission additionally requires
the full prepared Git commit. The caller cannot supply a script path, Slurm
option, job ID, result path, log path, or retry instruction.

Before submission, the lethe helper holds the existing code-update lock,
requires the exact clean checkout, rechecks the request and rendered-script
hashes, rejects a non-empty result destination, creates the active-run marker,
and persists a pending intent. The grid helper serializes the sole scheduler
mutation and calls only:

```text
/usr/bin/sbatch --parsable <exact prepared submit.sh>
```

The tracked single, batch, and workflow templates remain repository files,
but their hashes are also pinned in the protected preparation policy. Ordinary
experiment changes require only an exact reviewed commit. A change to generic
job-launch behavior requires a manual policy promotion before a new script can
be prepared.

The grid helper replaces the pending repository record with the receipt before
returning. An unavailable or malformed scheduler response becomes `unknown`;
pending and unknown submissions are never retried automatically.

Cancellation accepts only the prepared run ID. The fixed helpers resolve its
recorded active controller and validated BatchTools child Slurm IDs, then call
one bounded `scancel` without accepting a job ID or scheduler option from the
caller. Finalization and release remain separate explicit operations after
Slurm reports a terminal state.

Status queries the recorded top-level Slurm ID and any recorded BatchTools
child IDs together through the established A5 status helper. Log retrieval
derives top-level stdout and stderr from the submission receipt; optional
`log RUN_ID --child CHILD_KEY` derives child paths only from the validated
child index. Both return only new bounded content with separate cursors.
Finalization requires a terminal scheduler state and, for `COMPLETED`, every
declared completion file. It does not release the code checkout. `release` is
a separate operation that verifies matching terminal records before removing
the active-run marker.

### B1 call chains

```text
Codex
  -> /opt/a1-hpc/bin/hpc-job submit RUN_ID EXPECTED_COMMIT
  -> /usr/bin/ssh lethe
  -> hpc-lethe-job submit RUN_ID EXPECTED_COMMIT
  -> lock code update and job lifecycle
  -> verify prepared records, exact checkout, hashes, and result collision
  -> write active-run marker and pending submission intent
  -> /usr/bin/ssh lattice
  -> hpc-grid-job submit FIXED_BINDING
  -> /usr/bin/sbatch --parsable EXACT_PREPARED_SCRIPT
  -> replace pending record with one Slurm receipt
  -> reconcile the protected state copy and return the recorded job ID
```

```text
Codex
  -> /opt/a1-hpc/bin/hpc-job status|log|finalize|release RUN_ID
  -> derive every ID and path from protected records
  -> status: query recorded top-level and child IDs through hpc-grid-status
  -> log: read bounded incremental top-level or selected child streams
  -> finalize: bind terminal scheduler and declared-file evidence
  -> release: verify final evidence and remove the active-run marker
```

## B2 BatchTools child-job evidence

```text
local/hpc-job
remote_lethe/hpc-lethe-job
remote_grid/hpc-grid-job
promotion/promote_b2_job_local.sh
promotion/promote_b2_job_lethe.sh
INSTALL_B2.md
```

B2 keeps the B1 top-level submission path and permits a prepared `batch` job.
The tracked BatchTools submitter calls `/usr/bin/sbatch --parsable` for each
simulation job. Under one file lock it appends a bounded record to the
scientific result's `jobs/index.jsonl`; no monitor reconstructs IDs by scanning
logs or querying jobs by name.

Each record binds the prepared run ID to the child label, Slurm ID, parameter
coordinates, stdout/stderr paths, declared scientific output, and submission
time. Finalization ingests this file through `hpc_job_lifecycle.py`. A completed
batch requires exactly the prepared number of child records, and every child
output must also be declared by the tracked request. A terminal batch with a
malformed output declaration is finalized as failed, allowing safe release
without treating the scientific evidence as complete.

If a simulation job fails without producing the BatchTools completion
artifact, BatchTools can continue displaying it as running and keep the main
job alive. Child-aware status and log operations expose the real scheduler
state and the selected child error without an ad hoc SSH command. The protected
cancellation operation stops both the controller and all recorded children.

## B5 selective result access

```text
local/hpc-result
remote_lethe/hpc-lethe-result
hpc_result.py
promotion/promote_b5_result_local.sh
promotion/promote_b5_result_lethe.sh
INSTALL_B5.md
```

`hpc-result inventory RUN_ID` accepts only a finalized successful run. On its
first call, the lethe helper loads matching repository and protected lifecycle
records, reads the already-validated `jobs/index.jsonl`, and inspects only the
declared child outputs. It records child parameters, artifact type, repository-
relative path, size, modification time, and a checksum for bounded files. The
inventory is then stored under protected state and reused on later calls.

`hpc-result get RUN_ID CHILD_KEY ARTIFACT_TYPE` resolves exactly one entry from
that inventory. It accepts no path or wildcard, rejects changed files and
artifacts above 256 KiB, and copies the verified bytes beneath the ignored
`exp_results_local/hpc_codex/<run-id>/` cache. Before requesting bytes, the
local helper compares an existing cache file with inventory size and checksum;
a match returns `cache-hit` without repeating the artifact transfer.

### B5 call chains

```text
Codex
  -> /opt/a1-hpc/bin/hpc-result inventory RUN_ID
  -> /usr/bin/ssh lethe
  -> hpc-lethe-result inventory RUN_ID
  -> verify matching complete-run records
  -> load existing protected inventory, or inspect only declared outputs once
  -> return compact artifact metadata
```

```text
Codex
  -> /opt/a1-hpc/bin/hpc-result get RUN_ID CHILD_KEY ARTIFACT_TYPE
  -> obtain compact inventory metadata
  -> return cache-hit when the ignored local copy has the same checksum
  -> otherwise request the exact inventory entry from hpc-lethe-result
  -> verify size and checksum and atomically write the local cached copy
```

## Exit codes

- `0`: success;
- `2`: rejected input;
- `3`: unavailable or unknown remote state;
- `4`: known helper or operation failure.
