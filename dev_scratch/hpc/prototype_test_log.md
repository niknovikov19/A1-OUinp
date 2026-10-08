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

Status: passed 2026-10-06.

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

Commit, promotion, and identity verification 2026-10-06:

- the reviewed A3 implementation was committed as `5700b5d`, followed by the
  promotion-command documentation commit `da79b85`;
- final pinned and pushed A3 commit:
  `da79b85c85921b26f604cfcf7a15d87db1f8f045`;
- the protected A2 updater fast-forwarded the clean automation checkout from
  `e0c4d394e43ea51ba318e0c087f209cea6d8ccd5` to the exact A3 commit;
- independent status confirmed matching local and remote-tracking commits, a
  clean branch, no active run, and no update lock;
- the installed local bundle reported version `0.4.0-a3` and exact expected
  SHA256 `71b493bba432c9e1385140d42526c6705b030e11d55dd211fc1611fd72ee474c`;
- all installed local source and schema hashes matched the reviewed values;
- the protected request catalog replaced exactly eight zero placeholders with
  the A3 commit, retained one deliberate 40-one mismatch fixture, and had
  SHA256 `8583446bb3ada302776df10f3b5bc67604aa6a038af4a9e5dc771d16ea47d00f`;
- local protected directories were restored to mode `0555`, the preview entry
  point to `0555`, and the module, schemas, and catalog to `0444`, all owned by
  `root:root`;
- installed `hpc-lethe-preview` and `A1_OUinp-preview.json` matched reviewed
  raw hashes `483e6f085b703217cd40069f342801de33fe2cf52c5b3c03eec82b50cd523547`
  and `2183dc0f0d31d69f91f95ecd2a479e7918a6e1f35c77406783f4a02aa4fa3c3e`;
- their canonical remote configuration SHA256 was
  `b8c5d3c474fcfe5c5a23cde19b946b844f87887b4be7ddddaa8422f09d1666cc`;
- remote directories and helper were mode `0555`, configuration was mode
  `0444`, and all were owned by `niknovikov19:salvadord`;
- remote promotion used the owning lethe account without `sudo`; the local
  installation guide was corrected accordingly after the pinned commit.

Protected tests 2026-10-06:

- the first sandboxed local-rejection attempts failed closed with exit code
  `4` because mandatory audit appends were blocked by the Codex filesystem
  sandbox; no SSH or preview occurred in those attempts;
- after protected audit permission was granted, missing, unknown, traversal,
  and extra-argument request forms all returned exit code `2` locally;
- `a3-probe-one` returned exit code `0`, exact A3 commit, one calculated job,
  allowed resources, two tracked dependencies, and zero suspicious ignored
  files;
- `a3-tiny-six` reported axis sizes 2 and 3, six calculated jobs, concurrency
  3, and request SHA256
  `e1c69d04e31e5cea607271a1fa3bc38af81c96fca2e47a94e7ec989c851d098d`;
- two consecutive `a3-tiny-six` responses were byte-for-byte identical;
- `a3-existing-48` mechanically reported axis sizes `1 x 1 x 4 x 6 x 2`
  and 48 jobs, then returned exit code `2` for job-count, concurrency, core,
  memory, and wall-time ceiling violations;
- the unknown experiment and changed-commit requests returned exit code `2`
  with their specific mismatch details;
- unsupported partition and excessive-resource requests returned exit code
  `2` with explicit protected-limit violations;
- the empty-axis and missing-resources requests returned exit code `2` with
  precise structural errors;
- the protected audit tail contained all successful and rejected preview
  events, used helper version `0.4.0-a3`, and redacted request IDs as
  `<value>`;
- final independent status confirmed the automation checkout remained clean
  and unchanged at the exact A3 commit with no active run or update lock.

Gate conclusion: PASS. Preview selection is protected by request ID, exact
commit and tracked dependencies are verified remotely, job count is derived
from pinned axes, protected resource ceilings reject unsafe requests, repeated
previews are deterministic, and the complete path is audited without Git
mutation, Slurm access, run creation, repository-code execution, or transfer.

## A4 minimal Slurm submission candidate

Scheduler preflight reported by the user on lattice 2026-10-06:

- `sbatch` resolved to `/usr/bin/sbatch` and reported Slurm `25.11.4`;
- `sinfo` resolved to `/usr/bin/sinfo`;
- `cpu.q` was `up`, with a seven-day limit, `64+` CPUs, and `515100+` MB;
- the A4 request remains substantially below those values at one node, one
  core, 1 GB, and two minutes.

Candidate scope:

- local `hpc-submit` accepts only a protected request ID and writes a
  mandatory audit intent before opening SSH;
- `hpc-lethe-submit` requires a successful installed A3 preview and binds its
  digest, exact commit, result directory, job count, concurrency, output kind,
  and resources to fixed A4 policy;
- `run.json` and a per-run lock are created before grid submission;
- `hpc-grid-submit` writes a pending `submission.json` before its one fixed
  `/usr/bin/sbatch --parsable` call and persists the returned job ID;
- a submitted receipt or run record returns the existing job ID, while a
  pending or unknown receipt refuses a potentially duplicating retry;
- the immutable compute job writes four known log lines and an atomic
  `probe-result.json`; it does not execute repository simulation code.

Static verification 2026-10-06:

- all 14 Python candidate sources parsed with `ast.parse`, without import or
  execution;
- all 22 JSON, schema, configuration-example, and fixture files decoded;
- the A4 configuration, request, representative run record, and representative
  submission receipt passed their Draft 2020-12 schemas;
- independent fixture checks accepted only the documented parsable Slurm
  forms, confirmed a one-job request, matched the fixed resources, and bound
  the configured compute-job hash to the candidate source;
- every command block in `INSTALL_A4.md` passed `bash -n`;
- the four new helpers contain no `shell=True`, `os.system`, `Popen`, `eval`,
  or `exec` interface;
- no trailing whitespace or code lines longer than 88 characters were found;
- candidate helpers were not invoked, sourced, imported, or submitted.

Reviewed candidate SHA256 values:

- `hpc-submit`:
  `93c535091808a7c5d7115916e8632f9140bbaf001c55245933a553a3ea1d7e78`;
- `hpc_common.py`:
  `84e2aaae3658a613ad47648641869df61ec1a4a2442ea0c94ba35ec52242215c`;
- `hpc-lethe-submit`:
  `fbd00314ea61dab8740cfade961892522ef30b47770c5f1e6813e83d64711708`;
- `hpc-grid-submit`:
  `1825dc659160afafa0bb50f9123ad850619bbfd4f434a33cab314177e9c87787`;
- `hpc-grid-probe-job`:
  `39c5b55c293cf90fe62a450dc116aa328a379cdf0e423a1258076b6bc0424d44`;
- `remote-hpc-submit.json.example`:
  `fcad5d8ae33165899c394e5b433a07842fe80973e5d72fa16e00af61068ecf2c`;
- `preview-requests.json.example`:
  `8f1b41151940d9966f61e8ce5172accf9703391e7850d3389e0f15caab0c1d00`;
- `remote-hpc-submit-config.schema.json`:
  `661208e7bbabeecc2cbba17527c9cc3b1629c39ef9f833f7830b09baf3160aa7`;
- `submission-record.schema.json`:
  `08275824f920de7c500f2658091e4b42b8d8d0ec4b4c497a7e9bfb21671c1e9e`;
- `a4_submit_cases.json`:
  `35a3b53e9e4ae48f2c54147e10744604d3e852f6181fce5902d1cb7bbc0859b5`;
- expected installed local bundle:
  `cb1d52d6b5bcaac811cdf0c33e529f64d223549bf3044c43ef6cd13f27eb30ed`.

Gate conclusion: CANDIDATE READY, NOT YET PROMOTED OR TESTED. The next steps
are a scoped commit and push, exact A2 checkout update, manual promotion from
`INSTALL_A4.md`, protected read-only checks, and a separate explicit approval
before the one real Slurm submission.

### A4 first submission and correction

Promotion and protected pre-submission checks 2026-10-07:

- the local bundle reported exact version `0.5.0-a4` and SHA256
  `cb1d52d6b5bcaac811cdf0c33e529f64d223549bf3044c43ef6cd13f27eb30ed`;
- the automation checkout was clean at exact commit
  `ac889c679fb027d38b2c744513176340fdb6b64e`;
- all reported local and remote installed hashes matched the reviewed
  candidates, and reported protected modes matched the installation policy;
- malformed, unknown, traversal, and extra-argument submission forms all
  returned exit code `2` locally;
- the protected preview reported one fixed `cpu.q` job, one core, 1 GB, two
  minutes, and request digest
  `5b9f4ce1f54e4aa56a72088aa32d804fb9db875c5f613bd16df3d1b1b3dcfefa`;
- scheduler snapshots before and after preview contained no jobs.

The separately approved submission created exactly one Slurm job, `117689`.
Both durable records captured the same job ID and request digest before the
client received success. The job then ended `FAILED` with exit code `1:0` and
did not create `probe-result.json`. Its stderr was:

```text
Probe failed: Cannot inspect Submission configuration: [Errno 2] No such file or directory: '/var/spool/config/A1_OUinp-submit.json'
```

Root cause: `sbatch` executed its copied script beneath `/var/spool`, so the
compute script could not derive the shared helper root from `__file__`.
Submission, job-ID parsing, durable records, audit, and the no-duplicate
boundary behaved as designed. No retry or second job was attempted.

Correction candidate:

- the compute script now uses the fixed reviewed shared configuration path
  `/ddn/niknovikov19/hpc_codex/config/A1_OUinp-submit.json`;
- request `a4-slurm-probe-v2` supplies a fresh idempotency key while retaining
  the failed run and its evidence unchanged;
- the configuration allows only the corrected request ID and binds the new
  compute-script SHA256;
- AST, JSON-schema, installer-shell, fixed-path, request/resource, placeholder,
  and hash-binding checks passed without executing candidate code.

Corrected candidate SHA256 values:

- `hpc-grid-probe-job`:
  `174be04de6561b902f7d8a11ca516293ae35c05269847727181fd51a5f8dc2c8`;
- `remote-hpc-submit.json.example`:
  `d0b1aa7dba56af3c65c0f431b06ce0c84d0de059b20321658dd704945cea9530`;
- `preview-requests.json.example`:
  `a11062cb38dc28879d47595d0b317f59de50662a79b81b9a77cb3106bc9c22af`;
- `a4_submit_cases.json`:
  `6d35e2b514853770604eacc35899e4fe56644ae21e8c9a5a936590bc15e31876`.

Gate conclusion: CORRECTION READY, NOT PROMOTED. Job `117689` remains the
immutable failed first attempt. The corrected request must be committed,
pushed, promoted, previewed, and separately approved before submission.

### A4 shell-wrapper revision

The fixed-path correction commit `b13e823` was not promoted. Review of the
established launchers showed that repository Python files retain useful
`__file__` paths because Slurm spools a shell batch script, which then invokes
the original Python file from shared storage.

The revised candidate follows that structure:

- `hpc-grid-probe-job.sh` contains the seven fixed `#SBATCH` resource and
  export directives;
- `hpc-grid-submit` verifies the wrapper and Python payload hashes, requires
  the wrapper directives to exactly match protected configuration, and submits
  the wrapper with only protected job-name, log-path, working-directory, and
  optional-account command-line settings;
- the wrapper invokes the protected Python payload through its absolute shared
  path, so the payload once again derives the helper root from its original
  `__file__`;
- the protected request declares both wrapper and payload as tracked
  exact-commit dependencies;
- the remote submit helpers report version `0.5.1-a4`; the unchanged local
  bundle remains `0.5.0-a4`.

Static verification confirmed exact wrapper directives, shell syntax, Python
ASTs, JSON schemas, request/resource agreement, tracked-dependency declaration,
both configured file hashes, and absence of resource-allocation flags from the
constructed `sbatch` command. No candidate was executed or imported.

Final wrapper-based candidate SHA256 values:

- `hpc-lethe-submit`:
  `fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494`;
- `hpc-grid-submit`:
  `f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f`;
- `hpc-grid-probe-job`:
  `39c5b55c293cf90fe62a450dc116aa328a379cdf0e423a1258076b6bc0424d44`;
- `hpc-grid-probe-job.sh`:
  `fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665`;
- `remote-hpc-submit.json.example`:
  `064e86b2d99734b6f0f88d1031811dc872c5d78f7a19889009b4af473671423f`;
- `preview-requests.json.example`:
  `5b5beae245ee448093ea87aaadf9060260c43e7a7d9711b53194c3bd13fda711`;
- `remote-hpc-submit-config.schema.json`:
  `3fd2432071cc24ac1f615a1456fe018204c3b3438fc10438c7902790d248835a`;
- `a4_submit_cases.json`:
  `978b191c0be7496600631f27732a26677229f3310aad6fcd2de0225241e4381a`.

Gate conclusion: WRAPPER CORRECTION READY, NOT PROMOTED OR EXECUTED.

### A4 final wrapper promotion and protected test

Promotion and pre-submission checks 2026-10-08:

- local and remote promotion used exact commit
  `5b53fad6e8828bbef95026a4386cb7ad8cd5b5a3`;
- the local bundle reported version `0.5.0-a4` and SHA256
  `cb1d52d6b5bcaac811cdf0c33e529f64d223549bf3044c43ef6cd13f27eb30ed`;
- the generated protected request registry had SHA256
  `7ef2d02e126d5a40472a8d32113269178e9475c087a86816dff095ec18c5355d`;
- every installed local and remote artifact matched its reviewed candidate
  hash, and all helper, configuration, schema, run-root, state-root, and lock
  modes matched policy;
- the automation checkout was clean on `codex-hpc` at the exact commit, with
  no active run or update lock before submission;
- missing, unknown, traversal, and extra-argument submission forms were all
  rejected locally with exit code `2`;
- the protected preview reported one `cpu.q` job, one node, one core, 1 GB,
  two minutes, and request SHA256
  `01f5c42b28846f1ae243f45ff2cb1a32903ae28d54d49e45b3a2b4bdd14868ed`;
- bounded scheduler preflight reported empty `squeue` and recent `sacct`
  samples.

After separate explicit approval, the protected submit command created exactly
one Slurm job, `117706`. A second invocation returned `existing` with the same
job ID. The bounded scheduler probe then reported an empty `squeue` and
`117706|COMPLETED|0:0` from `sacct`.

The final exact-file report confirmed:

- `run.json`, `submission.json`, and `probe-result.json` agree on request ID,
  request SHA256, and job ID `117706`;
- `run.json` records the exact commit, fixed resources, and result directory;
- `submission.json` records parsable `sbatch` output `117706` and status
  `submitted`;
- `probe-result.json` records status `complete`, compute host `node02`, and the
  same request and job identities;
- stdout contains exactly the four expected probe lines and reports
  `marker=created`;
- stderr is empty, with the standard empty-file SHA256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- the run and controller directories are mode `0700`; JSON records are mode
  `0600`; Slurm logs are mode `0644` inside the inaccessible `0700` controller
  directory.

The protected audit tail contains one `submit-intent` event for each client
invocation, followed respectively by `submitted` and `existing`. The second
intent names an idempotent protected invocation, not a second scheduler call;
the durable receipt and scheduler evidence confirm that only one job existed.

Gate conclusion: PASS. A4 proved exact-commit preview binding, protected
resource and wrapper validation, durable intent-before-submit recording,
parsable job-ID capture, successful shell-wrapper execution on a compute node,
atomic result marking, fail-closed retry handling, and idempotent replay without
duplicate Slurm submission. Job `117689` remains the preserved failed first
attempt, and job `117706` is the successful wrapper-based completion.

## A5.1 completed-job monitoring candidate

Candidate scope 2026-10-08:

- local `hpc-status` accepts only a validated run ID or the fixed
  `--self-test` operation and appends a mandatory audit event;
- `hpc-lethe-status` resolves that ID beneath the fixed run root, rejects
  symlinked paths, and loads scheduler IDs only from `run.json`;
- `hpc-grid-status` accepts the bounded integer IDs from the lethe helper and
  performs one user-scoped `squeue` query for all IDs;
- IDs absent from `squeue` are passed together to at most one allocation-only
  `sacct` query with a fixed seven-day lookback;
- raw state, reason, and exit code are preserved beside normalized pending,
  running, completed, failed, cancelled, timeout, out-of-memory, or unknown
  state;
- absence from both scheduler responses is an accounting-gap `unknown` with a
  fixed 120-second retry recommendation, never an inferred failure;
- successful known observations atomically write `status.json` and reconcile
  `run.json.status`; unknown or unavailable state does not overwrite the run
  record;
- the protected fixture document is bound into configuration by SHA256 and the
  fixed self-test covers normalization, active/terminal parser output, and
  malformed rows without calling Slurm.

Static verification:

- all candidate Python files passed `ast.parse` without import or execution;
- all 26 JSON documents decoded, and the A5 configuration and representative
  status record passed their Draft 2020-12 schemas;
- an independent AST/literal fixture check confirmed all ten normalization
  cases and the eight-state vocabulary;
- both promotion scripts passed `bash -n` without execution;
- source review confirmed one `squeue` call for all recorded IDs, at most one
  `sacct` call for absent IDs, bounded output, fixed absolute scheduler paths,
  no log reads, no caller-provided paths, and no shell execution interface;
- no candidate helper was invoked, imported, sourced, or promoted.

Reviewed candidate SHA256 values:

- `hpc-status`:
  `dde49bb7b565adb96fb38b559e0cbbaa5eb8abbf5fc7353e5f72634871543cd0`;
- `hpc_common.py`:
  `e4b894a3b7e92585974d48ab6c4de87b77b3646665c20f6b9b730fa713432423`;
- `hpc-lethe-status`:
  `5f5f7ed374d35f9dd1e7d8dc163b276a84d8b86544b3f603d917f977e7171f83`;
- `hpc-grid-status`:
  `12cc75cf5355d8544cfba35e54dcc45e95c8043a4c401c7f8fa58679dfd82c9d`;
- `remote-hpc-status.json.example`:
  `3ccd72366ce7c3809edea0ed15b8acd87b5af8e1dcf856662798bacc76cac905`;
- `a5_status_cases.json`:
  `d0d9b5b2ffaa36b779ba78c8b42f825c57cbef42299acaa9de552de37b0b6840`;
- `remote-hpc-status-config.schema.json`:
  `fff824437f4b755b8fad896346c9ad53eae101add4b87a82031389551a189c75`;
- `status-record.schema.json`:
  `e29da82aa81c9cb62d9bb5f52f4b9201c3aae40c60eb9abe3672086e6a2e7ade`;
- expected installed local bundle:
  `ed3200ad97205464f86120ed0daf116cb73bb669b7d7c0c9615ce83c55f55d76`.

Gate conclusion: A5.1 CANDIDATE READY, NOT PROMOTED OR EXECUTED. First prove
parser fixtures and `sacct` fallback against completed A4 job `117706`. Only
then add and separately approve the A5.2 slow probe used to observe active and
accounting-gap lifecycle states.

### A5.1 first protected self-test and correction

Promotion of commit `c1f4d33ec9b1cbf79d0f02d66bd9785d52d57f13`
passed locally and on lethe. The first protected fixture call then failed with
exit code `4` before any scheduler query. The grid helper rejected the valid
shared status configuration because its runtime validator expected only the
grid-used top-level keys and treated the lethe-used `ssh`, `remote_helpers`,
and `runs` keys as unknown.

The correction makes `hpc-grid-status` validate the complete shared
configuration while continuing to use only its fixed scheduler, fixture, and
identity fields. Its component version is now `0.6.1-a5`; the corrected SHA256
is:

```text
dfab56a100baab8d06432f024ee0b57d6da786ef9e598479c4c0cbe8a65685a6  hpc-grid-status
```

The local `0.6.0-a5` bundle and other remote artifacts are unchanged. The
corrected remote helper must be promoted from a new exact commit before the
protected self-test is repeated.
