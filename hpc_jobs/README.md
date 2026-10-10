# Tracked HPC job interface

This folder contains the repository-owned part of the HPC-Codex contract.

- `requests/` contains reviewed job requests selected by request ID.
- `templates/` contains reviewed top-level `sbatch` templates.
- `runs/` is ignored and contains prepared scripts, top-level logs, and small
  submission records.
- `job-request.schema.json` documents the request JSON shape enforced by
  `hpc_job.py`.

Requests contain scientific target names and operational resources. Scientific
parameter values remain in `exp_configs/` or `workflow_configs/`. The expected
result path is an assertion against the path derived by `hpc_preflight.py`.

The exact Git commit is supplied to the protected preparation operation and is
stored in the prepared run record. It is intentionally not embedded in a
tracked request because a file cannot contain the hash of its own commit.

Protected preparation never imports repository experiment or workflow Python.
Scientific preflight runs locally and again inside the allocated top-level
Slurm job before expensive work or child-job submission.
