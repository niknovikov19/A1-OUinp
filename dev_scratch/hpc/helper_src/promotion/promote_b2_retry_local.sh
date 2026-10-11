#!/bin/bash

set -Eeuo pipefail

# Capture the complete local policy-promotion transcript
B2R_REPORT=$(mktemp /tmp/b2-retry-local-promotion.XXXXXX.txt)
chmod 0644 "$B2R_REPORT"
exec > >(tee "$B2R_REPORT") 2>&1
B2R_CONFIG_OPEN=0

b2r_cleanup() {
    local b2r_rc=$?

    set +e
    if test "$B2R_CONFIG_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/config
    fi
    if test "$b2r_rc" -eq 0; then
        printf '\nB2_RETRY_RESULT=PASS\n'
    else
        printf '\nB2_RETRY_RESULT=FAIL exit_code=%s\n' "$b2r_rc"
    fi
    printf 'B2_RETRY_REPORT=%s\n' "$B2R_REPORT"
    trap - EXIT
    exit "$b2r_rc"
}

trap b2r_cleanup EXIT

# Validate the exact reviewed checkout
test "$#" -eq 1
B2R_COMMIT=$1
B2R_REPO=/home/nnovikov/repo/A1-OUinp
B2R_CONFIG="$B2R_REPO/dev_scratch/hpc/helper_src/config_examples/hpc-helper.json.example"
printf 'B2 retry resource-policy promotion: local\n'
printf 'B2 retry commit: %s\n' "$B2R_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2R_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$B2R_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$B2R_REPO" -C "$B2R_REPO" rev-parse HEAD)" = "$B2R_COMMIT"
test "$(git -c safe.directory="$B2R_REPO" -C "$B2R_REPO" branch --show-current)" = 'codex-hpc'

# Review the non-secret protected resource ceiling
printf '\n== Reviewed local configuration ==\n'
python3 -m json.tool "$B2R_CONFIG"
sha256sum "$B2R_CONFIG"

# Install the reviewed global configuration
printf '\n== Installation ==\n'
B2R_CONFIG_OPEN=1
chmod 0755 /opt/a1-hpc/config
install -o root -g root -m 0444 "$B2R_CONFIG" /opt/a1-hpc/config/hpc-helper.json
chmod 0555 /opt/a1-hpc/config
B2R_CONFIG_OPEN=0

# Verify the installed policy and protected mode
printf '\n== Installed configuration ==\n'
sha256sum /opt/a1-hpc/config/hpc-helper.json
cmp -s "$B2R_CONFIG" /opt/a1-hpc/config/hpc-helper.json
/opt/a1-hpc/bin/hpc-helper-info --json info
stat -c '%A %a %U:%G %n' /opt/a1-hpc/config /opt/a1-hpc/config/hpc-helper.json
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
