# A1 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

The A1 test scope and end-to-end call chains are documented in `README.md`
under **A1 test scope** and **A1 call chains**.

## Candidate files

Review these files before promotion:

- `local/hpc-probe`;
- updated `local/hpc_common.py`;
- `remote_lethe/hpc-lethe-probe`;
- `remote_grid/hpc-grid-probe`;
- `config_examples/remote-hpc-probe.json.example`;
- `schemas/remote-hpc-probe-config.schema.json`.

The A1 candidates contain SSH and fixed read-only scheduler queries. They do
not contain Git mutation, Slurm submission or cancellation, log reading, file
transfer, or arbitrary remote-command interfaces.

Reviewed candidate SHA256 values:

```text
44f692483c3bd0f6ce4f8ff021e9c9df31e3cc8fb88983b915f4bd564192f867  hpc-probe
4b4cd381260d94ba18395d29e695b51128943c3009b537503ed342ca37d2bcfe  hpc_common.py
81fc1129913b2e89b7cc4ee2208bc3b0688d6632a4e22decda518d5234297499  hpc-lethe-probe
66578e0a511e7916006ed532c7feff3dbf6452576a704aee4649b29b15e86375  hpc-grid-probe
31fd5a3576c2aca42bbc173e9eca561d61f1af6984727fa31a2d2acbae0ba9fc  remote-hpc-probe.json.example
ff05fbcfc5a4a265808be0fdf5ecec5371a91b9c61e975b3b9d455acc3aa1ae5  remote-hpc-probe-config.schema.json
```

With the unchanged `hpc-helper-info`, the expected installed local bundle
SHA256 is:

```text
bd7b025379c6208f7747ea7b485f9a9cf936a273ecd4a54b1c7d9ecc2eef278b
```

## Local promotion

Manually copy the updated local files to:

```text
/opt/a1-hpc/bin/hpc-probe
/opt/a1-hpc/bin/hpc_common.py
/opt/a1-hpc/share/schemas/remote-hpc-probe-config.schema.json
```

Use modes `0555`, `0444`, and `0444`, respectively. Keep
`hpc-helper-info` installed; its source is unchanged, but it imports the new
bundle version and now includes `hpc-probe` in the reported bundle identity.

Confirm that `/opt/a1-hpc/config/hpc-helper.json` contains:

```json
"grid_host_alias": "lattice"
```

Restore the local protected directories to mode `0555` after promotion. Keep
`/opt/a1-hpc/state` owned by `nnovikov`, mode `0700`, and keep
`actions.jsonl` mode `0600`.

## Remote promotion

Manually copy the remote helpers to the shared filesystem:

```text
/ddn/niknovikov19/hpc_codex/helpers/lethe/hpc-lethe-probe
/ddn/niknovikov19/hpc_codex/helpers/grid/hpc-grid-probe
```

Install both helper files with mode `0555`. Their shebang pins the preflighted
Python interpreter:

```text
/ddn/niknovikov19/miniconda3/bin/python3
```

Copy `config_examples/remote-hpc-probe.json.example` to:

```text
/ddn/niknovikov19/hpc_codex/config/A1_OUinp.json
```

Review every value, then set the file to mode `0444`. It must contain no
credentials, key paths, tokens, or passwords. Set `helpers/lethe`,
`helpers/grid`, and `config` to mode `0555` after promotion. The project
`state` and `runs` directories remain writable by `niknovikov19`.

The shared filesystem means the same installed grid helper and configuration
paths are visible from lethe and lattice. This is expected; the helper roles
remain separate because only the lattice-side helper contains Slurm queries.

## Handoff to Codex

Report:

1. SHA256 for installed `hpc-probe`, `hpc_common.py`, `hpc-lethe-probe`,
   `hpc-grid-probe`, and `A1_OUinp.json`.
2. Confirmation that local and remote code/config files are read-only.
3. Confirmation that the local configuration uses the `lattice` SSH alias.
4. Permission to execute `/opt/a1-hpc/bin/hpc-probe`.

Codex will test only the protected local command. It will first verify bundle
identity, then probe lethe and grid, exercise rejected arguments, confirm
`unknown` handling where safely reproducible, and inspect the local audit log.
