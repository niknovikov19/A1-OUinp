#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe observation-promotion transcript
B2O_ROOT=/ddn/niknovikov19/hpc_codex
B2O_REPORT_DIR="$B2O_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B2O_REPORT_DIR"
chmod 0700 "$B2O_REPORT_DIR"
B2O_REPORT=$(mktemp "$B2O_REPORT_DIR/b2-observe-remote-promotion.XXXXXX.txt")
chmod 0600 "$B2O_REPORT"
exec > >(tee "$B2O_REPORT") 2>&1
B2O_DIR_OPEN=0

b2o_cleanup() {
    local b2o_rc=$?

    set +e
    if test "$B2O_DIR_OPEN" -eq 1; then
        chmod 0555 "$B2O_ROOT/helpers/lethe"
    fi
    if test "$b2o_rc" -eq 0; then
        printf '\nB2_OBSERVE_RESULT=PASS\n'
    else
        printf '\nB2_OBSERVE_RESULT=FAIL exit_code=%s\n' "$b2o_rc"
    fi
    printf 'B2_OBSERVE_REPORT=%s\n' "$B2O_REPORT"
    trap - EXIT
    exit "$b2o_rc"
}

b2o_check_sha256() {
    local b2o_expected=$1
    local b2o_path=$2
    local b2o_actual

    b2o_actual=$(sha256sum "$b2o_path")
    b2o_actual=${b2o_actual%% *}
    printf '%s  %s\n' "$b2o_actual" "$b2o_path"
    test "$b2o_actual" = "$b2o_expected"
}

trap b2o_cleanup EXIT

# Validate the exact clean automation checkout
test "$#" -eq 1
B2O_COMMIT=$1
B2O_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2O_SRC="$B2O_REPO/dev_scratch/hpc/helper_src"
printf 'B2 child-observation promotion: lethe\n'
printf 'B2 observation commit: %s\n' "$B2O_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2O_REPORT"
printf '%s\n' "$B2O_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$B2O_REPO" rev-parse HEAD)" = "$B2O_COMMIT"
test "$(git -C "$B2O_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B2O_REPO" status --porcelain=v1)"
test ! -e "$B2O_ROOT/state/A1_OUinp/active-run.json"

# Verify and install the changed lethe runtime file
printf '\n== Reviewed source hash ==\n'
b2o_check_sha256 'e7f7d7da72360dfb7be72aae4721dba7c2099242153452982c8822c4e0345453' "$B2O_SRC/remote_lethe/hpc-lethe-job"

printf '\n== Installation ==\n'
B2O_DIR_OPEN=1
chmod 0755 "$B2O_ROOT/helpers/lethe"
install -g salvadord -m 0555 \
    "$B2O_SRC/remote_lethe/hpc-lethe-job" \
    "$B2O_ROOT/helpers/lethe/hpc-lethe-job"
chmod 0555 "$B2O_ROOT/helpers/lethe"
B2O_DIR_OPEN=0

# Verify the promoted helper identity and permissions
printf '\n== Installed helper identity ==\n'
b2o_check_sha256 'e7f7d7da72360dfb7be72aae4721dba7c2099242153452982c8822c4e0345453' "$B2O_ROOT/helpers/lethe/hpc-lethe-job"
"$B2O_ROOT/helpers/lethe/hpc-lethe-job" version
stat -c '%A %a %U:%G %n' \
    "$B2O_ROOT/helpers/lethe" \
    "$B2O_ROOT/helpers/lethe/hpc-lethe-job"
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
