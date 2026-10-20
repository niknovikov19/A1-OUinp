# H1: local HPC waiting and reporting plan

Status: discussion draft, 2026-10-15. The user agreed to bounded resumable
watcher sessions, thirty-minute routine checkpoints, and completion handoff to Codex.
Runtime implementation and installation have not been approved. Remaining
design choices and defaults below are proposals until agreed.

## Outcome and scope

Move repeated status checks, sleeps, comparisons, and routine retries into a
deterministic local program. Keep complete bounded helper responses on disk
and return compact evidence when Codex needs to report or make a decision.
The success measure is fewer Codex checks during an unchanged wait, as well as
smaller reports. Reducing printed output alone does not satisfy H1.

Monitor one explicitly selected, already submitted run per invocation. Use
only installed protected helpers as the HPC backend. H1 does not depend on
H2/H3 and does not change simulation code, submission limits, scheduler query
chunking, remote commands, or the existing completion contract.

Result verification and finalization remain with Codex after the watcher
returns scheduler evidence. Background services, automatic finalization,
cancellation/resubmission, archive transfer, scientific analysis, and broader
batch scaling are outside the first-version monitoring scope.

## Names used in this plan

- **Codex:** the AI that starts the watcher, reads its reports, and decides
  what to do next. Repeatedly involving Codex consumes tokens.
- **Codex tool:** the interface Codex uses to start a local program or read
  its status/output. For example, `exec_command` starts the watcher and
  `write_stdin` can read output from an already running watcher.
- **Watcher:** the proposed local Python program. It checks HPC through the
  helpers, saves observations, and prepares reports without involving Codex
  in each HPC check.
- **Helper:** an existing protected program such as `hpc-job` that performs
  a bounded HPC operation for the watcher.
- **Slurm scheduler:** the HPC system that queues jobs, assigns resources,
  and reports job states. References to scheduler state below mean Slurm state.

## Existing behavior that constrains the design

- `hpc-job --json status RUN_ID` returns controller and recorded child
  scheduler states, child keys/parameters, run commit, observation time, helper
  identity, and normalized counts. Counts include the controller.
- Status reads the current child index. An absent index returns no children;
  the reply does not expose the expected total child count or prove that all
  expected children were submitted. The observed list can grow during startup.
- Status does not verify output files. `hpc-job finalize` checks the existing
  completion contract and writes durable final records; `release` is separate.
- Unknown jobs and accounting gaps are explicit. Scheduler observations are
  sequential rather than an atomic snapshot of the entire tree.
- `hpc-job log` reads the controller or one selected child incrementally.
  `logs` pages five children, with per-stream bounds and independent cursors.
  Log retrieval does not query the scheduler.
- Cursor storage belongs to the installed helper. Another reader can consume
  a stream before the watcher sees it; local watcher state cannot rewind it.
- A local job helper allows up to 240 seconds for a remote operation. A status
  command may therefore take longer than the proposed normal polling interval.
- Candidate helper executables in `helper_src` must not be invoked in place.
  Tests may import candidate code with mocked backends, following existing tests.

Sources: [monitoring contract](helper_src/INSTALL_MONITOR_ARCHIVE.md),
[accepted implementation](monitor_archive_testing.md),
[local helper](helper_src/local/hpc-job), and
[remote status/finalization](helper_src/remote_lethe/hpc-lethe-job).

## Agreed decisions and remaining proposals

| Decision | First-version choice or proposal | Alternative and consequence | Status |
| --- | --- | --- | --- |
| Process lifetime | Bounded watcher session with local state and explicit resume | Detached service needs ownership, shutdown, restart, and notification design | Agreed, 2026-10-15 |
| Routine Codex checks and chat checkpoints | Every 30 minutes by default, with a configurable Codex check interval; ordinary transitions stay local | A longer interval or attention/completion only involves Codex less often | Thirty-minute default agreed; configurable interval requested, 2026-10-15 |
| Completion handoff | Return scheduler evidence to Codex; finalization remains separate | Automatic protected finalization adds a state-changing operation | Agreed, 2026-10-15 |
| Integration | Separate local Python watcher calling installed `hpc-job` | A protected `hpc-watch` or `hpc-job watch` requires manual local promotion | Proposed |
| Polling | 60 seconds during startup, 120 seconds normally, 300 seconds for a stable pending queue | Fixed cadence is simpler but less responsive or more costly | Proposed |
| Log coverage | Controller periodically; selected child logs on trouble | Continuous all-child log collection increases connections and I/O | Proposed |
| Transport problems | Back off locally; return after three consecutive unavailable observations or ten minutes without a usable status, whichever occurs first | First-error handoff is faster but involves Codex for transient problems | Proposed |
| Local evidence | Append observations/events; atomically replace a small resume state | Only storing the latest snapshot loses diagnostic history | Proposed |

The separate watcher is ordinary orchestration, not a new security boundary.
Its command execution must still respect sandbox/network approval. Permissions
for a helper prefix do not automatically establish approval for a wrapper's
execution context. Do not solve this by broadly allowing Python or a shell.
If the actual environment requires a protected entry point, prepare that narrow
local candidate and promotion handoff instead; the remote backend stays intact.

## Two separate check intervals

The watcher checks HPC frequently. Codex checks the watcher much less often.
These are separate settings:

| Setting | Proposed value | What happens at this interval |
| --- | --- | --- |
| Watcher HPC check interval | 60 seconds during startup, 120 seconds normally, 300 seconds for a stable pending queue | The watcher calls a protected helper and saves the reply; Codex does not interpret each reply |
| `codex_check_interval_sec` | 1800 seconds, configurable | Codex checks whether the watcher is running or has exited, reads its latest status and compact report, and decides whether to continue |

The thirty-minute Codex check also supplies the agreed routine chat update;
there is no separate thirty-minute timer for that update. Failures, persistent
loss of HPC contact, and terminal job states should bring Codex back earlier
when the Codex tools support returning as soon as the watcher exits.

`codex_check_interval_sec` is a proposed setting of this monitoring workflow,
not a claim that Codex already has a built-in automatic wake-up setting. The
watcher can prepare a report after this interval, but a Codex tool must also
support waiting until then, or returning earlier when the watcher exits.
Writing a setting into watcher state cannot by itself wake Codex.

## First check: can Codex wait without repeatedly checking the watcher?

By starting or waiting for a program, this plan means starting or waiting for
the **watcher**. The intended sequence is:

1. Codex starts the watcher through a Codex tool.
2. The watcher checks HPC and saves observations using ordinary Python code.
3. Codex next checks the watcher's status/output after the configured Codex
   check interval, or earlier when the watcher reports a problem or completion.
4. Codex reads the short report, updates the user, and resumes monitoring when
   appropriate within the requested overall monitoring deadline.

We need to verify step 3. The available Codex tools can return a running
watcher's session ID and require another Codex tool call to read its output.
If Codex has to make those calls frequently, repeated Codex work still costs
tokens even while the watcher itself is doing all HPC checks in Python.

Official OpenAI documentation describes the `exec_command` and `write_stdin`
Codex tools. It does not establish that this interface can wait thirty minutes
without involving Codex, or notify Codex immediately when the watcher exits.
See the [Codex Prompting Guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide).
The requested timing remains something to verify in this environment.

Before implementing the complete watcher:

1. Use a harmless local fake watcher to test delayed output, completion,
   interruption, and how long the Codex tools can wait. Do not use HPC or
   introduce Codex/API calls into the watcher.
2. Count how often Codex actually resumes and reads watcher status/output,
   including checks forced by Codex tool time limits. Record the requested
   Codex check interval and the actual interval separately.
3. Prefer supported Codex tools that wait until the next planned Codex check
   or the watcher exits, with any intermediate waiting done in ordinary code.
4. If Codex tool limits require more frequent Codex checks, report the actual
   frequency and achievable savings, then revisit the integration choice.
   A watcher running in a separate terminal remains useful, but does not by
   itself provide automatic chat updates.

No detached process is assumed to wake a finished chat, survive host sleep, or
deliver a notification. Such capabilities require separate evidence/design.
Do not declare end-to-end H1 complete while this check remains unresolved.

## Proposed invocation and process behavior

Illustrative interface, subject to the integration decision:

```text
python3 dev_scratch/hpc/watch_run.py RUN_ID --codex-check-sec 1800
python3 dev_scratch/hpc/watch_run.py RUN_ID --codex-check-sec 1800 --resume
```

`--codex-check-sec` sets `codex_check_interval_sec` for the workflow; the
watcher and the Codex tool waiting for it must use the same agreed interval.
The proposed default is 1800 seconds. It is separate from the watcher's HPC
check interval and from the user's overall monitoring deadline.

One invocation owns one foreground watcher session. It returns one compact
report at a checkpoint, an attention event, observed terminal states,
interruption, or a local error. Checkpoint returns can be resumed within the
user's requested monitoring scope without a new permission conversation.
An overall monitoring deadline, if specified by the user, must persist across
resumes; thirty-minute checkpoints must not silently extend it.

The Codex check interval bounds one watcher session, including helper work.
At the next planned Codex check, stop launching helper calls,
terminate an unfinished local read operation if needed,
save partial evidence, and report a checkpoint/deadline rather than success.
Use monotonic time within a process and UTC timestamps for saved observations.
On resume, account for elapsed wall time and host sleep; never run catch-up
polls in a burst. An expired overall deadline requires a new explicit extension.

The backend path is fixed to `/opt/a1-hpc/bin/hpc-job`. Invoke it with argument
lists and no shell, using only `status`, `log`, and selected `--child` arguments
in the recommended monitoring-only version. Do not accept command, host, or
remote-path overrides. Validate run/child identifiers and returned run identity.

## Polling and reporting policy

| Situation | Watcher behavior | Codex/chat handoff |
| --- | --- | --- |
| Initial observation | Save identity, controller state, child states, and baseline | Startup information can be surfaced by the caller; no extra return needed |
| Startup, first five minutes | Poll at 60 seconds | Ordinary transitions accumulate locally |
| Normal active run | Poll at 120 seconds | Checkpoint unless attention arises |
| Entire observed tree pending and unchanged for ten minutes | Poll at 300 seconds; return to normal cadence on change | Checkpoint |
| Child starts or completes normally | Record event and update counts | Include grouped changes at checkpoint |
| Newly observed failed, timed-out, cancelled, OOM, or abnormal job | Save status; attempt bounded relevant logs | Return attention promptly |
| Controller exits while known children remain active | Save both facts and selected controller logs | Return attention; children are still active |
| Controller active, all currently known children terminal | Continue waiting; record the condition | Checkpoint; do not infer a hang or complete child coverage |
| Controller and all known children terminal | Save final scheduler observation and bounded controller logs | Return `scheduler-terminal`; result verification remains pending |
| Transport/helper response unavailable | Preserve last good observation as stale, store failure, retry with backoff | Return if persistence threshold or deadline is reached |
| Partial status or accounting gap | Keep unknown jobs explicit and respect bounded retry hints | Return if unresolved for the same persistence threshold |
| Identity mismatch, rejected operation, malformed local state, or disk failure | Stop monitoring with evidence | Immediate attention/local-error handoff |

Cadences are minimum gaps after a completed call; calls never overlap and slow
calls never cause immediate catch-up work. Proposed unavailable retry gaps are
60, 120, 240, then at most 300 seconds. Do not retry rejected input or a known
local installation/audit failure as if it were a transport outage.

Classify the exact scheduler state and exit code as well as its normalized
label. Unknown or unsupported state tokens are not completion. The first
observation must also catch jobs that were already abnormal when watching
started. A missing previously observed child remains a coverage problem even
if the rest of the reply looks complete.

There are two kinds of saved event: routine transitions and events requiring
attention. A deliberate resume after an attention return records that handoff
as acknowledged; an unchanged already reported failure should not create a
tight return/resume loop. A new failed child, worsening uncertainty, identity
change, or new terminal evidence still triggers a new handoff. Resume always
performs a fresh status call; saved state is not authoritative HPC evidence.

## Logs and local evidence

Read the controller on the first cycle, approximately every five minutes,
and before an attention/terminal handoff when time remains. During a cycle,
attempt at most one controller read and two selected child reads. Select
children by their validated keys from observed status. Reuse the helper's
per-stream byte/line limits and cursors.

Do not read all child pages every poll. If a bounded read reports backlog,
save `more_available` and return the fact in diagnostics; do not drain an
arbitrarily large backlog before reporting an urgent event. Literal warnings
and tracebacks may be included as evidence, but broad text matching must not
declare simulation failure or success. General log-based failure detection
and hang heuristics are deferred from the first version.

Proposed ignored storage, using the existing ignored `exp_results_local/`:

```text
exp_results_local/hpc_codex/RUN_ID/watch/
  watch.lock
  state.json
  observations-0001.jsonl
  events.jsonl
  report.json
```

Each observation records a sequence, command operation/selected child, UTC
start/end times, elapsed duration, return code, complete bounded stdout/stderr,
and parsed payload or parse error. Persist before computing events and
updating the small state. Keep scheduler data separate from helper-call
success: `status: ok` does not mean the simulation succeeded.

State includes schema version, run ID, bound commit/controller ID, observed
child identities, last good evidence, current uncertainty, pending/reportable
events, retry state, last report sequence, session times, the Codex check
interval/next planned Codex check, and any overall deadline. Also save the
watcher's last local update time and current operation before/after helper
calls and before sleeps, so Codex can distinguish a recent update from stale
watcher state. Atomically write state/report files and use one local per-run lock.
Store only monitoring data, never helper configuration credentials.

Each Codex check starts with the watcher itself: is its local process still
running, has it exited, and what status/output did it leave? Then read the
latest watcher update time, latest successful HPC observation time, report
reason, and any error. A running watcher does not prove HPC is reachable;
an exited watcher does not prove the HPC run completed. Read only the compact
report and necessary diagnostics unless further investigation is needed.

Rotate observations into 16 MiB segments with a proposed 256 MiB total local
watch budget per run. Preserve evidence rather than deleting old segments
silently; return `local-storage-limit` when the budget is reached. Bound each
captured helper stream to the installed response limit plus small diagnostic
headroom; stop an oversized local subprocess capture while saving that fact.

Coordinate other log readers during an active watch. The watcher lock cannot
exclude an independent direct helper invocation. A crash after a helper has
advanced its cursor but before local persistence can lose that chunk from the
watch history; record this limitation and interrupted calls explicitly. H1
does not promise exactly-once collection or repair the protected cursor API.

## Report contract

Return a compact JSON report, with optional concise human formatting. Separate
the reason the watcher returned from the observed scheduler condition.

Suggested reasons: `checkpoint`, `attention`, `scheduler-terminal`,
`monitoring-unavailable`, `deadline`, `interrupted`, and `local-error`.
No report uses unverified `run-complete` or treats monitoring timeout as Slurm
timeout. A successful checkpoint exit means the watcher operated successfully,
not that the run finished.

Include run/commit/controller identity, elapsed watch time, observation age,
controller state, child-only counts, number of observed children, coverage
limitations, grouped changes since the previous report, up to three attention
items, and paths/sequences for full local evidence. Explicitly state that
expected child coverage and output verification are not established by status.
Cap each report at 8 KiB, including excerpts; give omitted-item counts rather
than dropping important uncertainty silently. Define exit codes alongside the
implementation, keeping attention, unknown monitoring, local failure, and
interruption distinguishable from a normal checkpoint.

## Implementation steps after decisions

1. With the three scope choices agreed, verify how the Codex tools wait for
   the watcher and settle the remaining integration/default proposals. Write down
   measured Codex tool behavior and the chosen way to start/wait for the watcher.
2. Add a small standard-library watcher module and thin CLI, preferably
   `dev_scratch/hpc/watch_run.py`, without modifying installed backend code.
   Separate helper invocation, deterministic state/event calculation, local
   persistence, and the wait loop. Inject helper responses, clock, and sleep
   in tests; avoid a generic workflow framework.
3. Implement identity/coverage validation, schedule/backoff, resume/deadline
   behavior, local locking, bounded output/storage, and the report contract.
4. Add incremental controller reads and bounded child diagnostics. Keep
   reporting possible when diagnostic log reads fail or time runs out.
5. Add focused behavior tests in `tests/test_hpc_watch.py`. Review the diff and
   run the relevant existing HPC status/log tests if shared code is touched.
6. Document commands, continuation policy, interruption/recovery, evidence
   paths, and the measured reduction in Codex checks. Update the H1 backlog entry
   to reflect the agreed scope and actual implementation status.
7. Perform a small read-only check against an existing completed run through
   installed helpers. If a protected local watcher was selected, first
   prepare/review source hashes and installation instructions, let the user
   manually promote it, then test only the installed entry point.

No new scientific jobs, HPC checkout update, cancellation, finalization,
release, or archive download are required for the recommended acceptance check.

## Verification and acceptance

| Test scenario | Required result |
| --- | --- |
| Many identical valid polls | Local history grows; no routine return before checkpoint; report stays bounded |
| Normal child transitions and growing index | Correct grouped changes and child-only counts; no false completion |
| Controller completed with zero/partial children | Terminal handoff explicitly leaves expected coverage and results unverified |
| Controller exited with active children | Attention reports live children; no mutations |
| Initial or newly observed failure, including nonzero exit evidence | Prompt attention with bounded diagnostics |
| One unavailable call followed by recovery | Stale interval saved, last good state retained, normal polling resumes |
| Repeated unavailable/partial/accounting-gap observations | Bounded backoff then explicit unknown handoff |
| Dropped child, changed run/commit/job identity, malformed response | No successful completion inference; appropriate attention/error |
| Rejected request or local audit/configuration failure | No blind retry loop |
| Log backlog, truncation/rotation, missing log, cursor contention | Existing helper semantics preserved; diagnostics cannot block handoff indefinitely |
| Checkpoint/resume and known previously reported failure | Fresh status, preserved deadline/event history, no tight duplicate report loop |
| Interrupt during sleep or helper call; host sleep | Clean local stop/recovery; no catch-up burst or job cancellation |
| Two watchers for one run, corrupt state, disk full, oversized output | Explicit bounded local failure; evidence not silently discarded |
| Read-only completed-run integration | Correct identities and terminal handoff; no claim of verified output completeness |
| Configurable Codex check interval | HPC polling remains separate; planned Codex checks and watcher reports follow the selected interval |
| Codex checks watcher status/output | Distinguish running/exited watcher, stale local updates, and stale HPC evidence |
| Real Codex tool waiting experiment | Count actual Codex checks, including any required earlier by Codex tool limits, and compare with the previous workflow |

Use fake time/responses for long waits and failure paths. Offline tests prove
the program's state machine; they do not prove live chat wake-up behavior.
Acceptance needs both correct monitoring behavior and fewer actual Codex
checks in the selected interface. Record limitations and distinguish live
checks from synthetic coverage in the final acceptance note.
