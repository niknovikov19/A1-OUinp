# Large-batch status and lifecycle refactor

Status update: the user subsequently requested implementation of chunked
monitoring and result archiving. The first bounded implementation is complete
as candidate code; [its installation note](helper_src/INSTALL_MONITOR_ARCHIVE.md)
defines behavior, remaining limits, tests, and pending Gate-B promotion.
The original broader refactor below remains a historical/future design:
terminal caching, paginated status summaries, and thousand-job lifecycle
support are not implemented. The 60-child submission policy is unchanged.

Original status: refactor postponed, recorded on 2026-10-14. The temporary policy below
was promoted through Gate B and verified. This document does not authorize
larger submissions.

## Problem

A scientific batch can contain thousands of jobs while running only a few
concurrently. Status-query size, total batch size, and concurrency must be
independent concepts.

Currently `hpc-job status` and finalization collect the controller and every
recorded child ID, then pass that complete list to `hpc-grid-status` in one
request. The installed status policy accepts at most eleven IDs. It was sized
for the former ten-child pilot ceiling. Raising the submission ceiling to
twelve children left this independent status ceiling unchanged; thirteen IDs
are rejected before either scheduler command is executed.

The initial thirteen-ID pilot workaround has been superseded by the
[100-ID / 30-second Gate-B promotion](helper_src/promotion/install_status_limits.md).
Its installation passed and was verified against the expected policy hash.
This is not the large-batch design.

## Existing command sequence and bounds

For one accepted status invocation:

1. Validate the requested list of unique positive job IDs against
   `scheduler.max_job_ids`.
2. Run `squeue` once, scoped to the configured user. The current command lists
   all that user's active jobs and filters to requested IDs locally.
3. If requested IDs are missing from `squeue`, run `sacct` once with all those
   missing IDs in a single `--jobs` argument. Use allocation-only output and
   the configured accounting lookback.
4. Return one normalized record per requested ID, including explicit unknown
   records for missing accounting evidence.

The ID limit bounds accepted IDs, the accounting-query ID list, and the
returned record count. It does not bound raw `squeue` rows, query frequency,
concurrency, or simulation resources. There is no command per individual job
and no deliberate delay between scheduler commands.

Relevant existing bounds are separate:

| Layer | Existing bound | Scaling consequence |
| --- | --- | --- |
| Grid status policy | 100 IDs after promotion; validator permits up to 1000 | Whole job trees are rejected when their list exceeds the policy |
| Scheduler command | 30 s after promotion | A timeout is not a polling interval |
| Accounting lookup | 168-hour lookback | Very old jobs may lack visible evidence; this is not evidence of success |
| Raw scheduler stdout/stderr | 128 KiB per stream | Even a small request can fail if user-wide `squeue` output is large |
| Grid-to-Lethe and local job JSON | 1 MiB stdout at each job-helper hop | Verbose per-child status can exceed this even when raw scheduler output fits |
| Child index | 64 KiB total; 4 KiB per JSONL line | Total supported children depends on actual record lengths |
| Request completion list | 64 files | Four files per child plus one index currently allow at most fifteen children by this bound alone |
| Lifecycle state records | 64 KiB per record | Large preparation/finalization records need an audit too |
| Submission/concurrency policy | Twelve children; five concurrent | Independent authority/resource policy, not a scheduler-query setting |

The output-size checks currently run after subprocess output is captured.
They bound accepted output, not peak capture memory. The configuration's
1000-ID validation ceiling is also not a guarantee that every helper layer
supports a thousand-job batch.

## Proposed design

### Scheduler inspection

- Resolve job IDs only from the approved run's recorded controller and child
  receipts; do not broaden the helpers to arbitrary shell commands or targets.
- Keep one status observation of active jobs per poll. Prefer a user- and
  requested-ID-scoped `squeue` query where the deployment supports a suitably
  sized request; otherwise handle user-wide output explicitly without silently
  truncating it. If active-job requests must be chunked, document that cost.
- Query IDs missing from the active-job observation through `sacct` in
  configurable chunks. Start by testing 100 IDs per chunk rather than using
  the batch-size ceiling as the chunk size.
- With one active-job query and M missing IDs, the usual accounting command
  count becomes `ceil(M / chunk_size)`, not M individual commands.
- Retain per-command timeouts and introduce an explicit overall observation
  budget; a thousands-job poll must not inherit an inadequate small-pilot
  deadline.
- Capture output with a real byte limit or bounded streaming reader. Report
  oversize output explicitly; never truncate it and report incomplete data as
  complete.

### Results, polling, and consistency

- Separate the full internal observation from the normal user-facing summary:
  state counts, changed jobs, failures, and observation completeness.
- Provide paginated per-child detail with stable run-bound cursors. Output
  pages must remain bounded regardless of total batch size.
- Record observation timestamps and per-chunk failures. Several scheduler
  calls do not form an atomic snapshot; jobs may change state between calls.
- Preserve explicit unknown/accounting-delay states. Retry transient reads
  with bounded backoff; never infer completion or resubmit from a timeout.
- Cache confirmed terminal states for monitoring where appropriate. Before
  finalization, require complete authoritative evidence for every recorded
  job and the controller; use the same observation logic as status.
- Use one polling cadence per run rather than a separate scheduler poll per
  child. Do not repeatedly scan static result folders to infer job state.

### Other large-batch lifecycle dependencies

- Replace whole-index size assumptions with bounded record reading and a
  scalable index/page representation. Retain unique IDs and run ownership
  checks across pages.
- Replace the expanding per-file request completion list with a compact,
  validated output contract or manifest. Verify all required artifacts
  without loading an unbounded record into memory.
- Audit prepared/final records, cancellation-tree handling, helper transport
  limits, request schemas, and nesting of operation deadlines. Do not declare
  thousand-job support from status-query changes alone.
- Keep total-job authorization, concurrency, and per-job resources explicit
  and independently reviewed. Raising a read-only query limit must not raise
  submission or cancellation authority.

## Tests and rollout

1. Use fixtures for 1, 13, 1000, and 10000 jobs, with mixed active, completed,
   failed, cancelled, and temporarily missing states.
2. Verify chunk boundaries, command counts, unique coverage, ordering, and
   pagination. Include a user-wide active-job list larger than the requested
   set and long scheduler reasons.
3. Exercise partial chunk failure, malformed/oversized output, accounting
   delays, jobs changing state between queries, and overall-budget expiry.
4. Verify that finalization rejects incomplete evidence and that all record,
   manifest, and transport layers support the intended scale.
5. Keep large-scale tests synthetic; do not submit thousands of simulations
   just to test status plumbing.
6. Review source and policy changes, promote through Gate B, then test the
   protected installed helpers against a small real run. Record installed
   hashes and retain unknown-state behavior.

## Temporary recommendation without the refactor

For the existing small-batch workflow, the ID/timeout changes were promoted,
the other guards were retained, and the polling cadence remains a caller
convention. These values are not a thousand-job support claim:

| Setting | Recommendation | Reason |
| --- | --- | --- |
| `scheduler.max_job_ids` | 100, including controllers | Comfortable headroom without binding the status ceiling to every pilot-size change; accepted by the existing validator |
| `scheduler.query_timeout_sec` | 30 s per command | Allows more accounting latency; at most two commands mean up to 60 s of scheduler execution before transport overhead |
| `scheduler.accounting_lookback_hours` | Keep 168 | No evidence yet that a larger history is necessary for current pilots |
| Raw scheduler output bound | Keep 128 KiB per stream | Adequate candidate for small batches; fail explicitly and measure if exceeded |
| Job-helper response bound | Keep 1 MiB | No need to relax it for the current twelve-child run |
| Poll interval | About 60 s per run | Avoid repeated scheduler traffic; this is caller behavior, not currently a policy field |
| Total children / concurrency | Keep 12 / 5 | Query headroom does not authorize additional submissions or simultaneous simulations |

These are unbenchmarked temporary settings, not guarantees for every
job name, reason string, or response length. Before raising the actual batch
ceiling, measure index, request, final-record, and response sizes from a
representative run. Do not advertise hundreds or thousands of supported
children while those independent bounds remain unchanged.

Changing the ID and timeout settings requires only a reviewed remote-policy
promotion; no scheduler-query algorithm refactor is needed. The shared
`A1_OUinp-status.json` is consumed on Lethe and grid. The user reported PASS at
`/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/hpc-status-limits-promotion.XcoupK.txt`.
The verified installed SHA256 is
`28f59366c6c05c86c1fb7fbdc3be143293c27fde67c624ced54f66bf20deee7c`.
Whole-tree status and finalization subsequently passed for the twelve-child
connected pilot. No refactor was implemented.

## Code references

- [`hpc-grid-status`](helper_src/remote_grid/hpc-grid-status): request
  validation, scheduler commands, output checks, and normalization.
- [`hpc-lethe-job`](helper_src/remote_lethe/hpc-lethe-job): whole-tree status,
  child-index reading, transport handling, and finalization.
- [`hpc-job`](helper_src/local/hpc-job): local transport deadline and response
  handling.
- [`hpc_job.py`](../../hpc_job.py) and
  [`hpc_job_lifecycle.py`](../../hpc_job_lifecycle.py): request and lifecycle
  record contracts.
- [`remote-hpc-status.json.example`](helper_src/config_examples/remote-hpc-status.json.example):
  reviewable policy example with 100 IDs and a 30-second query timeout;
  installation was confirmed after the Gate-B promotion.
