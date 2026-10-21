# How a complete batch plan would change HPC-Codex

2026-10-20. This document proposes changes; it does not describe an implemented
replacement. This review changed documentation only.

Implementation update: the [narrow completion repair](../helper_src/INSTALL_COMPLETION_RECOVERY.md)
is installed and the pilot checkout was released. The
[local watcher](../watch_implementation/README.md) is now implemented separately.
The full batch-plan and portability changes below remain proposals. Descriptions
of the original list-mismatch failure refer to the implementation before that repair.

## Recommendation

Before submitting any simulations, the batch main should write a complete list
of planned simulations and their required output files. HPC-Codex should use that
list when it checks completion. The job request should no longer repeat those
filenames.

This requires a **medium-sized change across several scripts**. Most SSH and
Slurm operations can stay. Preparation, submission records, completion checks,
release, and result retrieval need coordinated changes. We should repeat most
Gate B tests and selected Gate A tests.

The immediate repair and pilot release are complete. They do not implement the
full batch-plan redesign proposed here.

## Terms identify programs, machines, and files

A **run** means one submission of a whole batch. A **simulation** means one
parameter combination within that batch. Slurm assigns separate job IDs to the
batch main and to each submitted simulation. Existing files sometimes call the
batch main the `controller` and a simulation job a `child`.

A **hash** is a calculated value that identifies a file's contents. The programs
compare hashes to detect whether they are using the same plan.

| Term used here | Concrete meaning | Where and when it runs |
|---|---|---|
| **Local commands** | Installed commands under `/opt/a1-hpc/bin/`, such as `hpc-job-prepare` and `hpc-job` | Codex or the user calls them on the local computer. They contact the lethe helpers. |
| **Lethe helpers** | Installed protected programs such as `hpc-lethe-prepare`, `hpc-lethe-job`, and `hpc-lethe-result` | They run on lethe when a local command calls them. They check records and files, contact grid helpers, and manage the checkout lock. |
| **Grid helpers** | Installed protected programs such as `hpc-grid-job` and `hpc-grid-status` | The lethe helpers call them on the grid login host, `lattice`. They submit or query Slurm jobs. |
| **Batch main** | `grid_search_slurm_local.py`, including its BatchTools submission code | It runs autonomously as a Slurm job on a compute node. It selects simulations, submits their jobs, and monitors their progress. |
| **Simulation job** | `run_exp.py` and the experiment code it calls | It runs autonomously as another Slurm job on compute nodes. It runs one simulation and writes scientific output files. |
| **Project code** | Python functions that interpret this repository's experiments: currently `hpc_preflight.py`, `exp_cfg.py`, `batch_params.py`, and related functions | Codex can call preflight locally. The batch main and simulation jobs execute the relevant functions on compute nodes. Lethe helpers must not import this code. |
| **Local watcher** | `hpc_watch.py`, started through `dev_scratch/hpc/watch_run.py`; it repeatedly calls installed status/log commands and saves observations | Codex or the user starts it on the local computer. It checks HPC without involving Codex in each check, then returns a report for Codex or the user to read. |

The local commands and remote helpers are separate programs. Calling a local
command currently performs one operation and exits; it does not start continuous
monitoring. The batch main and simulation jobs continue independently of Codex.

The [local watcher](../watch_implementation/README.md) implements the separation
described in the [watcher plan](../local_watch_plan.md). It periodically requests
Slurm status and selected logs through the existing local commands. It returns
a routine report after 30 minutes by default, or earlier on a problem or job
termination. Codex must wait for the process and read its report. Short waits
have been tested; actual 30-minute chat timing remains unmeasured. The watcher
runs as an ordinary local process, outside the AI model.

A **job request** is a JSON file, currently under `hpc_jobs/requests/`. It selects
an experiment, resources, limits, and output location. It is data, not a program
or a question asking the user for permission. The lethe preparation helper checks
it and saves a fixed copy for the run. Here, **preparation** means that operation.

**Release** means that the lethe job helper removes the run's active marker so
the automation checkout can be updated. Release does not mean that the scientific
results were successful.

## Why the current records caused the failure

Currently, two places list expected output files:

- The job request contains `completion_files`.
- After each successful simulation submission, the batch main calls
  the experiment's `get_batch_completion_files()` function in `exp_cfg.py` and
  writes the returned filenames, parameters,
  and Slurm job ID into `jobs/index.jsonl`.

The current index lists submitted simulations. It does not list all planned
simulations before submission begins.

When Codex calls `hpc-job finalize`, the lethe job helper checks the batch main's
Slurm state, checks the request-listed files, and reads the index. The helper's
`build_final_record()` function also checks whether the request included every
simulation's required files. It wrote `failed` for the pilot because those lists
differed. Later, `validate_final_record()` applied a different rule and rejected
that same record during release.

The batch main's own progress checks are separate. It accepts BatchTools completion
messages, with file existence as a fallback; it does not reread the index to decide
which simulations have finished.

## Proposed ownership and records

The following filenames and behavior are proposals.

| Record | Who writes it, and when? | What does it contain? |
|---|---|---|
| **Job request** | Codex or the user writes it locally before preparation. The lethe preparation helper saves its fixed copy. | The experiment selection, resources, approved roots, and maximum job count. It does not repeat simulation output filenames. |
| **Batch plan**, `plan.json` | The batch main writes it on the shared HPC filesystem before the first simulation submission. | Every planned simulation's stable ID, parameters, and required output filenames. This is the single definition of expected outputs. |
| **Submission records** | The batch main writes an intent before calling `sbatch`, then records the returned Slurm job ID after acceptance. | The simulation ID, submission attempt, plan hash, Slurm ID when known, and log paths. These records refer to the plan; they do not repeat output definitions. |
| **Simulation completion record** | The simulation job writes it after it has finished writing and checking its required outputs. | The simulation and attempt IDs, plan hash, and output checks. This record does not assert that the Slurm job has exited. |
| **Final record**, `final.json` | The lethe job helper writes it when Codex or the user calls finalize, after jobs have settled. | The plan identity, observed Slurm states, output checks, and the resulting batch status and reasons. |

The batch main should publish the plan by writing a temporary file and renaming
it. Once simulations can be submitted, nobody may add simulations to that plan
or change its output paths. A protected copy with the same hash is a copy of one
plan, not a separately maintained list.

Control records can remain under `hpc_jobs/runs/<run-id>` for A1. Configuration
should specify this location so another project can use a different directory.
Scientific results can keep their current locations.

### The programs would act in this order

1. **Codex works locally.** Project code resolves the parameters and filenames.
   When possible, it also generates a plan preview and calculates its hash.
2. **Codex calls preparation.** The lethe preparation helper saves the job request,
   Git commit, limits, and preview hash, if supplied. It reads data; it does not
   execute project Python.
3. **Codex calls submission.** The lethe and grid helpers submit the batch main.
4. **The batch main starts on a compute node.** It uses project code to create
   the complete plan. If preparation saved a preview hash, the batch main checks
   that its plan has the same hash. A mismatch stops submission.
5. **The batch main submits simulations.** It records each submission intent and
   returned Slurm ID. It enforces the existing submission and concurrency limits.
6. **Each simulation job writes its outputs.** It then writes its completion record.
7. **Codex or the user requests status, finalization, or release.** The lethe job
   helper reads the plan and records, asks grid helpers for Slurm states, and
   checks the relevant files. These operations must work even if the batch main
   has died. Release remains a separate explicit command.

If project code can resolve the plan only on HPC, step 1 cannot provide a preview
hash. We must then choose who accepts the plan: Codex or the user could review it
after a separate planning job finishes, or the job request could permit the batch
main to choose simulations within fixed limits. The second option does not
provide advance review of each simulation. This choice remains open.

## Consequences that the implementation must handle

| Situation | Required behavior |
|---|---|
| The request permits 60 simulations, but the plan contains 4. | Check completion against those 4 IDs. Keep the maximum, planned count, submission count, and concurrency separate. |
| The batch main dies after submitting 1 of 4 simulations. | Show 1 submitted and 3 unsubmitted. Keep the checkout locked while the submitted job is active or uncertain. |
| The batch main fails after submitting all simulations, which later succeed. | Allow scientific completion if every required output is valid. Preserve the main's failure separately. Any required batch-level summary must also exist. |
| The batch main hangs after simulations finish. | Keep the checkout locked until the main terminates. |
| Slurm accepts a simulation, but the main dies before saving its Slurm ID. | Use the saved submission intent and a unique scheduler-visible identity to find the job. Keep its state unknown if reconciliation fails; do not submit a duplicate automatically. |
| A file exists but is unfinished or belongs to an older run. | Reject it as completion evidence. Use fresh output locations and publish completed files safely. Project code checks scientific formats inside the simulation job. |
| Cancellation races with submission. | Stop the batch main, reconcile unfinished submission records, and account for every actual Slurm job. Planned but unsubmitted simulations have no Slurm IDs to cancel. |
| Some simulations succeed and others fail. | Consider allowing retrieval of individually verified outputs. This requires a new retrieval policy; current retrieval requires the whole run to be complete. |

Before release, the lethe job helper must establish that the main and every actual
simulation job have ended. It must also resolve uncertain submissions. If the
main dies before writing a plan, the helper must report that planning did not
finish rather than assume the batch contained zero simulations.

The functions that write and validate final records must use the same rules.
They should distinguish three decisions: whether scientific work succeeded,
whether the checkout can be released, and which outputs can be retrieved.

The batch main must also use the same simulation ordering when it builds the
plan and submits jobs. A separate Cartesian-product calculation could assign
BatchTools indices to the wrong parameters. Existing A1 filenames contain those
indices, so this mapping needs explicit tests.

Keep existing bounds initially: 60 submitted simulations, concurrency 10,
100 monitored Slurm IDs, 25 IDs per accounting query, 1 MiB for lifecycle/index
records, and 256 request-listed completion files. The new plan needs explicit
size limits too. Archives retain their 4096-file and 1 GiB limits. Routine status
checks should not scan every scientific output file.
This first change should not add automatic retries.

## How to keep HPC-Codex independent of this repository

Use **project code** for scientific decisions and **HPC helpers** for protected
operations. These names describe responsibilities, not additional machines or
background services. Earlier terms such as “adapter” meant project-specific
functions; “integration” meant changes to existing calling code.

| Keep in project code or project/site configuration | Keep in reusable HPC helpers |
|---|---|
| Read `exp_cfg.py`, `batch_params.py`, and `workflow_configs`; construct simulation parameters and filenames. | Read plans without knowing how parameters were calculated. |
| Configure result and control directories, project names, cache locations, and approved roots. | Enforce those roots, file limits, path checks, and project separation. |
| Set up NetPyNE, BatchTools, conda, compiled mechanisms, and site-specific Slurm options. | Submit approved scripts and query/cancel identified Slurm jobs. |
| Define required outputs, optional plots, and scientific checks. | Verify record identities and retrieve explicitly selected files safely. |

Specific dependencies to remove from reusable code include fixed `exp_results`
and `hpc_jobs` directory assumptions, `A1_OUinp` configuration names, inferred
repository roots such as `run_dir.parents[2]`, fixed archive subdirectories, and
selection rules that allow only one JSON output per simulation. Configuration
can preserve all current A1 paths while removing those assumptions from helpers.

Before extracting a package, test a second small project that uses the same
Slurm/BatchTools/NetPyNE tools but has no `exp_cfg.py`, `exp_configs`, or
`exp_results`. Its different layout should require project configuration and
project code, not changes to protected helpers.

A Git commit does not preserve ignored input files, installed Python packages,
or compiled mechanisms. Project code should record the relevant dependencies;
helpers should preserve that information without importing scientific packages
on lethe. The pilot's missing package showed why this matters.

## Which code and tests would change?

The main edits would affect `hpc_preflight.py`, `grid_search_slurm_local.py`,
`hpc_batch_jobs.py`, request validation in `hpc_job.py`, completion and release in
`hpc_job_lifecycle.py` and `hpc_job_control.py`, and the installed lethe helpers.
`hpc_result.py` and `hpc_archive.py` must read output definitions from the plan.
Grid helpers may need one bounded operation to reconcile missing submission IDs.

This is more than adding an index writer, but it does not require rewriting
NetPyNE, BatchTools, or SSH transport. Package extraction should follow separately.

The gate names below come from the [existing test plan](../prototype_work_plan.md).
These are proposed tests, not newly passed gates.

| Gate | What should we repeat or add? |
|---|---|
| A0: configuration and records | Test new formats, versions, limits, identities, and installed module hashes. |
| A1: connectivity | Retain existing topology results; run installed smoke checks and rejection tests. |
| A2: checkout updates | Repeat lock/release, idempotence, configured paths, and separation from the manual checkout. The previously deferred non-fast-forward test remains deferred. |
| A3: preparation | Repeat plan generation, hash agreement, parameter counts, dependency checks, limits, and rejection of altered plans. |
| A4: submission | Retain main-submission tests; add simulation intents, lost Slurm IDs, duplicate prevention, and reconciliation. |
| A5: status | Retain Slurm parsers/chunking; test complete plans with partial submissions, unknown jobs, and a dead main. |
| A6: logs | Retain bounded reads/cursors; test simulation lookup before and after submission. |
| B0: project support | Repeat preparation and directory checks; test the alternative project layout and manual execution. |
| B1: single simulation | Run a short real smoke test because shared helpers will change. |
| B2: batch submission | Prove the complete plan exists before the first simulation submission; verify parameter/ID mapping and concurrency. |
| B3: successful batch | Repeat four simulations with concurrency two, including finalization, retrieval, repeated commands, and release. |
| B4: failures | Add main death, partial submission, active simulations after main death, lost IDs, bad outputs, and cancellation races. |
| B5: results | Repeat file selection, cache identity, archive transfer, and path/size checks; test partial retrieval if we add it. |

Run the relevant local test suite, not just new tests. In particular, reproduce
the exact pilot failure and pass its record through writing, reading, validation,
and release. The existing malformed-output test checks construction only and uses
a cancelled main; it misses the observed failure. Also test torn or replaced
plans, duplicate IDs, incorrect output mappings, mixed versions, and all crash
points around submission. Use synthetic 60-simulation records to check limits.

A reasonable live test budget is six tiny batch scenarios: normal completion,
main death after one submission, main death after all submissions, a failed
simulation, a lost submission ID, and cancellation during submission. These
would use roughly 12–20 toy simulation jobs, plus one single-job smoke and one
tiny real NetPyNE batch. This estimates testing effort; no jobs were submitted
for this review. Queue delays and manual helper installation may dominate time.

## Should we include the local watcher in the same release?

Develop the ownership changes and removal of A1-specific assumptions together.
They affect many of the same records and helpers, so one coordinated installation
and Gate A/B test campaign should cover both. Extracting a separate package can
still follow later.

The watcher has a smaller effect on existing code. Add a separate local program
that calls `hpc-job --json status` and selected log operations. It should read
the revised status format without importing completion/release functions or
executing remote commands directly. No changes to the batch main, simulation
jobs, or remote helpers should be necessary specifically for the watcher.

Test its polling, saved state, resume, deadlines, failures, and bounded log reads
locally with fake helper replies and a simulated clock. Then check it against
one completed run and observe the success and failure batches already required
by B3/B4. Include a test that counts how often Codex actually resumes while the
watcher waits. The planned 30-minute interval remains unproven until that test.

These checks do not require repeating every Gate A/B test or submitting a separate
scientific cohort. If the watcher needs a protected installed entry point, include
that local program in the same reviewed installation; test its arguments,
permissions, identity, and use of existing commands. Remote installation should
not change specifically for the watcher. Coordinate log readers because the
current helper shares incremental log cursors.

Specify the new status format first, then build the watcher against it. Include
the watcher in the same release if its waiting mechanism works; keep its tests
separate so an unresolved local waiting issue does not block batch correctness.

## How to introduce the change

1. Repair the current final-record inconsistency and recover the existing run
   using reviewed, installed helpers. Preserve its original request and Slurm facts.
2. Define versioned request, plan, submission, and completion records. Keep old
   records readable; never treat the old submission-only index as a full plan.
   Choose one preparation interface instead of maintaining different meanings
   in the older preview catalogue and newer tracked requests.
3. Implement the fixed-batch path, run local tests, install reviewed helper
   versions together, and repeat the live tests above. Keep current resource
   limits and explicit release. A rollback must still read records already written.
4. Prove the alternative project layout, then extract reusable helpers into a
   separate package. Test installation paths and imports during that extraction.

Adaptive workflows need later plans for each stage or iteration; a fixed initial
plan cannot enumerate simulations whose parameters depend on future results.
Current workflow-related fields do not demonstrate a tested protected workflow.

## Sources

- [Batch main](../../../grid_search_slurm_local.py), [submission records](../../../hpc_batch_jobs.py), [project preflight](../../../hpc_preflight.py), and [job requests](../../../hpc_job.py).
- [Completion rules](../../../hpc_job_lifecycle.py), [file checks](../../../hpc_job_control.py), and [lethe job helper source](../helper_src/remote_lethe/hpc-lethe-job).
- [Result retrieval](../../../hpc_result.py) and [archives](../../../hpc_archive.py).
- [Gate plan](../prototype_work_plan.md), [recorded test results](../prototype_test_log.md), and [B0 responsibilities](../B0_IMPLEMENTATION_PLAN.md).
- [Helper installation rules](../helper_src/README.md), [previous checkout recovery](../helper_src/INSTALL_B2_FINALIZE_RECOVERY.md), and [installed monitoring/archive limits](../helper_src/INSTALL_MONITOR_ARCHIVE.md).
- [Review task](task.md) and [findings log](findings_log.md).
