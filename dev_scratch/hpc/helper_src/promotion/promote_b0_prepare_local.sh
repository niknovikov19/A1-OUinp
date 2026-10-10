#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
B0_REPORT=$(mktemp /tmp/b0-prepare-local-promotion.XXXXXX.txt)
chmod 0644 "$B0_REPORT"
exec > >(tee "$B0_REPORT") 2>&1

B0_LOCAL_DIRS_OPEN=0

b0_cleanup() {
    local b0_rc=$?

    set +e
    if test "$B0_LOCAL_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            /opt/a1-hpc/bin \
            /opt/a1-hpc/share/schemas
    fi
    if test "$b0_rc" -eq 0; then
        printf '\nB0_PREPARE_RESULT=PASS\n'
    else
        printf '\nB0_PREPARE_RESULT=FAIL exit_code=%s\n' "$b0_rc"
    fi
    printf 'B0_PREPARE_REPORT=%s\n' "$B0_REPORT"
    chmod 0644 "$B0_REPORT"
    trap - EXIT
    exit "$b0_rc"
}

b0_check_sha256() {
    local b0_expected=$1
    local b0_path=$2
    local b0_actual

    b0_actual=$(sha256sum "$b0_path")
    b0_actual=${b0_actual%% *}
    printf '%s  %s\n' "$b0_actual" "$b0_path"
    test "$b0_actual" = "$b0_expected"
}

trap b0_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
B0_COMMIT=$1
B0_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
B0_SRC="$B0_LOCAL_REPO/dev_scratch/hpc/helper_src"

printf 'B0.3 preparation promotion: local\n'
printf 'B0.3 commit: %s\n' "$B0_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B0_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$B0_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B0_LOCAL_REPO" \
    -C "$B0_LOCAL_REPO" rev-parse HEAD)" = "$B0_COMMIT"
test "$(git -c safe.directory="$B0_LOCAL_REPO" \
    -C "$B0_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify every reviewed local source artifact
printf '\n== Reviewed source hashes ==\n'
b0_check_sha256 '8e5c4621ec622e09ab8dbf023f18691dae953a87407f3bb694e448bca4d9de20' \
    "$B0_SRC/local/hpc-job-prepare"
b0_check_sha256 '166d9b783b50f90b9e7032be8397fbe8ea8f668be8e193b0736ccf9f71b566da' \
    "$B0_SRC/local/hpc_common.py"
b0_check_sha256 '6221cc6f242c9561b00c9515ed0f79201049066d78de78c726a5be511d6ff4f5' \
    "$B0_LOCAL_REPO/hpc_jobs/job-request.schema.json"
b0_check_sha256 '822f3ce58fa3efa9a3414494af6cc1d6803a874b5ac039c1d9bf0ec52ee2fa2a' \
    "$B0_SRC/schemas/remote-hpc-prepare-config.schema.json"
b0_check_sha256 'e875b0522369b8b130fc15f365fc55f43724eef03a47402dda51934ff8859c2c' \
    "$B0_SRC/schemas/prepared-job-record.schema.json"

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
B0_LOCAL_DIRS_OPEN=1
chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 \
    "$B0_SRC/local/hpc-job-prepare" \
    /opt/a1-hpc/bin/hpc-job-prepare
install -o root -g root -m 0444 \
    "$B0_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 \
    "$B0_LOCAL_REPO/hpc_jobs/job-request.schema.json" \
    /opt/a1-hpc/share/schemas/hpc-job-request.schema.json
install -o root -g root -m 0444 \
    "$B0_SRC/schemas/remote-hpc-prepare-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-prepare-config.schema.json
install -o root -g root -m 0444 \
    "$B0_SRC/schemas/prepared-job-record.schema.json" \
    /opt/a1-hpc/share/schemas/prepared-job-record.schema.json
chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas
B0_LOCAL_DIRS_OPEN=0

# Verify the installed bundle and permissions
printf '\n== Installed bundle identity ==\n'
B0_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$B0_INFO"
printf '%s\n' "$B0_INFO" | grep -Fq '"bundle_version": "0.8.0-b0"'
printf '%s\n' "$B0_INFO" | grep -Fq \
    '"bundle_sha256": "d64ff946c6832d0ee8f8f6fcd89b605f3c7c9b64b682e8fdb8145e9e1d95852f"'

printf '\n== Installed hashes ==\n'
b0_check_sha256 '8e5c4621ec622e09ab8dbf023f18691dae953a87407f3bb694e448bca4d9de20' \
    /opt/a1-hpc/bin/hpc-job-prepare
b0_check_sha256 '166d9b783b50f90b9e7032be8397fbe8ea8f668be8e193b0736ccf9f71b566da' \
    /opt/a1-hpc/bin/hpc_common.py
b0_check_sha256 '6221cc6f242c9561b00c9515ed0f79201049066d78de78c726a5be511d6ff4f5' \
    /opt/a1-hpc/share/schemas/hpc-job-request.schema.json
b0_check_sha256 '822f3ce58fa3efa9a3414494af6cc1d6803a874b5ac039c1d9bf0ec52ee2fa2a' \
    /opt/a1-hpc/share/schemas/remote-hpc-prepare-config.schema.json
b0_check_sha256 'e875b0522369b8b130fc15f365fc55f43724eef03a47402dda51934ff8859c2c' \
    /opt/a1-hpc/share/schemas/prepared-job-record.schema.json

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-job-prepare \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/hpc-job-request.schema.json \
    /opt/a1-hpc/share/schemas/remote-hpc-prepare-config.schema.json \
    /opt/a1-hpc/share/schemas/prepared-job-record.schema.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
