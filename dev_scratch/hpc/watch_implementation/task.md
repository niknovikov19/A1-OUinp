# Implement the local watcher

Implement the agreed bounded, resumable local watcher. Use installed
`/opt/a1-hpc/bin/hpc-job` status and incremental log operations only. Preserve
observations locally and return short reports for checkpoints, problems, and
Slurm termination. Keep result verification and all state-changing HPC operations
outside the watcher. Do not change experiments or remote helper code.

Test local process waiting first, then polling/state/resume/error behavior with
fake responses and time. Finish with a bounded read-only check against the existing
completed pilot. Record measured tool behavior separately from planned intervals.
