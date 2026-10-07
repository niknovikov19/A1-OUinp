# A4 manual promotion and test handoff

These instructions are for the user. Codex must not execute candidates from
`helper_src` or install them into protected local or remote locations.

## Capability and boundary

A4 submits only the protected `a4-slurm-probe-v2` request. The resulting Slurm
job writes a fixed JSON marker and four known log lines. It does not import or
execute repository simulation code.

The submitted resources are fixed at one `cpu.q` node, one task, one core,
1 GB, and two minutes. Caller-controlled commands, paths, hosts, scheduler
options, resources, environments, and request bodies are not accepted.

The first promoted probe, request `a4-slurm-probe`, was safely submitted as
job `117689` but failed before writing its marker. Slurm ran a spooled copy
under `/var/spool`, so deriving the protected configuration from `__file__`
produced the wrong path. The corrected compute script uses the reviewed fixed
shared configuration path. Request `a4-slurm-probe-v2` preserves the failed
run and receipt while providing a fresh idempotency key for the corrected
test. Do not delete or alter the original run directory.

Reviewed candidate SHA256 values:

```text
93c535091808a7c5d7115916e8632f9140bbaf001c55245933a553a3ea1d7e78  hpc-submit
84e2aaae3658a613ad47648641869df61ec1a4a2442ea0c94ba35ec52242215c  hpc_common.py
fbd00314ea61dab8740cfade961892522ef30b47770c5f1e6813e83d64711708  hpc-lethe-submit
1825dc659160afafa0bb50f9123ad850619bbfd4f434a33cab314177e9c87787  hpc-grid-submit
174be04de6561b902f7d8a11ca516293ae35c05269847727181fd51a5f8dc2c8  hpc-grid-probe-job
d0b1aa7dba56af3c65c0f431b06ce0c84d0de059b20321658dd704945cea9530  remote-hpc-submit.json.example
a11062cb38dc28879d47595d0b317f59de50662a79b81b9a77cb3106bc9c22af  preview-requests.json.example
661208e7bbabeecc2cbba17527c9cc3b1629c39ef9f833f7830b09baf3160aa7  remote-hpc-submit-config.schema.json
08275824f920de7c500f2658091e4b42b8d8d0ec4b4c497a7e9bfb21671c1e9e  submission-record.schema.json
6d35e2b514853770604eacc35899e4fe56644ae21e8c9a5a936590bc15e31876  a4_submit_cases.json
```

The expected installed local bundle version is `0.5.0-a4`, with SHA256:

```text
cb1d52d6b5bcaac811cdf0c33e529f64d223549bf3044c43ef6cd13f27eb30ed
```

## Commit and checkout prerequisite

Codex first commits and pushes the reviewed A4 source. Record the full commit
as `A4_COMMIT`. With separate approval, update the automation checkout to
exactly that commit through the proven A2 helper:

```bash
/opt/a1-hpc/bin/hpc-code-update --json "$A4_COMMIT"
```

Do not promote remote files until `hpc-code-status --json` reports a clean
`codex-hpc` checkout whose local and remote commits both equal `A4_COMMIT`.

## Local promotion

Run this section in the local WSL shell. Local protected installation needs
`sudo` because `/opt/a1-hpc` is owned by `root:root`.

```bash
A4_COMMIT='<full 40-character commit reported by Codex>'
A4_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A4_SRC="$A4_LOCAL_REPO/dev_scratch/hpc/helper_src"
A4_REGISTRY_TMP=$(mktemp)

printf '%s\n' "$A4_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -C "$A4_LOCAL_REPO" rev-parse HEAD)" = "$A4_COMMIT"

sha256sum \
    "$A4_SRC/local/hpc-submit" \
    "$A4_SRC/local/hpc_common.py" \
    "$A4_SRC/schemas/remote-hpc-submit-config.schema.json" \
    "$A4_SRC/schemas/submission-record.schema.json" \
    "$A4_SRC/config_examples/preview-requests.json.example"
```

Generate the protected request registry. This replaces the nine 40-zero
commit placeholders and preserves the deliberate 40-one A3 rejection case:

```bash
sed "s/0000000000000000000000000000000000000000/$A4_COMMIT/g" \
    "$A4_SRC/config_examples/preview-requests.json.example" \
    > "$A4_REGISTRY_TMP"

python3 -m json.tool "$A4_REGISTRY_TMP" >/dev/null
test "$(grep -c "\"expected_commit\": \"$A4_COMMIT\"" \
    "$A4_REGISTRY_TMP")" -eq 9
test "$(grep -c \
    '"expected_commit": "1111111111111111111111111111111111111111"' \
    "$A4_REGISTRY_TMP")" -eq 1
sha256sum "$A4_REGISTRY_TMP"
```

Review the generated registry, then install the local candidates. If an
install fails, restore the three directory modes to `0555` before stopping.

```bash
python3 -m json.tool "$A4_REGISTRY_TMP"

sudo chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas

sudo install -o root -g root -m 0555 \
    "$A4_SRC/local/hpc-submit" \
    /opt/a1-hpc/bin/hpc-submit

sudo install -o root -g root -m 0444 \
    "$A4_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py

sudo install -o root -g root -m 0444 \
    "$A4_SRC/schemas/remote-hpc-submit-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-submit-config.schema.json

sudo install -o root -g root -m 0444 \
    "$A4_SRC/schemas/submission-record.schema.json" \
    /opt/a1-hpc/share/schemas/submission-record.schema.json

sudo install -o root -g root -m 0444 \
    "$A4_REGISTRY_TMP" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

sudo chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas
```

Verify the installed hashes and modes, then remove the temporary registry:

```bash
/opt/a1-hpc/bin/hpc-helper-info --json info

sha256sum \
    /opt/a1-hpc/bin/hpc-submit \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-submit-config.schema.json \
    /opt/a1-hpc/share/schemas/submission-record.schema.json \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-submit \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

rm -f "$A4_REGISTRY_TMP"
unset A4_REGISTRY_TMP
```

Do not change `/opt/a1-hpc/state` or `actions.jsonl` ownership or modes.

## Remote promotion

Log in to lethe as `niknovikov19`. Remote promotion uses the owning account;
`sudo` is neither needed nor expected.

```bash
A4_COMMIT='<same full 40-character commit>'
A4_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A4_SRC="$A4_REMOTE_REPO/dev_scratch/hpc/helper_src"
A4_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A4_REMOTE_OWNER=niknovikov19
A4_REMOTE_GROUP=salvadord

printf '%s\n' "$A4_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -C "$A4_REMOTE_REPO" rev-parse HEAD)" = "$A4_COMMIT"
test -z "$(git -C "$A4_REMOTE_REPO" status --porcelain=v1)"

test "$(id -un)" = "$A4_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A4_REMOTE_GROUP"

python3 -m json.tool \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example" \
    >/dev/null

sha256sum \
    "$A4_SRC/remote_lethe/hpc-lethe-submit" \
    "$A4_SRC/remote_grid/hpc-grid-submit" \
    "$A4_SRC/remote_grid/hpc-grid-probe-job" \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example"
```

Review every value in the configuration. It must contain no credential,
repository URL, private-key path, token, or password:

```bash
python3 -m json.tool \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example"
```

Confirm the existing shared roots are owned by the expected account and
group. Tightening the run and state project roots to `0700` still allows both
lethe and lattice to use them because the shared filesystem presents the same
user identity on both hosts.

```bash
for A4_PATH in \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config" \
    "$A4_REMOTE_ROOT/runs/A1_OUinp" \
    "$A4_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A4_PATH")" = "$A4_REMOTE_OWNER"
    test "$(stat -c '%G' "$A4_PATH")" = "$A4_REMOTE_GROUP"
done

chmod 0755 \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config"

install -g "$A4_REMOTE_GROUP" -m 0555 \
    "$A4_SRC/remote_lethe/hpc-lethe-submit" \
    "$A4_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit"

install -g "$A4_REMOTE_GROUP" -m 0555 \
    "$A4_SRC/remote_grid/hpc-grid-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-submit"

install -g "$A4_REMOTE_GROUP" -m 0555 \
    "$A4_SRC/remote_grid/hpc-grid-probe-job" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"

install -g "$A4_REMOTE_GROUP" -m 0444 \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example" \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json"

if test ! -e "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"; then
    install -g "$A4_REMOTE_GROUP" -m 0600 /dev/null \
        "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"
fi
test -f "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"
chmod 0600 "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"

chmod 0700 \
    "$A4_REMOTE_ROOT/runs/A1_OUinp" \
    "$A4_REMOTE_ROOT/state/A1_OUinp"

chmod 0555 \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config"
```

If an install fails, restore the helper and configuration directories to
`0555` before stopping. Do not pre-create the `a4-slurm-probe-v2` run directory;
the helper must prove that it can create the durable record before `sbatch`.

Verify the protected remote copies:

```bash
python3 -m json.tool \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    >/dev/null

sha256sum \
    "$A4_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job" \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json"

stat -c '%A %a %U:%G %n' \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config" \
    "$A4_REMOTE_ROOT/runs/A1_OUinp" \
    "$A4_REMOTE_ROOT/state/A1_OUinp" \
    "$A4_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job" \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"
```

## Handoff to Codex

Report:

1. `A4_COMMIT` and a clean exact automation checkout.
2. All four installed remote hashes, the installed local `hpc-submit` and
   `hpc_common.py` hashes, the generated request-registry hash, and the local
   bundle identity.
3. Confirmation of `0555` helper/configuration directories, `0555` helpers,
   `0444` configurations/schemas, `0700` remote run/state project roots, and
   the `0600` submission lock.
4. Permission for read-only protected rejection and preview checks.

After those checks pass, Codex will separately request explicit approval for
the one real Slurm submission. Approval to test or inspect A4 is not approval
to submit.

## Protected test order

Codex will:

1. verify installed identities, modes, exact commit, and clean checkout;
2. reject malformed, unknown, traversal, and extra-argument request IDs
   locally without SSH or Slurm;
3. run the protected A3 preview of `a4-slurm-probe-v2` and confirm the fixed
   one-job policy;
4. stop and request explicit approval for the Slurm mutation;
5. after approval, run exactly
   `/opt/a1-hpc/bin/hpc-submit --json a4-slurm-probe-v2`;
6. repeat the same command and require the same job ID with result `existing`;
7. use the existing protected grid probe for bounded `squeue`/`sacct`
   evidence and ask the user to report the protected run files if needed;
8. inspect the local audit tail and confirm one submission intent plus the
   submitted and idempotent results.
