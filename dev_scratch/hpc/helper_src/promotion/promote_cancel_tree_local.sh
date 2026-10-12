#!/bin/bash

set -Eeuo pipefail

# Capture the local promotion transcript
CT_REPORT=$(mktemp /tmp/cancel-tree-local-promotion.XXXXXX.txt)
chmod 0644 "$CT_REPORT"
exec > >(tee "$CT_REPORT") 2>&1
CT_BIN_OPEN=0

ct_cleanup() {
    local ct_rc=$?

    set +e
    if test "$CT_BIN_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin
    fi
    if test "$ct_rc" -eq 0; then
        printf '\nCANCEL_TREE_RESULT=PASS\n'
    else
        printf '\nCANCEL_TREE_RESULT=FAIL exit_code=%s\n' "$ct_rc"
    fi
    printf 'CANCEL_TREE_REPORT=%s\n' "$CT_REPORT"
    trap - EXIT
    exit "$ct_rc"
}

ct_check_sha256() {
    local ct_expected=$1
    local ct_path=$2
    local ct_actual

    ct_actual=$(sha256sum "$ct_path")
    ct_actual=${ct_actual%% *}
    printf '%s  %s\n' "$ct_actual" "$ct_path"
    test "$ct_actual" = "$ct_expected"
}

trap ct_cleanup EXIT

# Bind installation to the exact reviewed checkout
test "$#" -eq 1
CT_COMMIT=$1
CT_REPO=/home/nnovikov/repo/A1-OUinp
CT_SRC="$CT_REPO/dev_scratch/hpc/helper_src"
printf 'Protected cancel-tree promotion: local\n'
printf 'Commit: %s\n' "$CT_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$CT_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -u)" -eq 0
test "$(git -c safe.directory="$CT_REPO" -C "$CT_REPO" rev-parse HEAD)" = "$CT_COMMIT"
test "$(git -c safe.directory="$CT_REPO" -C "$CT_REPO" branch --show-current)" = 'codex-hpc'

# Verify old and reviewed helper identities
ct_check_sha256 \
    '6436d884a1966e84daeba8a096062ea556a42203a4bdac59a2eab8a592e477dd' \
    /opt/a1-hpc/bin/hpc-job
ct_check_sha256 \
    '31af23b714403ba26cf2b45aa41e429781c2df68695a2984581293eebf605a6b' \
    /opt/a1-hpc/bin/hpc_common.py
ct_check_sha256 \
    '16f7eac981667352cc8e0b5d552bcc2205055a5afb916ca4fd483c4590946286' \
    "$CT_SRC/local/hpc-job"
ct_check_sha256 \
    'f838d11b469389da7762e335c197358776f5eb2b3c3606498334b2edba81e5b7' \
    "$CT_SRC/local/hpc_common.py"

# Install only the reviewed local helper files
CT_BIN_OPEN=1
chmod 0755 /opt/a1-hpc/bin
install -o root -g root -m 0555 "$CT_SRC/local/hpc-job" /opt/a1-hpc/bin/hpc-job
install -o root -g root -m 0444 "$CT_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
chmod 0555 /opt/a1-hpc/bin
CT_BIN_OPEN=0

# Verify the protected installation
ct_check_sha256 \
    '16f7eac981667352cc8e0b5d552bcc2205055a5afb916ca4fd483c4590946286' \
    /opt/a1-hpc/bin/hpc-job
ct_check_sha256 \
    'f838d11b469389da7762e335c197358776f5eb2b3c3606498334b2edba81e5b7' \
    /opt/a1-hpc/bin/hpc_common.py
/opt/a1-hpc/bin/hpc-helper-info info
/opt/a1-hpc/bin/hpc-job cancel --help
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
