# A3 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Candidate files

Review these files before promotion:

- `local/hpc-run-preview`;
- updated `local/hpc_common.py` and `local/hpc_common.md`;
- `remote_lethe/hpc-lethe-preview`;
- `config_examples/remote-hpc-preview.json.example`;
- `config_examples/preview-requests.json.example`;
- `schemas/remote-hpc-preview-config.schema.json`;
- `schemas/run-request.schema.json`;
- `test_fixtures/a3_preview_cases.json`.

The preview path is read-only. It does not run repository Python, create a run
directory, update Git, invoke Slurm, or transfer files. The request catalog is
protected configuration and contains deliberate negative-test entries.

Reviewed candidate SHA256 values:

```text
e677e8afc2018c46f1994d58765de8278acbf66140b5e23bd8c94591610adf20  hpc-run-preview
97851c0a7f1cea91283b56e95e63b15b8ba1250464242d381797c65040dd93e6  hpc_common.py
483e6f085b703217cd40069f342801de33fe2cf52c5b3c03eec82b50cd523547  hpc-lethe-preview
2183dc0f0d31d69f91f95ecd2a479e7918a6e1f35c77406783f4a02aa4fa3c3e  remote-hpc-preview.json.example
738db5d5a032af0203aedf98da5fd5b9cf21f845af18021b69b636179548ace5  preview-requests.json.example
454eaa3b79da53749b4599a6d4bf3275ae8f136cca94d616a89875192c07c499  remote-hpc-preview-config.schema.json
4add2e162b8037fb25c50e4a82b567eabe48c9c48658b899a4ac83a6a2ccc975  run-request.schema.json
a2989f2e5ab9aa6afae5779e2c38c4401b4489f3184127b771a4cfefed692ad6  a3_preview_cases.json
```

With the four unchanged local entry points, the expected installed local
bundle SHA256 is:

```text
71b493bba432c9e1385140d42526c6705b030e11d55dd211fc1611fd72ee474c
```

## Commit and checkout prerequisite

Codex first commits and pushes the reviewed A3 source. Record that full commit
as `A3_COMMIT`. Update the automation checkout to exactly `A3_COMMIT` through
the already proven A2 helper, with separate approval, before running previews.

The example request catalog uses 40 zeroes as the placeholder for
`A3_COMMIT`. Replace every 40-zero value in the protected copy only. Do not
replace the 40-one value in `a3-changed-commit`; that entry deliberately tests
commit mismatch rejection.

## Local promotion

Manually copy the changed local files to:

```text
/opt/a1-hpc/bin/hpc-run-preview
/opt/a1-hpc/bin/hpc_common.py
/opt/a1-hpc/share/schemas/remote-hpc-preview-config.schema.json
/opt/a1-hpc/share/schemas/run-request.schema.json
```

Install `hpc-run-preview` with mode `0555` and the module and schemas with mode
`0444`. Copy `config_examples/preview-requests.json.example` to:

```text
/opt/a1-hpc/config/A1_OUinp-preview-requests.json
```

Replace the 40-zero placeholders with exact `A3_COMMIT`, review the resulting
JSON, and set it to mode `0444`. Restore the protected local `bin`, `config`,
and `share/schemas` directories to mode `0555`. Keep local audit-state
ownership and permissions unchanged.

## Remote promotion

Manually copy the lethe helper to:

```text
/ddn/niknovikov19/hpc_codex/helpers/lethe/hpc-lethe-preview
```

Install it with mode `0555`. Copy
`config_examples/remote-hpc-preview.json.example` to:

```text
/ddn/niknovikov19/hpc_codex/config/A1_OUinp-preview.json
```

Review every path, allowlist, and limit. They should agree with the existing
protected local configuration. Set the file to mode `0444`, then restore the
remote `helpers/lethe` and `config` directories to mode `0555`.

Neither configuration file may contain credentials, a repository URL, key
path, token, password, arbitrary command, or caller-selectable filesystem
root.

## Handoff to Codex

Report:

1. `A3_COMMIT` and confirmation that the automation checkout is clean at it.
2. SHA256 for installed `hpc-run-preview`, `hpc_common.py`,
   `hpc-lethe-preview`, `A1_OUinp-preview.json`, and the edited
   `A1_OUinp-preview-requests.json`.
3. Confirmation that executable files are mode `0555`, configuration and
   schema files are mode `0444`, and protected directories are mode `0555`.
4. Permission to run the read-only protected preview tests.

## Protected test order

Codex will:

1. verify the installed source and bundle identities;
2. reject malformed, unknown, traversal, and extra-argument request IDs
   locally without SSH;
3. preview `a3-probe-one` and confirm one job;
4. preview `a3-tiny-six` twice and confirm six jobs and identical output and
   request digest;
5. preview `a3-existing-48`, confirm 48 calculated jobs, and confirm rejection
   by the protected 10-job ceiling;
6. confirm rejection of the unknown experiment, changed commit, unsupported
   partition, excessive resources, empty axis, and malformed request;
7. verify tracked-dependency and bounded suspicious-ignored-file reporting;
8. inspect the protected audit tail and confirm no Git mutation, Slurm action,
   run-directory creation, or file transfer occurred.
