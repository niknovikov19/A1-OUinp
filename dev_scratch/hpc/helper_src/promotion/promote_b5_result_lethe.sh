#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe promotion transcript
B5_ROOT=/ddn/niknovikov19/hpc_codex
B5_STATE="$B5_ROOT/state/A1_OUinp"
B5_REPORT_DIR="$B5_STATE/reports/promotion"
mkdir -p "$B5_REPORT_DIR"
chmod 0700 "$B5_REPORT_DIR"
B5_REPORT=$(mktemp "$B5_REPORT_DIR/b5-result-remote-promotion.XXXXXX.txt")
chmod 0600 "$B5_REPORT"
exec > >(tee "$B5_REPORT") 2>&1
B5_DIRS_OPEN=0

b5_cleanup() {
    local b5_rc=$?

    set +e
    if test "$B5_DIRS_OPEN" -eq 1; then
        chmod 0555 "$B5_ROOT/helpers/lethe" "$B5_ROOT/config"
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

# Validate the exact clean automation checkout
test "$#" -eq 1
B5_COMMIT=$1
B5_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B5_SRC="$B5_REPO/dev_scratch/hpc/helper_src"
B5_OWNER=niknovikov19
B5_GROUP=salvadord
printf 'B5 result-access promotion: lethe\n'
printf 'B5 commit: %s\n' "$B5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B5_REPORT"
printf '%s\n' "$B5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$B5_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$B5_GROUP"
test "$(git -C "$B5_REPO" rev-parse HEAD)" = "$B5_COMMIT"
test "$(git -C "$B5_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B5_REPO" status --porcelain=v1)"

# Display and verify the remote non-secret result policy
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool "$B5_SRC/config_examples/remote-hpc-result.json.example"
if grep -Eiq 'password|token|private[_-]?key|key[_-]?path|https?://|ssh://|git@' "$B5_SRC/config_examples/remote-hpc-result.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every promoted remote artifact
printf '\n== Reviewed source hashes ==\n'
b5_check_sha256 '159b197a2e3dbe499f77643763f5752100daa45e1cfe4359612341d4357fa903' "$B5_SRC/remote_lethe/hpc-lethe-result"
b5_check_sha256 'f99a45c010113fd04041cf374143541327f8da0921aa9e087880ecfd376e7684' "$B5_REPO/hpc_result.py"
b5_check_sha256 '22dc07fa180c35c293a995bccf9215fd50a579d7043d49fae9826aa6688063e2' "$B5_REPO/hpc_job.py"
b5_check_sha256 '8c095533e54d41f31ddfdecb555e9cb6683a805beeba0a72344de068f74f4ca4' "$B5_REPO/hpc_job_lifecycle.py"
b5_check_sha256 '59b9f353e4d2aec6be127d1752387476f36a5da0370aee8850529b4a92f759a1' "$B5_SRC/config_examples/remote-hpc-result.json.example"

# Install immutable code/config and writable bounded state
printf '\n== Installation ==\n'
B5_DIRS_OPEN=1
chmod 0755 "$B5_ROOT/helpers/lethe" "$B5_ROOT/config"
install -g "$B5_GROUP" -m 0555 "$B5_SRC/remote_lethe/hpc-lethe-result" "$B5_ROOT/helpers/lethe/hpc-lethe-result"
install -g "$B5_GROUP" -m 0444 "$B5_REPO/hpc_result.py" "$B5_ROOT/helpers/lethe/hpc_result.py"
install -g "$B5_GROUP" -m 0444 "$B5_REPO/hpc_job.py" "$B5_ROOT/helpers/lethe/hpc_job.py"
install -g "$B5_GROUP" -m 0444 "$B5_REPO/hpc_job_lifecycle.py" "$B5_ROOT/helpers/lethe/hpc_job_lifecycle.py"
install -g "$B5_GROUP" -m 0444 "$B5_SRC/config_examples/remote-hpc-result.json.example" "$B5_ROOT/config/A1_OUinp-result.json"
chmod 0555 "$B5_ROOT/helpers/lethe" "$B5_ROOT/config"
B5_DIRS_OPEN=0
mkdir -p "$B5_STATE/result-inventories"
chmod 0700 "$B5_STATE/result-inventories"
if test ! -e "$B5_STATE/result.lock"; then
    install -m 0600 /dev/null "$B5_STATE/result.lock"
fi
chmod 0600 "$B5_STATE/result.lock"

# Verify installed hashes and permissions
printf '\n== Installed identity ==\n'
b5_check_sha256 '159b197a2e3dbe499f77643763f5752100daa45e1cfe4359612341d4357fa903' "$B5_ROOT/helpers/lethe/hpc-lethe-result"
b5_check_sha256 'f99a45c010113fd04041cf374143541327f8da0921aa9e087880ecfd376e7684' "$B5_ROOT/helpers/lethe/hpc_result.py"
b5_check_sha256 '59b9f353e4d2aec6be127d1752387476f36a5da0370aee8850529b4a92f759a1' "$B5_ROOT/config/A1_OUinp-result.json"
"$B5_ROOT/helpers/lethe/hpc-lethe-result" version
stat -c '%A %a %U:%G %n' \
    "$B5_ROOT/helpers/lethe" \
    "$B5_ROOT/config" \
    "$B5_ROOT/helpers/lethe/hpc-lethe-result" \
    "$B5_ROOT/helpers/lethe/hpc_result.py" \
    "$B5_ROOT/config/A1_OUinp-result.json" \
    "$B5_STATE/result-inventories" \
    "$B5_STATE/result.lock"
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
