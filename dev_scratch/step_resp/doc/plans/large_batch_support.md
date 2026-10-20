# H2 / H3: remaining work for much larger HPC batches

Origin/status: the user requested a plan for large batches, then postponed the
broad refactor. Later requests implemented chunked scheduler queries, paged
logs, and compact archives. The remaining work below is still deferred, not
an approved implementation or permission to raise submission limits.

Proposed priority: P3 for the present project; necessary before claiming
end-to-end support for hundreds/thousands of jobs, not before another batch
within the current verified limits.

## Existing baseline — already complete

The installed system supports the tested 60-child batch with concurrency ten.
Scheduler status accepts at most 100 total IDs; accounting queries are chunked
at 25 IDs. Logs have bounded pages/cursors, and compact results can be archived,
transferred once, verified, and unpacked locally. These are not open tasks.

[Installed behavior and remaining bounds](../../../hpc/helper_src/INSTALL_MONITOR_ARCHIVE.md#bounds-and-remaining-work),
[60/10 policy](../../../hpc/helper_src/INSTALL_BATCH_60_CONCURRENCY_10.md),
[acceptance evidence](../../../hpc/monitor_archive_testing.md).

## H2 — smaller status replies and less repeated accounting work

Area: hpc-codex helper code. Relevant sources are
[hpc-grid-status](../../../hpc/helper_src/remote_grid/hpc-grid-status),
[hpc-lethe-job](../../../hpc/helper_src/remote_lethe/hpc-lethe-job), and
[local hpc-job](../../../hpc/helper_src/local/hpc-job).

The remaining design would separate state counts/changes from full child
records, expose bounded detail pages, and cache confirmed terminal states for
routine monitoring. Failures, unknown states, incomplete observations, and
timestamps must stay explicit. Finalization still needs complete authoritative
evidence, not an old cached success or truncated response.

Acceptance would include synthetic mixed-state trees, accounting delays,
partial failures, page coverage, transport/output limits, and finalization
rejecting incomplete evidence. No large simulation batch is needed for these
scaling tests. The exact cache and pagination interfaces are not finalized.

## H3 — scalable job index and completion contract

Area: repository job-management code plus protected helper readers/writers.
This is infrastructure, not a change to scientific network behavior.
Relevant repository modules are [hpc_batch_jobs.py](../../../../hpc_batch_jobs.py),
[hpc_job.py](../../../../hpc_job.py), and
[hpc_job_lifecycle.py](../../../../hpc_job_lifecycle.py).

The remaining design would avoid a whole-tree index and an expanding request
list containing every output file. A bounded index/manifest representation
must preserve run ownership, unique job identity, exact output verification,
and recoverable lifecycle records. Cancellation, preparation, finalization,
transport deadlines, and byte limits need a joint audit.

Acceptance would demonstrate synthetic 1000/10000-job record handling and
explicit failure for missing, duplicate, malformed, or oversized evidence.
Raising a policy cap alone is not this deliverable.

## Dependencies and boundaries

H2 and H3 can be designed separately, but both must work across the entire
helper chain before very large batches are advertised. Protected changes and
limit promotions still require the established user-run Gate-B process.
[The original refactor](../../../hpc/status_scaling_refactor_plan.md#proposed-design)
contains the broader design; its old settings are historical, not current limits.

Neither item is required for the [local waiting-loop proposal](monitoring_without_repeated_model_calls.md).
Neither requires a new model experiment, a baseline change, or new fitting.
