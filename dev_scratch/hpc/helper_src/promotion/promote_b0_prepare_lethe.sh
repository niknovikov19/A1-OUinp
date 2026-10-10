#!/bin/bash

set -Eeuo pipefail

# Capture the complete promotion transcript
B0_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
B0_REPORT_DIR="$B0_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B0_REPORT_DIR"
chmod 0700 "$B0_REPORT_DIR"
B0_REPORT=$(mktemp "$B0_REPORT_DIR/b0-prepare-remote-promotion.XXXXXX.txt")
chmod 0600 "$B0_REPORT"
exec > >(tee "$B0_REPORT") 2>&1

B0_REMOTE_DIRS_OPEN=0

b0_cleanup() {
    local b0_rc=$?

    set +e
    if test "$B0_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$B0_REMOTE_ROOT/helpers/lethe" \
            "$B0_REMOTE_ROOT/config"
    fi
    if test "$b0_rc" -eq 0; then
        printf '\nB0_PREPARE_RESULT=PASS\n'
    else
        printf '\nB0_PREPARE_RESULT=FAIL exit_code=%s\n' "$b0_rc"
    fi
    printf 'B0_PREPARE_REPORT=%s\n' "$B0_REPORT"
    chmod 0600 "$B0_REPORT"
    trap - EXIT
    exit "$b0_rc"
}

b0_check_sha256() {
    local b0_expected=$1
    local b0_path=$2
    local b0_actual

    b0_actual=$(sha256sum "$b0_path")
    b0_actual=${b0_actual%% *}
    printf '%s  %s\n' "$b0_actual" "$b0_path"
    test "$b0_actual" = "$b0_expected"
}

trap b0_cleanup EXIT

# Validate invocation, identity, and the exact automation checkout
test "$#" -eq 1
B0_COMMIT=$1
B0_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B0_SRC="$B0_REMOTE_REPO/dev_scratch/hpc/helper_src"
B0_REMOTE_OWNER=niknovikov19
B0_REMOTE_GROUP=salvadord
B0_STATE_ROOT="$B0_REMOTE_ROOT/state/A1_OUinp"
B0_RUN_ROOT="$B0_REMOTE_REPO/hpc_jobs/runs"
B0_RUN_RECORDS="$B0_STATE_ROOT/runs"

printf 'B0.3 preparation promotion: lethe\n'
printf 'B0.3 commit: %s\n' "$B0_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B0_REPORT"

printf '%s\n' "$B0_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$B0_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$B0_REMOTE_GROUP"
test "$(git -C "$B0_REMOTE_REPO" rev-parse HEAD)" = "$B0_COMMIT"
test "$(git -C "$B0_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B0_REMOTE_REPO" status --porcelain=v1)"

# Validate and display the non-secret remote preparation configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool \
    "$B0_SRC/config_examples/remote-hpc-prepare.json.example"
B0_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
B0_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$B0_SECRET_RE|$B0_URL_RE" \
    "$B0_SRC/config_examples/remote-hpc-prepare.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every reviewed remote source artifact
printf '\n== Reviewed source hashes ==\n'
b0_check_sha256 '4534cf3ef47f53d89319afafbce9f67206b6df315d5135cf98c7558cdfa37e23' \
    "$B0_SRC/remote_lethe/hpc-lethe-prepare"
b0_check_sha256 '029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893' \
    "$B0_REMOTE_REPO/hpc_job.py"
b0_check_sha256 'a9c0d8bd62025272e256a0022ce535c9bce28405591f4d7f8294c41b8ab39939' \
    "$B0_SRC/config_examples/remote-hpc-prepare.json.example"
b0_check_sha256 'a4b048d54db100915eb4eefb347588fe4c92096fc625c69a1a07f28008318eb9' \
    "$B0_SRC/test_fixtures/b0_prepare_cases.json"
b0_check_sha256 'b0d153b166dd7b91be1a77462b805114b055cf3123b00f349c7c6e36202ef32a' \
    "$B0_REMOTE_REPO/hpc_jobs/requests/b0-prepare-single.json"

# Confirm shared ownership and create fixed writable state roots
printf '\n== Existing shared roots ==\n'
for B0_PATH in \
    "$B0_REMOTE_ROOT/helpers/lethe" \
    "$B0_REMOTE_ROOT/config" \
    "$B0_STATE_ROOT" \
    "$B0_REMOTE_REPO/hpc_jobs"
do
    test "$(stat -c '%U' "$B0_PATH")" = "$B0_REMOTE_OWNER"
    test "$(stat -c '%G' "$B0_PATH")" = "$B0_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$B0_PATH"
done
mkdir -p "$B0_RUN_ROOT" "$B0_RUN_RECORDS"
chmod 0700 "$B0_RUN_ROOT" "$B0_RUN_RECORDS"
if ! test -e "$B0_STATE_ROOT/prepare.lock"; then
    : > "$B0_STATE_ROOT/prepare.lock"
fi
chmod 0600 "$B0_STATE_ROOT/prepare.lock"

# Install while ensuring protected directory modes are restored on failure
printf '\n== Installation ==\n'
B0_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$B0_REMOTE_ROOT/helpers/lethe" \
    "$B0_REMOTE_ROOT/config"
install -g "$B0_REMOTE_GROUP" -m 0555 \
    "$B0_SRC/remote_lethe/hpc-lethe-prepare" \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc-lethe-prepare"
install -g "$B0_REMOTE_GROUP" -m 0444 \
    "$B0_REMOTE_REPO/hpc_job.py" \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc_job.py"
install -g "$B0_REMOTE_GROUP" -m 0444 \
    "$B0_SRC/config_examples/remote-hpc-prepare.json.example" \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare.json"
install -g "$B0_REMOTE_GROUP" -m 0444 \
    "$B0_SRC/test_fixtures/b0_prepare_cases.json" \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare-fixtures.json"
chmod 0555 \
    "$B0_REMOTE_ROOT/helpers/lethe" \
    "$B0_REMOTE_ROOT/config"
B0_REMOTE_DIRS_OPEN=0

# Verify installed identities and permissions without preparing a run
printf '\n== Installed hashes ==\n'
python3 -m json.tool "$B0_REMOTE_ROOT/config/A1_OUinp-prepare.json" >/dev/null
python3 -m json.tool \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare-fixtures.json" \
    >/dev/null
b0_check_sha256 '4534cf3ef47f53d89319afafbce9f67206b6df315d5135cf98c7558cdfa37e23' \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc-lethe-prepare"
b0_check_sha256 '029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893' \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc_job.py"
b0_check_sha256 'a9c0d8bd62025272e256a0022ce535c9bce28405591f4d7f8294c41b8ab39939' \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare.json"
b0_check_sha256 'a4b048d54db100915eb4eefb347588fe4c92096fc625c69a1a07f28008318eb9' \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare-fixtures.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$B0_REMOTE_ROOT/helpers/lethe" \
    "$B0_REMOTE_ROOT/config" \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc-lethe-prepare" \
    "$B0_REMOTE_ROOT/helpers/lethe/hpc_job.py" \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare.json" \
    "$B0_REMOTE_ROOT/config/A1_OUinp-prepare-fixtures.json" \
    "$B0_RUN_ROOT" \
    "$B0_RUN_RECORDS" \
    "$B0_STATE_ROOT/prepare.lock"
test ! -e "$B0_RUN_ROOT/b0-prepare-single-001"
test ! -e "$B0_RUN_RECORDS/b0-prepare-single-001.json"
printf 'Fresh preparation fixture: absent as expected\n'

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
