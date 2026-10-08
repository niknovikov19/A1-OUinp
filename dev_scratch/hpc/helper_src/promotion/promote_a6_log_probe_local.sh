#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A62_REPORT=$(mktemp /tmp/a6-log-probe-local-promotion.XXXXXX.txt)
chmod 0644 "$A62_REPORT"
exec > >(tee "$A62_REPORT") 2>&1

A62_REGISTRY_TMP=''
A62_CONFIG_OPEN=0

a62_cleanup() {
    local a62_rc=$?

    set +e
    if test "$A62_CONFIG_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/config
    fi
    if test -n "$A62_REGISTRY_TMP" && test -f "$A62_REGISTRY_TMP"; then
        rm -f "$A62_REGISTRY_TMP"
    fi

    if test "$a62_rc" -eq 0; then
        printf '\nA6_2_RESULT=PASS\n'
    else
        printf '\nA6_2_RESULT=FAIL exit_code=%s\n' "$a62_rc"
    fi
    printf 'A6_2_REPORT=%s\n' "$A62_REPORT"
    chmod 0644 "$A62_REPORT"
    trap - EXIT
    exit "$a62_rc"
}

a62_check_sha256() {
    local a62_expected=$1
    local a62_path=$2
    local a62_actual

    a62_actual=$(sha256sum "$a62_path")
    a62_actual=${a62_actual%% *}
    printf '%s  %s\n' "$a62_actual" "$a62_path"
    test "$a62_actual" = "$a62_expected"
}

trap a62_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
A62_COMMIT=$1
A62_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A62_SRC="$A62_LOCAL_REPO/dev_scratch/hpc/helper_src"
A62_REGISTRY_TMP=$(mktemp /tmp/a6-log-probe-registry.XXXXXX.json)

printf 'A6.2 promotion: local request registry\n'
printf 'A6.2 commit: %s\n' "$A62_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A62_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$A62_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$A62_LOCAL_REPO" \
    -C "$A62_LOCAL_REPO" rev-parse HEAD)" = "$A62_COMMIT"
test "$(git -c safe.directory="$A62_LOCAL_REPO" \
    -C "$A62_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Generate the exact commit-bound request registry
printf '\n== Reviewed source hash ==\n'
a62_check_sha256 \
    '9628ae9fdf027107bd4371ee1a6c969932a92097ee9dcc5065689d16300b2722' \
    "$A62_SRC/config_examples/preview-requests.json.example"

printf '\n== Generated request registry ==\n'
sed "s/0000000000000000000000000000000000000000/$A62_COMMIT/g" \
    "$A62_SRC/config_examples/preview-requests.json.example" \
    > "$A62_REGISTRY_TMP"

python3 -m json.tool "$A62_REGISTRY_TMP" >/dev/null
test "$(grep -c "\"expected_commit\": \"$A62_COMMIT\"" \
    "$A62_REGISTRY_TMP")" -eq 11
test "$(grep -c \
    '"expected_commit": "1111111111111111111111111111111111111111"' \
    "$A62_REGISTRY_TMP")" -eq 1
if grep -q '0000000000000000000000000000000000000000' \
    "$A62_REGISTRY_TMP"; then
    printf 'Unreplaced commit placeholder found\n' >&2
    exit 1
fi
A62_REGISTRY_SHA256=$(sha256sum "$A62_REGISTRY_TMP")
A62_REGISTRY_SHA256=${A62_REGISTRY_SHA256%% *}
printf '%s  generated-preview-requests.json\n' "$A62_REGISTRY_SHA256"
printf 'expected_commit entries: 11\n'
printf 'deliberate rejection entries: 1\n'

# Install only the updated protected request registry
printf '\n== Installation ==\n'
A62_CONFIG_OPEN=1
chmod 0755 /opt/a1-hpc/config
install -o root -g root -m 0444 \
    "$A62_REGISTRY_TMP" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json
chmod 0555 /opt/a1-hpc/config
A62_CONFIG_OPEN=0

# Verify the unchanged A6 bundle and installed registry
printf '\n== Installed bundle identity ==\n'
A62_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$A62_INFO"
printf '%s\n' "$A62_INFO" | grep -Fq '"bundle_version": "0.7.0-a6"'
A62_BUNDLE_SHA=ce7488da6de975fb22fa93cdc39dbe893cfefb3b4ecc67abfb022d1477c5fb2a
printf '%s\n' "$A62_INFO" | grep -Fq \
    "\"bundle_sha256\": \"$A62_BUNDLE_SHA\""

printf '\n== Installed hash and permissions ==\n'
a62_check_sha256 \
    "$A62_REGISTRY_SHA256" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json
a62_check_sha256 \
    '58840c04606f72071184688aedc6c12449851da9d1235768b910466ef7b7fee1' \
    /opt/a1-hpc/bin/hpc-log
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/config \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json \
    /opt/a1-hpc/bin/hpc-log \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl \
    /opt/a1-hpc/state/log-cursors.json \
    /opt/a1-hpc/state/log-cursors.lock

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
