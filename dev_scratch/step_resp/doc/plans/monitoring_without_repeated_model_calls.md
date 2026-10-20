# H1: routine waiting without involving Codex for every HPC check

Origin/status: suggested by the assistant during the token-usage discussion;
not an approved implementation task. Discussion and detailed planning requested
on 2026-10-15. Bounded resumable watcher sessions, thirty-minute routine checkpoints,
and completion handoff to Codex are agreed; see the
[draft implementation plan](../../../hpc/local_watch_plan.md).
Proposed priority: P1 for recurring HPC work. This is a code improvement, not a
new scientific experiment.

## Problem and intended result

During the last batch, routine status polling repeatedly involved Codex
and its large conversation context. Slurm scheduler-query chunking limits scheduler
load, but does not solve that repeated Codex/context cost.

The intended deliverable is a deterministic local waiting loop that calls the
existing protected helpers, saves full observations locally, and exposes short
reports on important changes, errors, completion, or agreed checkpoints.
Incremental log reads would be used rather than repeatedly returning full logs.

## Implementation boundary

Area: local hpc-codex orchestration. A reviewed local wrapper or a watch action
in [hpc-job source](../../../hpc/helper_src/local/hpc-job) are possible integration
points; the interface/location is not decided. The loop itself needs new code;
the installed status/log/archive capabilities do not need to be rewritten.

The watcher will use bounded resumable sessions and a configurable interval
for Codex to check the watcher's status/output, defaulting to thirty minutes.
That Codex check also supplies the routine chat update. The watcher's own HPC
checks run more frequently through the helpers. Result verification/finalization
is handed back to Codex.

The design still needs agreed polling intervals, detailed stop/timeout behavior,
and a verified way for Codex tools to wait without involving Codex for every
unchanged HPC check. Unknown/partial status must remain visible. A lost connection
must not imply success, cancellation, or an automatic resubmission.

## Verification if selected

Fake helper responses and an injectable clock can test unchanged state,
transitions, failures, interrupted waits, temporary transport problems, and
bounded reports without waiting for long real simulations. A small installed
integration check would follow normal review/promotion rules if protected code
changes. No new scientific batch is needed to establish the loop's behavior.

Dependency: existing [helper behavior and acceptance](../../../hpc/monitor_archive_testing.md),
not H2/H3's larger-batch refactor. K1's model-construction repair is independent.
The completed figure collection and scientific results do not depend on H1.
