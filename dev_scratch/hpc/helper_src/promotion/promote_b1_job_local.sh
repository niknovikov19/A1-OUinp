#!/bin/bash

set -Eeuo pipefail

# Capture the complete local promotion transcript
B1_REPORT=$(mktemp /tmp/b1-job-local-promotion.XXXXXX.txt)
chmod 0644 "$B1_REPORT"
exec > >(tee "$B1_REPORT") 2>&1

B1_LOCAL_DIRS_OPEN=0

b1_cleanup() {
    local b1_rc=$?

    set +e
    if test "$B1_LOCAL_DIRS_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
    fi
    if test "$b1_rc" -eq 0; then
        printf '\nB1_JOB_RESULT=PASS\n'
    else
        printf '\nB1_JOB_RESULT=FAIL exit_code=%s\n' "$b1_rc"
    fi
    printf 'B1_JOB_REPORT=%s\n' "$B1_REPORT"
    chmod 0644 "$B1_REPORT"
    trap - EXIT
    exit "$b1_rc"
}

b1_check_sha256() {
    local b1_expected=$1
    local b1_path=$2
    local b1_actual

    b1_actual=$(sha256sum "$b1_path")
    b1_actual=${b1_actual%% *}
    printf '%s  %s\n' "$b1_actual" "$b1_path"
    test "$b1_actual" = "$b1_expected"
}

trap b1_cleanup EXIT

# Validate invocation and exact reviewed checkout
test "$#" -eq 1
B1_COMMIT=$1
B1_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
B1_SRC="$B1_LOCAL_REPO/dev_scratch/hpc/helper_src"

printf 'B1 prepared-job promotion: local\n'
printf 'B1 commit: %s\n' "$B1_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B1_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$B1_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B1_LOCAL_REPO" \
    -C "$B1_LOCAL_REPO" rev-parse HEAD)" = "$B1_COMMIT"
test "$(git -c safe.directory="$B1_LOCAL_REPO" \
    -C "$B1_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify every reviewed local source artifact
printf '\n== Reviewed source hashes ==\n'
b1_check_sha256 '8680486c21a5624e770b0abb12246ee642a80679956c56b40ad857d55d3ffe19' \
    "$B1_SRC/local/hpc-job"
b1_check_sha256 '53fab445f36923bd892e0df1999c8713ac2c4bda458beba62b298892e61ec17c' \
    "$B1_SRC/local/hpc_common.py"
b1_check_sha256 '67d7131c8be99d4933702e08b9b9a8d29371a0d0fe47560b856939139ff40ec9' \
    "$B1_SRC/schemas/remote-hpc-job-config.schema.json"

# Install while restoring protected modes on every exit
printf '\n== Installation ==\n'
B1_LOCAL_DIRS_OPEN=1
chmod 0755 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 \
    "$B1_SRC/local/hpc-job" \
    /opt/a1-hpc/bin/hpc-job
install -o root -g root -m 0444 \
    "$B1_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 \
    "$B1_SRC/schemas/remote-hpc-job-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json
chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
B1_LOCAL_DIRS_OPEN=0

# Verify bundle identity without invoking the new operation
printf '\n== Installed bundle identity ==\n'
B1_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$B1_INFO"
printf '%s\n' "$B1_INFO" | grep -Fq '"bundle_version": "0.9.0-b1"'
printf '%s\n' "$B1_INFO" | grep -Fq \
    '"bundle_sha256": "ec8fc7a262fc3296f8b9f89a6db8a176eeb43a0acbe39e5a91ce68e6d1aee530"'

printf '\n== Installed hashes and permissions ==\n'
b1_check_sha256 '8680486c21a5624e770b0abb12246ee642a80679956c56b40ad857d55d3ffe19' \
    /opt/a1-hpc/bin/hpc-job
b1_check_sha256 '53fab445f36923bd892e0df1999c8713ac2c4bda458beba62b298892e61ec17c' \
    /opt/a1-hpc/bin/hpc_common.py
b1_check_sha256 '67d7131c8be99d4933702e08b9b9a8d29371a0d0fe47560b856939139ff40ec9' \
    /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-job \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
