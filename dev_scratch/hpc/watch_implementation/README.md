# Run the local watcher

The watcher is a local Python process. It calls installed `hpc-job status` and
`hpc-job log`, saves their bounded responses locally, and prints one short JSON
report when it returns. It does not call an AI model.

From the repository root:

```bash
python3 dev_scratch/hpc/watch_run.py RUN_ID
python3 dev_scratch/hpc/watch_run.py RUN_ID --resume
python3 dev_scratch/hpc/watch_run.py RUN_ID --status
```

Replace `RUN_ID` with an already submitted run. `--status` inspects the local
process lock, update times, and last report reason; it does not contact HPC.
The program requires Python 3.10 or newer and the installed HPC-Codex helpers.
It introduces no remote helper or experiment changes.

## Two intervals control different actions

- The watcher queries HPC every 60 seconds during its first five minutes, then
  every 120 seconds. An unchanged pending queue uses 300 seconds after ten minutes.
  These gaps start after the preceding helper calls finish; calls never overlap.
- The watcher returns a routine report after 1800 seconds. Set
  `--codex-check-sec SECONDS` to change that interval (1–86400 seconds).
  Resume retains the saved interval unless this option supplies a replacement.

Failures, identity changes, persistent loss of status, or Slurm termination can
return a report earlier. Starting the Python process does not itself arrange a
future chat update. Codex must wait for the process and read its report. Short
tool waits are measured in the findings log; a real 30-minute chat wait has not
been measured.

## Read the report

| `reason` | Meaning | Exit code |
|---|---|---|
| `checkpoint` | The local session reached its reporting interval. | 0 |
| `scheduler-terminal` | The main and every currently recorded simulation have ended. | 0 |
| `attention` | A job failed, the main ended with simulations active, or the helper rejected an operation. | 2 |
| `monitoring-unavailable` | Status remained unavailable or incomplete after bounded retries. | 3 |
| `local-error` / `local-storage-limit` | The local process cannot continue reliably. | 4 |
| `deadline` | The overall monitoring deadline expired. | 5 |
| `interrupted` | Local monitoring stopped; HPC jobs were not cancelled. | 130 |

The report separates main state, simulation-only counts, missing/unknown jobs,
the last usable observation time, and diagnostic log problems. It includes up
to three attention items and points to the full local evidence. Reports are at
most 8 KiB.

`scheduler-terminal` does **not** establish the complete planned simulation list
or validate scientific files. The current status command cannot provide those
facts. Finalization, release, cancellation, resubmission, downloading results,
and scientific analysis remain separate actions.

## Resume and stop

`--resume` always requests fresh status unless the saved deadline has expired.
It acknowledges attention in the preceding saved report, so an unchanged known
failure does not cause an immediate repeat. New failures still trigger attention.

Set an overall UTC deadline with `--until`, for example:

```bash
python3 dev_scratch/hpc/watch_run.py RUN_ID --until 2026-10-21T04:00:00Z
```

The deadline survives checkpoint/resume and host sleep. Resume cannot silently
extend it. To explicitly extend an existing deadline, use
`--resume --extend-until NEW_UTC_TIMESTAMP`. Ctrl+C or SIGTERM stops the local
reader and saves an interruption report when local storage remains writable.
Neither operation cancels Slurm jobs.

## Local files and logs

The default directory is `exp_results_local/hpc_codex/RUN_ID/watch/`, which is
already ignored by Git. `--state-root PATH` changes the local cache root.

- `state.json` records identities, last status, freshness, and resume settings.
- `report.json` contains the latest short handoff.
- `observations-0001.jsonl`, etc. retain complete bounded helper replies.
- `events.jsonl` records transitions, attention, and explicit deadline extensions.
- `watch.lock` prevents two local watchers from owning the same run history.

The watcher rotates observations at 16 MiB and stops at a 256 MiB evidence budget.
It retains earlier files. A torn last observation is preserved and resume starts
a new segment. State and report files have separate small byte limits.

The watcher reads the main log initially, about every five minutes, and before
an attention/termination report. It reads at most two affected simulation logs
per cycle. `--no-logs` disables these reads. Log text does not determine job success.
Backlog is reported rather than drained without limit.

Existing helpers share log cursors across readers. Coordinate other log reads
while watching. An interruption after a helper advances its cursor can leave a
gap in the watcher's saved log history; the watcher cannot rewind that cursor.

The watcher executes only the fixed installed helper with argument lists.
It accepts no host, remote command, scheduler option, or helper-path override.
Network access may require approval for the watcher invocation; existing helper
permissions do not automatically apply to a Python wrapper. Do not grant an
unrestricted Python or shell prefix to avoid that check.
