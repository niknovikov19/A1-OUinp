# B0 repository-integration plan

Status: revised design approved. B0.1 and B0.2 pass locally, B0.3 passed
promotion and installed-command tests at commit
`c6a60561a0cba178edaf8b673d6f25c618ce248a`, and B0.4 passes its local
fixture gate. The B0.5 candidate passes locally and awaits exact-commit
protected preparation.

The earlier B0.2a `exp_results/automation/...` prototype has been removed. The
replacement keeps scientific results in their established locations and puts
only top-level job records and logs beneath `hpc_jobs/runs/`.

## Goal

Prepare the smallest repository interface needed to test HPC-Codex with real
jobs while preserving the existing experiment-management conventions.

B0 ends after local tests, protected preparation, preview, and an exact-commit
checkout update. No NetPyNE job is submitted until B1 and separate approval.

## Separation of responsibilities

HPC-Codex manages approved Slurm operations:

- validate a tracked job request against protected limits;
- prepare and hash one exact shell script;
- submit that script with `sbatch` exactly once;
- record top-level and known child Slurm IDs;
- report scheduler state and bounded log increments;
- verify declared completion evidence and retrieve selected artifacts.

Repository code interprets scientific configuration:

- `run_exp.py` and `exp_cfg.py` resolve a single simulation;
- the BatchTools main program and `batch_params.py` resolve a batch;
- `run_workflow.py` and `workflow_cfg.py` resolve workflow stages;
- experiment and workflow code determine their established result layouts.

The protected helpers do not reproduce `exp_cfg.py`, `batch_params.py`,
`workflow_cfg.py`, `cfg.saveFolder`, or workflow-stage logic.

Protected preparation also does not import or execute repository Python on
lethe. Scientific preflight runs locally for review and runs again inside the
allocated Slurm job before simulation work or BatchTools child submission.
The protected layer validates only the tracked JSON request, protected limits,
clean exact commit, fixed template tokens, repository-confined paths, and
recorded hashes.

## Intended repository layout on HPC

```text
A1_OUinp_codex/
  exp_configs/                       # tracked scientific configurations
    <experiment>/
  workflow_configs/                  # tracked workflow configurations
    <workflow>/
  hpc_jobs/
    requests/                        # tracked job requests
    templates/                       # tracked sbatch templates
    runs/                            # ignored prepared scripts and top-level logs
      <run-id>/
        request.json
        run.json
        submission.json
        submit.sh
        slurm-<job-id>.out
        slurm-<job-id>.err
  exp_results/                       # ignored scientific results
    <experiment>/
      <exp_name_sub>/
    workflows/
      <workflow>/
        <run-id>/
  exp_logs/                          # existing non-HPC-Codex runtime uses
```

Only `hpc_jobs/requests/` and `hpc_jobs/templates/` are tracked.
`hpc_jobs/runs/` is ignored.

The external HPC-Codex state root contains only small authoritative records:

```text
hpc_codex/state/A1_OUinp/
  run index
  audit records
  submission records and Slurm IDs
  recorded repository paths and hashes
  incremental-log cursors
  checkout lock and active-run marker
```

Large Slurm or simulation logs are not copied into this state root.

## Existing scientific result identity

Ordinary experiments retain their current correspondence:

```text
exp_configs/<experiment>/
exp_results/<experiment>/<exp_name_sub>/
```

`exp_name_sub` remains the human-readable identity derived from frequently
changed scientific constants. Codex must check that changing such a constant
also changes the resolved name where the experiment convention requires it.
The exact commit and saved configuration provide machine-readable provenance.

Workflows retain their current layout:

```text
workflow_configs/<workflow>/
exp_results/workflows/<workflow>/<run-id>/
```

Workflow stage specifications and resolved-parameter records identify the
experiments and scientific values used within each stage.

HPC-Codex does not insert an `automation/` or `hpc_runs/` directory into
`exp_results` during Gate B.

## Collision policy

The prepared request records the expected scientific result path as an
assertion, not as the source of scientific parameters. Repository code resolves
the actual path and must reject a mismatch before expensive work begins.

Initial Gate-B rules are conservative:

- a new job requires a result location that is safe for the selected
  experiment's existing behavior;
- an existing non-empty result location is rejected;
- no result is overwritten, deleted, archived, or resumed automatically;
- resource-only changes create a new job request and run ID, but do not create
  a new experiment or scientific result name;
- retaining multiple executions of the same scientific configuration requires
  a later, explicit experiment-management design.

The first B1 experiment therefore uses one fresh, purpose-built result path.

## Tracked job requests

A request is a small JSON record beneath `hpc_jobs/requests/`. It is selected
by a validated request ID and read only from the exact automation commit.

It records:

- a tracked template ID;
- an experiment or workflow identifier;
- top-level Slurm resources;
- BatchTools child resources and concurrency when applicable;
- workflow-stage simulation resources when applicable;
- the expected scientific result path and bounded completion evidence;
- protected-limit inputs such as maximum child count.

Scientific parameter values remain in `exp_cfg.py`, `batch_params.py`, or
`workflow_cfg.py`. A result path in the request is a checked expectation.

Changing scientific parameters follows the existing model:

```text
edit tracked Python configuration
  -> update descriptive result naming if needed
  -> local checks
  -> commit, push, exact checkout update
  -> preview and submit
```

Changing only Slurm resources creates or revises a tracked job request; it does
not require another experiment directory.

## Shell-script preparation

Templates beneath `hpc_jobs/templates/` remain ordinary tracked repository
files. The protected preparation helper reads the selected template from the
exact clean commit and renders a small fixed token set.

Values come from three sources:

- tracked request: target identifier and requested resources;
- protected configuration: checkout root, allowed resources, and reviewed
  absolute paths from the HPC `netpyne_batch_slurm` environment;
- protected derivation: run ID, safe job name, request path, and top-level log
  paths beneath `hpc_jobs/runs/<run-id>/`.

The helper writes `submit.sh` atomically beneath the ignored run directory,
records its source and rendered SHA256 values, and removes its write bits. The
submission helper rechecks the exact commit and script hash, then calls only:

```text
sbatch <exact prepared submit.sh>
```

The caller never supplies shell text or an arbitrary path.

## Job shapes

HPC-Codex is not limited internally to three hard-coded operations. It submits
approved tracked templates under one protected policy. Gate B exercises three
repository job shapes:

### Single simulation job

- the top-level Slurm job is the simulation job;
- it selects one validated experiment and uses existing `run_exp.py` behavior;
- repository code resolves `cfg.exp_name_sub` and the result path;
- no BatchTools child jobs exist.

### BatchTools main job

- the top-level Slurm job runs the BatchTools main program;
- `batch_params.py` remains authoritative for parameter axes;
- the tracked request supplies top-level resources, child-job resources, and
  maximum concurrency;
- BatchTools submits child simulation jobs through `sbatch`;
- B2 determines whether the existing submission result exposes enough child
  information or needs one atomic `jobs/index.jsonl` record per child.

### Workflow manager job

- the top-level Slurm job runs `run_workflow.py`;
- `workflow_cfg.py` remains authoritative for scientific workflow parameters;
- the request supplies manager-job and per-stage simulation resources;
- `run_workflow.py` validates stage names and applies those resource settings
  when constructing BatchTools jobs;
- the existing workflow result and completion records remain authoritative.

The same protected submission mechanism can later support another reviewed
tracked template, such as preprocessing or analysis, without accepting an
arbitrary command. Job arrays, dependencies, GPUs, cancellation, and retries
remain unavailable until separately designed and tested.

## B0 implementation status

Completed in B0.1-B0.4:

1. Audited representative single and batch experiments and workflow code for
   result-name resolution, collision behavior, expected files, and consumers.
2. Defined the tracked request schema and fixed-token templates. Protected
   ceilings remain enforced by protected configuration in B0.3.
3. Added `hpc_jobs/runs/` to `.gitignore` while keeping requests and templates
   tracked.
4. Added a preflight that resolves an experiment's expected scientific
   result path without running a simulation.
5. Preserved manual `run_exp.py` behavior and added validation needed to
   assert the expected result path for an HPC-Codex job.
6. Added strict tracked-request inputs to `grid_search_slurm_local.py` for the
   experiment, simulation-job resources, and concurrency while retaining the
   former no-argument manual defaults. `batch_params.py` remains authoritative
   for parameter axes.
7. Made the existing workflow CLI effective and added validated per-stage
   simulation-job resources plus a whole-workflow simulation-job budget.
8. Added local tests for request validation, script rendering, result-path
   assertions, collisions, resource propagation, and manual-mode compatibility.
9. Added protected local and lethe preparation candidates, configuration,
   schemas, fixtures, promotion scripts, and handoff instructions without
   executing a candidate from the repository.
10. Commit, push, update the exact automation checkout, and manually promote
    both B0.3 candidates.
11. Test the installed preparation command, idempotency, rejected inputs, and
    immutable records without submission.
12. Add the fixture-only B0.4 lifecycle contract for exact-commit locking,
    one-intent/one-receipt submission, fixed log paths, bounded child records,
    terminal evidence, and explicit active-run release.

Remaining:

13. Add the purpose-built B1 request and local preflight in B0.5. Do not
    submit a simulation during B0.

## Progressive B0 review points

### B0.1: repository contract audit and design

Pass condition: the selected single, batch, and workflow paths are documented,
all known result-path consumers are identified, and this revised design is
approved before implementation.

Status: PASS. The design was approved in discussion before implementation
resumed.

### B0.2: tracked request and repository interface

Pass condition: local tests show exact resource propagation, resolved result
paths, collision rejection, and unchanged manual invocation behavior without
calling Slurm or running a simulation.

Status: PASS locally. The `netpyne` environment passed 29 Gate-B contract and
entry-point tests, 36 workflow regression tests, and 16 dummy-workflow tests.
Representative real-config preflights resolved one existing single result path
and the existing 15-job `net_newsec_var_seed` batch without constructing a
network or contacting Slurm. The three previously recorded full-simulation
test failures remain unchanged and unrelated to B0.

### B0.3: protected preparation

Pass condition: after manual promotion, a reviewed request produces one
hash-bound `hpc_jobs/runs/<run-id>/submit.sh` and small external state records,
without submission.

Status: PASS. The protected helper validated the tracked request, exact clean
commit, protected limits, tracked target files, and allowlisted template hash.
The installed command prepared one immutable run snapshot, repeated it as an
idempotent no-op, rejected invalid identifiers and commit values, and created
no submission record or scheduler state.

### B0.4: protected real-job boundary

Pass condition: fixtures prove exact-commit locking, one-intent/one-receipt
submission handling, bounded log-path resolution, child-record ingestion, and
explicit finalize/release behavior without calling `sbatch`.

Status: PASS locally. `hpc_job_lifecycle.py` and its checked-in fixture prove
the record and transition contract with no scheduler command. Eighteen focused
tests cover clean exact-commit checks, fail-closed pending and unknown
submissions, idempotent receipts, bounded top-level and child logs, child-job
limits, terminal evidence, and explicit active-marker release.

### B0.5: B1 request and local smoke tests

Pass condition: one fresh purpose-built single experiment previews from an
exact clean commit with its existing descriptive result path, expected files,
top-level resources, and prepared-script hash. No simulation has run.

Status: local candidate PASS. `single_hpc_prototype/b1_smoke` defines one
unconnected `IT2` cell, a 1000 ms fixed-seed background-input simulation, and
one compact completion JSON. Its tracked request asserts the descriptive
result directory, one completion file, and a 1-node, 1-core, 2-GB, 10-minute
top-level job. Local tests bind the intended rendering for run ID
`b1-single-smoke-001` to SHA256
`1988abfe912bc5f4ba517a7245491ff2e583b721ced7e423575ed04432d9441d`.
Exact-commit protected preparation remains before the B0.5 gate passes.

## Required HPC environment handoff

Before finalizing the templates, record the reviewed absolute runtime paths
from the existing `netpyne_batch_slurm` environment on lattice. Local
development and tests use the local `netpyne` environment.

The HPC handoff must identify the established command used inside an `sbatch`
allocation. HPC-Codex itself uses only `sbatch` for top-level submission and
does not assume that `srun` is the correct internal launcher.

## B0 non-goals

- no real Slurm submission;
- no general experiment-management redesign;
- no automatic declarative replacement for edited Python constants;
- no multiple-attempt result layout;
- no production experiment migration;
- no cancellation, retry, or resubmission;
- no arbitrary remote path or shell interface;
- no recursive result-tree scan;
- no broad cleanup of historical analysis paths.

## B0 completion evidence

B0 is complete only when:

- the revised repository contract is approved;
- tracked request and template tests pass locally under `netpyne`;
- top-level and child/stage resources propagate to the intended Slurm fields;
- existing experiment and workflow result layouts remain unchanged;
- result-path mismatches and collisions are rejected;
- the prepared script and small external records are hash-bound and immutable;
- the purpose-built B1 request previews from one exact clean commit;
- the automation checkout is updated through the proven A2 path;
- no real simulation has run.
