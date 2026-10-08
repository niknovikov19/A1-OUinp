# HPC helper candidate sources

This directory contains reviewable source candidates for protected HPC helper commands. Files here are not the live security boundary and must never be invoked or sourced in place.

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
in the exact repository commit. A protected run-preparation helper creates and
hashes a run-specific shell snapshot at
`exp_results/automation/<experiment>/<run-id>/controller/submit.sh`; launcher
development does not require promoting a new infrastructure helper each time.
A separate protected submission helper rechecks that snapshot's recorded hash
before calling `sbatch`. The script and run records remain with the ignored
scientific-result package, while global audit and lock state remain outside it.

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

## Exit codes

- `0`: success;
- `2`: rejected input;
- `3`: unavailable or unknown remote state;
- `4`: known helper or operation failure.
