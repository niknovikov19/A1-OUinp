#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
A52_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
A52_REPORT_DIR="$A52_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$A52_REPORT_DIR"
chmod 0700 "$A52_REPORT_DIR"
A52_REPORT=$(mktemp "$A52_REPORT_DIR/a5-lifecycle-remote-promotion.XXXXXX.txt")
chmod 0600 "$A52_REPORT"
exec > >(tee "$A52_REPORT") 2>&1

A52_REMOTE_DIRS_OPEN=0

a52_cleanup() {
    local a52_rc=$?

    set +e
    if test "$A52_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$A52_REMOTE_ROOT/helpers/grid" \
            "$A52_REMOTE_ROOT/config"
    fi

    if test "$a52_rc" -eq 0; then
        printf '\nA5_2_RESULT=PASS\n'
    else
        printf '\nA5_2_RESULT=FAIL exit_code=%s\n' "$a52_rc"
    fi
    printf 'A5_2_REPORT=%s\n' "$A52_REPORT"
    chmod 0600 "$A52_REPORT"
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

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
A52_COMMIT=$1
A52_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
A52_SRC="$A52_REMOTE_REPO/dev_scratch/hpc/helper_src"
A52_REMOTE_OWNER=niknovikov19
A52_REMOTE_GROUP=salvadord

printf 'A5.2 promotion: lethe lifecycle probe\n'
printf 'A5.2 commit: %s\n' "$A52_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$A52_REPORT"

printf '%s\n' "$A52_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$A52_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$A52_REMOTE_GROUP"
test "$(git -C "$A52_REMOTE_REPO" rev-parse HEAD)" = "$A52_COMMIT"
test "$(git -C "$A52_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$A52_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret submission configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$A52_SRC/config_examples/remote-hpc-submit.json.example"
A52_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
A52_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$A52_SECRET_RE|$A52_URL_RE" \
    "$A52_SRC/config_examples/remote-hpc-submit.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify the complete protected submission chain
printf '\n== Reviewed source hashes ==\n'
a52_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A52_SRC/remote_lethe/hpc-lethe-submit"
a52_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A52_SRC/remote_grid/hpc-grid-submit"
a52_check_sha256 \
    '1b26896c7193475da71db8b39acc7934034b29deab924f9891f31c23d5244195' \
    "$A52_SRC/remote_grid/hpc-grid-probe-job"
a52_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A52_SRC/remote_grid/hpc-grid-probe-job.sh"
a52_check_sha256 \
    '4ae471d14d71e65af57008c1ceff84a42fc7c63e6388bbcfe29c2052ba55d414' \
    "$A52_SRC/config_examples/remote-hpc-submit.json.example"

# Confirm shared-path ownership and the fresh fixed run ID
printf '\n== Existing shared roots ==\n'
for A52_PATH in \
    "$A52_REMOTE_ROOT/helpers/grid" \
    "$A52_REMOTE_ROOT/config" \
    "$A52_REMOTE_ROOT/runs/A1_OUinp" \
    "$A52_REMOTE_ROOT/state/A1_OUinp"
do
    test "$(stat -c '%U' "$A52_PATH")" = "$A52_REMOTE_OWNER"
    test "$(stat -c '%G' "$A52_PATH")" = "$A52_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$A52_PATH"
done
test ! -e "$A52_REMOTE_ROOT/runs/A1_OUinp/a5-lifecycle-probe"

# Install only the updated probe payload and submission configuration
printf '\n== Installation ==\n'
A52_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$A52_REMOTE_ROOT/helpers/grid" \
    "$A52_REMOTE_ROOT/config"
install -g "$A52_REMOTE_GROUP" -m 0555 \
    "$A52_SRC/remote_grid/hpc-grid-probe-job" \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"
install -g "$A52_REMOTE_GROUP" -m 0444 \
    "$A52_SRC/config_examples/remote-hpc-submit.json.example" \
    "$A52_REMOTE_ROOT/config/A1_OUinp-submit.json"
chmod 0555 \
    "$A52_REMOTE_ROOT/helpers/grid" \
    "$A52_REMOTE_ROOT/config"
A52_REMOTE_DIRS_OPEN=0

# Verify all installed files used by A5.2
printf '\n== Installed hashes ==\n'
python3 -m json.tool \
    "$A52_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    >/dev/null
a52_check_sha256 \
    'fcd83892b12d6109025682cf2bfe1c6a05e0dd2b7b510efbbf62260e9539a494' \
    "$A52_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit"
a52_check_sha256 \
    'f59c99925dcda79126c8d2e20faf10e9e3ad964f076931c13c1fc3fb7629c19f' \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-submit"
a52_check_sha256 \
    '1b26896c7193475da71db8b39acc7934034b29deab924f9891f31c23d5244195' \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job"
a52_check_sha256 \
    'fdf35982027b6f33ff09a423072cdbd901fd42bd80f2ca766b1c3138cfdda665' \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh"
a52_check_sha256 \
    '4ae471d14d71e65af57008c1ceff84a42fc7c63e6388bbcfe29c2052ba55d414' \
    "$A52_REMOTE_ROOT/config/A1_OUinp-submit.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$A52_REMOTE_ROOT/helpers/lethe/hpc-lethe-submit" \
    "$A52_REMOTE_ROOT/helpers/grid" \
    "$A52_REMOTE_ROOT/config" \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-submit" \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job" \
    "$A52_REMOTE_ROOT/helpers/grid/hpc-grid-probe-job.sh" \
    "$A52_REMOTE_ROOT/config/A1_OUinp-submit.json" \
    "$A52_REMOTE_ROOT/runs/A1_OUinp" \
    "$A52_REMOTE_ROOT/state/A1_OUinp/submit.lock"

printf 'Fresh request directory: absent as expected\n'
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
