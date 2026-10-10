# Codex-to-HPC prototype work plan

## Goal

Build and validate a small Codex-to-HPC workflow progressively. The prototype should prove that Codex can synchronize one exact Git commit, submit an approved Slurm job, monitor it, inspect bounded logs, and retrieve one selected result without receiving general SSH access or touching the manual HPC checkout.

The work is split into two milestones:

1. A capability spike proves the uncertain infrastructure pieces with fixed, inexpensive probes.
2. The integrated prototype applies the proven pieces to one simulation and then a tiny BatchTools batch.

Full workflow development starts only after the capability spike passes.

## Fixed safety boundary

- Codex works in the local WSL clone and never invokes `ssh`, `scp`, `sftp`, `rsync`, SSHFS, or a general remote-command wrapper.
- Codex may invoke only reviewed, fixed-purpose helpers from a protected directory outside its write access.
- Grid receives only Slurm-related commands. Lightweight Git, metadata, and bounded log operations run on lethe.
- The existing manual lethe checkout is never changed by an automation helper.
- The automation checkout uses a dedicated branch and accepts only clean, fast-forward updates to an expected commit.
- Update, submission, cancellation, resubmission, and bulk transfer require explicit user approval. Status and bounded log reads for an approved run do not require repeated approval.
- Connection or scheduler uncertainty is reported as `unknown`; it never causes automatic resubmission or cancellation.
- The initial child-job ceiling is 10. The integrated tests will stay below it.
- Every remote action is associated with a run ID, exact commit, helper version, timestamp, result, and any Slurm IDs.

## Helper source, promotion, and testing loop

Candidate helper scripts will be written under:

```text
dev_scratch/hpc/helper_src/
    local/                  # WSL entry points
    remote_lethe/           # Fixed lethe-side operations, if needed
    remote_grid/            # Fixed Slurm-only operations, if needed
    config_examples/        # Non-secret example configuration
    test_fixtures/          # Scheduler, Git, and log parser fixtures
    INSTALL.md
```

The candidate scripts are source artifacts only. Codex will not invoke or source a candidate helper from this directory.

For every capability, use this exact loop:

1. Codex writes only the minimal candidate helper and tests/fixtures needed for that capability.
2. Codex reviews the diff and may perform non-executing static checks, but does not run the candidate helper.
3. The user reviews and manually copies the candidate to protected local and, if needed, remote directories outside Codex's write access.
4. The user makes the installed code and configuration non-writable to Codex and reports the installed command path/version.
5. Codex invokes only the installed helper and records the observed result.
6. If the test fails, Codex edits the candidate source; the user promotes the new version; Codex retests. Codex never patches the installed copy.
7. The next capability begins only after the current gate passes.

Each installed helper must support `--version` or an equivalent information command that reports a source hash. This lets us confirm that the protected copy matches the reviewed candidate.

### Infrastructure helpers versus experiment launchers

Manual promotion applies to infrastructure helpers that enforce the safety
boundary. The A4 shell wrapper is also promoted because the A4 probe must test
Slurm without executing repository code.

Real-experiment launchers are different. Their source should remain tracked in
the repository and travel with the exact approved commit. Tracked job requests
and shell templates live beneath `hpc_jobs/requests/` and
`hpc_jobs/templates/`. A protected helper validates the clean commit, selects
one reviewed request and template, and renders one run-specific `submit.sh`
beneath the ignored `hpc_jobs/runs/<run-id>/` directory. Experiment development
therefore does not require manual helper promotion for every request or
template edit.

Only typed request fields may be rendered: resources, safe identifiers, and
paths derived beneath fixed roots. Arbitrary shell text is never accepted.
The protected run-preparation helper writes the script atomically and removes
its write bits as an accidental-mutation guard. A separate protected submission
helper verifies the recorded run ID and script SHA256 immediately before
calling `sbatch`; the hash check, not the file mode alone, establishes the
submitted identity. Both infrastructure helpers remain manually promoted.

The generated script and top-level Slurm logs stay together beneath the
ignored job-run directory:

```text
hpc_jobs/
    requests/                         # tracked
    templates/                        # tracked
    runs/                             # ignored
        <run-id>/
            request.json
            run.json
            submission.json
            submit.sh
            slurm-<job-id>.out
            slurm-<job-id>.err
```

Scientific results keep their existing repository layouts:

```text
exp_configs/<experiment>/
exp_results/<experiment>/<exp_name_sub>/

workflow_configs/<workflow>/
exp_results/workflows/<workflow>/<run-id>/
```

The protected state root stores only small authoritative audit, index,
submission, hash, path, lock, and cursor records. Large Slurm and simulation
logs are not copied there. Job-run directories are retained until an explicit
archive or deletion operation and must never be silently overwritten.

The user will choose the protected paths. A representative arrangement is:

```text
WSL protected bin/          # Executable by Codex, not writable by Codex
WSL protected config/       # Host aliases, branch, paths, limits; read-only
lethe protected bin/        # Outside both Git checkouts
grid protected bin/         # Only if fixed remote Slurm wrappers are needed
```

Secrets, SSH configuration, usernames, and private keys must not be stored in the repository or printed in logs.

## Proposed helper interface

The exact names may change during the spike, but the exposed operations should remain narrow:

```text
hpc-helper-info
hpc-probe lethe|grid
hpc-code-status
hpc-code-update EXPECTED_40_CHAR_COMMIT
hpc-run-preview RUN_REQUEST
hpc-run-prepare RUN_REQUEST RUN_ID
hpc-submit RUN_ID EXPECTED_SCRIPT_SHA256
hpc-status RUN_ID
hpc-log RUN_ID top
hpc-log RUN_ID job JOB_LABEL
hpc-result-list RUN_ID ARTIFACT_TYPE
hpc-result-get RUN_ID JOB_LABEL ARTIFACT_TYPE
```

`RUN_REQUEST` denotes a validated request ID or a fixed repository-relative request record, never an arbitrary filesystem path. No helper may accept shell text, an SSH destination, an arbitrary branch, an arbitrary remote path, a wildcard, or an arbitrary Slurm command. Run IDs, commit hashes, experiment names, job labels, and artifact types must be validated against strict formats and known records.

## Records and audit trail

Use three complementary records:

- Protected-helper audit log: one JSON line for every invocation, including rejected calls. Do not log secrets or full environment variables.
- Small protected per-run record: authoritative commit, request digest,
  top-level and child Slurm IDs, repository paths, hashes, and last known state.
- Prototype test log: a repository Markdown file updated after every gate with helper version, commands invoked, sanitized output, pass/fail, and conclusions.

The helper should emit structured JSON for machine use and a short human-readable summary. State-changing operations should write their intent record before acting, then update it atomically after the result is known.

## Milestone A: capability spike

This milestone does not run NetPyNE. It answers whether the code-transfer, two-hop helper, Slurm, monitoring, and bounded-log mechanisms work as expected on this particular cluster.

### Gate A0: freeze prototype configuration

Purpose: make every later command target a fixed, reviewable scope.

Codex work:

- Add a non-secret configuration template.
- Define strict validators for run IDs, full Git hashes, experiment IDs, and job labels.
- Define exit codes such as `0=success`, `2=rejected input`, `3=unknown/unavailable`, and `4=known operation failure`.
- Define the audit and `run.json` schemas.

User input/promotion:

- Select the dedicated automation branch; `codex-hpc` is the working name.
- Confirm the automation checkout path, distinct from the manual checkout.
- Supply protected configuration with the existing SSH host aliases, Git remote, allowed branch, scheduler user/account if needed, and resource ceilings.

Tests after promotion:

- `hpc-helper-info` reports the installed version/hash and redacted configuration.
- Invalid identifiers and extra arguments are rejected locally without making a connection.
- The audit log contains successful and rejected invocations.

Pass condition: installed-helper identity is verifiable, configuration is fixed, and malformed input cannot reach SSH.

### Gate A1: prove bounded lethe and grid connectivity

Purpose: validate the two-hop path without exposing a remote shell.

Helper behavior:

- `hpc-probe lethe` performs only a fixed lightweight check and reports whether the configured automation checkout is visible.
- `hpc-probe grid` performs only fixed read-only Slurm queries, for example scheduler/version availability and a bounded query for the configured user.
- Timeouts and connection errors return `unknown` with a nonzero exit code.

Tests after promotion:

- Reach lethe through the installed helper.
- Reach grid through the installed helper and confirm that `squeue` and `sacct` are available.
- Record the actual `squeue` and `sacct` output formats we must parse; record `sbatch --parsable` output only at the approved submission gate A4.
- Try punctuation, path traversal, extra arguments, and unsupported probe names; all must be rejected before connection.
- Confirm no helper option exposes an interactive session or arbitrary command.

Pass condition: both hops work through allowlisted operations, scheduler output is understood, and an outage maps to `unknown` rather than `failed`.

### Gate A2: prove WSL push to GitHub and protected pull to lethe

Purpose: validate exact-commit code synchronization independently of job submission.

Helper behavior:

- `hpc-code-status` reports checkout path, branch, full commit, cleanliness, and whether an automation-run lock is active.
- `hpc-code-update COMMIT` verifies a full hash, fixed remote/branch, clean checkout, no active incompatible run, and fast-forward ancestry before updating.
- Update is implemented as fixed fetch plus fast-forward-only movement, never an automatic merge or reset.
- A second call for the same commit is a successful no-op.

Tests after promotion:

1. Codex commits a harmless tracked prototype artifact on the dedicated branch and pushes it.
2. `hpc-code-status` records the old remote commit.
3. After explicit approval, `hpc-code-update` installs the expected commit.
4. `hpc-code-status` confirms the exact full hash and clean state.
5. Repeat the update and confirm idempotent no-op behavior.
6. Confirm rejection of an unknown hash, wrong-format hash, dirty checkout, and non-fast-forward update. Unsafe states should be exercised with a disposable fixture or a user-created harmless remote marker, not by damaging the real checkout.

Pass condition: the GitHub round trip preserves the exact commit, cannot modify the manual checkout, and refuses ambiguous or divergent states.

### Gate A3: prove mechanical preview and request pinning

Purpose: catch parameter explosions and resource mistakes before any Slurm mutation.

Implementation target:

- Define a versioned run-request format containing run type, experiment ID, expected commit, requested resources, concurrency, expected output kind, and a unique request ID.
- Calculate child count from the actual parameter axes, not a manually entered count.
- Produce a canonical request digest that later submission must match.
- Report tracked/untracked state and suspicious ignored dependencies needed by changed code.
- Enforce protected ceilings for child count, nodes, cores, memory, wall time, concurrency, and allowed partitions.

Tests after promotion:

- Preview a one-job probe request.
- Preview a tiny multi-axis fixture and verify the Cartesian-product count.
- Preview the existing 48-job configuration and confirm it is reported as 48 and rejected by the initial 10-job ceiling.
- Reject an unknown experiment, changed commit, unsupported partition, excessive resource request, empty parameter axis, and malformed request.
- Run the same request twice and confirm identical canonical output/digest apart from explicitly volatile display fields.

Pass condition: preview is deterministic, agrees with hand-checked test grids, and large or malformed requests cannot become submissions.

### Gate A4: prove minimal Slurm submission and idempotency

Purpose: test the submission channel without involving repository code or BatchTools.

Helper behavior:

- Submit one immutable remote probe script with the smallest practical resources and short wall time.
- Create the run directory and `run.json` before calling `sbatch`.
- Use `sbatch --parsable` and save the returned job ID atomically.
- Use a unique run ID/request digest as an idempotency key.
- A repeated call for the same request returns the existing job ID and never submits a duplicate.

Tests after promotion and explicit submission approval:

- Submit a fixed job that writes a few known lines and one tiny result marker.
- Verify the returned top-level Slurm job ID is present in `run.json`.
- Invoke the same request again and verify there is still only one scheduler job ID.
- Simulate a lost client response by retrying the same request after submission; confirm recovery from the run record/scheduler instead of duplication.
- Verify unique stdout/stderr names containing the run ID and/or job ID.

Pass condition: one approved request creates exactly one cheap Slurm job and remains safe under retry.

### Gate A5: prove compact scheduler monitoring

Purpose: learn the cluster's real lifecycle and accounting behavior before monitoring simulations.

Helper behavior:

- `hpc-status RUN_ID` loads only known IDs from the run record.
- Make one `squeue` query for all active known IDs and one `sacct` query for absent/terminal known IDs.
- Normalize cluster states into pending, running, completed, failed, cancelled, timeout, out-of-memory, and unknown.
- Preserve raw scheduler state and reason alongside the normalized state.

Tests after promotion:

- Query the completed A4 job and verify `sacct` fallback.
- With explicit approval, submit one fixed short-lived probe that remains alive long enough to observe pending/running and then completed.
- Measure accounting delay between disappearance from `squeue` and appearance in `sacct`; define the grace behavior from evidence.
- Confirm one status call does not open per-job connections or read job logs.
- Exercise parser fixtures for failed, cancelled, timeout, OOM, missing, malformed, and connection-error responses.

Pass condition: the same run can be classified through its lifecycle with bounded scheduler calls, including the accounting-gap case.

### Gate A6: prove incremental and bounded log reads

Purpose: validate log access without rereading large files or walking result trees.

Helper behavior:

- Resolve top-level job log paths only from the known run record.
- Track size, byte offset, modification time, and a file identity marker locally.
- Return only appended content, with a default cap of 200 lines and a byte cap.
- Detect truncation or replacement and reset safely.
- Never accept a path from the caller.

Tests after promotion:

- Read the A4/A5 probe log once.
- Read it again and obtain `no new output`.
- Use a fixed probe that appends lines over time and confirm the second read contains only new lines.
- Verify line/byte truncation notices.
- Reject unknown run IDs, unknown job labels, traversal strings, wildcards, and symlink escape fixtures.

Pass condition: repeated monitoring transfers only new bounded content and cannot select arbitrary files.

### Capability-spike review

Stop and review after A6. Continue to integrated development only if all of the following are demonstrated:

- protected two-hop invocation is reliable enough for fixed operations;
- WSL push and clean fast-forward lethe pull reproduce an exact commit;
- Slurm returns a stable parsable ID;
- retrying a submission does not duplicate it;
- `squeue`/`sacct` provide enough information for compact monitoring;
- known logs can be read incrementally without remote directory scans;
- protected audit and per-run records are sufficient to reconstruct what happened.

If a condition fails, revise only that mechanism and repeat its gate. Do not compensate by granting broader SSH or path access.

## Milestone B: integrated simulation prototype

### Gate B0: adapt repository entry points

Purpose: add the smallest repository interface needed for approved real jobs
without redesigning experiment management.

Repository work:

- Preserve `exp_configs/<experiment>` to
  `exp_results/<experiment>/<exp_name_sub>` and the existing workflow result
  layout. Do not insert an automation-run hierarchy into `exp_results`.
- Add tracked `hpc_jobs/requests/` and `hpc_jobs/templates/`; ignore
  `hpc_jobs/runs/`.
- Replace hardcoded manual-checkout paths with script-relative paths or
  protected configuration.
- Stop selecting experiments by editing submission-script constants. Select a
  validated tracked request from the exact commit.
- Keep scientific parameters in `exp_cfg.py`, `batch_params.py`, and
  `workflow_cfg.py`. Treat an expected result path in a request as an
  assertion, not a second source of scientific parameters.
- Make local preflight resolve and display the established scientific result
  directory. Reject mismatches and existing non-empty destinations.
- Render a reviewed tracked template to
  `hpc_jobs/runs/<run-id>/submit.sh`, record its source/rendered hashes, and
  have the protected submission helper revalidate both before calling
  `sbatch`.
- Store top-level Slurm logs beneath the same ignored job-run directory. Keep
  large logs out of the external HPC-Codex state root.
- Separate top-level resources from BatchTools child-job resources and workflow
  stage-job resources.
- Preserve manual `run_exp.py` behavior. Give `grid_search_slurm_local.py`
  strict inputs for operational settings while retaining `batch_params.py` as
  the parameter-axis source.
- Make the existing `run_workflow.py` command-line parser the actual script
  entry point and validate prepared per-stage resource settings.
- Reuse workflow patterns for resolved parameters, durable job records, output
  validation, and BatchTools artifacts without routing B1 through a workflow.
- Add an active-run lock that blocks checkout updates while submitted jobs may
  still read the checkout.
- Create one purpose-built, short B1 experiment with a fresh result location.

Local verification:

- Unit-test request canonicalization, result-path resolution and collision
  rejection, resource propagation, script rendering, run metadata, lock
  handling, and state normalization.
- Verify that manual entry points remain compatible.
- Smoke-test repository planning locally under `netpyne` without running a real
  simulation.
- Review the diff, commit it, push it, preview it, and update the automation checkout through the proven A2 path.

Pass condition: the automation checkout can prepare one hash-bound job beneath
`hpc_jobs/runs/` while preserving the established scientific result layout,
leaving the manual checkout unchanged, and overwriting no result or log.

### Gate B1: one short simulation

Purpose: prove the complete path with the smallest meaningful NetPyNE run.

Implementation status: the scheduler-free B1 candidate connects prepared-run
submission, status, incremental top-level logs, terminal evidence, and
explicit checkout release to the B0 record contract. It must be manually
promoted and the lattice runtime paths must be checked before a fresh run is
prepared. No real submission is authorized by implementation or promotion.

The first real job reached Slurm but stopped in shell setup because nounset
mode preceded `.bashrc`. That attempt was finalized and released. The tracked
single, batch, and workflow templates now activate the HPC environment before
strict shell mode; B1 must retry with a new immutable run ID and separate
submission approval.

Sequence:

1. Preview a one-simulation request and review commit, experiment, duration, resources, output path, and expected artifacts.
2. Obtain explicit approval to update and submit.
3. Update to the exact previewed commit and submit once.
4. Monitor scheduler state and incremental top-level job logs.
5. Validate the durable completion record and exact expected result files.
6. Confirm the run record ends in a state supported by both scheduler and output evidence.

Pass condition: one simulation completes from an exact commit, all records agree, and no fixed-name file or previous result is overwritten.

### Gate B2: discover and record BatchTools child jobs

Purpose: resolve the largest application-specific uncertainty before building general batch monitoring.

Start with a successful two-child batch. Inspect only bounded output from the
BatchTools main job and known BatchTools artifact locations to determine:

- whether the current `LocalSlurmSubmit` exposes the child Slurm ID directly;
- the exact `sbatch` response available to BatchTools;
- when job labels, scripts, stdout/stderr, `.sgl` files, and completion records appear;
- whether the BatchTools main job can terminate before every child completion
  record is visible.

If IDs and paths are not available reliably, make the smallest change to `LocalSlurmSubmit` so it records one JSONL entry atomically at each child submission. Do not rediscover child jobs by recursively searching logs on every status check.

Pass condition: `jobs/index.jsonl` maps both labels to Slurm IDs, parameter coordinates, exact log paths, and expected outputs.

### Gate B3: tiny successful batch

Purpose: validate compact batch status and completion logic.

Sequence:

- Preview a 4-job batch with concurrency at most 2.
- Obtain explicit approval and submit it once.
- Monitor the BatchTools main job and all known IDs using one compact status
  operation per cycle.
- Inspect child logs only for a selected scientific sanity check or an abnormal/missing-output state.
- Compare Slurm terminal states, BatchTools main-job state, job completion
  records, and expected result existence.

Pass condition: all four jobs and outputs are accounted for without opening every log or scanning the result tree.

### Gate B4: controlled failure and uncertainty handling

Purpose: prove conservative behavior before relying on the workflow.

Use fixtures whenever the behavior can be tested without consuming cluster resources. Use one explicitly approved tiny failing child only for behavior that requires the real BatchTools/Slurm path.

Test cases:

- one child fails while others complete;
- the BatchTools main job exits while a child remains known to Slurm;
- Slurm says complete but an expected output is missing;
- the BatchTools main job reports a socket error but all durable outputs exist;
- BatchTools waits after all outputs are valid;
- monitoring connection is unavailable;
- the submission response is lost after Slurm accepted the job.

Expected behavior:

- show exact affected parameters and bounded log tails;
- keep scheduler state, BatchTools state, and output validity separate;
- classify unreachable state as `unknown`;
- never cancel, resubmit, or duplicate automatically;
- request user direction before any recovery action.

Pass condition: every case yields a conservative diagnosis and no unapproved state-changing action.

### Gate B5: selective result inventory and retrieval

Purpose: inspect a useful artifact without broad remote I/O.

Implementation target:

- Generate one inventory from known outputs when the run completes, or
  incrementally from completion records. Do not require scientific results to
  move out of their established experiment or workflow locations.
- Store relative path, job label/parameters, artifact type, size, modification time, and an optional checksum for small files.
- Resolve retrieval only by run ID, job label, and allowlisted artifact type.
- Cap files and bytes, default to one file, and cache by fingerprint locally.
- Store selected local copies beneath the existing ignored
  `exp_results_local/` area. Run large analysis as a separately approved Slurm
  job and retrieve only its compact outputs.

Tests after promotion:

- List the tiny batch's inventory without scanning the tree again.
- Retrieve one selected PNG or small PKL.
- Request it again and confirm a cache hit with no repeat transfer.
- Reject arbitrary paths, wildcards, unknown labels/types, too many files, and an oversized transfer.

When result analysis begins, use `sim_data_analyzer` where applicable.

Pass condition: one exact result can be selected and cached without granting general file-transfer or recursive-search capability.

## Prototype completion criteria

The prototype is complete when Codex can, using only protected helpers:

- identify the installed helper version and leave an audit record;
- push a dedicated branch and update only the clean automated checkout to an exact commit;
- preview actual job count/resources and reject requests over protected limits;
- submit one approved request idempotently;
- report top-level and child scheduler states compactly;
- read only new bounded top-level output and selected child-log tails;
- validate durable completion records and expected outputs;
- retrieve one selected cached artifact;
- report outages and contradictory evidence without cancellation or resubmission;
- leave the manual VS Code–lethe checkout untouched.

## Explicitly deferred work

Do not add these until the prototype has been used successfully on several real runs:

- autonomous cancellation or resubmission;
- unattended indefinite monitoring or remote `watch` sessions;
- arbitrary remote commands or arbitrary path retrieval;
- broad indexing of historical result trees;
- automatic bulk transfer;
- automatic modification of the manual checkout;
- concurrent runs using different source revisions;
- multiple retained executions of one non-workflow scientific result identity;
- replacement of edited Python scientific constants with a declarative
  experiment system;
- automatic attempt/resume/archive semantics for existing result directories;
- MCP server, daemon, database, or permanent broker;
- automatic HPC-to-WSL code push. Manual HPC fixes continue through the existing reviewed Git workflow.

## Immediate next action

Commit and push the tracked shell-setup correction, update the clean automation
checkout, and prepare a fresh B1 run at that exact commit. Review its newly
rendered script and obtain separate explicit approval before the second real
`sbatch` call. The B0 evidence run `b1-single-smoke-001` and failed B1 run
`b1-single-smoke-002` must not be submitted again.
