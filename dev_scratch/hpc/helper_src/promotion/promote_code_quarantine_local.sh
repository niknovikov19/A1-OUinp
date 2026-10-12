#!/bin/bash

set -Eeuo pipefail

# Capture the local promotion transcript
CQ_REPORT=$(mktemp /tmp/code-quarantine-local-promotion.XXXXXX.txt)
chmod 0644 "$CQ_REPORT"
exec > >(tee "$CQ_REPORT") 2>&1
CQ_DIRS_OPEN=0

cq_cleanup() {
    local cq_rc=$?
    set +e
    if test "$CQ_DIRS_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
    fi
    if test "$cq_rc" -eq 0; then
        printf '\nCQ_LOCAL_RESULT=PASS\n'
    else
        printf '\nCQ_LOCAL_RESULT=FAIL exit_code=%s\n' "$cq_rc"
    fi
    printf 'CQ_LOCAL_REPORT=%s\n' "$CQ_REPORT"
    trap - EXIT
    exit "$cq_rc"
}

cq_check_sha256() {
    local cq_expected=$1
    local cq_path=$2
    local cq_actual
    cq_actual=$(sha256sum "$cq_path")
    cq_actual=${cq_actual%% *}
    printf '%s  %s\n' "$cq_actual" "$cq_path"
    test "$cq_actual" = "$cq_expected"
}

trap cq_cleanup EXIT

# Validate the reviewed commit and candidate files
test "$#" -eq 1
CQ_COMMIT=$1
CQ_REPO=/home/nnovikov/repo/A1-OUinp
CQ_SRC="$CQ_REPO/dev_scratch/hpc/helper_src"
printf 'Code-quarantine promotion: local\n'
printf 'Commit: %s\n' "$CQ_COMMIT"
printf 'Report: %s\n' "$CQ_REPORT"
test "$(id -u)" -eq 0
printf '%s\n' "$CQ_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -c safe.directory="$CQ_REPO" -C "$CQ_REPO" rev-parse HEAD)" = "$CQ_COMMIT"
test "$(git -c safe.directory="$CQ_REPO" -C "$CQ_REPO" branch --show-current)" = 'codex-hpc'
git -c safe.directory="$CQ_REPO" -C "$CQ_REPO" diff --quiet HEAD -- \
    dev_scratch/hpc/helper_src/local/hpc-code-update \
    dev_scratch/hpc/helper_src/local/hpc_common.py \
    dev_scratch/hpc/helper_src/schemas/remote-hpc-code-config.schema.json

printf '\n== Reviewed source hashes ==\n'
cq_check_sha256 'dc52c8783035fedc6a7190644433df46e044e332dd93834d82f36a362a41833c' "$CQ_SRC/local/hpc-code-update"
cq_check_sha256 '31af23b714403ba26cf2b45aa41e429781c2df68695a2984581293eebf605a6b' "$CQ_SRC/local/hpc_common.py"
cq_check_sha256 'e30bf293471db2786f63e17b9768d2ea2312cd4cb4bab9354709e6270eb7df19' "$CQ_SRC/schemas/remote-hpc-code-config.schema.json"

# Install only the changed protected local files
printf '\n== Installation ==\n'
CQ_DIRS_OPEN=1
chmod 0755 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
install -o root -g root -m 0555 "$CQ_SRC/local/hpc-code-update" /opt/a1-hpc/bin/hpc-code-update
install -o root -g root -m 0444 "$CQ_SRC/local/hpc_common.py" /opt/a1-hpc/bin/hpc_common.py
install -o root -g root -m 0444 "$CQ_SRC/schemas/remote-hpc-code-config.schema.json" /opt/a1-hpc/share/schemas/remote-hpc-code-config.schema.json
chmod 0555 /opt/a1-hpc/bin /opt/a1-hpc/share/schemas
CQ_DIRS_OPEN=0

printf '\n== Installed identity and permissions ==\n'
cq_check_sha256 'dc52c8783035fedc6a7190644433df46e044e332dd93834d82f36a362a41833c' /opt/a1-hpc/bin/hpc-code-update
cq_check_sha256 '31af23b714403ba26cf2b45aa41e429781c2df68695a2984581293eebf605a6b' /opt/a1-hpc/bin/hpc_common.py
cq_check_sha256 'e30bf293471db2786f63e17b9768d2ea2312cd4cb4bab9354709e6270eb7df19' /opt/a1-hpc/share/schemas/remote-hpc-code-config.schema.json
/opt/a1-hpc/bin/hpc-helper-info --json info
stat -c '%A %a %U:%G %n' \
    /opt/a1-hpc/bin \
    /opt/a1-hpc/share/schemas \
    /opt/a1-hpc/bin/hpc-code-update \
    /opt/a1-hpc/bin/hpc_common.py
