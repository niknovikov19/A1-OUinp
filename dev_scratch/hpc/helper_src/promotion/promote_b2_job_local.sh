#!/bin/bash

set -Eeuo pipefail

# Capture the complete local promotion transcript
B2_REPORT=$(mktemp /tmp/b2-job-local-promotion.XXXXXX.txt)
chmod 0644 "$B2_REPORT"
exec > >(tee "$B2_REPORT") 2>&1
B2_DIRS_OPEN=0

b2_cleanup() {
    local b2_rc=$?

    set +e
    if test "$B2_DIRS_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
    fi
    if test "$b2_rc" -eq 0; then
        printf '\nB2_JOB_RESULT=PASS\n'
    else
        printf '\nB2_JOB_RESULT=FAIL exit_code=%s\n' "$b2_rc"
    fi
    printf 'B2_JOB_REPORT=%s\n' "$B2_REPORT"
    trap - EXIT
    exit "$b2_rc"
}

b2_check_sha256() {
    local b2_expected=$1
    local b2_path=$2
    local b2_actual

    b2_actual=$(sha256sum "$b2_path")
    b2_actual=${b2_actual%% *}
    printf '%s  %s\n' "$b2_actual" "$b2_path"
    test "$b2_actual" = "$b2_expected"
}

trap b2_cleanup EXIT

# Validate the exact reviewed checkout
test "$#" -eq 1
B2_COMMIT=$1
B2_REPO=/home/nnovikov/repo/A1-OUinp
B2_SRC="$B2_REPO/dev_scratch/hpc/helper_src"
printf 'B2 child-job promotion: local\n'
printf 'B2 commit: %s\n' "$B2_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$B2_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B2_REPO" -C "$B2_REPO" rev-parse HEAD)" = "$B2_COMMIT"
test "$(git -c safe.directory="$B2_REPO" -C "$B2_REPO" branch --show-current)" = 'codex-hpc'

# Verify and install the complete changed local bundle subset
printf '\n== Reviewed source hashes ==\n'
b2_check_sha256 '93fa254df6e20b47776fe4a0f3a4148e049af59ea75b462353be0c8a0bb964b6' "$B2_SRC/local/hpc-job"
b2_check_sha256 '18dc811456311f058338a979fbdefe6cb4a123f92a004ecce47b2bcc0c0a2f9f' "$B2_SRC/local/hpc_common.py"
b2_check_sha256 '67d7131c8be99d4933702e08b9b9a8d29371a0d0fe47560b856939139ff40ec9' "$B2_SRC/schemas/remote-hpc-job-config.schema.json"

printf '\n== Installation ==\n'
B2_DIRS_OPEN=1
chmod 0755 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 "$B2_SRC/local/hpc-job" /opt/a1-hpc/bin/hpc-job
install -o root -g root -m 0444 "$B2_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 "$B2_SRC/schemas/remote-hpc-job-config.schema.json" /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json
chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
B2_DIRS_OPEN=0

# Verify the promoted identity and permissions
printf '\n== Installed bundle identity ==\n'
B2_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$B2_INFO"
printf '%s\n' "$B2_INFO" | grep -Fq '"bundle_version": "0.10.0-b2"'
printf '%s\n' "$B2_INFO" | grep -Fq '"bundle_sha256": "defc17cce0d1d5ec640730e6bfb90aa4c436ac7c69e2de5db55df3b7268caa41"'
b2_check_sha256 '93fa254df6e20b47776fe4a0f3a4148e049af59ea75b462353be0c8a0bb964b6' /opt/a1-hpc/bin/hpc-job
b2_check_sha256 '18dc811456311f058338a979fbdefe6cb4a123f92a004ecce47b2bcc0c0a2f9f' /opt/a1-hpc/bin/hpc_common.py
stat -c '%A %a %U:%G %n' /opt/a1-hpc/bin /opt/a1-hpc/share/schemas /opt/a1-hpc/bin/hpc-job /opt/a1-hpc/bin/hpc_common.py
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
