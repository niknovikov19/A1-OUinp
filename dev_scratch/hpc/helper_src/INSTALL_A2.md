# A2 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Candidate files

Review these files before promotion:

- `local/hpc-code-status`;
- `local/hpc-code-update`;
- updated `local/hpc_common.py`;
- `remote_lethe/hpc-lethe-code`;
- `config_examples/remote-hpc-code.json.example`;
- `schemas/remote-hpc-code-config.schema.json`;
- `schemas/code-update-record.schema.json`.

The status helper performs only fixed reads. The update helper can fetch the
configured `codex-hpc` branch and fast-forward only the configured automation
checkout after exact-commit, cleanliness, branch, active-run, and lock checks.
It cannot select a path, branch, remote, or Git operation supplied by a caller.

Reviewed candidate SHA256 values:

```text
dd51bb1a57124d6fbdb56cbac0f5315565b2a68cdc6096cf7f70b164edb16226  hpc-code-status
bfb151d5069ee269ac4d37939ac4aa8a5fdd04c95d42d74c471fa9c54b70c254  hpc-code-update
9237a884629f0061bb5cc079c48e7faa7cbb5be712534669451f6658a48fd7ce  hpc_common.py
cdf26a3bab06ea5ca43a50c8efaca8869100ae7be12d6fc304b5a25e86269d87  hpc-lethe-code
d3244b0d9e686791fc40c0b8e690dc9b55363c543f586c0ded7cd9fdd6ae3507  remote-hpc-code.json.example
4cfb4f81b15654eddb4871c3f5cd6c032e8e8559f279a17477445d904056c543  remote-hpc-code-config.schema.json
2819e23a8c9b88313f962be3a151a1dd62119b69c45e4307c2341d8f7a9d4490  code-update-record.schema.json
```

With the unchanged `hpc-helper-info` and `hpc-probe`, the expected installed
local bundle SHA256 is:

```text
b49d5aa7790739563856b9e6316004a306b4550658d383bbec7f41cfb37421eb
```

## Local promotion

Manually copy the updated local files to:

```text
/opt/a1-hpc/bin/hpc-code-status
/opt/a1-hpc/bin/hpc-code-update
/opt/a1-hpc/bin/hpc_common.py
/opt/a1-hpc/share/schemas/remote-hpc-code-config.schema.json
/opt/a1-hpc/share/schemas/code-update-record.schema.json
```

Use mode `0555` for both entry points and `0444` for the module and schemas.
Keep the installed `hpc-helper-info` and `hpc-probe`; their source is unchanged.
Restore the local protected directories to mode `0555` after promotion. Keep
the local audit state permissions unchanged.

## Remote promotion

Manually copy the lethe helper to:

```text
/ddn/niknovikov19/hpc_codex/helpers/lethe/hpc-lethe-code
```

Install it with mode `0555`. Copy
`config_examples/remote-hpc-code.json.example` to:

```text
/ddn/niknovikov19/hpc_codex/config/A1_OUinp-code.json
```

Review every value, then set the remote code configuration to mode `0444`.
It must contain no credentials, repository URL, key path, token, or password.
Restore the remote `helpers/lethe` and `config` directories to mode `0555`.

Pre-create the fixed update-lock file as the HPC account:

```bash
touch /ddn/niknovikov19/hpc_codex/state/A1_OUinp/code-update.lock
chmod 0600 /ddn/niknovikov19/hpc_codex/state/A1_OUinp/code-update.lock
```

The state directory remains owned and writable by `niknovikov19`. Do not
create `active-run.json`; its presence is reserved for an actual active run.
The helper creates and atomically replaces `last-code-update.json` during an
approved update attempt.

## Handoff to Codex

Report:

1. SHA256 for installed `hpc-code-status`, `hpc-code-update`,
   `hpc_common.py`, `hpc-lethe-code`, and `A1_OUinp-code.json`.
2. Confirmation that code and configuration files are read-only.
3. Confirmation that `code-update.lock` exists with mode `0600`.
4. Permission to execute `/opt/a1-hpc/bin/hpc-code-status`.

Do not grant persistent approval for `hpc-code-update`. Each state-changing
test invocation requires explicit approval for the exact protected command.

## Protected test order

Codex will:

1. verify the installed local bundle identity;
2. read status and confirm the clean baseline commit;
3. reject malformed hashes locally without SSH;
4. create a scoped local commit containing only reviewed HPC prototype files;
5. push that exact commit only after explicit approval;
6. read status again before any remote update;
7. invoke one exact-commit update only after explicit approval;
8. confirm the exact clean commit and repeat the update as a no-op;
9. exercise unknown-hash and dirty-checkout rejection safely;
10. test non-fast-forward policy with a disposable fixture rather than
    diverging the real automation checkout.
