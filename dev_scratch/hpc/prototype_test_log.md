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

Status: operational tests passed; isolated non-fast-forward test deferred by
user choice on 2026-10-05.

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

Push and first exact-update attempt 2026-10-05:

- scoped local commit:
  `e0c4d394e43ea51ba318e0c087f209cea6d8ccd5`;
- the commit contained only reviewed `dev_scratch/hpc/` changes; unrelated
  untracked `doc/paper/` content was not staged;
- the push advanced `origin/codex-hpc` from the baseline to the exact scoped
  commit;
- protected status before update confirmed the HPC checkout remained clean at
  baseline `b2c7595198e0128bc9a5f73f25c55b57733422ae`;
- the separately approved exact update returned structured `unknown` with exit
  code `3` because lethe's non-interactive Git fetch received GitHub SSH
  `Permission denied (publickey)`;
- the helper did not retry or move the checkout;
- protected status after the failed fetch confirmed the checkout remained
  clean at the baseline, with no active run or update lock;
- read-only GitHub fetch authentication on lethe must be established before a
  separately approved retry.

HTTPS recovery and exact fast-forward 2026-10-05:

- because the repository is public, the user changed only the automation
  checkout's `origin` URL to unauthenticated GitHub HTTPS;
- a non-interactive `ls-remote` resolved `origin/codex-hpc` to exact approved
  commit `e0c4d394e43ea51ba318e0c087f209cea6d8ccd5`;
- the separately approved retry returned exit code `0` and result
  `fast-forwarded`;
- the helper reported before commit
  `b2c7595198e0128bc9a5f73f25c55b57733422ae` and after commit exactly
  `e0c4d394e43ea51ba318e0c087f209cea6d8ccd5`;
- independent protected status confirmed local and remote-tracking commits at
  the exact target, branch `codex-hpc`, a clean checkout, zero changes, no
  active run, and no active update lock;
- the audit trail contained a redacted update intent followed by a successful
  `fast-forwarded` result;
- the separately approved same-commit retry returned exit code `0` and result
  `no-op`, with identical before, expected, and after commits;
- independent status after the no-op confirmed the exact commit, clean branch,
  zero changes, no active run, and no active update lock.

Unapproved full-hash rejection 2026-10-05:

- the separately approved update using 40 zeroes returned exit code `2` and
  status `rejected`;
- the helper reported reason `expected-commit-is-not-remote-branch-head` and
  the actual remote head remained the approved exact commit;
- independent status confirmed the checkout remained clean at the exact
  approved commit, with no active run or update lock.

Dirty-checkout rejection 2026-10-05:

- the user created one harmless untracked marker in the dedicated automation
  checkout;
- protected status reported `clean: false` and exactly one change while
  retaining the exact approved commit;
- the approved exact-commit update returned exit code `4`, status `failed`,
  and detail `Automation checkout is not clean`;
- post-rejection status confirmed the commit and remote-tracking commit were
  unchanged, the marker remained present, and the update lock was released;
- after manual marker removal, protected status confirmed the real automation
  checkout was clean again at the exact approved commit with no active lock.

Final verification and deferred test 2026-10-05:

- final protected status confirmed the real automation checkout remained clean
  at exact commit `e0c4d394e43ea51ba318e0c087f209cea6d8ccd5`;
- the remote-tracking commit matched, the configured branch was correct, and
  no active run or update lock was present;
- the protected audit tail retained the unavailable-fetch, successful
  fast-forward, successful no-op, unknown-hash rejection, and dirty-checkout
  rejection events with caller commit values redacted;
- the user elected to defer the disposable-fixture non-fast-forward test;
- no disposable repository was created and no configuration change was made.

Gate conclusion: PARTIAL PASS. The exact GitHub round trip, clean
fast-forward, idempotent no-op, strict hash validation, remote-head pinning,
dirty-checkout refusal, failure safety, locking, and audit behavior are proven.
The installed helper's non-fast-forward refusal remains statically reviewed
but not exercised against a divergent repository, so A2 is not recorded as an
unqualified pass.

## Gate A3: deterministic run preview and request pinning

Status: candidate source prepared; commit, manual promotion, and protected
tests pending.

Prepared A3 behavior:

- local `hpc-run-preview` accepts only a path-safe request ID and selects it
  from one fixed protected catalog;
- the catalog request is canonicalized, hashed, URL-safe-base64 encoded, and
  sent only to the fixed lethe preview helper;
- the remote helper independently validates the request and a separate
  protected configuration before inspecting the repository;
- the configured automation checkout must be clean, on `codex-hpc`, and at
  the request's exact full commit;
- experiments resolve only below `exp_configs`, and every declared dependency
  must be a tracked non-symlink regular file;
- parameter axes are part of the pinned request, while child count is omitted
  and mechanically calculated as their Cartesian product;
- partition, output kind, concurrency, job count, cores, memory, nodes, and
  wall time are checked against independent protected limits;
- ignored files below the experiment are inspected with a bounded report of
  source/config-like paths;
- responses contain no timestamp, so unchanged requests and repository state
  produce identical output and canonical request digests;
- A3 contains no Git mutation, Slurm command, run-directory creation,
  repository-Python execution, or file transfer.

Static review:

- all candidate Python entry/source files parsed with `ast.parse` without
  import or execution;
- all JSON, schema, configuration-example, and fixture files decoded
  successfully;
- no trailing whitespace or code lines longer than 88 characters were found;
- the new helpers contain no `shell=True`, arbitrary-command interface, Git
  mutation, Slurm command, or transfer primitive;
- all four repository dependencies declared by the example catalog were
  confirmed tracked;
- independent AST/literal inspection of the existing experiment confirmed
  axis sizes `1 x 1 x 4 x 6 x 2`, or 48 jobs;
- independent fixture inspection confirmed the one-job, six-job, 48-job, and
  empty-axis products without invoking candidate code;
- candidate helpers were not invoked, sourced, or imported.

Reviewed candidate SHA256 values:

- `hpc-run-preview`:
  `e677e8afc2018c46f1994d58765de8278acbf66140b5e23bd8c94591610adf20`;
- `hpc_common.py`:
  `97851c0a7f1cea91283b56e95e63b15b8ba1250464242d381797c65040dd93e6`;
- `hpc-lethe-preview`:
  `483e6f085b703217cd40069f342801de33fe2cf52c5b3c03eec82b50cd523547`;
- `remote-hpc-preview.json.example`:
  `2183dc0f0d31d69f91f95ecd2a479e7918a6e1f35c77406783f4a02aa4fa3c3e`;
- `preview-requests.json.example`:
  `738db5d5a032af0203aedf98da5fd5b9cf21f845af18021b69b636179548ace5`;
- `remote-hpc-preview-config.schema.json`:
  `454eaa3b79da53749b4599a6d4bf3275ae8f136cca94d616a89875192c07c499`;
- `run-request.schema.json`:
  `4add2e162b8037fb25c50e4a82b567eabe48c9c48658b899a4ac83a6a2ccc975`;
- `a3_preview_cases.json`:
  `a2989f2e5ab9aa6afae5779e2c38c4401b4489f3184127b771a4cfefed692ad6`;
- expected installed local bundle:
  `71b493bba432c9e1385140d42526c6705b030e11d55dd211fc1611fd72ee474c`.
