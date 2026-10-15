#!/bin/bash
set -Eeuo pipefail

# Record the user's remote Gate-B installation and its final result
MA_REPORT_DIR=/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion
mkdir -p "$MA_REPORT_DIR"
MA_REPORT=$(mktemp "$MA_REPORT_DIR/monitor-archive-remote-promotion.XXXXXX.txt")
chmod 0600 "$MA_REPORT"
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
/ddn/niknovikov19/miniconda3/bin/python3 /ddn/niknovikov19/repo/A1_OUinp_codex/dev_scratch/hpc/helper_src/promotion/promote_monitor_archive.py lethe "$1"
