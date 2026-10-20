# Open work: code changes and experiment choices

This is a planning inventory, not an execution request. It includes unfinished
work and experiment suggestions; it does not turn either into an agreed task.
Each item has a linked description, implementation scope, and decision status.

Priorities are **proposed ordering**, not changes to the user's decisions:
P1 = highest practical/scientific value before more routine batches;
P2 = candidate for the next scientific question; P3 = can wait for expansion
or a demonstrated scaling need. A P1 item explicitly deferred by the user
remains deferred.

## Code changes

| ID | Work and description | Where changes belong | Decision status | Priority |
| --- | --- | --- | --- | --- |
| K1 | [Make same-seed model construction reproducible](simulation_reproducibility.md#k1--code-investigation-and-repair) | Model/network-construction code, likely companion subnet builder; not hpc-codex | Discussed bugfix; user explicitly deferred it. Companion-repo changes need approval | P1: scientific comparison quality |
| H1 | [Move routine waiting into ordinary code](monitoring_without_repeated_model_calls.md) | Local hpc-codex orchestration; existing status/log helpers remain the backend | Detailed planning started; bounded resume, 30-minute checkpoints, and completion handoff agreed; implementation not yet approved | P1: reduce recurring monitoring cost |
| H2 | [Return compact status summaries and avoid repeated finished-job queries](large_batch_support.md#h2--smaller-status-replies-and-less-repeated-accounting-work) | Protected HPC helpers and local transport | Remaining part of the discussed/postponed large-batch refactor | P3: when current limits become restrictive |
| H3 | [Make job lists and result verification work beyond current batch limits](large_batch_support.md#h3--scalable-job-index-and-completion-contract) | Repository job-management modules plus protected helper readers/writers | Remaining part of the discussed/postponed large-batch refactor | P3: before hundreds/thousands of jobs |

K1 is a simulation-core concern. H3 changes repository infrastructure, not the
scientific model. H1/H2/H3 do not authorize changes to helper permissions or
submission caps; protected installation still uses the agreed promotion process.

## Tests and experiment candidates

These are different kinds of work. Most reuse existing simulation features;
their configuration, job requests, and any small comparison additions still
need review. No next scientific grid has been selected.

| ID | Question/test and description | Implementation needed | Origin / decision status | Priority |
| --- | --- | --- | --- | --- |
| E1 | [Do identical-input jobs now reproduce the same activity?](simulation_reproducibility.md#e1--small-identical-input-repeat-test) | Existing zero-input experiment; controlled repeat identities and comparisons, coupled to K1 | Proposed verification during the bug discussion; deferred with the fix | P1 when K1 resumes |
| E2 | [Target the negative IT2→PV2 prediction mismatch](experiment_candidates.md#e2--targeted-follow-up-of-the-negative-it2pv2-discrepancy) | Existing amplitude/timing settings and analysis; no new stimulus or fitter | New assistant suggestion from this review of the latest result; not an agreed experiment | P2 if explaining the mismatch is the next aim |
| E3 | [Probe SOM2, VIP2, and NGF2 input directions](experiment_candidates.md#e3--probe-the-remaining-individual-l2-input-populations) | Enable existing single-population groups and prepare a new grid; no new model feature | Remaining scope from the earlier connected-experiment proposal; not selected for execution | P3: broader validation |
| E4 | [Test combined inputs against individual responses](experiment_candidates.md#e4--simultaneous-inputs-test-response-addition) | Existing weighted groups; new settings/requests and possibly a measured-sum comparison table | Earlier optional superposition proposal; no combined-input protocol agreed | P3: after suitable component probes |

## Dependencies and choices

- **K1 and E1 belong together:** code diagnosis/repair needs a controlled repeat
  test. E1 may include a pre-fix diagnostic comparison; matching numeric seeds
  alone is not proof of repair.
- **H1 does not wait for H2/H3.** A local waiting loop can use the already
  installed bounded helpers. Reducing repeated Codex checks and supporting
  thousands of jobs are separate problems.
- **H2/H3 need an end-to-end check before very large batches.** Enlarging a
  status-query limit alone cannot remove request/index/finalization limits.
- **E2/E3/E4 are choices, not one mandatory sequence.** E4 can start with
  IT2/PV2 component probes; it need not wait for all E3 input directions.
  A claim of exact paired-noise cancellation does require K1/E1; descriptive
  experiments can retain the known limitation if explicitly chosen.

My proposed first decision is whether to resume K1/E1 and/or implement H1
before another batch. The next scientific question can then be chosen from
E2/E3/E4 or replaced by a different user-selected direction. This ordering
is a recommendation, not an inferred approval.

## Completed, stopped, and outside scope

These do not compete in the open queue:

| Work | State and evidence |
| --- | --- |
| Chunked scheduler queries, paged logs, compact archive handoff | [Implemented and acceptance-tested](../../../hpc/monitor_archive_testing.md); H2/H3 concern remaining scaling work |
| Sixty-child cap / concurrency ten | [Installed policy](../../../hpc/helper_src/INSTALL_BATCH_60_CONCURRENCY_10.md), not a proposal to raise it again |
| Longer connected measurement and five-seed/two-magnitude test | [Completed results](../results/connected_steps_5seeds_15_30pa.md); not an overdue experiment |
| Initial five-figure presentation collection | [Complete](../../data/slide_assets/jq_prediction/README.md); no extra slide tasks assumed |
| Improve J fits / replace provisional zeros | [Stopped by user decision](../contracts/static_prediction.md); not a low-priority task to resume automatically |
| Predict dynamic/oscillatory responses | [Outside current scope](../contracts/open_loop_identification.md); not in this backlog |
