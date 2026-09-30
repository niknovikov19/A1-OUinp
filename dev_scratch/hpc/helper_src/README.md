# HPC helper candidate sources

This directory contains reviewable source candidates for protected HPC helper commands. Files here are not the live security boundary and must never be invoked or sourced in place.

## Promotion rule

For each capability:

1. Codex writes and reviews the candidate source here.
2. The user manually copies the required files to a protected directory outside Codex's write access.
3. The user reports the installed path and source hashes.
4. Codex tests only the protected installed command.

If a test fails, update the candidate, manually promote it again, and retest the installed copy. Never patch the installed copy through Codex.

## A0 contents

```text
local/hpc-helper-info
local/hpc_common.py
local/hpc_common.md
config_examples/hpc-helper.json.example
schemas/audit-event.schema.json
schemas/hpc-helper-config.schema.json
schemas/run.schema.json
test_fixtures/identifiers.json
INSTALL.md
```

`hpc-helper-info` has no SSH, Git mutation, Slurm, or file-transfer capability. It reports the installed source identity, validates the protected configuration, tests identifier validators, reads at most 20 prior audit events, and appends an audit event for every invocation.

## Exit codes

- `0`: success;
- `2`: rejected input;
- `3`: unavailable or unknown remote state, reserved for later gates;
- `4`: known helper or operation failure.
