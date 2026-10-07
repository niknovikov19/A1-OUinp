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

Run these commands in the local WSL shell after Codex reports the final pushed
`A3_COMMIT`. Replace the value on the first line before running anything:

```bash
A3_COMMIT='<full 40-character commit reported by Codex>'
A3_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A3_SRC="$A3_LOCAL_REPO/dev_scratch/hpc/helper_src"
A3_CATALOG_TMP=$(mktemp)

printf '%s\n' "$A3_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -C "$A3_LOCAL_REPO" rev-parse HEAD)" = "$A3_COMMIT"

sha256sum \
    "$A3_SRC/local/hpc-run-preview" \
    "$A3_SRC/local/hpc_common.py" \
    "$A3_SRC/schemas/remote-hpc-preview-config.schema.json" \
    "$A3_SRC/schemas/run-request.schema.json" \
    "$A3_SRC/config_examples/preview-requests.json.example"
```

Create the protected catalog in a temporary file. This replaces only the
40-zero placeholder; the deliberate 40-one changed-commit fixture remains
unchanged:

```bash
sed "s/0000000000000000000000000000000000000000/$A3_COMMIT/g" \
    "$A3_SRC/config_examples/preview-requests.json.example" \
    > "$A3_CATALOG_TMP"

python3 -m json.tool "$A3_CATALOG_TMP" >/dev/null
test "$(grep -c "\"expected_commit\": \"$A3_COMMIT\"" "$A3_CATALOG_TMP")" -eq 8
test "$(grep -c '"expected_commit": "1111111111111111111111111111111111111111"' "$A3_CATALOG_TMP")" -eq 1
sha256sum "$A3_CATALOG_TMP"
```

Install the files as `root:root`. The first `chmod` makes only root able to
write because the directories remain root-owned. If any install command fails,
run the final `chmod 0555` command before stopping:

```bash
sudo chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas

sudo install -o root -g root -m 0555 \
    "$A3_SRC/local/hpc-run-preview" \
    /opt/a1-hpc/bin/hpc-run-preview

sudo install -o root -g root -m 0444 \
    "$A3_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py

sudo install -o root -g root -m 0444 \
    "$A3_SRC/schemas/remote-hpc-preview-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-preview-config.schema.json

sudo install -o root -g root -m 0444 \
    "$A3_SRC/schemas/run-request.schema.json" \
    /opt/a1-hpc/share/schemas/run-request.schema.json

sudo install -o root -g root -m 0444 \
    "$A3_CATALOG_TMP" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

sudo chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas
```

Verify the installed hashes and modes before removing the temporary file:

```bash
sha256sum \
    /opt/a1-hpc/bin/hpc-run-preview \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-preview-config.schema.json \
    /opt/a1-hpc/share/schemas/run-request.schema.json \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-run-preview \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

rm -f "$A3_CATALOG_TMP"
unset A3_CATALOG_TMP
```

Do not change `/opt/a1-hpc/state` or `actions.jsonl` ownership or modes.

## Remote promotion

First update the automation checkout to exact `A3_COMMIT` through the approved
A2 helper. Then log in to lethe and run the following commands. Set
`A3_COMMIT` to the same final commit:

```bash
A3_COMMIT='<same full 40-character commit>'
A3_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A3_SRC="$A3_REMOTE_REPO/dev_scratch/hpc/helper_src"
A3_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A3_REMOTE_OWNER=niknovikov19
A3_REMOTE_GROUP=salvadord

printf '%s\n' "$A3_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -C "$A3_REMOTE_REPO" rev-parse HEAD)" = "$A3_COMMIT"
test -z "$(git -C "$A3_REMOTE_REPO" status --porcelain=v1)"

test "$(stat -c '%U' "$A3_REMOTE_ROOT/helpers/lethe")" = "$A3_REMOTE_OWNER"
test "$(stat -c '%G' "$A3_REMOTE_ROOT/helpers/lethe")" = "$A3_REMOTE_GROUP"
test "$(stat -c '%U' "$A3_REMOTE_ROOT/config")" = "$A3_REMOTE_OWNER"
test "$(stat -c '%G' "$A3_REMOTE_ROOT/config")" = "$A3_REMOTE_GROUP"
test "$(id -un)" = "$A3_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A3_REMOTE_GROUP"

python3 -m json.tool \
    "$A3_SRC/config_examples/remote-hpc-preview.json.example" \
    >/dev/null

sha256sum \
    "$A3_SRC/remote_lethe/hpc-lethe-preview" \
    "$A3_SRC/config_examples/remote-hpc-preview.json.example"
```

Review the displayed source configuration before installation:

```bash
python3 -m json.tool \
    "$A3_SRC/config_examples/remote-hpc-preview.json.example"
```

Install as the owning lethe account; `sudo` is neither needed nor expected.
The account already owns both directories and belongs to the established
shared-filesystem group. If an install command fails, run the final
`chmod 0555` command before stopping:

```bash
chmod 0755 \
    "$A3_REMOTE_ROOT/helpers/lethe" \
    "$A3_REMOTE_ROOT/config"

install \
    -g "$A3_REMOTE_GROUP" \
    -m 0555 \
    "$A3_SRC/remote_lethe/hpc-lethe-preview" \
    "$A3_REMOTE_ROOT/helpers/lethe/hpc-lethe-preview"

install \
    -g "$A3_REMOTE_GROUP" \
    -m 0444 \
    "$A3_SRC/config_examples/remote-hpc-preview.json.example" \
    "$A3_REMOTE_ROOT/config/A1_OUinp-preview.json"

chmod 0555 \
    "$A3_REMOTE_ROOT/helpers/lethe" \
    "$A3_REMOTE_ROOT/config"
```

Verify the protected copies:

```bash
python3 -m json.tool \
    "$A3_REMOTE_ROOT/config/A1_OUinp-preview.json" \
    >/dev/null

sha256sum \
    "$A3_REMOTE_ROOT/helpers/lethe/hpc-lethe-preview" \
    "$A3_REMOTE_ROOT/config/A1_OUinp-preview.json"

stat -c '%A %a %U:%G %n' \
    "$A3_REMOTE_ROOT/helpers/lethe" \
    "$A3_REMOTE_ROOT/config" \
    "$A3_REMOTE_ROOT/helpers/lethe/hpc-lethe-preview" \
    "$A3_REMOTE_ROOT/config/A1_OUinp-preview.json"
```

The helper hash must match the reviewed candidate. The installed remote
configuration hash must match the example because no substitution is needed.

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
