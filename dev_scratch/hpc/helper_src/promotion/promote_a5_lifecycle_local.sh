#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A52_REPORT=$(mktemp /tmp/a5-lifecycle-local-promotion.XXXXXX.txt)
chmod 0644 "$A52_REPORT"
exec > >(tee "$A52_REPORT") 2>&1

A52_REGISTRY_TMP=''
A52_CONFIG_OPEN=0

a52_cleanup() {
    local a52_rc=$?

    set +e
    if test "$A52_CONFIG_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/config
    fi
    if test -n "$A52_REGISTRY_TMP" && test -f "$A52_REGISTRY_TMP"; then
        rm -f "$A52_REGISTRY_TMP"
    fi

    if test "$a52_rc" -eq 0; then
        printf '\nA5_2_RESULT=PASS\n'
    else
        printf '\nA5_2_RESULT=FAIL exit_code=%s\n' "$a52_rc"
    fi
    printf 'A5_2_REPORT=%s\n' "$A52_REPORT"
    chmod 0644 "$A52_REPORT"
    trap - EXIT
    exit "$a52_rc"
}

a52_check_sha256() {
    local a52_expected=$1
    local a52_path=$2
    local a52_actual

    a52_actual=$(sha256sum "$a52_path")
    a52_actual=${a52_actual%% *}
    printf '%s  %s\n' "$a52_actual" "$a52_path"
    test "$a52_actual" = "$a52_expected"
}

trap a52_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
A52_COMMIT=$1
A52_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A52_SRC="$A52_LOCAL_REPO/dev_scratch/hpc/helper_src"
A52_REGISTRY_TMP=$(mktemp /tmp/a5-lifecycle-registry.XXXXXX.json)

printf 'A5.2 promotion: local request registry\n'
printf 'A5.2 commit: %s\n' "$A52_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A52_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$A52_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$A52_LOCAL_REPO" \
    -C "$A52_LOCAL_REPO" rev-parse HEAD)" = "$A52_COMMIT"
test "$(git -c safe.directory="$A52_LOCAL_REPO" \
    -C "$A52_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify and generate the commit-bound request registry
printf '\n== Reviewed source hash ==\n'
a52_check_sha256 \
    '6f5c27643a3f2eb404ab0ed77ab5a3a54a2fa042230e19d5b5d7b63943177dea' \
    "$A52_SRC/config_examples/preview-requests.json.example"

printf '\n== Generated request registry ==\n'
sed "s/0000000000000000000000000000000000000000/$A52_COMMIT/g" \
    "$A52_SRC/config_examples/preview-requests.json.example" \
    > "$A52_REGISTRY_TMP"

python3 -m json.tool "$A52_REGISTRY_TMP" >/dev/null
test "$(grep -c "\"expected_commit\": \"$A52_COMMIT\"" \
    "$A52_REGISTRY_TMP")" -eq 10
test "$(grep -c \
    '"expected_commit": "1111111111111111111111111111111111111111"' \
    "$A52_REGISTRY_TMP")" -eq 1
if grep -q '0000000000000000000000000000000000000000' \
    "$A52_REGISTRY_TMP"; then
    printf 'Unreplaced commit placeholder found\n' >&2
    exit 1
fi
A52_REGISTRY_SHA256=$(sha256sum "$A52_REGISTRY_TMP")
A52_REGISTRY_SHA256=${A52_REGISTRY_SHA256%% *}
printf '%s  generated-preview-requests.json\n' "$A52_REGISTRY_SHA256"
printf 'expected_commit entries: 10\n'
printf 'deliberate rejection entries: 1\n'

# Install only the updated protected request registry
printf '\n== Installation ==\n'
A52_CONFIG_OPEN=1
chmod 0755 /opt/a1-hpc/config
install -o root -g root -m 0444 \
    "$A52_REGISTRY_TMP" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json
chmod 0555 /opt/a1-hpc/config
A52_CONFIG_OPEN=0

# Verify the unchanged bundle, installed registry, and state permissions
printf '\n== Installed bundle identity ==\n'
A52_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$A52_INFO"
printf '%s\n' "$A52_INFO" | grep -Fq '"bundle_version": "0.6.0-a5"'
A52_BUNDLE_SHA=ed3200ad97205464f86120ed0daf116cb73bb669b7d7c0c9615ce83c55f55d76
printf '%s\n' "$A52_INFO" | grep -Fq \
    "\"bundle_sha256\": \"$A52_BUNDLE_SHA\""

printf '\n== Installed hash and permissions ==\n'
a52_check_sha256 \
    "$A52_REGISTRY_SHA256" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/config \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
