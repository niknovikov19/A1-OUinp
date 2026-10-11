#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe cancellation-promotion transcript
B2C_ROOT=/ddn/niknovikov19/hpc_codex
B2C_REPORT_DIR="$B2C_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B2C_REPORT_DIR"
chmod 0700 "$B2C_REPORT_DIR"
B2C_REPORT=$(mktemp "$B2C_REPORT_DIR/b2-cancel-remote-promotion.XXXXXX.txt")
chmod 0600 "$B2C_REPORT"
exec > >(tee "$B2C_REPORT") 2>&1
B2C_TMP=$(mktemp -d /tmp/b2-cancel-promotion.XXXXXX)
B2C_LETHE_OPEN=0
B2C_GRID_OPEN=0
B2C_CONFIG_OPEN=0

b2c_cleanup() {
    local b2c_rc=$?

    set +e
    if test "$B2C_LETHE_OPEN" -eq 1; then
        chmod 0555 "$B2C_ROOT/helpers/lethe"
    fi
    if test "$B2C_GRID_OPEN" -eq 1; then
        chmod 0555 "$B2C_ROOT/helpers/grid"
    fi
    if test "$B2C_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$B2C_ROOT/config"
    fi
    rm -f \
        "$B2C_TMP/hpc-lethe-job" \
        "$B2C_TMP/hpc-grid-job" \
        "$B2C_TMP/A1_OUinp-job.json"
    rmdir "$B2C_TMP" 2>/dev/null || true
    if test "$b2c_rc" -eq 0; then
        printf '\nB2_CANCEL_RESULT=PASS\n'
    else
        printf '\nB2_CANCEL_RESULT=FAIL exit_code=%s\n' "$b2c_rc"
    fi
    printf 'B2_CANCEL_REPORT=%s\n' "$B2C_REPORT"
    trap - EXIT
    exit "$b2c_rc"
}

b2c_check_sha256() {
    local b2c_expected=$1
    local b2c_path=$2
    local b2c_actual

    b2c_actual=$(sha256sum "$b2c_path")
    b2c_actual=${b2c_actual%% *}
    printf '%s  %s\n' "$b2c_actual" "$b2c_path"
    test "$b2c_actual" = "$b2c_expected"
}

trap b2c_cleanup EXIT

# Bind promotion to the active run and exact remote branch commit
test "$#" -eq 1
B2C_COMMIT=$1
B2C_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
printf 'B2 protected-cancel promotion: lethe\n'
printf 'B2 cancel commit: %s\n' "$B2C_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2C_REPORT"
printf '%s\n' "$B2C_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$B2C_REPO" rev-parse HEAD)" = 'c519334849484517fca28c658a401f806ebd6067'
test -z "$(git -C "$B2C_REPO" status --porcelain=v1)"
python3 - "$B2C_ROOT/state/A1_OUinp/active-run.json" <<'PY'
import json
import sys

with open(sys.argv[1], 'r') as fid:
    active = json.load(fid)
assert active['run_id'] == 'b2-child-discovery-006'
assert active['git_commit'] == 'c519334849484517fca28c658a401f806ebd6067'
PY
git -C "$B2C_REPO" fetch --no-tags origin codex-hpc
test "$(git -C "$B2C_REPO" rev-parse refs/remotes/origin/codex-hpc)" = "$B2C_COMMIT"

# Extract and verify only the reviewed remote files
git -C "$B2C_REPO" show "$B2C_COMMIT:dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-job" > "$B2C_TMP/hpc-lethe-job"
git -C "$B2C_REPO" show "$B2C_COMMIT:dev_scratch/hpc/helper_src/remote_grid/hpc-grid-job" > "$B2C_TMP/hpc-grid-job"
git -C "$B2C_REPO" show "$B2C_COMMIT:dev_scratch/hpc/helper_src/config_examples/remote-hpc-job.json.example" > "$B2C_TMP/A1_OUinp-job.json"
printf '\n== Reviewed source hashes ==\n'
b2c_check_sha256 '02a5f4f2016cbd15828ae5f8741962ac6ff6a73011b3b81b3c8e8fc2dd2040dd' "$B2C_TMP/hpc-lethe-job"
b2c_check_sha256 'fab001eb9fa278dfea1fa1cd7c3db1cd3fd568ab6a3040995ad9d412534f67f9' "$B2C_TMP/hpc-grid-job"
b2c_check_sha256 '1a87c434b7ff302467f792e8bf9100708209ad2ed8cc934618241a189079a497' "$B2C_TMP/A1_OUinp-job.json"
python3 -m json.tool "$B2C_TMP/A1_OUinp-job.json" >/dev/null
/usr/bin/ssh \
    -o BatchMode=yes \
    -o ConnectTimeout=15 \
    -o ConnectionAttempts=1 \
    -- lattice \
    /usr/bin/scancel --version

# Install the active-run-safe cancellation path
printf '\n== Installation ==\n'
B2C_LETHE_OPEN=1
chmod 0755 "$B2C_ROOT/helpers/lethe"
install -g salvadord -m 0555 "$B2C_TMP/hpc-lethe-job" "$B2C_ROOT/helpers/lethe/hpc-lethe-job"
chmod 0555 "$B2C_ROOT/helpers/lethe"
B2C_LETHE_OPEN=0
B2C_GRID_OPEN=1
chmod 0755 "$B2C_ROOT/helpers/grid"
install -g salvadord -m 0555 "$B2C_TMP/hpc-grid-job" "$B2C_ROOT/helpers/grid/hpc-grid-job"
chmod 0555 "$B2C_ROOT/helpers/grid"
B2C_GRID_OPEN=0
B2C_CONFIG_OPEN=1
chmod 0755 "$B2C_ROOT/config"
install -g salvadord -m 0444 "$B2C_TMP/A1_OUinp-job.json" "$B2C_ROOT/config/A1_OUinp-job.json"
chmod 0555 "$B2C_ROOT/config"
B2C_CONFIG_OPEN=0

# Verify hashes, versions and protected permissions
printf '\n== Installed identities ==\n'
b2c_check_sha256 '02a5f4f2016cbd15828ae5f8741962ac6ff6a73011b3b81b3c8e8fc2dd2040dd' "$B2C_ROOT/helpers/lethe/hpc-lethe-job"
b2c_check_sha256 'fab001eb9fa278dfea1fa1cd7c3db1cd3fd568ab6a3040995ad9d412534f67f9' "$B2C_ROOT/helpers/grid/hpc-grid-job"
b2c_check_sha256 '1a87c434b7ff302467f792e8bf9100708209ad2ed8cc934618241a189079a497' "$B2C_ROOT/config/A1_OUinp-job.json"
"$B2C_ROOT/helpers/lethe/hpc-lethe-job" version
stat -c '%A %a %U:%G %n' \
    "$B2C_ROOT/helpers/lethe" \
    "$B2C_ROOT/helpers/grid" \
    "$B2C_ROOT/config" \
    "$B2C_ROOT/helpers/lethe/hpc-lethe-job" \
    "$B2C_ROOT/helpers/grid/hpc-grid-job" \
    "$B2C_ROOT/config/A1_OUinp-job.json" \
    "$B2C_ROOT/state/A1_OUinp/active-run.json"
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
