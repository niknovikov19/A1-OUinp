#!/bin/bash

set -Eeuo pipefail

# Capture the complete lethe promotion transcript
B2_ROOT=/ddn/niknovikov19/hpc_codex
B2_REPORT_DIR="$B2_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$B2_REPORT_DIR"
chmod 0700 "$B2_REPORT_DIR"
B2_REPORT=$(mktemp "$B2_REPORT_DIR/b2-job-remote-promotion.XXXXXX.txt")
chmod 0600 "$B2_REPORT"
exec > >(tee "$B2_REPORT") 2>&1
B2_DIRS_OPEN=0

b2_cleanup() {
    local b2_rc=$?

    set +e
    if test "$B2_DIRS_OPEN" -eq 1; then
        chmod 0555 "$B2_ROOT/helpers/lethe" "$B2_ROOT/helpers/grid" "$B2_ROOT/config"
    fi
    if test "$b2_rc" -eq 0; then
        printf '\nB2_JOB_RESULT=PASS\n'
    else
        printf '\nB2_JOB_RESULT=FAIL exit_code=%s\n' "$b2_rc"
    fi
    printf 'B2_JOB_REPORT=%s\n' "$B2_REPORT"
    trap - EXIT
    exit "$b2_rc"
}

b2_check_sha256() {
    local b2_expected=$1
    local b2_path=$2
    local b2_actual

    b2_actual=$(sha256sum "$b2_path")
    b2_actual=${b2_actual%% *}
    printf '%s  %s\n' "$b2_actual" "$b2_path"
    test "$b2_actual" = "$b2_expected"
}

trap b2_cleanup EXIT

# Validate the exact clean automation checkout
test "$#" -eq 1
B2_COMMIT=$1
B2_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2_SRC="$B2_REPO/dev_scratch/hpc/helper_src"
B2_OWNER=niknovikov19
B2_GROUP=salvadord
B2_RUN_ID=b2-child-discovery-001
B2_STATE="$B2_ROOT/state/A1_OUinp"
printf 'B2 child-job promotion: lethe\n'
printf 'B2 commit: %s\n' "$B2_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Report: %s\n' "$B2_REPORT"
printf '%s\n' "$B2_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = "$B2_OWNER"
id -nG | tr ' ' '\n' | grep -Fxq "$B2_GROUP"
test "$(git -C "$B2_REPO" rev-parse HEAD)" = "$B2_COMMIT"
test "$(git -C "$B2_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$B2_REPO" status --porcelain=v1)"

# Display the changed non-secret preparation policy
printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool "$B2_SRC/config_examples/remote-hpc-prepare.json.example"
if grep -Eiq 'password|token|private[_-]?key|key[_-]?path|https?://|ssh://|git@' "$B2_SRC/config_examples/remote-hpc-prepare.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi

# Verify every promoted source artifact
printf '\n== Reviewed source hashes ==\n'
b2_check_sha256 '3ce085f9ebab84c86f64e4ae87d03096347663c5300f2302dac3f57769da613b' "$B2_SRC/remote_lethe/hpc-lethe-job"
b2_check_sha256 '2dbd520a195c93bb8aceb42cb37a2396dac83c3caea94b64d6fb1f3682292d65' "$B2_SRC/remote_grid/hpc-grid-job"
b2_check_sha256 '22dc07fa180c35c293a995bccf9215fd50a579d7043d49fae9826aa6688063e2' "$B2_REPO/hpc_job.py"
b2_check_sha256 '816748343f3ea75ae88e3d95a2ffd7e4461b85238e93333961d519043369e895' "$B2_REPO/hpc_job_lifecycle.py"
b2_check_sha256 '95a58889e3a7622282a95556e5e7aad44d9e4b1b5456b07398da73618f98de8d' "$B2_REPO/hpc_job_control.py"
b2_check_sha256 'e6de93ce6b2384affa906382c1ffebea32777d4750b5013e2ce3f50fb86e7f78' "$B2_SRC/config_examples/remote-hpc-prepare.json.example"
b2_check_sha256 'b39c9a26daf5edf7b5833ce59e2001a0f844f662093ea156fe562d503a89b94c' "$B2_SRC/config_examples/remote-hpc-job.json.example"
b2_check_sha256 '344dbe86ff40acabb33c66e884c67fbb08d254089b17d80a8b66efe4e3686d6a' "$B2_REPO/hpc_batch_jobs.py"
b2_check_sha256 '2880d60a7a59b6f44f2a543976f344dd21d48c44d337ce92de98c3813df05640' "$B2_REPO/grid_search_slurm_local.py"
b2_check_sha256 'a5b6bae1475a5b3f9cad7cdc5428fd6783a822d80292a54c27983006b0c01d75' "$B2_REPO/hpc_jobs/templates/batch.sh"
b2_check_sha256 '9a7ca9bfb9c220b76084fb1c4c631354a81c2a4b16e66e602926c549cfce7057' "$B2_REPO/hpc_jobs/requests/b2-child-discovery.json"
b2_check_sha256 '89e644dae2eff844f00f363751787ebb9cb62d1f723bcd07b1bd3b7944f71c35' "$B2_REPO/exp_configs/batch_hpc_prototype/b2_child_discovery/exp_cfg.py"
b2_check_sha256 '0bf00d9179bd3c29e052810f021abd86a46a70696eabde94a5abe7d4ef50231e' "$B2_REPO/exp_configs/batch_hpc_prototype/b2_child_discovery/batch_params.py"

# Install while restoring shared helper modes on every exit
printf '\n== Installation ==\n'
B2_DIRS_OPEN=1
chmod 0755 "$B2_ROOT/helpers/lethe" "$B2_ROOT/helpers/grid" "$B2_ROOT/config"
install -g "$B2_GROUP" -m 0555 "$B2_SRC/remote_lethe/hpc-lethe-job" "$B2_ROOT/helpers/lethe/hpc-lethe-job"
install -g "$B2_GROUP" -m 0555 "$B2_SRC/remote_grid/hpc-grid-job" "$B2_ROOT/helpers/grid/hpc-grid-job"
for B2_HELPER_DIR in "$B2_ROOT/helpers/lethe" "$B2_ROOT/helpers/grid"; do
    install -g "$B2_GROUP" -m 0444 "$B2_REPO/hpc_job.py" "$B2_HELPER_DIR/hpc_job.py"
    install -g "$B2_GROUP" -m 0444 "$B2_REPO/hpc_job_lifecycle.py" "$B2_HELPER_DIR/hpc_job_lifecycle.py"
    install -g "$B2_GROUP" -m 0444 "$B2_REPO/hpc_job_control.py" "$B2_HELPER_DIR/hpc_job_control.py"
done
install -g "$B2_GROUP" -m 0444 "$B2_SRC/config_examples/remote-hpc-prepare.json.example" "$B2_ROOT/config/A1_OUinp-prepare.json"
install -g "$B2_GROUP" -m 0444 "$B2_SRC/config_examples/remote-hpc-job.json.example" "$B2_ROOT/config/A1_OUinp-job.json"
chmod 0555 "$B2_ROOT/helpers/lethe" "$B2_ROOT/helpers/grid" "$B2_ROOT/config"
B2_DIRS_OPEN=0

# Verify hashes, permissions, and a fresh immutable run identity
printf '\n== Installed hashes and permissions ==\n'
b2_check_sha256 '3ce085f9ebab84c86f64e4ae87d03096347663c5300f2302dac3f57769da613b' "$B2_ROOT/helpers/lethe/hpc-lethe-job"
b2_check_sha256 '2dbd520a195c93bb8aceb42cb37a2396dac83c3caea94b64d6fb1f3682292d65' "$B2_ROOT/helpers/grid/hpc-grid-job"
b2_check_sha256 'e6de93ce6b2384affa906382c1ffebea32777d4750b5013e2ce3f50fb86e7f78' "$B2_ROOT/config/A1_OUinp-prepare.json"
stat -c '%A %a %U:%G %n' "$B2_ROOT/helpers/lethe" "$B2_ROOT/helpers/grid" "$B2_ROOT/config" "$B2_ROOT/helpers/lethe/hpc-lethe-job" "$B2_ROOT/helpers/grid/hpc-grid-job" "$B2_ROOT/config/A1_OUinp-prepare.json"
test ! -e "$B2_REPO/hpc_jobs/runs/$B2_RUN_ID"
test ! -e "$B2_STATE/runs/$B2_RUN_ID.json"
printf 'Fresh B2 run ID: absent as expected\n'
printf '\nCompleted UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
