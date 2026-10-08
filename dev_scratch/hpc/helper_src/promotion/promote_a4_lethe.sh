#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A4_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A4_REPORT_DIR="$A4_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$A4_REPORT_DIR"
chmod 0700 "$A4_REPORT_DIR"
A4_REPORT=$(mktemp "$A4_REPORT_DIR/a4-remote-promotion.XXXXXX.txt")
chmod 0600 "$A4_REPORT"
exec > >(tee "$A4_REPORT") 2>&1

A4_REMOTE_DIRS_OPEN=0

a4_cleanup() {
    local a4_rc=$?

    set +e
    if test "$A4_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$A4_REMOTE_ROOT/helpers/lethe" \
            "$A4_REMOTE_ROOT/helpers/grid" \
            "$A4_REMOTE_ROOT/config"
    fi

    if test "$a4_rc" -eq 0; then
        printf '\nA4_RESULT=PASS\n'
    else
        printf '\nA4_RESULT=FAIL exit_code=%s\n' "$a4_rc"
    fi
    printf 'A4_REPORT=%s\n' "$A4_REPORT"
    chmod 0600 "$A4_REPORT"
    trap - EXIT
    exit "$a4_rc"
}

a4_check_sha256() {
    local a4_expected=$1
    local a4_path=$2
    local a4_actual

    a4_actual=$(sha256sum "$a4_path")
    a4_actual=${a4_actual%% *}
    printf '%s  %s\n' "$a4_actual" "$a4_path"
    test "$a4_actual" = "$a4_expected"
}

trap a4_cleanup EXIT

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
A4_COMMIT=$1
A4_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A4_SRC="$A4_REMOTE_REPO/dev_scratch/hpc/helper_src"
A4_REMOTE_OWNER=niknovikov19
A4_REMOTE_GROUP=salvadord

printf 'A4 promotion: lethe\n'
printf 'A4 commit: %s\n' "$A4_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A4_REPORT"

printf '%s\n' "$A4_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$A4_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A4_REMOTE_GROUP"
test "$(git -C "$A4_REMOTE_REPO" rev-parse HEAD)" = "$A4_COMMIT"
test "$(git -C "$A4_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$A4_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret protected configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example"
if grep -Eiq \
    'password|token|private[_-]?key|key[_-]?path|repository[_-]?url|repo[_-]?url|https?://|ssh://|git@' \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every reviewed remote source artifact
printf '\n== Reviewed source hashes ==\n'
a4_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A4_SRC/remote_lethe/hpc-lethe-submit"
a4_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A4_SRC/remote_grid/hpc-grid-submit"
a4_check_sha256 \
    '39c5b55c293cf90fe62a450dc116aa328a379cdf0e423a1258076b6bc0424d44' \
    "$A4_SRC/remote_grid/hpc-grid-probe-job"
a4_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A4_SRC/remote_grid/hpc-grid-probe-job.sh"
a4_check_sha256 \
    '064e86b2d99734b6f0f88d1031811dc872c5d78f7a19889009b4af473671423f' \
    "$A4_SRC/config_examples/remote-hpc-submit.json.example"

# Confirm existing shared-path ownership before changing modes
printf '\n== Existing shared roots ==\n'
for A4_PATH in \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config" \
    "$A4_REMOTE_ROOT/runs/A1_OUinp" \
    "$A4_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A4_PATH")" = "$A4_REMOTE_OWNER"
    test "$(stat -c '%G' "$A4_PATH")" = "$A4_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$A4_PATH"
done

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A4_REMOTE_DIRS_OPEN=1
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
install -g "$A4_REMOTE_GROUP" -m 0555 \
    "$A4_SRC/remote_grid/hpc-grid-probe-job.sh" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh"
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
A4_REMOTE_DIRS_OPEN=0

# Verify the installed files and permissions
printf '\n== Installed hashes ==\n'
python3 -m json.tool \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    >/dev/null
a4_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A4_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit"
a4_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-submit"
a4_check_sha256 \
    '39c5b55c293cf90fe62a450dc116aa328a379cdf0e423a1258076b6bc0424d44' \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"
a4_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh"
a4_check_sha256 \
    '064e86b2d99734b6f0f88d1031811dc872c5d78f7a19889009b4af473671423f' \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$A4_REMOTE_ROOT/helpers/lethe" \
    "$A4_REMOTE_ROOT/helpers/grid" \
    "$A4_REMOTE_ROOT/config" \
    "$A4_REMOTE_ROOT/runs/A1_OUinp" \
    "$A4_REMOTE_ROOT/state/A1_OUinp" \
    "$A4_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-submit" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job" \
    "$A4_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh" \
    "$A4_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    "$A4_REMOTE_ROOT/state/A1_OUinp/submit.lock"

if test -e "$A4_REMOTE_ROOT/runs/A1_OUinp/a4-slurm-probe-v2"; then
    printf 'Fresh request directory: already exists\n'
else
    printf 'Fresh request directory: absent as expected\n'
fi

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
