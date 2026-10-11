#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe recovery-promotion transcript
B2F_ROOT=/ddn/niknovikov19/hpc_codex
B2F_REPORT_DIR="$B2F_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B2F_REPORT_DIR"
chmod 0700 "$B2F_REPORT_DIR"
B2F_REPORT=$(mktemp "$B2F_REPORT_DIR/b2-finalize-recovery.XXXXXX.txt")
chmod 0600 "$B2F_REPORT"
exec > >(tee "$B2F_REPORT") 2>&1
B2F_DIRS_OPEN=0
B2F_TMP=$(mktemp -d /tmp/b2-finalize-recovery.XXXXXX)

b2f_cleanup() {
    local b2f_rc=$?

    set +e
    if test "$B2F_DIRS_OPEN" -eq 1; then
        chmod 0555 "$B2F_ROOT/helpers/lethe" "$B2F_ROOT/helpers/grid"
    fi
    rm -f "$B2F_TMP/hpc-lethe-job" "$B2F_TMP/hpc_job_lifecycle.py"
    rmdir "$B2F_TMP"
    if test "$b2f_rc" -eq 0; then
        printf '\nB2_FINALIZE_RECOVERY_RESULT=PASS\n'
    else
        printf '\nB2_FINALIZE_RECOVERY_RESULT=FAIL exit_code=%s\n' "$b2f_rc"
    fi
    printf 'B2_FINALIZE_RECOVERY_REPORT=%s\n' "$B2F_REPORT"
    trap - EXIT
    exit "$b2f_rc"
}

b2f_check_sha256() {
    local b2f_expected=$1
    local b2f_path=$2
    local b2f_actual

    b2f_actual=$(sha256sum "$b2f_path")
    b2f_actual=${b2f_actual%% *}
    printf '%s  %s\n' "$b2f_actual" "$b2f_path"
    test "$b2f_actual" = "$b2f_expected"
}

b2f_active_run_id() {
    python3 -c \
        'import json, sys; print(json.load(open(sys.argv[1]))["run_id"])' \
        "$B2F_ACTIVE"
}

trap b2f_cleanup EXIT

# Validate the fetched commit without changing the active checkout
test "$#" -eq 1
B2F_COMMIT=$1
B2F_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2F_ACTIVE="$B2F_ROOT/state/A1_OUinp/active-run.json"
printf 'B2 failed-finalization recovery promotion: lethe\n'
printf 'Recovery commit: %s\n' "$B2F_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2F_REPORT"
printf '%s\n' "$B2F_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$B2F_REPO" rev-parse refs/remotes/origin/codex-hpc)" = "$B2F_COMMIT"
git -C "$B2F_REPO" merge-base --is-ancestor HEAD "$B2F_COMMIT"
test -f "$B2F_ACTIVE"
test "$(b2f_active_run_id)" = 'b2-child-discovery-004'

# Export and verify only the finalization sources
git -C "$B2F_REPO" show \
    "$B2F_COMMIT:dev_scratch/hpc/helper_src/remote_lethe/hpc-lethe-job" \
    > "$B2F_TMP/hpc-lethe-job"
git -C "$B2F_REPO" show "$B2F_COMMIT:hpc_job_lifecycle.py" > "$B2F_TMP/hpc_job_lifecycle.py"
printf '\n== Reviewed recovery hashes ==\n'
b2f_check_sha256 \
    '3bb41084aa89cb726cdcb512ba6f761351cd3fd596fc58b32b625b90a195faff' \
    "$B2F_TMP/hpc-lethe-job"
b2f_check_sha256 \
    '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' \
    "$B2F_TMP/hpc_job_lifecycle.py"

# Install the reviewed finalizer while preserving the active run
printf '\n== Installation ==\n'
B2F_DIRS_OPEN=1
chmod 0755 "$B2F_ROOT/helpers/lethe" "$B2F_ROOT/helpers/grid"
install -g salvadord -m 0555 "$B2F_TMP/hpc-lethe-job" "$B2F_ROOT/helpers/lethe/hpc-lethe-job"
install -g salvadord -m 0444 \
    "$B2F_TMP/hpc_job_lifecycle.py" \
    "$B2F_ROOT/helpers/lethe/hpc_job_lifecycle.py"
install -g salvadord -m 0444 \
    "$B2F_TMP/hpc_job_lifecycle.py" \
    "$B2F_ROOT/helpers/grid/hpc_job_lifecycle.py"
chmod 0555 "$B2F_ROOT/helpers/lethe" "$B2F_ROOT/helpers/grid"
B2F_DIRS_OPEN=0

# Verify installed identities and unchanged active evidence
printf '\n== Installed recovery hashes and permissions ==\n'
b2f_check_sha256 \
    '3bb41084aa89cb726cdcb512ba6f761351cd3fd596fc58b32b625b90a195faff' \
    "$B2F_ROOT/helpers/lethe/hpc-lethe-job"
b2f_check_sha256 \
    '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' \
    "$B2F_ROOT/helpers/lethe/hpc_job_lifecycle.py"
b2f_check_sha256 \
    '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' \
    "$B2F_ROOT/helpers/grid/hpc_job_lifecycle.py"
test "$(b2f_active_run_id)" = 'b2-child-discovery-004'
stat -c '%A %a %U:%G %n' \
    "$B2F_ROOT/helpers/lethe" \
    "$B2F_ROOT/helpers/grid" \
    "$B2F_ROOT/helpers/lethe/hpc-lethe-job" \
    "$B2F_ROOT/helpers/lethe/hpc_job_lifecycle.py" \
    "$B2F_ROOT/helpers/grid/hpc_job_lifecycle.py"
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
