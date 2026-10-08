#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A5_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A5_REPORT_DIR="$A5_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$A5_REPORT_DIR"
chmod 0700 "$A5_REPORT_DIR"
A5_REPORT=$(mktemp "$A5_REPORT_DIR/a5-remote-promotion.XXXXXX.txt")
chmod 0600 "$A5_REPORT"
exec > >(tee "$A5_REPORT") 2>&1

A5_REMOTE_DIRS_OPEN=0

a5_cleanup() {
    local a5_rc=$?

    set +e
    if test "$A5_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$A5_REMOTE_ROOT/helpers/lethe" \
            "$A5_REMOTE_ROOT/helpers/grid" \
            "$A5_REMOTE_ROOT/config"
    fi

    if test "$a5_rc" -eq 0; then
        printf '\nA5_RESULT=PASS\n'
    else
        printf '\nA5_RESULT=FAIL exit_code=%s\n' "$a5_rc"
    fi
    printf 'A5_REPORT=%s\n' "$A5_REPORT"
    chmod 0600 "$A5_REPORT"
    trap - EXIT
    exit "$a5_rc"
}

a5_check_sha256() {
    local a5_expected=$1
    local a5_path=$2
    local a5_actual

    a5_actual=$(sha256sum "$a5_path")
    a5_actual=${a5_actual%% *}
    printf '%s  %s\n' "$a5_actual" "$a5_path"
    test "$a5_actual" = "$a5_expected"
}

trap a5_cleanup EXIT

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
A5_COMMIT=$1
A5_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A5_SRC="$A5_REMOTE_REPO/dev_scratch/hpc/helper_src"
A5_REMOTE_OWNER=niknovikov19
A5_REMOTE_GROUP=salvadord

printf 'A5 promotion: lethe\n'
printf 'A5 commit: %s\n' "$A5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A5_REPORT"

printf '%s\n' "$A5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$A5_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A5_REMOTE_GROUP"
test "$(git -C "$A5_REMOTE_REPO" rev-parse HEAD)" = "$A5_COMMIT"
test "$(git -C "$A5_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$A5_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret protected configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$A5_SRC/config_examples/remote-hpc-status.json.example"
A5_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
A5_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$A5_SECRET_RE|$A5_URL_RE" \
    "$A5_SRC/config_examples/remote-hpc-status.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every reviewed remote source artifact
printf '\n== Reviewed source hashes ==\n'
a5_check_sha256 \
    '5f5f7ed374d35f9dd1e7d8dc163b276a84d8b86544b3f603d917f977e7171f83' \
    "$A5_SRC/remote_lethe/hpc-lethe-status"
a5_check_sha256 \
    'dfab56a100baab8d06432f024ee0b57d6da786ef9e598479c4c0cbe8a65685a6' \
    "$A5_SRC/remote_grid/hpc-grid-status"
a5_check_sha256 \
    '3ccd72366ce7c3809edea0ed15b8acd87b5af8e1dcf856662798bacc76cac905' \
    "$A5_SRC/config_examples/remote-hpc-status.json.example"
a5_check_sha256 \
    'd0d9b5b2ffaa36b779ba78c8b42f825c57cbef42299acaa9de552de37b0b6840' \
    "$A5_SRC/test_fixtures/a5_status_cases.json"

# Confirm existing shared-path ownership before changing modes
printf '\n== Existing shared roots ==\n'
for A5_PATH in \
    "$A5_REMOTE_ROOT/helpers/lethe" \
    "$A5_REMOTE_ROOT/helpers/grid" \
    "$A5_REMOTE_ROOT/config" \
    "$A5_REMOTE_ROOT/runs/A1_OUinp" \
    "$A5_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A5_PATH")" = "$A5_REMOTE_OWNER"
    test "$(stat -c '%G' "$A5_PATH")" = "$A5_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$A5_PATH"
done

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A5_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$A5_REMOTE_ROOT/helpers/lethe" \
    "$A5_REMOTE_ROOT/helpers/grid" \
    "$A5_REMOTE_ROOT/config"

install -g "$A5_REMOTE_GROUP" -m 0555 \
    "$A5_SRC/remote_lethe/hpc-lethe-status" \
    "$A5_REMOTE_ROOT/helpers/lethe/hpc-lethe-status"
install -g "$A5_REMOTE_GROUP" -m 0555 \
    "$A5_SRC/remote_grid/hpc-grid-status" \
    "$A5_REMOTE_ROOT/helpers/grid/hpc-grid-status"
install -g "$A5_REMOTE_GROUP" -m 0444 \
    "$A5_SRC/config_examples/remote-hpc-status.json.example" \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status.json"
install -g "$A5_REMOTE_GROUP" -m 0444 \
    "$A5_SRC/test_fixtures/a5_status_cases.json" \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status-fixtures.json"

chmod 0555 \
    "$A5_REMOTE_ROOT/helpers/lethe" \
    "$A5_REMOTE_ROOT/helpers/grid" \
    "$A5_REMOTE_ROOT/config"
A5_REMOTE_DIRS_OPEN=0

# Verify the installed files and permissions
printf '\n== Installed hashes ==\n'
python3 -m json.tool \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status.json" \
    >/dev/null
python3 -m json.tool \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status-fixtures.json" \
    >/dev/null
a5_check_sha256 \
    '5f5f7ed374d35f9dd1e7d8dc163b276a84d8b86544b3f603d917f977e7171f83' \
    "$A5_REMOTE_ROOT/helpers/lethe/hpc-lethe-status"
a5_check_sha256 \
    'dfab56a100baab8d06432f024ee0b57d6da786ef9e598479c4c0cbe8a65685a6' \
    "$A5_REMOTE_ROOT/helpers/grid/hpc-grid-status"
a5_check_sha256 \
    '3ccd72366ce7c3809edea0ed15b8acd87b5af8e1dcf856662798bacc76cac905' \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status.json"
a5_check_sha256 \
    'd0d9b5b2ffaa36b779ba78c8b42f825c57cbef42299acaa9de552de37b0b6840' \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status-fixtures.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$A5_REMOTE_ROOT/helpers/lethe" \
    "$A5_REMOTE_ROOT/helpers/grid" \
    "$A5_REMOTE_ROOT/config" \
    "$A5_REMOTE_ROOT/runs/A1_OUinp" \
    "$A5_REMOTE_ROOT/state/A1_OUinp" \
    "$A5_REMOTE_ROOT/helpers/lethe/hpc-lethe-status" \
    "$A5_REMOTE_ROOT/helpers/grid/hpc-grid-status" \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status.json" \
    "$A5_REMOTE_ROOT/config/A1_OUinp-status-fixtures.json"

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
