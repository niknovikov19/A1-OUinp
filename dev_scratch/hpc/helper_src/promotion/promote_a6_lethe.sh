#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A6_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A6_REPORT_DIR="$A6_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$A6_REPORT_DIR"
chmod 0700 "$A6_REPORT_DIR"
A6_REPORT=$(mktemp "$A6_REPORT_DIR/a6-remote-promotion.XXXXXX.txt")
chmod 0600 "$A6_REPORT"
exec > >(tee "$A6_REPORT") 2>&1

A6_REMOTE_DIRS_OPEN=0

a6_cleanup() {
    local a6_rc=$?

    set +e
    if test "$A6_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$A6_REMOTE_ROOT/helpers/lethe" \
            "$A6_REMOTE_ROOT/config"
    fi

    if test "$a6_rc" -eq 0; then
        printf '\nA6_RESULT=PASS\n'
    else
        printf '\nA6_RESULT=FAIL exit_code=%s\n' "$a6_rc"
    fi
    printf 'A6_REPORT=%s\n' "$A6_REPORT"
    chmod 0600 "$A6_REPORT"
    trap - EXIT
    exit "$a6_rc"
}

a6_check_sha256() {
    local a6_expected=$1
    local a6_path=$2
    local a6_actual

    a6_actual=$(sha256sum "$a6_path")
    a6_actual=${a6_actual%% *}
    printf '%s  %s\n' "$a6_actual" "$a6_path"
    test "$a6_actual" = "$a6_expected"
}

trap a6_cleanup EXIT

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
A6_COMMIT=$1
A6_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A6_SRC="$A6_REMOTE_REPO/dev_scratch/hpc/helper_src"
A6_REMOTE_OWNER=niknovikov19
A6_REMOTE_GROUP=salvadord

printf 'A6 promotion: lethe\n'
printf 'A6 commit: %s\n' "$A6_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A6_REPORT"

printf '%s\n' "$A6_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$A6_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A6_REMOTE_GROUP"
test "$(git -C "$A6_REMOTE_REPO" rev-parse HEAD)" = "$A6_COMMIT"
test "$(git -C "$A6_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$A6_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret remote log configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$A6_SRC/config_examples/remote-hpc-log.json.example"
A6_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
A6_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$A6_SECRET_RE|$A6_URL_RE" \
    "$A6_SRC/config_examples/remote-hpc-log.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every reviewed remote source artifact
printf '\n== Reviewed source hashes ==\n'
a6_check_sha256 \
    'fe5cb43eb133fcf1749620e2a9e421b36e1b0bdabc278d7ab5fa7dc90169bff3' \
    "$A6_SRC/remote_lethe/hpc-lethe-log"
a6_check_sha256 \
    '66ddc07b2ee57a6063bc6c9e6bf0e562fbc760092998fd6c95d573053e8ec034' \
    "$A6_SRC/config_examples/remote-hpc-log.json.example"
a6_check_sha256 \
    'c753d732b59f335cd4b322af5673ef528673232f228a10cc18756d779e30b929' \
    "$A6_SRC/test_fixtures/a6_log_cases.json"

# Confirm shared ownership and known A5 controller-log records
printf '\n== Existing shared roots and A5 records ==\n'
for A6_PATH in \
    "$A6_REMOTE_ROOT/helpers/lethe" \
    "$A6_REMOTE_ROOT/config" \
    "$A6_REMOTE_ROOT/runs/A1_OUinp" \
    "$A6_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A6_PATH")" = "$A6_REMOTE_OWNER"
    test "$(stat -c '%G' "$A6_PATH")" = "$A6_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$A6_PATH"
done
A6_TEST_RUN="$A6_REMOTE_ROOT/runs/A1_OUinp/a5-lifecycle-probe"
test -f "$A6_TEST_RUN/run.json"
test ! -L "$A6_TEST_RUN/run.json"
test -f "$A6_TEST_RUN/submission.json"
test ! -L "$A6_TEST_RUN/submission.json"

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
A6_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$A6_REMOTE_ROOT/helpers/lethe" \
    "$A6_REMOTE_ROOT/config"
install -g "$A6_REMOTE_GROUP" -m 0555 \
    "$A6_SRC/remote_lethe/hpc-lethe-log" \
    "$A6_REMOTE_ROOT/helpers/lethe/hpc-lethe-log"
install -g "$A6_REMOTE_GROUP" -m 0444 \
    "$A6_SRC/config_examples/remote-hpc-log.json.example" \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log.json"
install -g "$A6_REMOTE_GROUP" -m 0444 \
    "$A6_SRC/test_fixtures/a6_log_cases.json" \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log-fixtures.json"
chmod 0555 \
    "$A6_REMOTE_ROOT/helpers/lethe" \
    "$A6_REMOTE_ROOT/config"
A6_REMOTE_DIRS_OPEN=0

# Verify installed identities and permissions
printf '\n== Installed hashes ==\n'
python3 -m json.tool "$A6_REMOTE_ROOT/config/A1_OUinp-log.json" >/dev/null
python3 -m json.tool \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log-fixtures.json" \
    >/dev/null
a6_check_sha256 \
    'fe5cb43eb133fcf1749620e2a9e421b36e1b0bdabc278d7ab5fa7dc90169bff3' \
    "$A6_REMOTE_ROOT/helpers/lethe/hpc-lethe-log"
a6_check_sha256 \
    '66ddc07b2ee57a6063bc6c9e6bf0e562fbc760092998fd6c95d573053e8ec034' \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log.json"
a6_check_sha256 \
    'c753d732b59f335cd4b322af5673ef528673232f228a10cc18756d779e30b929' \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log-fixtures.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$A6_REMOTE_ROOT/helpers/lethe" \
    "$A6_REMOTE_ROOT/config" \
    "$A6_REMOTE_ROOT/helpers/lethe/hpc-lethe-log" \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log.json" \
    "$A6_REMOTE_ROOT/config/A1_OUinp-log-fixtures.json" \
    "$A6_REMOTE_ROOT/runs/A1_OUinp" \
    "$A6_REMOTE_ROOT/state/A1_OUinp"

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
