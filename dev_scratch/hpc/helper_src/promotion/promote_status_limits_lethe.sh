#!/bin/bash

set -Eeuo pipefail

# Record the narrowly scoped status-policy promotion
HPCLIM_ROOT=/ddn/niknovikov19/hpc_codex
HPCLIM_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
HPCLIM_REPORT_DIR="$HPCLIM_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$HPCLIM_REPORT_DIR"
chmod 0700 "$HPCLIM_REPORT_DIR"
HPCLIM_REPORT=$(mktemp "$HPCLIM_REPORT_DIR/hpc-status-limits-promotion.XXXXXX.txt")
chmod 0600 "$HPCLIM_REPORT"
exec > >(tee "$HPCLIM_REPORT") 2>&1
HPCLIM_CONFIG_OPEN=0
HPCLIM_TEMP=''

hpclim_cleanup() {
    local hpclim_rc=$?

    set +e
    if test "$HPCLIM_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$HPCLIM_ROOT/config"
    fi
    if test -n "$HPCLIM_TEMP"; then
        rm -f -- "$HPCLIM_TEMP"
    fi
    if test "$hpclim_rc" -eq 0; then
        printf '\nHPC_STATUS_LIMIT_RESULT=PASS\n'
    else
        printf '\nHPC_STATUS_LIMIT_RESULT=FAIL exit_code=%s\n' "$hpclim_rc"
    fi
    printf 'HPC_STATUS_LIMIT_REPORT=%s\n' "$HPCLIM_REPORT"
    trap - EXIT
    exit "$hpclim_rc"
}

trap hpclim_cleanup EXIT

# Bind the promotion to the existing checkout without fetching during a run
test "$#" -eq 1
HPCLIM_COMMIT=$1
printf '%s\n' "$HPCLIM_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$HPCLIM_REPO" rev-parse HEAD)" = "$HPCLIM_COMMIT"
test "$(git -C "$HPCLIM_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$HPCLIM_REPO" status --porcelain=v1)"
printf 'Status limits promotion: 100 IDs, 30-second query timeout\nCommit: %s\n' "$HPCLIM_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Allow an active run because only read-only status-query limits change
HPCLIM_TARGET="$HPCLIM_ROOT/config/A1_OUinp-status.json"
HPCLIM_OLD_HASH='251a37ff7b3c933489d6c2206593a982f95e831173972f45b617957edf910b4e'
HPCLIM_PILOT_HASH='4dfe14a7219c36094158017cd091f548312e4b5a7984b623a9bbfc3bb8491e85'
HPCLIM_NEW_HASH='28f59366c6c05c86c1fb7fbdc3be143293c27fde67c624ced54f66bf20deee7c'
HPCLIM_INSTALLED_HASH=$(sha256sum "$HPCLIM_TARGET")
HPCLIM_INSTALLED_HASH=${HPCLIM_INSTALLED_HASH%% *}
printf '%s  %s\n' "$HPCLIM_INSTALLED_HASH" "$HPCLIM_TARGET"
case "$HPCLIM_INSTALLED_HASH" in
    "$HPCLIM_OLD_HASH"|"$HPCLIM_PILOT_HASH"|"$HPCLIM_NEW_HASH") ;;
    *) printf 'Unexpected installed status-policy hash\n'; exit 1 ;;
esac

# Change exactly two values and verify the complete resulting policy
HPCLIM_TEMP=$(mktemp /tmp/hpc-status-limits-policy.XXXXXX.json)
sed -E \
    -e 's/"max_job_ids": (11|13),/"max_job_ids": 100,/' \
    -e 's/"query_timeout_sec": 15,/"query_timeout_sec": 30,/' \
    "$HPCLIM_TARGET" > "$HPCLIM_TEMP"
HPCLIM_TEMP_HASH=$(sha256sum "$HPCLIM_TEMP")
HPCLIM_TEMP_HASH=${HPCLIM_TEMP_HASH%% *}
test "$HPCLIM_TEMP_HASH" = "$HPCLIM_NEW_HASH"
python3 -m json.tool "$HPCLIM_TEMP" >/dev/null

# Install only the reviewed policy and restore the protected directory
HPCLIM_CONFIG_OPEN=1
chmod 0755 "$HPCLIM_ROOT/config"
install -g salvadord -m 0444 "$HPCLIM_TEMP" "$HPCLIM_TARGET"
chmod 0555 "$HPCLIM_ROOT/config"
HPCLIM_CONFIG_OPEN=0
HPCLIM_INSTALLED_HASH=$(sha256sum "$HPCLIM_TARGET")
HPCLIM_INSTALLED_HASH=${HPCLIM_INSTALLED_HASH%% *}
test "$HPCLIM_INSTALLED_HASH" = "$HPCLIM_NEW_HASH"
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
