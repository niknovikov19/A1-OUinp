#!/bin/bash

set -Eeuo pipefail

# Capture the complete local cancellation-promotion transcript
B2C_REPORT=$(mktemp /tmp/b2-cancel-local-promotion.XXXXXX.txt)
chmod 0644 "$B2C_REPORT"
exec > >(tee "$B2C_REPORT") 2>&1
B2C_BIN_OPEN=0
B2C_SCHEMA_OPEN=0

b2c_cleanup() {
    local b2c_rc=$?

    set +e
    if test "$B2C_BIN_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin
    fi
    if test "$B2C_SCHEMA_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/share/schemas
    fi
    if test "$b2c_rc" -eq 0; then
        printf '\nB2_CANCEL_RESULT=PASS\n'
    else
        printf '\nB2_CANCEL_RESULT=FAIL exit_code=%s\n' "$b2c_rc"
    fi
    printf 'B2_CANCEL_REPORT=%s\n' "$B2C_REPORT"
    trap - EXIT
    exit "$b2c_rc"
}

b2c_check_sha256() {
    local b2c_expected=$1
    local b2c_path=$2
    local b2c_actual

    b2c_actual=$(sha256sum "$b2c_path")
    b2c_actual=${b2c_actual%% *}
    printf '%s  %s\n' "$b2c_actual" "$b2c_path"
    test "$b2c_actual" = "$b2c_expected"
}

trap b2c_cleanup EXIT

# Validate the exact reviewed local checkout
test "$#" -eq 1
B2C_COMMIT=$1
B2C_REPO=/home/nnovikov/repo/A1-OUinp
B2C_SRC="$B2C_REPO/dev_scratch/hpc/helper_src"
printf 'B2 protected-cancel promotion: local\n'
printf 'B2 cancel commit: %s\n' "$B2C_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2C_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$B2C_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B2C_REPO" -C "$B2C_REPO" rev-parse HEAD)" = "$B2C_COMMIT"
test "$(git -c safe.directory="$B2C_REPO" -C "$B2C_REPO" branch --show-current)" = 'codex-hpc'

# Verify the reviewed local sources
printf '\n== Reviewed source hashes ==\n'
b2c_check_sha256 '6436d884a1966e84daeba8a096062ea556a42203a4bdac59a2eab8a592e477dd' "$B2C_SRC/local/hpc-job"
b2c_check_sha256 'f16bcb69ae0346f63ef7deed299565f0cb5f35154a9c90ae69526880f8eec8fd' "$B2C_SRC/local/hpc_common.py"
b2c_check_sha256 '8a13ac620d4bf120c826462aaf0c5b83b0d7ba247bd2a034b9824a54ce333040' "$B2C_SRC/schemas/remote-hpc-job-config.schema.json"

# Install only the changed protected local files
printf '\n== Installation ==\n'
B2C_BIN_OPEN=1
chmod 0755 /opt/a1-hpc/bin
install -o root -g root -m 0555 "$B2C_SRC/local/hpc-job" /opt/a1-hpc/bin/hpc-job
install -o root -g root -m 0444 "$B2C_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
chmod 0555 /opt/a1-hpc/bin
B2C_BIN_OPEN=0
B2C_SCHEMA_OPEN=1
chmod 0755 /opt/a1-hpc/share/schemas
install -o root -g root -m 0444 \
    "$B2C_SRC/schemas/remote-hpc-job-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json
chmod 0555 /opt/a1-hpc/share/schemas
B2C_SCHEMA_OPEN=0

# Verify the promoted version, hashes and permissions
printf '\n== Installed identities ==\n'
/opt/a1-hpc/bin/hpc-helper-info --json info
/opt/a1-hpc/bin/hpc-job cancel --help
b2c_check_sha256 '6436d884a1966e84daeba8a096062ea556a42203a4bdac59a2eab8a592e477dd' /opt/a1-hpc/bin/hpc-job
b2c_check_sha256 'f16bcb69ae0346f63ef7deed299565f0cb5f35154a9c90ae69526880f8eec8fd' /opt/a1-hpc/bin/hpc_common.py
b2c_check_sha256 '8a13ac620d4bf120c826462aaf0c5b83b0d7ba247bd2a034b9824a54ce333040' /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-job \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-job-config.schema.json \
    /opt/a1-hpc/state/actions.jsonl
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
