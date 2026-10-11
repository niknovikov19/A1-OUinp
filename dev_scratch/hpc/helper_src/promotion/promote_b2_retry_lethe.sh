#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe policy-promotion transcript
B2R_ROOT=/ddn/niknovikov19/hpc_codex
B2R_REPORT_DIR="$B2R_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B2R_REPORT_DIR"
chmod 0700 "$B2R_REPORT_DIR"
B2R_REPORT=$(mktemp "$B2R_REPORT_DIR/b2-retry-remote-promotion.XXXXXX.txt")
chmod 0600 "$B2R_REPORT"
exec > >(tee "$B2R_REPORT") 2>&1
B2R_CONFIG_OPEN=0

b2r_cleanup() {
    local b2r_rc=$?

    set +e
    if test "$B2R_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$B2R_ROOT/config"
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

# Validate the exact clean automation checkout
test "$#" -eq 1
B2R_COMMIT=$1
B2R_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2R_CONFIG="$B2R_REPO/dev_scratch/hpc/helper_src/config_examples/remote-hpc-prepare.json.example"
B2R_REQUEST="$B2R_REPO/hpc_jobs/requests/b2-child-discovery.json"
B2R_TEMPLATE="$B2R_REPO/hpc_jobs/templates/batch.sh"
B2R_STATE="$B2R_ROOT/state/A1_OUinp"
printf 'B2 node-isolation policy promotion: lethe\n'
printf 'B2 retry commit: %s\n' "$B2R_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2R_REPORT"
printf '%s\n' "$B2R_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
test "$(git -C "$B2R_REPO" rev-parse HEAD)" = "$B2R_COMMIT"
test "$(git -C "$B2R_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B2R_REPO" status --porcelain=v1)"

# Review the preparation ceiling and exact B2 allocation
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool "$B2R_CONFIG"
printf '\n== Reviewed B2 request ==\n'
python3 -m json.tool "$B2R_REQUEST"
sha256sum "$B2R_CONFIG" "$B2R_REQUEST" "$B2R_TEMPLATE"

# Install only the reviewed preparation policy
printf '\n== Installation ==\n'
B2R_CONFIG_OPEN=1
chmod 0755 "$B2R_ROOT/config"
install -g salvadord -m 0444 "$B2R_CONFIG" "$B2R_ROOT/config/A1_OUinp-prepare.json"
chmod 0555 "$B2R_ROOT/config"
B2R_CONFIG_OPEN=0

# Verify the installed policy and fresh retry identity
printf '\n== Installed configuration ==\n'
sha256sum "$B2R_ROOT/config/A1_OUinp-prepare.json"
cmp -s "$B2R_CONFIG" "$B2R_ROOT/config/A1_OUinp-prepare.json"
stat -c '%A %a %U:%G %n' "$B2R_ROOT/config" "$B2R_ROOT/config/A1_OUinp-prepare.json"
test ! -e "$B2R_REPO/hpc_jobs/runs/b2-child-discovery-004"
test ! -e "$B2R_STATE/runs/b2-child-discovery-004.json"
test ! -e "$B2R_STATE/active-run.json"
printf 'Fresh B2 retry run ID: absent as expected\n'
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
