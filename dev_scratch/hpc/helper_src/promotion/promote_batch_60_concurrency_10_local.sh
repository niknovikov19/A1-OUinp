#!/bin/bash
set -Eeuo pipefail

# Record the user's local policy promotion and its result
B60_REPORT=$(mktemp /tmp/batch-60-concurrency-10-local-promotion.XXXXXX.txt)
chmod 0644 "$B60_REPORT"
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
test "$(id -u)" -eq 0
/usr/bin/python3 /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_batch_limits.py local "$1"
