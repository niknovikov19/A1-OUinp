#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A6_REPORT=$(mktemp /tmp/a6-local-promotion.XXXXXX.txt)
chmod 0644 "$A6_REPORT"
exec > >(tee "$A6_REPORT") 2>&1

A6_LOCAL_DIRS_OPEN=0

a6_cleanup() {
    local a6_rc=$?

    set +e
    if test "$A6_LOCAL_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            /opt/a1-hpc/bin \
            /opt/a1-hpc/share/schemas
    fi

    if test "$a6_rc" -eq 0; then
        printf '\nA6_RESULT=PASS\n'
    else
        printf '\nA6_RESULT=FAIL exit_code=%s\n' "$a6_rc"
    fi
    printf 'A6_REPORT=%s\n' "$A6_REPORT"
    chmod 0644 "$A6_REPORT"
    trap - EXIT
    exit "$a6_rc"
}

a6_check_sha256() {
    local a6_expected=$1
    local a6_path=$2
    local a6_actual

    a6_actual=$(sha256sum "$a6_path")
    a6_actual=${a6_actual%% *}
    printf '%s  %s\n' "$a6_actual" "$a6_path"
    test "$a6_actual" = "$a6_expected"
}

trap a6_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
A6_COMMIT=$1
A6_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A6_SRC="$A6_LOCAL_REPO/dev_scratch/hpc/helper_src"

printf 'A6 promotion: local\n'
printf 'A6 commit: %s\n' "$A6_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A6_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$A6_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$A6_LOCAL_REPO" \
    -C "$A6_LOCAL_REPO" rev-parse HEAD)" = "$A6_COMMIT"
test "$(git -c safe.directory="$A6_LOCAL_REPO" \
    -C "$A6_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify every reviewed local source artifact
printf '\n== Reviewed source hashes ==\n'
a6_check_sha256 \
    '58840c04606f72071184688aedc6c12449851da9d1235768b910466ef7b7fee1' \
    "$A6_SRC/local/hpc-log"
a6_check_sha256 \
    '3a530d2642c802c56a1f87ed621e2a022a87d976183a1f2ec51d14476557cdc3' \
    "$A6_SRC/local/hpc_common.py"
a6_check_sha256 \
    'a8ba0c96003c974370c139e9b340dcf8f4a5802638f5c25b63a4b6d319c380b4' \
    "$A6_SRC/schemas/remote-hpc-log-config.schema.json"
a6_check_sha256 \
    'e347a74947d70c64c6422c25b343bac3e11cdfc5e421d69761c73989dc18997a' \
    "$A6_SRC/schemas/log-cursor-state.schema.json"
a6_check_sha256 \
    '10e02d67326b32d1fa331138ec6058a7f71672f8de459069d6e6efbb7127d7b2' \
    "$A6_SRC/schemas/log-read-result.schema.json"

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A6_LOCAL_DIRS_OPEN=1
chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 \
    "$A6_SRC/local/hpc-log" \
    /opt/a1-hpc/bin/hpc-log
install -o root -g root -m 0444 \
    "$A6_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 \
    "$A6_SRC/schemas/remote-hpc-log-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-log-config.schema.json
install -o root -g root -m 0444 \
    "$A6_SRC/schemas/log-cursor-state.schema.json" \
    /opt/a1-hpc/share/schemas/log-cursor-state.schema.json
install -o root -g root -m 0444 \
    "$A6_SRC/schemas/log-read-result.schema.json" \
    /opt/a1-hpc/share/schemas/log-read-result.schema.json
chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas
A6_LOCAL_DIRS_OPEN=0

# Verify the installed bundle, files, and unchanged audit state
printf '\n== Installed bundle identity ==\n'
A6_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$A6_INFO"
printf '%s\n' "$A6_INFO" | grep -Fq '"bundle_version": "0.7.0-a6"'
A6_BUNDLE_SHA=ce7488da6de975fb22fa93cdc39dbe893cfefb3b4ecc67abfb022d1477c5fb2a
printf '%s\n' "$A6_INFO" | grep -Fq \
    "\"bundle_sha256\": \"$A6_BUNDLE_SHA\""

printf '\n== Installed hashes ==\n'
a6_check_sha256 \
    '58840c04606f72071184688aedc6c12449851da9d1235768b910466ef7b7fee1' \
    /opt/a1-hpc/bin/hpc-log
a6_check_sha256 \
    '3a530d2642c802c56a1f87ed621e2a022a87d976183a1f2ec51d14476557cdc3' \
    /opt/a1-hpc/bin/hpc_common.py
a6_check_sha256 \
    'a8ba0c96003c974370c139e9b340dcf8f4a5802638f5c25b63a4b6d319c380b4' \
    /opt/a1-hpc/share/schemas/remote-hpc-log-config.schema.json
a6_check_sha256 \
    'e347a74947d70c64c6422c25b343bac3e11cdfc5e421d69761c73989dc18997a' \
    /opt/a1-hpc/share/schemas/log-cursor-state.schema.json
a6_check_sha256 \
    '10e02d67326b32d1fa331138ec6058a7f71672f8de459069d6e6efbb7127d7b2' \
    /opt/a1-hpc/share/schemas/log-read-result.schema.json

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-log \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-log-config.schema.json \
    /opt/a1-hpc/share/schemas/log-cursor-state.schema.json \
    /opt/a1-hpc/share/schemas/log-read-result.schema.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
