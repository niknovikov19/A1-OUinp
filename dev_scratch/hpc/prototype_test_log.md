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
