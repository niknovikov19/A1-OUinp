# Tracked HPC job interface

This folder contains the repository-owned part of the HPC-Codex contract.

- `requests/` contains reviewed job requests selected by request ID.
- `templates/` contains reviewed top-level `sbatch` templates.
- `runs/` is ignored and contains prepared scripts, top-level logs, and small
  submission records.
- `job-request.schema.json` documents the request JSON shape enforced by
  `hpc_job.py`.
- `hpc_job_lifecycle.py` defines the exact submission, log, child-job,
  finalization, and release records used by later protected helpers.
- `hpc_job_control.py` provides strict `sbatch` receipt parsing, normalized
  scheduler-result validation, bounded incremental log reading, and declared
  completion-file inspection for those records.

Requests contain scientific target names and operational resources. Scientific
parameter values remain in `exp_configs/` or `workflow_configs/`. The expected
result path is an assertion against the path derived by `hpc_preflight.py`.

The canonical batch main-job template temporarily excludes `node10` because
three B2 Ray-startup attempts stalled there. BatchTools-generated simulation
jobs do not inherit that exclusion.

The exact Git commit is supplied to the protected preparation operation and is
stored in the prepared run record. It is intentionally not embedded in a
tracked request because a file cannot contain the hash of its own commit.

Protected preparation never imports repository experiment or workflow Python.
Scientific preflight runs locally and again inside the allocated top-level
Slurm job before expensive work or child-job submission.

The lifecycle module contains no scheduler command. Its fixture tests prove
fail-closed intent/receipt transitions and path bounds before B1 connects the
same record contract to a protected `sbatch` helper.

The protected job layer consumes a prepared run by ID. It writes
`submission.json`, `final.json`, and `release.json` beside the immutable
snapshot while retaining matching mode-`0600` records in external protected
state. Finalization and release remain separate: a terminal job continues to
block checkout updates until its evidence is finalized and explicitly
released.

For tracked batch requests, `grid_search_slurm_local.py` writes one locked
JSONL entry at each successful child submission. The index remains beneath the
established scientific result directory in `jobs/index.jsonl`; it contains
small submission evidence, while child stdout and stderr stay in the adjacent
ignored `jobs/` directory. The protected finalizer trusts only validated
records bound to the prepared run and declared output paths.
