# B0 integrated simulation implementation plan

Status: B0.1 architecture audit complete; B0.2 repository work is in progress.
No protected helper has been changed, promoted, or executed for B0.

## Goal

Prepare the repository and protected helper boundary for unique, immutable
single and batch simulation runs. B0 ends after local tests, a protected
preview, and a clean exact-commit checkout update. It does not submit a real
simulation; that is Gate B1 and requires separate explicit approval.

## B0.1 audit findings

| Component | Current behavior | B0 consequence |
| --- | --- | --- |
| `submit_single_slurm_local.sh` | Hardcodes experiment, manual checkout, fixed logs, 60 tasks, 256 GB, and 24 hours. Stdout and stderr use the same fixed file. | Convert it into a tracked launcher template. Never execute it directly from the mutable repository location. |
| `submit_batch_slurm_local.sh` | Hardcodes manual checkout and fixed controller logs. Controller resources are mixed conceptually with child resources. | Convert it into a tracked controller template with separately rendered controller resources. |
| `grid_search_slurm_local.py` | Selects the experiment and child resources through edited module constants. Uses fixed result/checkpoint locations and concurrency. | Refactor into callable functions plus a strict CLI driven by one immutable run-context file. |
| `run_exp.py` | Single mode accepts an unchecked experiment string. Batch mode infers the experiment by stripping a fixed number of characters from `simLabel`. Single results default to `exp_results/<experiment>`. | Resolve a validated experiment explicitly and accept one exact run result directory. Remove label-length experiment discovery from the automation path. |
| `LocalSlurmSubmit` | Writes useful child scripts but does not durably record the parsed child Slurm submission response at submission time. | Keep script generation for B0/B1. Add atomic child-ID recording only at B2 if the real two-child probe confirms it is needed. |
| `run_workflow.py` | Already uses script-relative roots, validated run IDs, immutable resolved parameters, source hashes, per-stage directories, durable job records, output validation, and attempt-specific BatchTools artifacts. | Reuse these patterns instead of creating a second incompatible workflow model. Do not route B1 through a full iterative workflow. |
| `workflow_utils.py` | Provides stable JSON hashing, atomic writes, parameter-grid expansion, job validation, polling, and artifact collection. | Extract or reuse the pure pieces for automation run preparation and tests. |
| Protected A-stage helpers | Prove exact commit, preview, submission idempotency, lifecycle status, and bounded incremental logs, but assume one fixed probe wrapper and `run_id == request_id`. | Extend the model to separate request ID from unique run ID and to submit a hash-bound rendered launcher. Preserve the proven rejection, audit, and uncertainty behavior. |
| Result storage | `.gitignore` already ignores `exp_results/automation/`. | Store real automation run directories there; Git updates remain clean while results stay beside the repository. |
| Runtime environment | Local development and tests use `netpyne`. HPC Slurm jobs use the existing `netpyne_batch_slurm` environment, but the launchers select it through interactive shell setup. Its exact Python, `nrniv`, environment prefix, and supporting variables are not yet recorded. | Keep the two environments distinct. Replace interactive HPC activation with reviewed absolute paths and fixed environment values from `netpyne_batch_slurm` after one read-only lattice probe. |

## Reusable baseline

The focused workflow baseline is verified in the local `netpyne` environment:

```text
/home/nnovikov/conda_env/netpyne/bin/python -m unittest discover \
  -s tests -p 'test_workflow.py'
/home/nnovikov/conda_env/netpyne/bin/python -m unittest discover \
  -s tests -p 'test_workflow_dummy.py'
Ran 52 tests: OK
```

The broader `tests.test_workflow_fullsim` baseline has three existing failures:

- two expectations no longer match the current full-simulation configuration;
- one mocked `sim_data_analyzer.xr_adapters` module lacks `get_lfp_xr`.

B0 tests must pass independently. Changes to the full-simulation baseline will
be kept separate unless a B0 change directly requires that module.

## Target architecture

```text
protected request catalog + exact Git commit + validated unique RUN_ID
  -> hpc-run-preview
  -> protected run preparation on lethe
       -> resolve tracked launcher template from the exact checkout
       -> create exp_results/automation/<experiment>/<run-id>/
       -> write canonical request.json and immutable run.json
       -> render controller/submit.sh
       -> record template and rendered-script SHA256 values
       -> register RUN_ID in the protected run index
  -> explicit hpc-submit RUN_ID approval
       -> lock against concurrent Git updates
       -> revalidate checkout commit, run record, and submit.sh SHA256
       -> create the global active-run marker
       -> sbatch the exact controller/submit.sh once
  -> controller
       -> single: run one validated experiment
       -> batch: submit known child requests with separate child resources
  -> hpc-status / hpc-log
       -> resolve RUN_ID only through protected metadata
       -> never accept an arbitrary filesystem path
```

## Run directory

```text
exp_results/automation/<experiment>/<run-id>/
  request.json
  run.json
  submission.json
  status.json
  controller/
    submit.sh
    slurm-<controller-id>.out
    slurm-<controller-id>.err
  jobs/
    index.jsonl
    scripts/
    logs/
    comm/
    summaries/
  sim_results/
  meta/
```

The run directory is user-owned and writable while work is active. Immutable
inputs and records are written atomically and never silently replaced. The
rendered `submit.sh` is made non-writable after preparation. Global locks,
audit state, and the run index stay under the existing out-of-repository state
root.

## Design decisions

### Request and run identity

- `request_id` selects one reviewed catalog entry.
- `run_id` is a separate validated unique name, at most 80 characters.
- Reusing a run ID is accepted only when request digest, commit, template hash,
  rendered-script hash, and immutable metadata are identical.
- A protected run index maps a run ID to its exact generated directory. Status,
  log, and submission helpers use the index; callers never provide a path.

### Launcher rendering

- The single and batch launcher sources remain ordinary tracked repository
  files.
- The preparation helper reads them only from the exact automation checkout.
- Rendering supports a small fixed token set. Every token must occur exactly
  once where required; missing, duplicated, unknown, newline-bearing, or
  shell-active values are rejected.
- Controller resources, absolute checkout path, experiment ID, run directory,
  and fixed runtime paths are inserted from validated protected data.
- `run.json` records both source-template and rendered-script SHA256 values.
- The submission helper hashes `submit.sh` again immediately before `sbatch`.

### Resource separation

Version-2 simulation requests distinguish:

- `controller_resources`: the outer single simulation or batch controller;
- `child_resources`: BatchTools simulation jobs, required only for batch runs;
- `calculated_child_jobs` and `max_concurrent_jobs`.

The protected global limits apply independently to controller and child
resources. A controller allocation is never reused as an implicit child
allocation.

### Runtime environment

Rendered scripts will use absolute reviewed `srun`, `nrniv`, and Python paths,
plus fixed environment variables. They will not source `~/.bashrc`, call
`conda activate`, inherit arbitrary shell functions, or depend on the login
shell's current directory.

### Checkout lock

- Preparation alone does not block Git updates.
- Submission acquires the same global lock used by the A2 updater, rechecks the
  commit and run snapshot, and creates `active-run.json` before `sbatch`.
- A known submission failure removes the marker; an uncertain outcome keeps it.
- Terminal scheduler state alone does not remove the marker. A protected
  finalize operation requires terminal state plus the expected durable output
  evidence, then archives the marker and releases the checkout.
- Release after an abandoned prepared run or uncertain submission is explicit,
  audited, and never automatic.

## Progressive implementation gates

### B0.2: pure repository refactor

Implement and test without protected installation or Slurm:

- add a small pure module for experiment/run-ID validation, result-path
  construction, canonical run context, and fixed launcher-token rendering;
- refactor `grid_search_slurm_local.py` into functions and a strict CLI;
- add explicit automation arguments to `run_exp.py` while retaining the manual
  invocation path;
- remove BatchTools experiment discovery by `simLabel` suffix from the
  automation path;
- convert `submit_single_slurm_local.sh` and
  `submit_batch_slurm_local.sh` into reviewed tracked templates;
- add golden rendering and rejection tests.

Pass condition: local tests produce unique single and batch run layouts and
scripts without importing NEURON, invoking BatchTools, or calling Slurm.

### B0.3: protected preparation candidate

Add candidate helpers and schemas, but do not execute them from the repository:

- local `hpc-run-prepare REQUEST_ID RUN_ID`;
- lethe-side fixed preparation helper;
- version-2 request, run-record, run-index, and render-result schemas;
- protected configuration for the automation result root, tracked templates,
  runtime paths, and fixed limits;
- fixture self-tests for immutable reuse, collision rejection, symlinks,
  traversal, token errors, resource overflow, and atomic records.

Pass condition: after manual promotion, one fixture request prepares the exact
directory and script snapshot without submission.

### B0.4: real-run submission boundary

Extend the proven submission/status/log path:

- submit by run ID through the protected run index;
- revalidate the rendered script and exact commit;
- implement the active-run marker state machine;
- retain one-intent/one-receipt idempotency and uncertain-outcome behavior;
- resolve B-run controller logs from the indexed run directory;
- add explicit finalize/release behavior.

Pass condition: fixture and dry-run tests prove all checks without calling
`sbatch`; the A-stage probe path remains valid or is deliberately migrated.

### B0.5: purpose-built B1 experiment and local smoke test

- create a new small experiment configuration specifically for B1;
- keep duration, active populations, recording, and expected artifacts minimal
  but scientifically meaningful;
- define one single-run catalog entry with conservative resources;
- smoke-test config resolution and expected-output planning without simulation;
- run all B0 tests plus the 52-test reusable workflow baseline;
- review, commit, push, preview, and fast-forward the automation checkout.

Pass condition: the exact B1 request previews one unique run and a hash-bound
controller script, while no simulation has been submitted.

## Required lattice environment handoff

Before finalizing rendered launchers, record these values after activating the
approved `netpyne_batch_slurm` environment on lattice:

```bash
printf 'CONDA_PREFIX=%s\n' "$CONDA_PREFIX"
command -v python3
command -v nrniv
command -v srun
python3 --version
nrniv --version
python3 -c 'import netpyne, neuron; print(netpyne.__version__, neuron.__version__)'
```

This is read-only. The reviewed paths will be configuration values, not
credentials and not caller-controlled arguments.

## B0 non-goals

- no real Slurm submission;
- no production experiment migration;
- no cancellation or resubmission;
- no arbitrary remote path or shell interface;
- no recursive result-tree scans;
- no child-ID inference until the B2 two-child observation;
- no broad cleanup of unrelated hardcoded historical analysis paths.

## B0 completion evidence

B0 is complete only when:

- validation and rendering tests pass;
- single and batch controller resources are demonstrably separate from child
  resources;
- unique result/log paths and immutable run records are proven;
- run-index and active-lock transitions pass fixtures;
- rendered script tampering is rejected;
- the purpose-built B1 request previews from one exact clean commit;
- the automation checkout is updated through A2 without touching the manual
  checkout;
- no real simulation has run.
