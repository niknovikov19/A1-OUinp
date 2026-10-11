#!/bin/bash

set -Eeuo pipefail

# Capture the complete local promotion transcript
B5_REPORT=$(mktemp /tmp/b5-result-local-promotion.XXXXXX.txt)
chmod 0644 "$B5_REPORT"
exec > >(tee "$B5_REPORT") 2>&1
B5_DIRS_OPEN=0

b5_cleanup() {
    local b5_rc=$?

    set +e
    if test "$B5_DIRS_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/config /opt/a1-hpc/share/schemas
    fi
    if test "$b5_rc" -eq 0; then
        printf '\nB5_RESULT=PASS\n'
    else
        printf '\nB5_RESULT=FAIL exit_code=%s\n' "$b5_rc"
    fi
    printf 'B5_REPORT=%s\n' "$B5_REPORT"
    trap - EXIT
    exit "$b5_rc"
}

b5_check_sha256() {
    local b5_expected=$1
    local b5_path=$2
    local b5_actual

    b5_actual=$(sha256sum "$b5_path")
    b5_actual=${b5_actual%% *}
    printf '%s  %s\n' "$b5_actual" "$b5_path"
    test "$b5_actual" = "$b5_expected"
}

trap b5_cleanup EXIT

# Validate the exact reviewed checkout
test "$#" -eq 1
B5_COMMIT=$1
B5_REPO=/home/nnovikov/repo/A1-OUinp
B5_SRC="$B5_REPO/dev_scratch/hpc/helper_src"
printf 'B5 result-access promotion: local\n'
printf 'B5 commit: %s\n' "$B5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B5_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$B5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B5_REPO" -C "$B5_REPO" rev-parse HEAD)" = "$B5_COMMIT"
test "$(git -c safe.directory="$B5_REPO" -C "$B5_REPO" branch --show-current)" = 'codex-hpc'

# Display and verify the local non-secret cache policy
printf '\n== Reviewed local configuration ==\n'
python3 -m json.tool "$B5_SRC/config_examples/local-hpc-result.json.example"
if grep -Eiq 'password|token|private[_-]?key|key[_-]?path|https?://|ssh://|git@' "$B5_SRC/config_examples/local-hpc-result.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every promoted local artifact
printf '\n== Reviewed source hashes ==\n'
b5_check_sha256 '8a51b05bb53988703d93a43d24406d9fa98d553920c30d3d0fcbe0998d616e11' "$B5_SRC/local/hpc-result"
b5_check_sha256 '85039dca58bdfc423ec33885ef556b64d154e00f485e6fa3b707318c3f79ad9d' "$B5_SRC/local/hpc_common.py"
b5_check_sha256 'c161238017b5c44edbd09dffde2398c89136524ef46c6607eba9399d3c9a6e89' "$B5_SRC/config_examples/local-hpc-result.json.example"
b5_check_sha256 '58f0ebe2464fd4a6cd29af56edd06baf05a0c236f580e1ebf7254edd5c28f4de' "$B5_SRC/schemas/local-hpc-result-config.schema.json"
b5_check_sha256 'ca2b7cae75e7958f3c9d37d725136fca299be42e7579ffef01556d9bdfe8c108' "$B5_SRC/schemas/remote-hpc-result-config.schema.json"
b5_check_sha256 '04604163773397d81553369577fad684e1e7fef1c6fc0f782a3287f9e9a9c0ab' "$B5_SRC/schemas/result-inventory.schema.json"

# Install while restoring protected directories on every exit
printf '\n== Installation ==\n'
B5_DIRS_OPEN=1
chmod 0755 /opt/a1-hpc/bin /opt/a1-hpc/config /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 "$B5_SRC/local/hpc-result" /opt/a1-hpc/bin/hpc-result
install -o root -g root -m 0444 "$B5_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 "$B5_SRC/config_examples/local-hpc-result.json.example" /opt/a1-hpc/config/A1_OUinp-result.json
install -o root -g root -m 0444 "$B5_SRC/schemas/local-hpc-result-config.schema.json" /opt/a1-hpc/share/schemas/local-hpc-result-config.schema.json
install -o root -g root -m 0444 "$B5_SRC/schemas/remote-hpc-result-config.schema.json" /opt/a1-hpc/share/schemas/remote-hpc-result-config.schema.json
install -o root -g root -m 0444 "$B5_SRC/schemas/result-inventory.schema.json" /opt/a1-hpc/share/schemas/result-inventory.schema.json
chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/config /opt/a1-hpc/share/schemas
B5_DIRS_OPEN=0

# Verify installed identity and permissions
printf '\n== Installed identity ==\n'
B5_INFO=$(/opt/a1-hpc/bin/hpc-helper-info --json info)
printf '%s\n' "$B5_INFO"
printf '%s\n' "$B5_INFO" | grep -Fq '"bundle_version": "0.13.0-b5"'
printf '%s\n' "$B5_INFO" | grep -Fq '"hpc-result": "8a51b05bb53988703d93a43d24406d9fa98d553920c30d3d0fcbe0998d616e11"'
b5_check_sha256 'c161238017b5c44edbd09dffde2398c89136524ef46c6607eba9399d3c9a6e89' /opt/a1-hpc/config/A1_OUinp-result.json
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/config \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-result \
    /opt/a1-hpc/bin/hpc_common.py \
    /opt/a1-hpc/config/A1_OUinp-result.json
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
