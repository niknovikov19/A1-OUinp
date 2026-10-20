# K1 / E1: reproducible model construction and its repeat test

Status: the user explicitly deferred the fix. No core/companion code changes
or repeat simulations are authorized by this plan. Proposed priority: P1,
because same-seed comparisons currently do not cancel stochastic variation.

## K1 — code investigation and repair

Area: model/network construction, not hpc-codex and not curve fitting.
The likely change is in the companion subnet builder; a repository adapter
may also need adjustment depending on the diagnosis. Editing the companion
repository requires separate permission.

The observed bug is different activity before the step, even for nominally
identical zero-input jobs with the same seed. The concrete suspected cause is
unstable frozen-population ordering from list(set(...)), affecting cell IDs
and random streams. This has not been proved to be the sole cause.

The bounded work, if resumed, would be:

1. Trace population order, cell IDs, and random-stream assignment in identical
   configurations; distinguish this construction effect from numerical variability.
2. Make the necessary ordering/stream assignment deterministic without changing
   calibrated rx, surrogate target rates, current corrections, or connectivity.
3. Add a construction-order regression test, then validate with E1 below.

A changed hash seed or one matching pair alone would not establish a general
fix. Existing datasets remain intact; repaired runs need new identities.

Evidence and original proposed verification:
[issue summary](../issues/same_seed_reproducibility.md) and
[detailed observations](../archive/same_seed_reproducibility_evidence.md).

## E1 — small identical-input repeat test

Origin/status: verification proposed during the bug discussion, deferred with
the repair. This is a test of K1, not another J–Q response experiment.

Existing structure is sufficient: the connected-step configuration supports
zero-input jobs and recorded seed/configuration metadata. No new stimulus or
experiment family is required. Repeated jobs would need distinct attempt/job
identities so completed files are never reused or overwritten.

The exact grid is not selected. A resumed investigation would specify whether
to compare before/after the code change, the seed/rank configuration, and the
comparison criterion. Useful checks are identical construction/GID/stream
metadata, zero-input activity, and pre-step treatment/control activity. Any
remaining non-identical output would be quantified rather than called a pass.

Dependency: E1 provides evidence for K1; it can include pre-fix diagnostic runs,
but cannot establish that a fix works without the corresponding changed-code
comparison. It does not require the larger-batch refactor. The existing
[connected-step interface](../contracts/connected_current_steps.md) supplies
the inputs and compact rate/count outputs.
