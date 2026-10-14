#!/bin/bash

set -Eeuo pipefail

# Capture the remote policy-promotion transcript
HPC5_ROOT=/ddn/niknovikov19/hpc_codex
HPC5_REPORT_DIR="$HPC5_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$HPC5_REPORT_DIR"
chmod 0700 "$HPC5_REPORT_DIR"
HPC5_REPORT=$(mktemp "$HPC5_REPORT_DIR/hpc-concurrency-5-promotion.XXXXXX.txt")
chmod 0600 "$HPC5_REPORT"
exec > >(tee "$HPC5_REPORT") 2>&1
HPC5_CONFIG_OPEN=0

hpc5_cleanup() {
    local hpc5_rc=$?

    set +e
    if test "$HPC5_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$HPC5_ROOT/config"
    fi
    if test "$hpc5_rc" -eq 0; then
        printf '\nHPC_CONCURRENCY_RESULT=PASS\n'
    else
        printf '\nHPC_CONCURRENCY_RESULT=FAIL exit_code=%s\n' "$hpc5_rc"
    fi
    printf 'HPC_CONCURRENCY_REPORT=%s\n' "$HPC5_REPORT"
    trap - EXIT
    exit "$hpc5_rc"
}

hpc5_check_sha256() {
    local hpc5_expected=$1
    local hpc5_path=$2
    local hpc5_actual

    hpc5_actual=$(sha256sum "$hpc5_path")
    hpc5_actual=${hpc5_actual%% *}
    printf '%s  %s\n' "$hpc5_actual" "$hpc5_path"
    test "$hpc5_actual" = "$hpc5_expected"
}

trap hpc5_cleanup EXIT

# Bind installation to the exact clean automation checkout
test "$#" -eq 1
HPC5_COMMIT=$1
HPC5_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
HPC5_SOURCE="$HPC5_REPO/dev_scratch/hpc/helper_src/config_examples/remote-hpc-prepare.json.example"
HPC5_TARGET="$HPC5_ROOT/config/A1_OUinp-prepare.json"
printf 'Concurrency-five promotion: lethe\n'
printf 'Commit: %s\n' "$HPC5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$HPC5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$HPC5_REPO" rev-parse HEAD)" = "$HPC5_COMMIT"
test "$(git -C "$HPC5_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$HPC5_REPO" status --porcelain=v1)"

# Verify the installed and reviewed configurations
hpc5_check_sha256 \
    '42e043602a8b6ccb6a30a99582c72df229251cf8a08f6bca0c746b77e15ea064' \
    "$HPC5_TARGET"
hpc5_check_sha256 \
    '434cf03d636027e73358af04a4b5b7d7a93704ef9ed307e13be15bb8f8e795' \
    "$HPC5_SOURCE"
python3 -m json.tool "$HPC5_SOURCE" >/dev/null

# Install only the remote preparation policy file
HPC5_CONFIG_OPEN=1
chmod 0755 "$HPC5_ROOT/config"
install -g salvadord -m 0444 "$HPC5_SOURCE" "$HPC5_TARGET"
chmod 0555 "$HPC5_ROOT/config"
HPC5_CONFIG_OPEN=0

# Verify the installed concurrency ceiling
hpc5_check_sha256 \
    '434cf03d636027e73358af04a4b5b7d7a93704ef9ed307e13be15bb8f8e795' \
    "$HPC5_TARGET"
python3 -m json.tool "$HPC5_TARGET" >/dev/null
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
