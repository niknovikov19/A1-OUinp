#!/bin/bash

set -Eeuo pipefail

# Capture the remote promotion transcript
CT_ROOT=/ddn/niknovikov19/hpc_codex
CT_REPORT_DIR="$CT_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$CT_REPORT_DIR"
chmod 0700 "$CT_REPORT_DIR"
CT_REPORT=$(mktemp "$CT_REPORT_DIR/cancel-tree-promotion.XXXXXX.txt")
chmod 0600 "$CT_REPORT"
exec > >(tee "$CT_REPORT") 2>&1
CT_TMP=$(mktemp -d /tmp/cancel-tree-promotion.XXXXXX)
CT_DIRS_OPEN=0

ct_cleanup() {
    local ct_rc=$?

    set +e
    if test "$CT_DIRS_OPEN" -eq 1; then
        chmod 0555 "$CT_ROOT/helpers/lethe" "$CT_ROOT/helpers/grid"
    fi
    rm -f \
        "$CT_TMP/hpc-lethe-job" \
        "$CT_TMP/hpc-grid-job" \
        "$CT_TMP/hpc_job_lifecycle.py"
    rmdir "$CT_TMP" 2>/dev/null || true
    if test "$ct_rc" -eq 0; then
        printf '\nCANCEL_TREE_RESULT=PASS\n'
    else
        printf '\nCANCEL_TREE_RESULT=FAIL exit_code=%s\n' "$ct_rc"
    fi
    printf 'CANCEL_TREE_REPORT=%s\n' "$CT_REPORT"
    trap - EXIT
    exit "$ct_rc"
}

ct_check_sha256() {
    local ct_expected=$1
    local ct_path=$2
    local ct_actual

    ct_actual=$(sha256sum "$ct_path")
    ct_actual=${ct_actual%% *}
    printf '%s  %s\n' "$ct_actual" "$ct_path"
    test "$ct_actual" = "$ct_expected"
}

trap ct_cleanup EXIT

# Fetch the reviewed commit without changing the active checkout
test "$#" -eq 1
CT_COMMIT=$1
CT_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
CT_ACTIVE="$CT_ROOT/state/A1_OUinp/active-run.json"
printf 'Protected cancel-tree promotion: lethe\n'
printf 'Commit: %s\n' "$CT_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$CT_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test -f "$CT_ACTIVE"
test -z "$(git -C "$CT_REPO" status --porcelain=v1)"
git -C "$CT_REPO" fetch --no-tags origin codex-hpc
test "$(git -C "$CT_REPO" rev-parse refs/remotes/origin/codex-hpc)" = "$CT_COMMIT"
git -C "$CT_REPO" merge-base --is-ancestor HEAD "$CT_COMMIT"

# Export the reviewed sources from the fetched commit
git -C "$CT_REPO" show \
    "$CT_COMMIT:dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-job" \
    > "$CT_TMP/hpc-lethe-job"
git -C "$CT_REPO" show \
    "$CT_COMMIT:dev_scratch/hpc/helper_src/remote_grid/hpc-grid-job" \
    > "$CT_TMP/hpc-grid-job"
git -C "$CT_REPO" show \
    "$CT_COMMIT:hpc_job_lifecycle.py" \
    > "$CT_TMP/hpc_job_lifecycle.py"

# Verify old and reviewed helper identities
ct_check_sha256 \
    '02a5f4f2016cbd15828ae5f8741962ac6ff6a73011b3b81b3c8e8fc2dd2040dd' \
    "$CT_ROOT/helpers/lethe/hpc-lethe-job"
ct_check_sha256 \
    'fab001eb9fa278dfea1fa1cd7c3db1cd3fd568ab6a3040995ad9d412534f67f9' \
    "$CT_ROOT/helpers/grid/hpc-grid-job"
ct_check_sha256 \
    '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' \
    "$CT_ROOT/helpers/lethe/hpc_job_lifecycle.py"
ct_check_sha256 \
    '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' \
    "$CT_ROOT/helpers/grid/hpc_job_lifecycle.py"
ct_check_sha256 \
    'aa18e56bc7d329809f66d1bc79bf93377693b01f5259a25b0b40f2b2e5a92ff5' \
    "$CT_TMP/hpc-lethe-job"
ct_check_sha256 \
    'a290c44462ecc35bc49568cff01152ea28275013eea9aef745ea9921df8b1435' \
    "$CT_TMP/hpc-grid-job"
ct_check_sha256 \
    'ac10405e60b2cad369810ed3eb278c309eb50d705cda081c80971d970d8c44fc' \
    "$CT_TMP/hpc_job_lifecycle.py"

# Install the reviewed remote helper files
CT_DIRS_OPEN=1
chmod 0755 "$CT_ROOT/helpers/lethe" "$CT_ROOT/helpers/grid"
install -g salvadord -m 0555 \
    "$CT_TMP/hpc-lethe-job" \
    "$CT_ROOT/helpers/lethe/hpc-lethe-job"
install -g salvadord -m 0555 \
    "$CT_TMP/hpc-grid-job" \
    "$CT_ROOT/helpers/grid/hpc-grid-job"
install -g salvadord -m 0444 \
    "$CT_TMP/hpc_job_lifecycle.py" \
    "$CT_ROOT/helpers/lethe/hpc_job_lifecycle.py"
install -g salvadord -m 0444 \
    "$CT_TMP/hpc_job_lifecycle.py" \
    "$CT_ROOT/helpers/grid/hpc_job_lifecycle.py"
chmod 0555 "$CT_ROOT/helpers/lethe" "$CT_ROOT/helpers/grid"
CT_DIRS_OPEN=0

# Verify installed identities and preserve the active marker
ct_check_sha256 \
    'aa18e56bc7d329809f66d1bc79bf93377693b01f5259a25b0b40f2b2e5a92ff5' \
    "$CT_ROOT/helpers/lethe/hpc-lethe-job"
ct_check_sha256 \
    'a290c44462ecc35bc49568cff01152ea28275013eea9aef745ea9921df8b1435' \
    "$CT_ROOT/helpers/grid/hpc-grid-job"
ct_check_sha256 \
    'ac10405e60b2cad369810ed3eb278c309eb50d705cda081c80971d970d8c44fc' \
    "$CT_ROOT/helpers/lethe/hpc_job_lifecycle.py"
ct_check_sha256 \
    'ac10405e60b2cad369810ed3eb278c309eb50d705cda081c80971d970d8c44fc' \
    "$CT_ROOT/helpers/grid/hpc_job_lifecycle.py"
test -f "$CT_ACTIVE"
"$CT_ROOT/helpers/lethe/hpc-lethe-job" version
/usr/bin/ssh \
    -o BatchMode=yes \
    -o ConnectTimeout=15 \
    -o ConnectionAttempts=1 \
    -- lattice \
    "$CT_ROOT/helpers/grid/hpc-grid-job" version
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
