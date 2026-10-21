# Review findings

## Scope and initial evidence — 2026-10-20

- Read the original HPC workflow, capability-gate work plan, B0 integration plan,
  current helper/promotion layout, and HPC test inventory. The original boundary
  separates protected infrastructure from repository scientific adapters and
  forbids importing repository Python during protected preparation on lethe.
- The proposed plan must therefore be resolved in scheduled repository code, or
  through an explicitly designed preflight handoff; generic protected helpers
  should consume bounded declarative data rather than interpret `exp_cfg.py`.
- The initial gate plan and B0 documents are historical design/test evidence,
  not a guarantee that every behavior proposed there is currently implemented.
  Assess current source and tests separately.

## Current contract and regression gaps

- `grid_search_slurm_local.py` resolves child outputs only after `sbatch`
  returns, then records IDs/parameters/outputs. A complete pre-submission plan
  would also move contract/filename validation before that mutation.
- Its dispatcher accepts the normal BatchTools message before checking output
  files. File presence is a fallback, and does not certify closed/valid results
  or a terminal Slurm allocation.
- `build_final_record()` checks only the controller's terminal scheduler state,
  requested file presence, submitted child count, and whether child outputs were
  listed in the overall request. `validate_final_record()` omits that last
  condition, producing the observed inconsistency. Neither function receives a
  complete planned child set or per-child scheduler observations.
- Prepared `simulation_job_limit` comes from the requested maximum, but current
  completion compares submitted count against that maximum as though it were
  the exact planned count. A new contract must separate cap, planned count,
  submitted attempts, and active concurrency.
- Existing test `test_invalid_child_output_declaration_finalizes_as_failed`
  uses `CANCELLED`, checks only construction, and does not round-trip through
  validation/release. It misses the actual `COMPLETED` + all request files
  present + undeclared child outputs failure. Shared verdict evidence and
  builder/validator/release round-trip tests are required.
- Status, cancellation, child logs, selective inventories, and compact archives
  all depend on the current child-index/output contract. This is a cross-cutting
  lifecycle change, even with unchanged SSH hops and Slurm binaries.
- Portability dependencies exist inside protected preparation and validation,
  not just in the scientific launcher: `exp_configs`, `workflow_configs`,
  `hpc_jobs`, `exp_results`, exact per-target result layouts, fixed `A1_OUinp`
  config basenames, artifact suffix/type assumptions, and the compact archive
  directory profile. The request/prepared/schema boundaries need versioning.

## Assessment prepared

- Wrote `assessment.md` with proposed ownership, full-plan versus submission
  evidence, main-independent scientific outcomes, release safety, publication
  integrity, submission uncertainty, stable BatchTools mapping, partial-result
  access, migration, and core/backend/project adapter separation.
- Mapped affected source modules and Gate A0–A6/B0–B5 re-testing. Existing parser,
  transport and bounded stream behavior can largely be retained; lifecycle and
  Gate B acceptance need substantial repetition. A static AST inventory counted
  119 methods in 14 `tests/test_hpc*.py` files; no tests were executed in this review.
- The proposed initial live acceptance programme is six small controlled batch
  scenarios, a legacy single-job smoke and a tiny NetPyNE batch; this is a test
  budget estimate, not approval or an actual job request. Most failure/large-plan
  combinations should be fixtures.
- Explicitly separated the existing version-1 recovery from a future contract
  migration. Full-plan creation alone cannot reconcile an accepted submission
  without a receipt, prove file validity, or permit release while children are
  still running. No helper installation, remote command, simulation or code
  mutation was performed during this review.

## Terminology and grammar revised — 2026-10-20

- Rewrote `assessment.md` using defined names for local commands, lethe/grid
  helpers, the batch main, simulation jobs, project code, and each data record.
  Each program's definition identifies its machine and who calls it.
- Replaced overlapping terms and compressed phrases with explicit actors and
  actions. Added the proposed sequence from local preparation to release, and
  stated that no persistent local monitoring process is implied.
- Reduced the assessment from approximately 5100 to 2700 words while retaining
  the change scope, failure cases, portability requirements, and Gate A/B tests.
  Checked local links and whitespace. Changed documentation only; left the four
  previously staged pilot files untouched.

## Clarified the status of local monitoring — 2026-10-20

- Checked the local watcher plan and installed `hpc-job`. We agreed on separating
  repeated checks from Codex, but the watcher remains unimplemented. Installed
  status/log commands perform individual operations; they do not run a watch loop.
- Added the proposed local watcher to the terminology table and linked its plan.
  Distinguished its local Python process from Codex and from remote helpers.

## Assessed whether to combine the changes — 2026-10-20

- Recommend one installation and Gate A/B campaign for ownership changes and
  removal of A1-specific assumptions; package extraction can follow separately.
- A local watcher can use the revised status/log commands without changing
  batch execution or remote helpers specifically for monitoring. Its additional
  tests are mainly local; existing B3/B4 jobs can also exercise its live reports.
- The remaining uncertainties concern Codex waiting, shared log cursors, and
  whether the local environment needs an installed watcher entry point. None
  requires a new scientific cohort to investigate. No code or jobs changed.
