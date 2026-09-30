# Codex-to-HPC automation strategy

## Purpose

This document proposes a practical first version of Codex-assisted HPC operation for the `netstim-bkg` branch of [`niknovikov19/A1-OUinp`](https://github.com/niknovikov19/A1-OUinp/tree/netstim-bkg).

The goal is to remove repetitive work around code synchronization, Slurm submission, monitoring, log inspection, and selective result inspection while respecting these constraints:

- Codex runs locally in WSL and does not run on lethe or grid.
- Codex must not obtain an interactive SSH session or execute arbitrary remote commands.
- The existing manual VS Code–lethe workflow must remain separate and unchanged.
- Only Slurm-related commands may run on grid.
- Lightweight file and log operations may run on lethe, but they must be limited.
- Simulation and other substantial computation must run as Slurm jobs on compute nodes.
- Codex may prepare code locally, commit it, and push it to GitHub.
- A controlled helper may update a separate HPC checkout and submit the committed code.
- Codex may inspect a small number of selected logs or results, but it must not freely walk large result trees.
- Submission, cancellation, resubmission, and bulk result transfer require human approval initially.

The first implementation should use small, fixed-purpose shell or Python commands. An MCP server, database, permanent service, special HPC account, or fully autonomous recovery system is not needed initially.

## Relevant repository structure

The current ordinary batch path is:

```text
submit_batch_slurm_local.sh
    -> grid_search_slurm_local.py
        -> BatchTools submits child Slurm jobs
            -> run_exp.py
                -> exp_results/<experiment>/...
```

At the inspected branch head, the important characteristics were:

- `submit_batch_slurm_local.sh` submits the BatchTools controller with 2 tasks, 16 GB, and a 24-hour limit.
- Its controller logs use fixed names: `batch_sl_1.out` and `batch_sl_1.err`.
- `grid_search_slurm_local.py` requests 60 cores and 256 GB per simulation, with a seven-hour limit and up to six concurrent simulations.
- The selected `net_2pulses_var_seed_f_amps_dt0` batch parameters produce `1 x 1 x 4 x 6 x 2 = 48` child jobs.
- `run_exp.py` puts ordinary results under `exp_results/<experiment>`.
- Result files, logs, pickles, and much of `exp_results` are intentionally ignored by Git.

These facts make a pre-submission job-count and resource summary essential. A few short parameter lists can multiply into many expensive simulations.

The newer `run_workflow.py` and `workflow_utils.py` already contain patterns that should be reused:

- unique workflow/run directories;
- immutable resolved run parameters;
- separate `batchtools/scripts`, `batchtools/logs`, `batchtools/comm`, `batchtools/summaries`, `job_meta`, `sim_results`, and `processed` directories;
- compact per-job completion records;
- validation that expected outputs really exist;
- preservation of BatchTools artifacts by attempt;
- treating valid durable outputs as more authoritative than some BatchTools communication errors.

The implementation should reuse these ideas instead of inventing an unrelated result-management system.

## Recommended high-level arrangement

```text
Local WSL repository
    Codex edits, tests, commits, and pushes
              |
              | fixed-purpose protected commands only
              v
Protected local HPC helpers
    hold workflow rules and use SSH internally
              |
              +--> lethe: update automation checkout, inspect bounded files
              |
              +--> grid: sbatch, squeue, sacct, limited scancel
              |
              v
Compute nodes
    run simulations, processing, and large packaging jobs
```

Codex must not call `ssh`, `scp`, `sftp`, `rsync`, mount commands, or arbitrary remote-shell wrappers directly. It may call only the protected helpers described below. Some helpers may use SSH or rsync internally.

## Keep the manual and automated HPC checkouts separate

Keep the current checkout used by VS Code on lethe. Create a second checkout used only for Codex-prepared runs, for example:

```text
/ddn/niknovikov19/repo/A1_OUinp
    Manual VS Code–lethe checkout

/ddn/niknovikov19/repo/A1_OUinp_codex
    Automated-run checkout
```

The automated helper may update only `A1_OUinp_codex`. Codex never edits either checkout directly.

This separation prevents:

- an automated update from conflicting with an uncommitted manual HPC fix;
- an automated operation from changing the branch used in VS Code;
- uncertainty about whether a result came from manually modified or committed code;
- a failed pull from leaving the manual working directory in an inconvenient state.

The current hardcoded `/ddn/.../A1_OUinp` paths in submission scripts should become relative to the script/repository directory or controlled through one configuration value. This is necessary for the separate automated checkout.

## Use Git for source-code transfer

Continue using commit, push, and pull for tracked source code. Git is preferable to rsync or SCP for this purpose because it:

- identifies the exact code version;
- provides a reviewable record of changes;
- transfers only tracked code rather than simulation outputs;
- avoids partially copying a set of source files;
- makes it possible to associate every run with a commit.

Use rsync or tar archives for result data, not for routine code deployment.

The automated code-update helper should:

1. Operate only in the automated checkout.
2. Refuse to continue if that checkout contains uncommitted changes.
3. Fetch the dedicated automation branch.
4. Accept only a fast-forward update; never create an automatic merge.
5. Record the resulting Git commit in the run record.
6. Confirm that the intended local changes were tracked and committed.
7. Refuse to update the checkout while an automated run using it is active.

The final restriction prevents one long-running batch from seeing source files changed for a newer batch. Initially, permit only one active code version in the automated checkout. Separate per-run Git worktrees can be considered later if concurrent runs using different revisions become necessary.

An ignored local helper can make a smoke test pass without being transferred to HPC. The local preflight check should therefore report untracked and ignored dependencies that appear relevant to the changed code.

## Protected helper commands

Start with a small command-line interface installed outside the repository in a location Codex cannot modify. For example:

```text
/usr/local/bin/hpc-code-update
/usr/local/bin/hpc-run-preview
/usr/local/bin/hpc-submit
/usr/local/bin/hpc-status
/usr/local/bin/hpc-log
/usr/local/bin/hpc-result-list
/usr/local/bin/hpc-result-get
/usr/local/bin/hpc-result-pack
```

The directory should not be writable by the WSL account used by Codex. If remote helper scripts are needed on lethe, they must also live outside the Git checkout so a Codex-authored commit cannot replace them.

Each helper must perform one defined operation and validate its arguments. It must not accept arbitrary shell text or arbitrary remote paths.

Acceptable interfaces include:

```text
hpc-status RUN_ID
hpc-log RUN_ID controller
hpc-log RUN_ID job JOB_LABEL
hpc-result-list RUN_ID png
hpc-result-get RUN_ID job JOB_LABEL raster
```

Do not implement interfaces such as:

```text
hpc-remote-command "ARBITRARY COMMAND"
hpc-result-get "ARBITRARY REMOTE PATH"
```

Narrow arguments prevent mistakes such as an experiment name containing shell punctuation, a typo reading outside the result directory, or a request intended for lethe causing non-Slurm computation on grid.

## Submission workflow

### 1. Local preparation

Codex works in the local WSL clone:

- edits source and experiment configuration;
- runs appropriate local tests and smoke tests;
- reviews the diff;
- commits the changes;
- pushes the dedicated automation branch.

No HPC state changes during this step.

### 2. Mandatory preview

Before updating HPC or submitting a job, `hpc-run-preview` should produce a mechanical summary based on the actual configuration:

```text
Branch: codex-hpc
Commit: 73acfe1
Run type: batch
Experiment: batch_rxbkg_state1_mech1/example

Calculated child jobs: 8
Maximum concurrent child jobs: 4

Resources per child:
  partition: cpu.q
  nodes: 1
  cores: 60
  memory: 256 GB
  time limit: 7 hours

BatchTools controller:
  cores: 2
  memory: 16 GB
  time limit: 24 hours

Planned run ID: 20260914-1430-example
Planned result directory: .../automation_runs/20260914-1430-example
```

The helper, not Codex, must calculate the number of parameter combinations.

Initially impose a configurable maximum, for example 10 child jobs. Refuse larger submissions unless the user explicitly approves raising or bypassing that limit.

This prevents:

- an unnoticed Cartesian-product explosion in `batch_params.py`;
- a test using production-scale duration or resources;
- accidental use of the wrong partition;
- unexpectedly high concurrency;
- submission of a different experiment than the one the user reviewed.

### 3. Human approval

Initially require explicit approval for:

- updating the automated HPC checkout;
- submitting a single or batch run;
- cancelling any Slurm job;
- resubmitting a failed or uncertain job;
- packaging or downloading a large result collection.

Status checks and bounded reads of already approved run logs may operate without repeated approval.

### 4. Update, record, and submit

After approval, the helper should:

1. Verify the automated checkout is clean.
2. Verify no incompatible automated run is active.
3. Update it using a fast-forward-only Git operation.
4. Verify and record the resulting commit.
5. Create a unique run ID and run directory.
6. Write the initial run record.
7. Submit the BatchTools controller through grid.
8. Record the controller's Slurm job ID.
9. Record child-job IDs and log paths as BatchTools submits them.

If submission succeeds but the local connection breaks before the response is received, the helper must search the run record or scheduler before retrying. It must not blindly submit a duplicate.

## Per-run files

Use a layout based on the existing workflow implementation:

```text
automation_runs/<run_id>/
    run.json
    status.json
    controller/
        slurm-<controller-job-id>.out
        slurm-<controller-job-id>.err
    jobs/
        index.jsonl
        scripts/
        logs/
    job_meta/
    sim_results/
    processed/
```

`run.json` should record at least:

- run ID;
- Git commit;
- branch;
- run type;
- experiment name;
- submission time;
- controller Slurm job ID;
- calculated number of child jobs;
- concurrency limit;
- requested resources;
- expected result directory;
- status such as `prepared`, `submitted`, `running`, `complete`, `failed`, or `unknown`.

Do not reuse fixed log names such as `batch_sl_1.out`. Include the run ID and/or Slurm job ID in every controller-log name. This prevents a new run from overwriting or being confused with an earlier run.

`jobs/index.jsonl` should contain one short record per submitted child:

- BatchTools label;
- Slurm job ID;
- parameter values;
- stdout and stderr paths;
- expected result location;
- last known Slurm status.

For an initial small prototype, child files may be discovered once after submission and cached. A later small change to the custom `LocalSlurmSubmit` class should record this information directly when each child is submitted.

## Log and status monitoring

Monitoring must combine four kinds of evidence:

1. Slurm state for the controller and child jobs.
2. The BatchTools controller log.
3. Selected per-job logs.
4. Completion records and expected result files.

No single source is sufficient by itself.

### One compact status operation

`hpc-status RUN_ID` should use the known job IDs from the run record and job index. It should make one scheduler request covering all relevant IDs rather than one SSH call per job.

Use `squeue` for active jobs and `sacct` for completed, failed, timed-out, cancelled, or otherwise absent jobs. Return a concise summary:

```text
Run: 20260914-1430-example
Commit: 73acfe1

Controller: RUNNING
Children:
  pending: 1
  running: 3
  completed: 3
  failed: 1

Valid result records: 3/8
New controller warnings: 1

Attention:
  job 482913 failed
  parameters: seed=1000, amp1=0.02, amp2=0.2
```

Scheduler queries are the inexpensive way to monitor many jobs. Do not open every child log merely to determine whether its job is running.

### Controller-log monitoring

There is one BatchTools controller log per run. It is reasonable to follow it, but do not reread it from the beginning.

Maintain local monitoring state containing:

- last observed file size;
- last byte offset read;
- last modification time;
- last returned warnings or errors.

On each check:

- return `no new controller output` if the file did not grow;
- otherwise read only bytes appended since the previous check;
- cap output, for example at 200 new lines;
- detect truncation or replacement and reset the offset safely.

A bounded local monitoring command may maintain one SSH connection for a defined period, such as 30 minutes, and poll through it. Alternatively, SSH connection multiplexing may be used internally. This avoids repeated logins without using remote `watch`.

### Per-job log monitoring

Do not follow all child logs continuously. Normally, the Slurm summary is enough.

Automatically read a child log only when:

- the job newly enters `FAILED`, `OUT_OF_MEMORY`, `TIMEOUT`, `CANCELLED`, or another abnormal state;
- the job remains running unusually long;
- Slurm reports completion but the expected output record is absent;
- the user or Codex selects a particular job for a scientific sanity check.

Default limits should be conservative:

- inspect at most two or three child jobs per monitoring cycle;
- return at most the last 100–200 lines from each selected log;
- use exact cached paths from the job index;
- never use a recursive filesystem search to locate logs repeatedly.

For a small initial batch, it is acceptable to inspect all failed jobs if their number remains below the configured per-check limit.

### Monitoring intervals

Suggested defaults for long-running simulations:

- every 30–60 seconds during initial controller startup;
- every 2–5 minutes while the queue state is stable;
- an immediate detailed check when a job first fails or the run reaches a terminal state;
- stop automatic polling after a configurable duration and report that monitoring ended.

Do not poll indefinitely without the user asking for continued monitoring.

### Interpret difficult cases conservatively

| Observation | Interpretation and action |
| --- | --- |
| Controller running and child jobs active | Normal. Do not inspect every child log. |
| Controller log unchanged but children progress in Slurm | Usually normal waiting. Continue low-frequency status checks. |
| Controller reports a socket error but all expected output records exist | Results may be valid. Report the controller error separately from simulation completion. |
| Controller exited while children remain active | Continue monitoring known child IDs. Do not resubmit. |
| Slurm reports completion but an expected output is absent | Mark that child incomplete and inspect its log. |
| SSH or HPC is unavailable | Mark the state `unknown`, not `failed`. Do not resubmit. |
| Some children failed | Show parameters and bounded log tails, then ask before cancellation or resubmission. |
| All children and expected outputs are complete but BatchTools still waits | Report a likely BatchTools/controller hang. Do not automatically kill it. |

The existing durable `job_meta` and output-validation logic in the workflow code should be reused where possible.

## Selective result access

### Read-only mounted scope

Read-only SSHFS remains acceptable for carefully selected results. Mount only a particular run, experiment, or small subdirectory, not the full HPC repository or all historical results.

Prefer a structure such as:

```text
HPC_mount/<run_id>/
```

Keep the actual mount outside the Git working tree. Add an exact symlink into the expected local `exp_results` path only when a script requires the original repository layout.

Codex must not run recursive operations on a mounted tree, including:

- unrestricted `find`;
- `tree` over the mount;
- recursive `du`;
- recursive globbing such as `**/*`;
- recursive search that follows symlinks;
- repeated counting or inventory of every file.

These restrictions prevent a request such as “find every PV2 plot” from causing thousands of metadata reads on lethe.

### Result inventory

Each automated run should have a small inventory file containing:

- relative path;
- job label or parameter coordinates;
- artifact type;
- file size;
- modification time;
- optionally a checksum for small files.

Codex reads the inventory first and selects exact files from it. The inventory may be generated once when a run completes, or incrementally from known output paths. Do not regenerate a full recursive inventory during every monitoring check.

### Selective retrieval

`hpc-result-get` should support requests such as:

```text
hpc-result-get RUN_ID job JOB_LABEL raster
hpc-result-get RUN_ID job JOB_LABEL data-pkl
```

It should:

- accept only a known run ID, job label, and artifact type;
- resolve the exact path from the inventory;
- reject arbitrary paths and wildcards;
- default to one file;
- cap the number of files and total bytes per request;
- show the size before transferring an unusually large file;
- save a local cached copy;
- avoid downloading the file again when it has not changed.

This permits Codex to inspect a representative PNG or PKL while preventing an accidental request for every result in a batch.

### Access to complete result collections

When all results are needed:

1. Prefer an existing merge or processing script that produces compact combined outputs.
2. Run substantial processing as a Slurm job on compute nodes.
3. If raw files are still required, create a tar archive for the exact run.
4. Transfer the archive with a protected rsync-based helper after explicit approval.

Large archive creation or merging should not run interactively on grid and should not impose substantial computation or I/O load on lethe. Submit it as a Slurm job when necessary.

Use existing retention controls such as `keep_pkl=False` when full pickles are not required downstream.

## Required guardrails and examples

| Guardrail | Example of misuse or mistake it prevents |
| --- | --- |
| Separate automated HPC checkout | An automated pull conflicts with a manual lethe fix. |
| No direct SSH from Codex | Codex accidentally runs Python on grid or recursively searches lethe. |
| Helpers are outside Codex-writable directories | Codex edits the submission helper to bypass its limits. |
| No arbitrary remote command or path argument | A malformed experiment name becomes unintended shell syntax. |
| Mechanical job-count and resource preview | Several parameter lists unexpectedly produce hundreds of simulations. |
| Configurable initial job-count ceiling | An experimental change immediately launches a production-scale batch. |
| Unique run IDs and log paths | `batch_sl_1.out` from a new run overwrites or is confused with an old log. |
| Clean, fast-forward-only Git update | The automated checkout develops an unnoticed merge or mixed state. |
| No checkout update during active runs | Children from one batch execute different versions of the code. |
| One scheduler query for all known jobs | Monitoring creates dozens of SSH connections or opens every job log. |
| Incremental controller-log reads | Codex repeatedly rereads a very large controller log. |
| Exact child-log selection and line limits | “Check the errors” opens hundreds of per-job logs. |
| Exact result selection and transfer limits | A wildcard downloads thousands of PNG or PKL files. |
| Local cache for selected results | Codex retrieves the same unchanged artifact repeatedly. |
| `unknown` status on connection failure | A temporary HPC outage is mistaken for job failure and triggers duplication. |
| Human approval for cancel and resubmit | Codex kills useful jobs or duplicates expensive simulations while diagnosing uncertainty. |

## Codex configuration layers

The repository already contains an `AGENTS.md` with coding-style guidance. Add a concise HPC section later containing behavioral instructions such as:

- never invoke SSH or remote-transfer commands directly;
- use only named protected HPC helpers;
- never perform recursive searches on `HPC_mount`;
- preview every submission;
- never cancel or resubmit without explicit approval;
- treat unavailable monitoring as `unknown`;
- report exact run ID, commit, Slurm IDs, and result paths.

`AGENTS.md` is guidance, not the actual security boundary. The real restrictions should be enforced by:

- Codex sandbox/network settings;
- user-level Codex command rules outside the repository;
- non-writable fixed-purpose helper scripts;
- validation inside the local and remote helpers.

Useful official Codex references:

- [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Command rules](https://learn.chatgpt.com/docs/agent-configuration/rules)

Command rules are an additional Codex-side guardrail, not a replacement for argument validation in the helper scripts.

## Initial implementation scope

The first working version should include only:

1. A separate automated checkout on lethe.
2. One dedicated Git branch for Codex-prepared work.
3. A protected code-update helper.
4. A submission-preview helper that calculates job count and resources.
5. Protected single-run and batch-run submission helpers.
6. Unique run metadata and controller-log names.
7. A compact status helper using one scheduler query for known job IDs.
8. Incremental BatchTools controller-log reading.
9. Selective, bounded per-job log reading.
10. A result inventory plus selective cached PNG/PKL retrieval.
11. Explicit approval for update, submit, cancel, resubmit, and bulk transfer.
12. A small end-to-end test with no more than approximately 4–10 child jobs.

Do not initially implement:

- autonomous resubmission;
- autonomous cancellation;
- continuous indefinite monitoring;
- broad result-tree indexing on every check;
- arbitrary remote execution;
- automatic modification of the manual HPC checkout;
- an MCP server or permanent broker service;
- multiple concurrent source revisions.

## Suggested implementation order

1. Make repository and output paths configurable so the automated checkout can be separate.
2. Add unique run IDs, run records, and per-run controller logs.
3. Add submission preview and job-count/resource validation.
4. Implement protected code update and submission helpers.
5. Implement status queries and incremental controller-log reading.
6. Record or cache child-job IDs, parameter coordinates, and log paths.
7. Add bounded child-log inspection.
8. Add result inventories and selective cached retrieval.
9. Test with a single simulation.
10. Test with a batch of a few jobs, including one deliberate failure.
11. Test interruption cases: SSH loss, controller error, missing result, and an already-submitted request whose response was lost.
12. Only after the manual workflow is reliable, consider limited unattended monitoring or an MCP interface.

## Definition of a successful first version

The first version is successful when Codex can:

- prepare and push a committed code change locally;
- show exactly what code, experiment, job count, and resources would be used;
- update only the automated HPC checkout after approval;
- submit one run without obtaining a general SSH capability;
- report controller and child Slurm states in one compact summary;
- show only newly appended controller-log content;
- select and inspect a small number of relevant child logs;
- retrieve one selected PNG or PKL without walking the entire result tree;
- recognize uncertainty without automatically cancelling or duplicating jobs;
- leave the manual VS Code–lethe checkout untouched.

