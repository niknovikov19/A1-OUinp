#!/bin/bash

set -Eeuo pipefail

# Capture the complete remote promotion transcript
B1_REMOTE_ROOT=/ddn/niknovikov19/hpc_codex
B1_REPORT_DIR="$B1_REMOTE_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B1_REPORT_DIR"
chmod 0700 "$B1_REPORT_DIR"
B1_REPORT=$(mktemp "$B1_REPORT_DIR/b1-job-remote-promotion.XXXXXX.txt")
chmod 0600 "$B1_REPORT"
exec > >(tee "$B1_REPORT") 2>&1

B1_REMOTE_DIRS_OPEN=0

b1_cleanup() {
    local b1_rc=$?

    set +e
    if test "$B1_REMOTE_DIRS_OPEN" -eq 1; then
        chmod 0555 \
            "$B1_REMOTE_ROOT/helpers/lethe" \
            "$B1_REMOTE_ROOT/helpers/grid" \
            "$B1_REMOTE_ROOT/config"
    fi
    if test "$b1_rc" -eq 0; then
        printf '\nB1_JOB_RESULT=PASS\n'
    else
        printf '\nB1_JOB_RESULT=FAIL exit_code=%s\n' "$b1_rc"
    fi
    printf 'B1_JOB_REPORT=%s\n' "$B1_REPORT"
    chmod 0600 "$B1_REPORT"
    trap - EXIT
    exit "$b1_rc"
}

b1_check_sha256() {
    local b1_expected=$1
    local b1_path=$2
    local b1_actual

    b1_actual=$(sha256sum "$b1_path")
    b1_actual=${b1_actual%% *}
    printf '%s  %s\n' "$b1_actual" "$b1_path"
    test "$b1_actual" = "$b1_expected"
}

trap b1_cleanup EXIT

# Validate invocation, identity, and exact automation checkout
test "$#" -eq 1
B1_COMMIT=$1
B1_REMOTE_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B1_SRC="$B1_REMOTE_REPO/dev_scratch/hpc/helper_src"
B1_REMOTE_OWNER=niknovikov19
B1_REMOTE_GROUP=salvadord
B1_STATE_ROOT="$B1_REMOTE_ROOT/state/A1_OUinp"
B1_RUN_ROOT="$B1_REMOTE_REPO/hpc_jobs/runs"

printf 'B1 prepared-job promotion: lethe\n'
printf 'B1 commit: %s\n' "$B1_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B1_REPORT"

printf '%s\n' "$B1_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$B1_REMOTE_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$B1_REMOTE_GROUP"
test "$(git -C "$B1_REMOTE_REPO" rev-parse HEAD)" = "$B1_COMMIT"
test "$(git -C "$B1_REMOTE_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B1_REMOTE_REPO" status --porcelain=v1)"

# Display and validate the non-secret remote configuration
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool "$B1_SRC/config_examples/remote-hpc-job.json.example"
B1_SECRET_RE='password|token|private[_-]?key|key[_-]?path'
B1_URL_RE='repository[_-]?url|repo[_-]?url|https?://|ssh://|git@'
if grep -Eiq \
    "$B1_SECRET_RE|$B1_URL_RE" \
    "$B1_SRC/config_examples/remote-hpc-job.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every reviewed remote source artifact
printf '\n== Reviewed source hashes ==\n'
b1_check_sha256 '2556cd22f3591189f63b21bbb6a46b3722ee7ca2045cd079110a314d76ef70d3' \
    "$B1_SRC/remote_lethe/hpc-lethe-job"
b1_check_sha256 '70623d66bc717c3041118f3773466bd31ae3aa5c133080c2bb1ffbb82780d0a6' \
    "$B1_SRC/remote_grid/hpc-grid-job"
b1_check_sha256 '029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893' \
    "$B1_REMOTE_REPO/hpc_job.py"
b1_check_sha256 'ede38c3b8534e5c3c535b33263379dcc5804228be809e24c133a3163079b2d19' \
    "$B1_REMOTE_REPO/hpc_job_lifecycle.py"
b1_check_sha256 '95a58889e3a7622282a95556e5e7aad44d9e4b1b5456b07398da73618f98de8d' \
    "$B1_REMOTE_REPO/hpc_job_control.py"
b1_check_sha256 'b39c9a26daf5edf7b5833ce59e2001a0f844f662093ea156fe562d503a89b94c' \
    "$B1_SRC/config_examples/remote-hpc-job.json.example"
b1_check_sha256 'b90ecb9ea30fee7ba73f520f7ca14e4d6b834289fc7238e27d461b470b3a4484' \
    "$B1_SRC/config_examples/remote-hpc-prepare.json.example"
b1_check_sha256 'f096e453957cc94c25660093757b86ef536f1786e471cef1b36af0d43666506f' \
    "$B1_SRC/test_fixtures/b1_job_cases.json"
b1_check_sha256 '37c76569edd655692cbfad02250f4941d94dc89696e897a172d279678e29290c' \
    "$B1_REMOTE_ROOT/helpers/grid/hpc-grid-status"

# Confirm shared ownership and create only fixed writable state paths
printf '\n== Existing shared roots ==\n'
for B1_PATH in \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid" \
    "$B1_REMOTE_ROOT/config" \
    "$B1_STATE_ROOT" \
    "$B1_RUN_ROOT"
do
    test "$(stat -c '%U' "$B1_PATH")" = "$B1_REMOTE_OWNER"
    test "$(stat -c '%G' "$B1_PATH")" = "$B1_REMOTE_GROUP"
    stat -c '%A %a %U:%G %n' "$B1_PATH"
done
for B1_DIR in submissions finals releases; do
    mkdir -p "$B1_STATE_ROOT/$B1_DIR"
    chmod 0700 "$B1_STATE_ROOT/$B1_DIR"
done
for B1_LOCK in job.lock grid-submit.lock; do
    if ! test -e "$B1_STATE_ROOT/$B1_LOCK"; then
        : > "$B1_STATE_ROOT/$B1_LOCK"
    fi
    chmod 0600 "$B1_STATE_ROOT/$B1_LOCK"
done
test -f "$B1_STATE_ROOT/code-update.lock"
chmod 0600 "$B1_STATE_ROOT/code-update.lock"

# Install while restoring protected directory modes on every exit
printf '\n== Installation ==\n'
B1_REMOTE_DIRS_OPEN=1
chmod 0755 \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid" \
    "$B1_REMOTE_ROOT/config"
install -g "$B1_REMOTE_GROUP" -m 0555 \
    "$B1_SRC/remote_lethe/hpc-lethe-job" \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc-lethe-job"
install -g "$B1_REMOTE_GROUP" -m 0555 \
    "$B1_SRC/remote_grid/hpc-grid-job" \
    "$B1_REMOTE_ROOT/helpers/grid/hpc-grid-job"
for B1_HELPER_DIR in \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid"
do
    install -g "$B1_REMOTE_GROUP" -m 0444 \
        "$B1_REMOTE_REPO/hpc_job.py" \
        "$B1_HELPER_DIR/hpc_job.py"
    install -g "$B1_REMOTE_GROUP" -m 0444 \
        "$B1_REMOTE_REPO/hpc_job_lifecycle.py" \
        "$B1_HELPER_DIR/hpc_job_lifecycle.py"
    install -g "$B1_REMOTE_GROUP" -m 0444 \
        "$B1_REMOTE_REPO/hpc_job_control.py" \
        "$B1_HELPER_DIR/hpc_job_control.py"
done
install -g "$B1_REMOTE_GROUP" -m 0444 \
    "$B1_SRC/config_examples/remote-hpc-job.json.example" \
    "$B1_REMOTE_ROOT/config/A1_OUinp-job.json"
install -g "$B1_REMOTE_GROUP" -m 0444 \
    "$B1_SRC/config_examples/remote-hpc-prepare.json.example" \
    "$B1_REMOTE_ROOT/config/A1_OUinp-prepare.json"
install -g "$B1_REMOTE_GROUP" -m 0444 \
    "$B1_SRC/test_fixtures/b1_job_cases.json" \
    "$B1_REMOTE_ROOT/config/A1_OUinp-job-fixtures.json"
chmod 0555 \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid" \
    "$B1_REMOTE_ROOT/config"
B1_REMOTE_DIRS_OPEN=0

# Verify installed identities and permissions without any job operation
printf '\n== Installed hashes ==\n'
python3 -m json.tool "$B1_REMOTE_ROOT/config/A1_OUinp-job.json" >/dev/null
python3 -m json.tool "$B1_REMOTE_ROOT/config/A1_OUinp-prepare.json" >/dev/null
python3 -m json.tool "$B1_REMOTE_ROOT/config/A1_OUinp-job-fixtures.json" >/dev/null
b1_check_sha256 '2556cd22f3591189f63b21bbb6a46b3722ee7ca2045cd079110a314d76ef70d3' \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc-lethe-job"
b1_check_sha256 '70623d66bc717c3041118f3773466bd31ae3aa5c133080c2bb1ffbb82780d0a6' \
    "$B1_REMOTE_ROOT/helpers/grid/hpc-grid-job"
for B1_HELPER_DIR in \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid"
do
    b1_check_sha256 '029745924df05dfdc5431f3c74001fbc458c2949dd0c10f1cf5222742fb24893' \
        "$B1_HELPER_DIR/hpc_job.py"
    b1_check_sha256 'ede38c3b8534e5c3c535b33263379dcc5804228be809e24c133a3163079b2d19' \
        "$B1_HELPER_DIR/hpc_job_lifecycle.py"
    b1_check_sha256 '95a58889e3a7622282a95556e5e7aad44d9e4b1b5456b07398da73618f98de8d' \
        "$B1_HELPER_DIR/hpc_job_control.py"
done
b1_check_sha256 'b39c9a26daf5edf7b5833ce59e2001a0f844f662093ea156fe562d503a89b94c' \
    "$B1_REMOTE_ROOT/config/A1_OUinp-job.json"
b1_check_sha256 'b90ecb9ea30fee7ba73f520f7ca14e4d6b834289fc7238e27d461b470b3a4484' \
    "$B1_REMOTE_ROOT/config/A1_OUinp-prepare.json"
b1_check_sha256 'f096e453957cc94c25660093757b86ef536f1786e471cef1b36af0d43666506f' \
    "$B1_REMOTE_ROOT/config/A1_OUinp-job-fixtures.json"

printf '\n== Installed permissions ==\n'
stat -c '%A %a %U:%G %n' \
    "$B1_REMOTE_ROOT/helpers/lethe" \
    "$B1_REMOTE_ROOT/helpers/grid" \
    "$B1_REMOTE_ROOT/config" \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc-lethe-job" \
    "$B1_REMOTE_ROOT/helpers/grid/hpc-grid-job" \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc_job.py" \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc_job_lifecycle.py" \
    "$B1_REMOTE_ROOT/helpers/lethe/hpc_job_control.py" \
    "$B1_REMOTE_ROOT/helpers/grid/hpc_job.py" \
    "$B1_REMOTE_ROOT/helpers/grid/hpc_job_lifecycle.py" \
    "$B1_REMOTE_ROOT/helpers/grid/hpc_job_control.py" \
    "$B1_REMOTE_ROOT/config/A1_OUinp-job.json" \
    "$B1_REMOTE_ROOT/config/A1_OUinp-prepare.json" \
    "$B1_STATE_ROOT/submissions" \
    "$B1_STATE_ROOT/finals" \
    "$B1_STATE_ROOT/releases" \
    "$B1_STATE_ROOT/job.lock" \
    "$B1_STATE_ROOT/grid-submit.lock" \
    "$B1_STATE_ROOT/code-update.lock"
test ! -e "$B1_RUN_ROOT/b1-single-smoke-003"
test ! -e "$B1_STATE_ROOT/runs/b1-single-smoke-003.json"
printf 'Fresh B1 run ID: absent as expected\n'

printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
