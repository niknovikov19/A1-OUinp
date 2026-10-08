#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A5_REPORT=$(mktemp /tmp/a5-local-promotion.XXXXXX.txt)
chmod 0644 "$A5_REPORT"
exec > >(tee "$A5_REPORT") 2>&1

A5_LOCAL_DIRS_OPEN=0

a5_cleanup() {
    local a5_rc=$?

    set +e
    if test "$A5_LOCAL_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            /opt/a1-hpc/bin \
            /opt/a1-hpc/share/schemas
    fi

    if test "$a5_rc" -eq 0; then
        printf '\nA5_RESULT=PASS\n'
    else
        printf '\nA5_RESULT=FAIL exit_code=%s\n' "$a5_rc"
    fi
    printf 'A5_REPORT=%s\n' "$A5_REPORT"
    chmod 0644 "$A5_REPORT"
    trap - EXIT
    exit "$a5_rc"
}

a5_check_sha256() {
    local a5_expected=$1
    local a5_path=$2
    local a5_actual

    a5_actual=$(sha256sum "$a5_path")
    a5_actual=${a5_actual%% *}
    printf '%s  %s\n' "$a5_actual" "$a5_path"
    test "$a5_actual" = "$a5_expected"
}

trap a5_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
A5_COMMIT=$1
A5_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A5_SRC="$A5_LOCAL_REPO/dev_scratch/hpc/helper_src"

printf 'A5 promotion: local\n'
printf 'A5 commit: %s\n' "$A5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A5_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$A5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$A5_LOCAL_REPO" \
    -C "$A5_LOCAL_REPO" rev-parse HEAD)" = "$A5_COMMIT"
test "$(git -c safe.directory="$A5_LOCAL_REPO" \
    -C "$A5_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify every reviewed local source artifact
printf '\n== Reviewed source hashes ==\n'
a5_check_sha256 \
    'dde49bb7b565adb96fb38b559e0cbbaa5eb8abbf5fc7353e5f72634871543cd0' \
    "$A5_SRC/local/hpc-status"
a5_check_sha256 \
    'e4b894a3b7e92585974d48ab6c4de87b77b3646665c20f6b9b730fa713432423' \
    "$A5_SRC/local/hpc_common.py"
a5_check_sha256 \
    'fff824437f4b755b8fad896346c9ad53eae101add4b87a82031389551a189c75' \
    "$A5_SRC/schemas/remote-hpc-status-config.schema.json"
a5_check_sha256 \
    'e29da82aa81c9cb62d9bb5f52f4b9201c3aae40c60eb9abe3672086e6a2e7ade' \
    "$A5_SRC/schemas/status-record.schema.json"

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A5_LOCAL_DIRS_OPEN=1
chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas

install -o root -g root -m 0555 \
    "$A5_SRC/local/hpc-status" \
    /opt/a1-hpc/bin/hpc-status
install -o root -g root -m 0444 \
    "$A5_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 \
    "$A5_SRC/schemas/remote-hpc-status-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-status-config.schema.json
install -o root -g root -m 0444 \
    "$A5_SRC/schemas/status-record.schema.json" \
    /opt/a1-hpc/share/schemas/status-record.schema.json

chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas
A5_LOCAL_DIRS_OPEN=0

# Verify the installed bundle, files, and permissions
printf '\n== Installed bundle identity ==\n'
A5_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$A5_INFO"
printf '%s\n' "$A5_INFO" | grep -Fq '"bundle_version": "0.6.0-a5"'
A5_BUNDLE_SHA=ed3200ad97205464f86120ed0daf116cb73bb669b7d7c0c9615ce83c55f55d76
printf '%s\n' "$A5_INFO" | grep -Fq \
    "\"bundle_sha256\": \"$A5_BUNDLE_SHA\""

printf '\n== Installed hashes ==\n'
a5_check_sha256 \
    'dde49bb7b565adb96fb38b559e0cbbaa5eb8abbf5fc7353e5f72634871543cd0' \
    /opt/a1-hpc/bin/hpc-status
a5_check_sha256 \
    'e4b894a3b7e92585974d48ab6c4de87b77b3646665c20f6b9b730fa713432423' \
    /opt/a1-hpc/bin/hpc_common.py
a5_check_sha256 \
    'fff824437f4b755b8fad896346c9ad53eae101add4b87a82031389551a189c75' \
    /opt/a1-hpc/share/schemas/remote-hpc-status-config.schema.json
a5_check_sha256 \
    'e29da82aa81c9cb62d9bb5f52f4b9201c3aae40c60eb9abe3672086e6a2e7ade' \
    /opt/a1-hpc/share/schemas/status-record.schema.json

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-status \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-status-config.schema.json \
    /opt/a1-hpc/share/schemas/status-record.schema.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
