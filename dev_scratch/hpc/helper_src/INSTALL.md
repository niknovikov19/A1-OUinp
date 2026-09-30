# A0 manual promotion and test handoff

These instructions are for the user. Codex must not run the candidate from `helper_src` or perform the protected installation.

## Protected layout

Choose an absolute `A1_HPC_PROTECTED_ROOT` outside Codex's writable workspace. The installed layout is:

```text
<A1_HPC_PROTECTED_ROOT>/
    bin/
        hpc-helper-info
        hpc_common.py
    config/
        hpc-helper.json
    state/
        actions.jsonl
    share/schemas/
        audit-event.schema.json
        hpc-helper-config.schema.json
        run.schema.json
```

The code and configuration directories must not be writable by Codex. The helper needs append access to `state/actions.jsonl`; the state directory remains outside the Codex filesystem sandbox.

## Files to review before promotion

- `local/hpc-helper-info`
- `local/hpc_common.py`
- `config_examples/hpc-helper.json.example`
- all files under `schemas/`

The A0 command contains no SSH, Git mutation, Slurm, or transfer operation.

## Manual promotion outline

Run the equivalent operations yourself, substituting your protected root and the actual candidate-source path:

```bash
export A1_HPC_PROTECTED_ROOT=/absolute/protected/a1-hpc
mkdir -p "$A1_HPC_PROTECTED_ROOT/bin"
mkdir -p "$A1_HPC_PROTECTED_ROOT/config"
mkdir -p "$A1_HPC_PROTECTED_ROOT/state"
mkdir -p "$A1_HPC_PROTECTED_ROOT/share/schemas"

install -m 0555 local/hpc-helper-info "$A1_HPC_PROTECTED_ROOT/bin/hpc-helper-info"
install -m 0444 local/hpc_common.py "$A1_HPC_PROTECTED_ROOT/bin/hpc_common.py"
install -m 0444 schemas/*.schema.json "$A1_HPC_PROTECTED_ROOT/share/schemas/"
install -m 0444 config_examples/hpc-helper.json.example "$A1_HPC_PROTECTED_ROOT/config/hpc-helper.json"
touch "$A1_HPC_PROTECTED_ROOT/state/actions.jsonl"
chmod 0600 "$A1_HPC_PROTECTED_ROOT/state/actions.jsonl"
```

The `state` directory and `actions.jsonl` must be owned by the local account
that invokes the helper. Code, configuration, and schemas should remain owned
by the protecting account. For example, when the helper runs as `nnovikov`:

```bash
chown nnovikov:nnovikov "$A1_HPC_PROTECTED_ROOT/state"
chown nnovikov:nnovikov "$A1_HPC_PROTECTED_ROOT/state/actions.jsonl"
```

Edit only the protected `config/hpc-helper.json` and verify:

- `branch` is `codex-hpc`;
- automation and manual checkout paths are different;
- the automation run root is intentional;
- host aliases match the user's SSH configuration;
- remote helper directories are outside both Git checkouts;
- scheduler user/account, partitions, and ceilings are correct;
- no credentials, private-key paths, tokens, or passwords are present.

After editing, make the configuration non-writable:

```bash
chmod 0444 "$A1_HPC_PROTECTED_ROOT/config/hpc-helper.json"
chmod 0700 "$A1_HPC_PROTECTED_ROOT/state"
chmod 0555 "$A1_HPC_PROTECTED_ROOT/bin"
chmod 0555 "$A1_HPC_PROTECTED_ROOT/config"
chmod 0555 "$A1_HPC_PROTECTED_ROOT/share/schemas"
chmod 0555 "$A1_HPC_PROTECTED_ROOT/share"
chmod 0555 "$A1_HPC_PROTECTED_ROOT"
```

Apply stronger ownership or ACL restrictions if that is how the protected directory is kept outside Codex's write access. Do not add the protected root to the repository workspace.

## Handoff to Codex

Report:

1. The absolute installed path to `hpc-helper-info`.
2. The SHA256 values of installed `hpc-helper-info` and `hpc_common.py`.
3. Whether the example values in the protected config were changed and reviewed.
4. Whether Codex should request approval to execute that exact installed command prefix.

Codex will then test only the installed command, in this order:

```text
hpc-helper-info version
hpc-helper-info info
hpc-helper-info validate <kind> <valid fixture>
hpc-helper-info validate <kind> <invalid fixture>
hpc-helper-info <unsupported arguments>
hpc-helper-info audit-tail
```

The A0 gate passes only when the installed hashes are known, the config validates, valid identifiers pass, invalid identifiers return exit code 2, and `audit-tail` shows the preceding successes and rejections.
