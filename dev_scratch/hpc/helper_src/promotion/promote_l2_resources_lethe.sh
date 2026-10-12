#!/bin/bash

set -Eeuo pipefail

# Capture the remote policy-promotion transcript
L2R_ROOT=/ddn/niknovikov19/hpc_codex
L2R_REPORT_DIR="$L2R_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$L2R_REPORT_DIR"
chmod 0700 "$L2R_REPORT_DIR"
L2R_REPORT=$(mktemp "$L2R_REPORT_DIR/l2-resources-promotion.XXXXXX.txt")
chmod 0600 "$L2R_REPORT"
exec > >(tee "$L2R_REPORT") 2>&1
L2R_CONFIG_OPEN=0

l2r_cleanup() {
    local l2r_rc=$?

    set +e
    if test "$L2R_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$L2R_ROOT/config"
    fi
    if test "$l2r_rc" -eq 0; then
        printf '\nL2_RESOURCES_RESULT=PASS\n'
    else
        printf '\nL2_RESOURCES_RESULT=FAIL exit_code=%s\n' "$l2r_rc"
    fi
    printf 'L2_RESOURCES_REPORT=%s\n' "$L2R_REPORT"
    trap - EXIT
    exit "$l2r_rc"
}

l2r_check_sha256() {
    local l2r_expected=$1
    local l2r_path=$2
    local l2r_actual

    l2r_actual=$(sha256sum "$l2r_path")
    l2r_actual=${l2r_actual%% *}
    printf '%s  %s\n' "$l2r_actual" "$l2r_path"
    test "$l2r_actual" = "$l2r_expected"
}

trap l2r_cleanup EXIT

# Bind installation to the exact clean automation checkout
test "$#" -eq 1
L2R_COMMIT=$1
L2R_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
L2R_SOURCE="$L2R_REPO/dev_scratch/hpc/helper_src/config_examples/remote-hpc-prepare.json.example"
L2R_TARGET="$L2R_ROOT/config/A1_OUinp-prepare.json"
printf 'L2 resource-ceiling promotion: lethe\n'
printf 'Commit: %s\n' "$L2R_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$L2R_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$L2R_REPO" rev-parse HEAD)" = "$L2R_COMMIT"
test "$(git -C "$L2R_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$L2R_REPO" status --porcelain=v1)"

# Verify the old and reviewed configurations
l2r_check_sha256 \
    '9150f8c191e8635e4ab27e66a105fa48b27e5489c471aea64df2b4d686a96f3e' \
    "$L2R_TARGET"
l2r_check_sha256 \
    '42e043602a8b6ccb6a30a99582c72df229251cf8a08f6bca0c746b77e15ea064' \
    "$L2R_SOURCE"
python3 -m json.tool "$L2R_SOURCE" >/dev/null

# Install only the remote preparation policy file
L2R_CONFIG_OPEN=1
chmod 0755 "$L2R_ROOT/config"
install -g salvadord -m 0444 "$L2R_SOURCE" "$L2R_TARGET"
chmod 0555 "$L2R_ROOT/config"
L2R_CONFIG_OPEN=0

# Verify the installed resource ceiling
l2r_check_sha256 \
    '42e043602a8b6ccb6a30a99582c72df229251cf8a08f6bca0c746b77e15ea064' \
    "$L2R_TARGET"
python3 -m json.tool "$L2R_TARGET" >/dev/null
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
