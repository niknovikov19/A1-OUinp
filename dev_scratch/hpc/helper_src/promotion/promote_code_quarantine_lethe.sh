#!/bin/bash

set -Eeuo pipefail

# Capture the remote promotion transcript in protected state
CQ_ROOT=/ddn/niknovikov19/hpc_codex
CQ_STATE="$CQ_ROOT/state/A1_OUinp"
CQ_REPORT_DIR="$CQ_STATE/reports/promotion"
mkdir -p "$CQ_REPORT_DIR"
chmod 0700 "$CQ_REPORT_DIR"
CQ_REPORT=$(mktemp "$CQ_REPORT_DIR/code-quarantine-remote-promotion.XXXXXX.txt")
chmod 0600 "$CQ_REPORT"
exec > >(tee "$CQ_REPORT") 2>&1
CQ_DIRS_OPEN=0

cq_cleanup() {
    local cq_rc=$?
    set +e
    if test "$CQ_DIRS_OPEN" -eq 1; then
        chmod 0555 "$CQ_ROOT/helpers/lethe" "$CQ_ROOT/config"
    fi
    if test "$cq_rc" -eq 0; then
        printf '\nCQ_REMOTE_RESULT=PASS\n'
    else
        printf '\nCQ_REMOTE_RESULT=FAIL exit_code=%s\n' "$cq_rc"
    fi
    printf 'CQ_REMOTE_REPORT=%s\n' "$CQ_REPORT"
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

# Read only the fixed manually staged candidate for this commit
test "$#" -eq 1
CQ_COMMIT=$1
printf '%s\n' "$CQ_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
CQ_STAGE="$CQ_ROOT/staging/code-quarantine/$CQ_COMMIT"
printf 'Code-quarantine promotion: lethe\n'
printf 'Commit: %s\n' "$CQ_COMMIT"
printf 'Source: %s\n' "$CQ_STAGE"
printf 'Report: %s\n' "$CQ_REPORT"
test "$(id -un)" = 'niknovikov19'
test -d "$CQ_STAGE"
test ! -L "$CQ_STAGE"

printf '\n== Reviewed remote configuration ==\n'
python3 -m json.tool "$CQ_STAGE/remote-hpc-code.json.example"
if grep -Eiq 'password|token|private[_-]?key|key[_-]?path|https?://|ssh://|git@' "$CQ_STAGE/remote-hpc-code.json.example"; then
    printf 'Credential-like value or repository URL found\n' >&2
    exit 1
fi
printf '\n== Reviewed source hashes ==\n'
cq_check_sha256 'e004cf00ac09e02f8a169399fc58bdb63d8dc8b8c2c2237343c500b34992a9c7' "$CQ_STAGE/hpc-lethe-code"
cq_check_sha256 '723227216c3c9062403b9d0b99413728c634e58d781a1260a0ff1c790c06c6fa' "$CQ_STAGE/remote-hpc-code.json.example"
test -d "$CQ_STATE"
test ! -L "$CQ_STATE"
test ! -e "$CQ_STATE/code-quarantine/active.json"
if test -e "$CQ_STATE/code-quarantine"; then
    test -d "$CQ_STATE/code-quarantine"
    test ! -L "$CQ_STATE/code-quarantine"
fi

# Install immutable code/config and create private recovery state
printf '\n== Installation ==\n'
CQ_DIRS_OPEN=1
chmod 0755 "$CQ_ROOT/helpers/lethe" "$CQ_ROOT/config"
install -g salvadord -m 0555 "$CQ_STAGE/hpc-lethe-code" "$CQ_ROOT/helpers/lethe/hpc-lethe-code"
install -g salvadord -m 0444 "$CQ_STAGE/remote-hpc-code.json.example" "$CQ_ROOT/config/A1_OUinp-code.json"
chmod 0555 "$CQ_ROOT/helpers/lethe" "$CQ_ROOT/config"
CQ_DIRS_OPEN=0
if test ! -d "$CQ_STATE/code-quarantine"; then
    mkdir -m 0700 "$CQ_STATE/code-quarantine"
fi
chmod 0700 "$CQ_STATE/code-quarantine"

printf '\n== Installed hashes and permissions ==\n'
cq_check_sha256 'e004cf00ac09e02f8a169399fc58bdb63d8dc8b8c2c2237343c500b34992a9c7' "$CQ_ROOT/helpers/lethe/hpc-lethe-code"
cq_check_sha256 '723227216c3c9062403b9d0b99413728c634e58d781a1260a0ff1c790c06c6fa' "$CQ_ROOT/config/A1_OUinp-code.json"
"$CQ_ROOT/helpers/lethe/hpc-lethe-code" version
stat -c '%A %a %U:%G %n' \
    "$CQ_ROOT/helpers/lethe" \
    "$CQ_ROOT/config" \
    "$CQ_ROOT/helpers/lethe/hpc-lethe-code" \
    "$CQ_ROOT/config/A1_OUinp-code.json" \
    "$CQ_STATE/code-quarantine"
