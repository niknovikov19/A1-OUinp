#!/bin/bash

set -Eeuo pipefail

# Capture the complete local observation-promotion transcript
B2O_REPORT=$(mktemp /tmp/b2-observe-local-promotion.XXXXXX.txt)
chmod 0644 "$B2O_REPORT"
exec > >(tee "$B2O_REPORT") 2>&1
B2O_BIN_OPEN=0

b2o_cleanup() {
    local b2o_rc=$?

    set +e
    if test "$B2O_BIN_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin
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

# Validate the exact reviewed checkout
test "$#" -eq 1
B2O_COMMIT=$1
B2O_REPO=/home/nnovikov/repo/A1-OUinp
B2O_SRC="$B2O_REPO/dev_scratch/hpc/helper_src"
printf 'B2 child-observation promotion: local\n'
printf 'B2 observation commit: %s\n' "$B2O_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2O_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$B2O_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B2O_REPO" -C "$B2O_REPO" rev-parse HEAD)" = "$B2O_COMMIT"
test "$(git -c safe.directory="$B2O_REPO" -C "$B2O_REPO" branch --show-current)" = 'codex-hpc'

# Verify and install only the changed local runtime files
printf '\n== Reviewed source hashes ==\n'
b2o_check_sha256 'ac15e9e9279d670d96d9c9bfef60df92e5a1757fe9daae809da9a64d9f33d46f' "$B2O_SRC/local/hpc-job"
b2o_check_sha256 'c95d9c5ffda7233c8d8c515faeef94739ec13d5b37bf9db51b7e281f69999f0f' "$B2O_SRC/local/hpc_common.py"

printf '\n== Installation ==\n'
B2O_BIN_OPEN=1
chmod 0755 /opt/a1-hpc/bin
install -o root -g root -m 0555 "$B2O_SRC/local/hpc-job" /opt/a1-hpc/bin/hpc-job
install -o root -g root -m 0444 "$B2O_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
chmod 0555 /opt/a1-hpc/bin
B2O_BIN_OPEN=0

# Verify the promoted bundle identity and permissions
printf '\n== Installed bundle identity ==\n'
B2O_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$B2O_INFO"
printf '%s\n' "$B2O_INFO" | grep -Fq '"bundle_version": "0.11.0-b2"'
printf '%s\n' "$B2O_INFO" | grep -Fq '"bundle_sha256": "b4c1541e7fa6466b475ce6150bbc117b042a66ffa177b7e8e92bfb0900682fd4"'
b2o_check_sha256 'ac15e9e9279d670d96d9c9bfef60df92e5a1757fe9daae809da9a64d9f33d46f' /opt/a1-hpc/bin/hpc-job
b2o_check_sha256 'c95d9c5ffda7233c8d8c515faeef94739ec13d5b37bf9db51b7e281f69999f0f' /opt/a1-hpc/bin/hpc_common.py
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/bin/hpc-job \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
