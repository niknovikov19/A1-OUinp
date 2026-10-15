#!/bin/bash
set -Eeuo pipefail

# Record the user's local Gate-B installation and its final result
MA_REPORT=$(mktemp /tmp/monitor-archive-local-promotion.XXXXXX.txt)
chmod 0644 "$MA_REPORT"
exec > >(tee "$MA_REPORT") 2>&1
ma_finish() {
    local ma_rc=$?
    if test "$ma_rc" -eq 0; then
        printf '\nMONITOR_ARCHIVE_RESULT=PASS\n'
    else
        printf '\nMONITOR_ARCHIVE_RESULT=FAIL exit_code=%s\n' "$ma_rc"
    fi
    printf 'MONITOR_ARCHIVE_REPORT=%s\n' "$MA_REPORT"
}
trap ma_finish EXIT
test "$#" -eq 1
test "$(id -u)" -eq 0
/usr/bin/python3 /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_monitor_archive.py local "$1"
