#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A62_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A62_REPORT_DIR="$A62_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$A62_REPORT_DIR"
chmod 0700 "$A62_REPORT_DIR"
A62_REPORT=$(mktemp "$A62_REPORT_DIR/a6-log-probe-remote-promotion.XXXXXX.txt")
chmod 0600 "$A62_REPORT"
exec > >(tee "$A62_REPORT") 2>&1

A62_REMOTE_DIRS_OPEN=0

a62_cleanup() {
    local a62_rc=$?

    set +e
    if test "$A62_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$A62_REMOTE_ROOT/helpers/grid" \
            "$A62_REMOTE_ROOT/config"
    fi

    if test "$a62_rc" -eq 0; then
        printf '\nA6_2_RESULT=PASS\n'
    else
        printf '\nA6_2_RESULT=FAIL exit_code=%s\n' "$a62_rc"
    fi
    printf 'A6_2_REPORT=%s\n' "$A62_REPORT"
    chmod 0600 "$A62_REPORT"
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

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
A62_COMMIT=$1
A62_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A62_SRC="$A62_REMOTE_REPO/dev_scratch/hpc/helper_src"
A62_REMOTE_OWNER=niknovikov19
A62_REMOTE_GROUP=salvadord

printf 'A6.2 promotion: lethe incremental-log probe\n'
printf 'A6.2 commit: %s\n' "$A62_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A62_REPORT"

printf '%s\n' "$A62_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$A62_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A62_REMOTE_GROUP"
test "$(git -C "$A62_REMOTE_REPO" rev-parse HEAD)" = "$A62_COMMIT"
test "$(git -C "$A62_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$A62_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret submission configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$A62_SRC/config_examples/remote-hpc-submit.json.example"
A62_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
A62_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$A62_SECRET_RE|$A62_URL_RE" \
    "$A62_SRC/config_examples/remote-hpc-submit.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify the complete submission and log-read chain
printf '\n== Reviewed source hashes ==\n'
a62_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A62_SRC/remote_lethe/hpc-lethe-submit"
a62_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A62_SRC/remote_grid/hpc-grid-submit"
a62_check_sha256 \
    'df473859c40126158e6c0a569bd21dc41e634de7a845f6ed85c3a337d3e43610' \
    "$A62_SRC/remote_grid/hpc-grid-probe-job"
a62_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A62_SRC/remote_grid/hpc-grid-probe-job.sh"
a62_check_sha256 \
    '14330c9e7af7d061aaef434b6e8eb14a328af86fc399e913ed1bab14e936e270' \
    "$A62_SRC/config_examples/remote-hpc-submit.json.example"

# Confirm shared-path ownership and the fresh fixed run ID
printf '\n== Existing shared roots ==\n'
for A62_PATH in \
    "$A62_REMOTE_ROOT/helpers/grid" \
    "$A62_REMOTE_ROOT/config" \
    "$A62_REMOTE_ROOT/runs/A1_OUinp" \
    "$A62_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A62_PATH")" = "$A62_REMOTE_OWNER"
    test "$(stat -c '%G' "$A62_PATH")" = "$A62_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$A62_PATH"
done
test ! -e "$A62_REMOTE_ROOT/runs/A1_OUinp/a6-incremental-log-probe"

# Install only the updated probe payload and submission configuration
printf '\n== Installation ==\n'
A62_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$A62_REMOTE_ROOT/helpers/grid" \
    "$A62_REMOTE_ROOT/config"
install -g "$A62_REMOTE_GROUP" -m 0555 \
    "$A62_SRC/remote_grid/hpc-grid-probe-job" \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"
install -g "$A62_REMOTE_GROUP" -m 0444 \
    "$A62_SRC/config_examples/remote-hpc-submit.json.example" \
    "$A62_REMOTE_ROOT/config/A1_OUinp-submit.json"
chmod 0555 \
    "$A62_REMOTE_ROOT/helpers/grid" \
    "$A62_REMOTE_ROOT/config"
A62_REMOTE_DIRS_OPEN=0

# Verify installed submission files and unchanged A6 log reader
printf '\n== Installed hashes ==\n'
python3 -m json.tool \
    "$A62_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    >/dev/null
a62_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A62_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit"
a62_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-submit"
a62_check_sha256 \
    'df473859c40126158e6c0a569bd21dc41e634de7a845f6ed85c3a337d3e43610' \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"
a62_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh"
a62_check_sha256 \
    '14330c9e7af7d061aaef434b6e8eb14a328af86fc399e913ed1bab14e936e270' \
    "$A62_REMOTE_ROOT/config/A1_OUinp-submit.json"
a62_check_sha256 \
    'fe5cb43eb133fcf1749620e2a9e421b36e1b0bdabc278d7ab5fa7dc90169bff3' \
    "$A62_REMOTE_ROOT/helpers/lethe/hpc-lethe-log"
a62_check_sha256 \
    '66ddc07b2ee57a6063bc6c9e6bf0e562fbc760092998fd6c95d573053e8ec034' \
    "$A62_REMOTE_ROOT/config/A1_OUinp-log.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$A62_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit" \
    "$A62_REMOTE_ROOT/helpers/lethe/hpc-lethe-log" \
    "$A62_REMOTE_ROOT/helpers/grid" \
    "$A62_REMOTE_ROOT/config" \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-submit" \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job" \
    "$A62_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh" \
    "$A62_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    "$A62_REMOTE_ROOT/config/A1_OUinp-log.json" \
    "$A62_REMOTE_ROOT/runs/A1_OUinp" \
    "$A62_REMOTE_ROOT/state/A1_OUinp/submit.lock"

printf 'Fresh request directory: absent as expected\n'
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
