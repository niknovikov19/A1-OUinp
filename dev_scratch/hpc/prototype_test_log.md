# Codex-to-HPC prototype test log

## Environment

- Local branch: `codex-hpc`
- Plan: `dev_scratch/hpc/prototype_work_plan.md`
- Candidate source: `dev_scratch/hpc/helper_src/`
- Protected installation: `/opt/a1-hpc`

## Gate A0: prototype configuration and helper identity

Status: passed 2026-09-30.

Candidate version: `0.1.0-a0`

Prepared artifacts:

- local `hpc-helper-info` command with no remote capabilities;
- shared identifier and configuration validation;
- deterministic installed-source hashing;
- mandatory local JSONL audit append;
- non-secret configuration example and schema;
- initial audit-event and run-record schemas;
- valid and invalid identifier fixtures;
- manual promotion instructions.

Candidate execution record: no candidate helper was invoked or sourced from the repository.

Static review:

- Python source parsed successfully with `ast.parse` without import or execution.
- All five JSON/example files parsed successfully.
- No trailing whitespace was found.
- No subprocess, SSH, transfer, or Slurm command primitive was found in the A0 local source.

Reviewed candidate SHA256 values:

- `hpc-helper-info`: `5a8a5099234f08c9dfcdb482a4fd3a9788d1deb77258deb1a89097a25fce1aa0`
- `hpc_common.py`: `0167482e0dbc901154f47713aa351f9b394d5af0dbdd54d9f77057e9d8d0b24b`

Promotion handoff received 2026-09-30:

- installed command: `/opt/a1-hpc/bin/hpc-helper-info`;
- installed `hpc-helper-info` SHA256 matches the reviewed candidate;
- installed `hpc_common.py` SHA256 matches the reviewed candidate;
- protected configuration was edited and reviewed;
- execution of the exact installed command was approved.

Installed-helper test attempt 2026-09-30:

- command: `/opt/a1-hpc/bin/hpc-helper-info version`;
- observed exit code: `1`;
- result: failed before version output because mandatory audit access raised
  `PermissionError` for `/opt/a1-hpc/state/actions.jsonl`;
- diagnosis: `/opt/a1-hpc/state` is mode `0700` and owned by `root:root`, while
  the helper executes as `nnovikov`;
- no candidate or protected file was changed by Codex during this test;
- required user action: make only the protected `state` directory and audit
  file owned and writable by the helper's invoking account, then rerun A0.

Post-permission-fix verification 2026-09-30:

- installed helper version: `0.1.0-a0`;
- bundle SHA256:
  `5d61170509e9f07618f35f4aa7aa8f0845122f8cba8e38ccb660ab06b5df9fe2`;
- installed source hashes again matched both reviewed candidate hashes;
- protected configuration validated successfully;
- protected configuration SHA256:
  `beb6acc4228d231682d0a30bbc03900f3ba60d0562ffd83a38981df85ca22883`;
- install root and audit path resolved to `/opt/a1-hpc` and
  `/opt/a1-hpc/state/actions.jsonl`;
- valid run ID, full lowercase Git hash, experiment ID, and job label all
  returned exit code `0`;
- run-ID traversal and punctuation, short and uppercase Git hashes,
  experiment traversal, and a wildcard job label all returned exit code `2`;
- an extra argument and unsupported command both returned exit code `2`;
- `audit-tail` returned the preceding successful and rejected events;
- public command words were retained in audit events, while identifier values
  and unsupported input were recorded as `<value>`;
- no A0 command exposed or invoked SSH, Git mutation, Slurm, or transfer
  behavior.

Gate conclusion: PASS. Installed-helper identity is verifiable, the fixed
protected configuration validates, malformed inputs are rejected locally, and
mandatory audit records cover both successful and rejected invocations.

Final protected configuration verification 2026-09-30:

- configuration SHA256:
  `ce6208ee7f4a509faea9632a3714db5b031dc328eabe339f50363435b8023e86`;
- remote helper root: `/ddn/niknovikov19/hpc_codex/helpers/`;
- run root: `/ddn/niknovikov19/hpc_codex/runs/A1_OUinp`;
- limits: 10 total child jobs, 4 concurrent jobs, 1 core, 2 GB memory,
  1 node, and 10 minutes per job;
- configuration validation returned exit code `0` and wrote its audit event;
- installed runtime source and bundle hashes were unchanged.

## Gate A1: bounded lethe and grid connectivity

Status: passed 2026-09-30.

Remote preflight supplied by the user:

- the shared `/ddn/niknovikov19/hpc_codex` hierarchy was created;
- the `codex-hpc` branch was pushed and cloned at
  `/ddn/niknovikov19/repo/A1_OUinp_codex`;
- lethe can see the automation checkout;
- lethe and lattice both resolve Python 3.11.4 at
  `/ddn/niknovikov19/miniconda3/bin/python3`;
- both hosts provide `/usr/bin/ssh`;
- lattice provides `/usr/bin/squeue` and `/usr/bin/sacct`;
- both Slurm commands report version `25.11.4`;
- the physical grid SSH alias is `lattice`; the logical helper target remains
  `grid`.

Prepared A1 behavior:

- local `hpc-probe` accepts only `lethe` or `grid`;
- lethe checks only the configured automation checkout and `.git` marker;
- grid is reached only through the fixed lethe-side helper;
- the grid helper runs fixed version, user-scoped `squeue`, and recent
  user-scoped `sacct` queries;
- subprocess timeouts, output limits, and structured `unknown` results are
  enforced;
- no A1 helper implements Git mutation, Slurm mutation, log access, file
  transfer, or an arbitrary command interface.

Static review:

- all five local and remote Python entry/source files parsed successfully with
  `ast.parse`, without import or execution;
- all configuration, schema, and fixture JSON parsed successfully;
- no trailing whitespace was found;
- candidate helpers were not invoked or sourced from the repository.

Reviewed candidate SHA256 values:

- `hpc-helper-info` (unchanged):
  `5a8a5099234f08c9dfcdb482a4fd3a9788d1deb77258deb1a89097a25fce1aa0`;
- `hpc-probe`:
  `44f692483c3bd0f6ce4f8ff021e9c9df31e3cc8fb88983b915f4bd564192f867`;
- `hpc_common.py`:
  `4b4cd381260d94ba18395d29e695b51128943c3009b537503ed342ca37d2bcfe`;
- `hpc-lethe-probe`:
  `81fc1129913b2e89b7cc4ee2208bc3b0688d6632a4e22decda518d5234297499`;
- `hpc-grid-probe`:
  `66578e0a511e7916006ed532c7feff3dbf6452576a704aee4649b29b15e86375`;
- expected local installed bundle:
  `bd7b025379c6208f7747ea7b485f9a9cf936a273ecd4a54b1c7d9ecc2eef278b`.

Promotion handoff and protected tests 2026-09-30:

- all four changed/added helper source hashes and the raw remote configuration
  hash matched the reviewed candidates;
- installed local bundle version: `0.2.0-a1`;
- installed local bundle SHA256 matched the expected
  `bd7b025379c6208f7747ea7b485f9a9cf936a273ecd4a54b1c7d9ecc2eef278b`;
- protected local configuration validated with SHA256
  `ccc33153ff841b9a1c0c89e31cebfea3e45b599a165efef5a7f039b396d876f3`;
- the protected local configuration used physical grid alias `lattice`;
- the lethe probe returned exit code `0`, host `lethe`, and confirmed the
  automation checkout and `.git` marker;
- the lethe response reported the reviewed lethe-helper source hash and remote
  canonical configuration SHA256
  `3a49b3ff1f377e28098f523bcdc73b014b0323b7ead0199e16f2d764f4e6be93`;
- the grid probe returned exit code `0`, host `lattice`, and confirmed the
  route through host `lethe`;
- the grid response reported both reviewed remote-helper source hashes;
- `squeue` and `sacct` both reported Slurm `25.11.4`;
- the observed `squeue` format was pipe-delimited job ID, full state, and
  reason using `%i|%T|%r`;
- the observed `sacct` format was pipe-delimited raw job ID, state, and exit
  code using `JobIDRaw,State,ExitCode`;
- both user-scoped query samples contained zero rows at test time;
- missing target, physical alias `lattice`, traversal, punctuation, and an
  extra argument each returned exit code `2` locally;
- `audit-tail` showed both successful probes and all five rejected invocations
  with helper `hpc-probe`, version `0.2.0-a1`, and caller values redacted;
- no Git mutation, Slurm mutation, log access, or file transfer occurred.

Controlled unavailable-state procedure:

- induce one controlled temporary grid-helper outage, confirm the protected
  local probe returns structured `unknown` with exit code `3`, restore the
  helper, and confirm the normal grid probe still succeeds.

Controlled unavailable-state test 2026-09-30:

- the user temporarily removed execute permission from the protected grid
  helper;
- one protected `hpc-probe --json grid` invocation returned exit code `3`;
- the result contained target `grid`, status `unknown`, and reason
  `invalid-grid-output`;
- the result retained the protected local configuration identity;
- no retry, fallback command, scheduler mutation, or other recovery action was
  attempted;
- after the user restored mode `0555`, the final grid probe returned exit code
  `0`, host `lattice`, both reviewed helper hashes, and both Slurm `25.11.4`
  versions;
- `audit-tail` showed the grid sequence `success`, `unknown` with exit code
  `3`, then `success` after restoration.

Gate conclusion: PASS. Both fixed hops work, the configured checkout and
scheduler interfaces are visible, malformed local input cannot initiate SSH,
and an induced remote-helper outage maps to audited `unknown` without retry or
mutation.

## Gate A2: exact-commit Git synchronization

Status: candidate source prepared; manual promotion and protected tests
pending.

Remote preflight supplied by the user:

- lethe Git path: `/usr/bin/git`;
- lethe Git version: `2.39.3`;
- automation checkout: `/ddn/niknovikov19/repo/A1_OUinp_codex`;
- branch: `codex-hpc`;
- baseline commit: `b2c7595198e0128bc9a5f73f25c55b57733422ae`;
- checkout status output was empty;
- configured remote name: `origin`.

Prepared A2 behavior:

- read-only status reports path, branch, local and remote-tracking commits,
  cleanliness, update-lock state, and active-run state;
- update accepts only one full lowercase commit hash and one fixed checkout,
  branch, remote, Git executable, state root, and lock path;
- update requires a clean expected branch, no active-run marker, and an
  exclusive nonblocking lock;
- an intent record is written locally before remote invocation and a pending
  remote record is written before fetch;
- fetch is limited to the configured branch without tags;
- the requested commit must equal the fetched remote branch head and descend
  from the current commit;
- the only successful outcomes are fast-forward and idempotent no-op;
- no reset, divergent merge, arbitrary Git argument, manual-checkout access,
  lattice access, Slurm operation, or file transfer is implemented.

Static review:

- all local and remote Python sources parsed successfully with `ast.parse`,
  without import or execution;
- all configuration, schema, and fixture JSON parsed successfully;
- no trailing whitespace or overlong code lines were found;
- no shell execution, reset, checkout mutation, transfer, or Slurm primitive
  was found in the A2 sources;
- candidate helpers were not invoked or sourced from the repository.

Reviewed candidate SHA256 values:

- `hpc-code-status`:
  `dd51bb1a57124d6fbdb56cbac0f5315565b2a68cdc6096cf7f70b164edb16226`;
- `hpc-code-update`:
  `bfb151d5069ee269ac4d37939ac4aa8a5fdd04c95d42d74c471fa9c54b70c254`;
- `hpc_common.py`:
  `9237a884629f0061bb5cc079c48e7faa7cbb5be712534669451f6658a48fd7ce`;
- `hpc-lethe-code`:
  `cdf26a3bab06ea5ca43a50c8efaca8869100ae7be12d6fc304b5a25e86269d87`;
- expected local installed bundle:
  `b49d5aa7790739563856b9e6316004a306b4550658d383bbec7f41cfb37421eb`.

Initial promotion verification 2026-10-05:

- installed local bundle version was `0.3.0-a2`;
- installed local bundle SHA256 exactly matched
  `b49d5aa7790739563856b9e6316004a306b4550658d383bbec7f41cfb37421eb`;
- all five installed local source hashes matched the reviewed candidates;
- the first protected read-only status call returned exit code `4` without
  fetching or changing the checkout;
- the remote helper reported that `A1_OUinp-code.json` was missing its required
  top-level `state` key;
- remote configuration correction and status retest are pending.

Corrected promotion verification 2026-10-05:

- protected status returned exit code `0` from host `lethe`;
- installed `hpc-lethe-code` version was `0.3.0-a2` and its SHA256 matched the
  reviewed candidate;
- remote canonical configuration SHA256 was
  `f67a290fbbb50b3355a6272de2b3ee46354eca9f9caea97c18d672be4915e3e0`;
- checkout path and branch matched the protected configuration;
- local and remote-tracking commits both equaled the recorded baseline
  `b2c7595198e0128bc9a5f73f25c55b57733422ae`;
- the checkout was clean with zero reported changes;
- no active run or active update lock was reported;
- a seven-character commit hash returned exit code `2` locally;
- the audit trail recorded the successful status and rejected update request,
  with the malformed caller value stored as `<value>`;
- no fetch or checkout update occurred.
