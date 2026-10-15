#!/bin/bash
set -Eeuo pipefail

# Record the user's remote policy promotion and its result
B60_REPORT_DIR=/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion
mkdir -p "$B60_REPORT_DIR"
B60_REPORT=$(mktemp "$B60_REPORT_DIR/batch-60-concurrency-10-remote-promotion.XXXXXX.txt")
chmod 0600 "$B60_REPORT"
exec > >(tee "$B60_REPORT") 2>&1
b60_finish() {
    local b60_rc=$?
    if test "$b60_rc" -eq 0; then
        printf '\nHPC_BATCH_LIMITS_RESULT=PASS\n'
    else
        printf '\nHPC_BATCH_LIMITS_RESULT=FAIL exit_code=%s\n' "$b60_rc"
    fi
    printf 'HPC_BATCH_LIMITS_REPORT=%s\n' "$B60_REPORT"
}
trap b60_finish EXIT
test "$#" -eq 1
/ddn/niknovikov19/miniconda3/bin/python3 /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_batch_limits.py lethe "$1"
