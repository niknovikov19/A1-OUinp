# Watcher implementation findings

- Implementation was authorized on October 20, 2026. The older plan's statement
  that runtime implementation lacked approval is superseded by this request.
- Existing status/log commands each perform one operation. Status does not prove
  the complete planned child set or output validity. Logs share local helper
  cursors, so independent readers can consume content before the watcher.
- Use a separate local Python program and the installed helper's JSON responses.
  No changes to experiment parameters, remote helpers, or batch execution are
  required for this watcher.
- A real 12-second local waiting probe returned a session ID. One subsequent
  Codex check waited for completion (13.142 seconds from launch, 5.738 seconds
  inside the wait call). No intervening model check was required. This verifies
  short foreground waits, not a 30-minute chat wake-up guarantee.
- Implemented `hpc_watch.py` and the thin local entry point
  `dev_scratch/hpc/watch_run.py`. They use the installed helper only for status
  and selected logs; no experiment, remote helper, or scheduler mutation changed.
- All 36 watcher tests passed. Tests use fake time and helper replies for polling,
  resume, deadlines, accounting gaps, identity changes, failures, log diagnostics,
  and storage. Policy tests mock fsync; separate real-process checks exercise
  bounded pipes, process termination, and local persistence.
- A real 12.066-second watcher process performed six simulated HPC checks and
  returned one checkpoint. Codex checked it once after launch; one waiting-tool
  call observed its completion. `wait_measurement.json` records the process
  duration, simulated check count, and ignored local evidence directory. This
  proves short repeated polling without model checks between polls; the actual
  30-minute chat timing remains unmeasured.
- Live read-only check passed against `thal-irem-fade-pilot-20261020b` using the
  installed helper through the new local watcher. It made one status call and
  one main-log read, then returned `scheduler-terminal` in 9.734 seconds with
  main 118799 and four completed simulations. It explicitly left output validity
  and complete planned-child coverage unverified. See `live_acceptance.json`.
- The ordinary Python wrapper required a one-off network approval. No protected
  installation or persistent Python/shell allow rule was added. Default cache
  files remain under the existing ignored `exp_results_local/` tree.
- Attention is acknowledged when the caller explicitly resumes after a saved
  report. Log replies must match the observed Slurm ID as well as the run/child
  label. A recorded live-response replay checks the final parser against actual
  installed-helper replies without another HPC query.
- Final regression passed: **174 HPC tests**, including **38 watcher tests**,
  in the project NetPyNE environment. Existing helper, lifecycle, archive,
  preparation, and batch-entrypoint tests remain green. No Gate A/B scientific
  jobs or protected installations were needed.
- Local `--status` confirmed the live watcher had exited and reported its last
  usable observation and handoff reason without contacting HPC. The recorded
  status/log replay passed the final Slurm-ID checks as well.
- Default 1800-second checkpoints are implemented and tested with simulated
  time. Actual 30-minute chat waiting remains unmeasured; the watcher does not
  promise to wake an inactive chat or survive the tool session ending.
