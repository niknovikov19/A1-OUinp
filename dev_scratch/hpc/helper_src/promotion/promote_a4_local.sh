#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A4_REPORT=$(mktemp /tmp/a4-local-promotion.XXXXXX.txt)
chmod 0644 "$A4_REPORT"
exec > >(tee "$A4_REPORT") 2>&1

A4_REGISTRY_TMP=''
A4_LOCAL_DIRS_OPEN=0

a4_cleanup() {
    local a4_rc=$?

    set +e
    if test "$A4_LOCAL_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            /opt/a1-hpc/bin \
            /opt/a1-hpc/config \
            /opt/a1-hpc/share/schemas
    fi
    if test -n "$A4_REGISTRY_TMP" && test -f "$A4_REGISTRY_TMP"; then
        rm -f "$A4_REGISTRY_TMP"
    fi

    if test "$a4_rc" -eq 0; then
        printf '\nA4_RESULT=PASS\n'
    else
        printf '\nA4_RESULT=FAIL exit_code=%s\n' "$a4_rc"
    fi
    printf 'A4_REPORT=%s\n' "$A4_REPORT"
    chmod 0644 "$A4_REPORT"
    trap - EXIT
    exit "$a4_rc"
}

a4_check_sha256() {
    local a4_expected=$1
    local a4_path=$2
    local a4_actual

    a4_actual=$(sha256sum "$a4_path")
    a4_actual=${a4_actual%% *}
    printf '%s  %s\n' "$a4_actual" "$a4_path"
    test "$a4_actual" = "$a4_expected"
}

trap a4_cleanup EXIT

# Validate invocation and the exact reviewed checkout
test "$#" -eq 1
A4_COMMIT=$1
A4_LOCAL_REPO=/home/nnovikov/repo/A1-OUinp
A4_SRC="$A4_LOCAL_REPO/dev_scratch/hpc/helper_src"
A4_REGISTRY_TMP=$(mktemp /tmp/a4-preview-registry.XXXXXX.json)

printf 'A4 promotion: local\n'
printf 'A4 commit: %s\n' "$A4_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A4_REPORT"

test "$(id -u)" -eq 0
printf '%s\n' "$A4_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$A4_LOCAL_REPO" \
    -C "$A4_LOCAL_REPO" rev-parse HEAD)" = "$A4_COMMIT"
test "$(git -c safe.directory="$A4_LOCAL_REPO" \
    -C "$A4_LOCAL_REPO" branch --show-current)" = 'codex-hpc'

# Verify every reviewed local source artifact
printf '\n== Reviewed source hashes ==\n'
a4_check_sha256 \
    '93c535091808a7c5d7115916e8632f9140bbaf001c55245933a553a3ea1d7e78' \
    "$A4_SRC/local/hpc-submit"
a4_check_sha256 \
    '84e2aaae3658a613ad47648641869df61ec1a4a2442ea0c94ba35ec52242215c' \
    "$A4_SRC/local/hpc_common.py"
a4_check_sha256 \
    '3fd2432071cc24ac1f615a1456fe018204c3b3438fc10438c7902790d248835a' \
    "$A4_SRC/schemas/remote-hpc-submit-config.schema.json"
a4_check_sha256 \
    '08275824f920de7c500f2658091e4b42b8d8d0ec4b4c497a7e9bfb21671c1e9e' \
    "$A4_SRC/schemas/submission-record.schema.json"
a4_check_sha256 \
    '5b5beae245ee448093ea87aaadf9060260c43e7a7d9711b53194c3bd13fda711' \
    "$A4_SRC/config_examples/preview-requests.json.example"

# Generate and validate the commit-bound request registry
printf '\n== Generated request registry ==\n'
sed "s/0000000000000000000000000000000000000000/$A4_COMMIT/g" \
    "$A4_SRC/config_examples/preview-requests.json.example" \
    > "$A4_REGISTRY_TMP"

python3 -m json.tool "$A4_REGISTRY_TMP" >/dev/null
test "$(grep -c "\"expected_commit\": \"$A4_COMMIT\"" \
    "$A4_REGISTRY_TMP")" -eq 9
test "$(grep -c \
    '"expected_commit": "1111111111111111111111111111111111111111"' \
    "$A4_REGISTRY_TMP")" -eq 1
if grep -q '0000000000000000000000000000000000000000' "$A4_REGISTRY_TMP"; then
    printf 'Unreplaced commit placeholder found\n' >&2
    exit 1
fi
A4_REGISTRY_SHA256=$(sha256sum "$A4_REGISTRY_TMP")
A4_REGISTRY_SHA256=${A4_REGISTRY_SHA256%% *}
printf '%s  generated-preview-requests.json\n' "$A4_REGISTRY_SHA256"
printf 'expected_commit entries: 9\n'
printf 'deliberate rejection entries: 1\n'

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A4_LOCAL_DIRS_OPEN=1
chmod 0755 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas

install -o root -g root -m 0555 \
    "$A4_SRC/local/hpc-submit" \
    /opt/a1-hpc/bin/hpc-submit
install -o root -g root -m 0444 \
    "$A4_SRC/local/hpc_common.py" \
    /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 \
    "$A4_SRC/schemas/remote-hpc-submit-config.schema.json" \
    /opt/a1-hpc/share/schemas/remote-hpc-submit-config.schema.json
install -o root -g root -m 0444 \
    "$A4_SRC/schemas/submission-record.schema.json" \
    /opt/a1-hpc/share/schemas/submission-record.schema.json
install -o root -g root -m 0444 \
    "$A4_REGISTRY_TMP" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

chmod 0555 \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas
A4_LOCAL_DIRS_OPEN=0

# Verify the installed bundle, files, and permissions
printf '\n== Installed bundle identity ==\n'
A4_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$A4_INFO"
printf '%s\n' "$A4_INFO" | grep -Fq '"bundle_version": "0.5.0-a4"'
printf '%s\n' "$A4_INFO" | grep -Fq \
    '"bundle_sha256": "cb1d52d6b5bcaac811cdf0c33e529f64d223549bf3044c43ef6cd13f27eb30ed"'

printf '\n== Installed hashes ==\n'
a4_check_sha256 \
    '93c535091808a7c5d7115916e8632f9140bbaf001c55245933a553a3ea1d7e78' \
    /opt/a1-hpc/bin/hpc-submit
a4_check_sha256 \
    '84e2aaae3658a613ad47648641869df61ec1a4a2442ea0c94ba35ec52242215c' \
    /opt/a1-hpc/bin/hpc_common.py
a4_check_sha256 \
    '3fd2432071cc24ac1f615a1456fe018204c3b3438fc10438c7902790d248835a' \
    /opt/a1-hpc/share/schemas/remote-hpc-submit-config.schema.json
a4_check_sha256 \
    '08275824f920de7c500f2658091e4b42b8d8d0ec4b4c497a7e9bfb21671c1e9e' \
    /opt/a1-hpc/share/schemas/submission-record.schema.json
a4_check_sha256 \
    "$A4_REGISTRY_SHA256" \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-submit \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/share/schemas/remote-hpc-submit-config.schema.json \
    /opt/a1-hpc/share/schemas/submission-record.schema.json \
    /opt/a1-hpc/config/A1_OUinp-preview-requests.json \
    /opt/a1-hpc/state \
    /opt/a1-hpc/state/actions.jsonl

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
