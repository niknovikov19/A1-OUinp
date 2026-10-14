#!/bin/bash

set -Eeuo pipefail

# Capture the child-limit promotion transcript
HPC12_ROOT=/opt/a1-hpc
HPC12_REPO=/home/nnovikov/repo/A1-OUinp
HPC12_REPORT=$(mktemp /tmp/hpc-child-limit-12-local-promotion.XXXXXX.txt)
chmod 0644 "$HPC12_REPORT"
exec > >(tee "$HPC12_REPORT") 2>&1
HPC12_CONFIG_OPEN=0

hpc12_cleanup() {
    local hpc12_rc=$?

    set +e
    if test "$HPC12_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$HPC12_ROOT/config"
    fi
    if test "$hpc12_rc" -eq 0; then
        printf '\nHPC_CHILD_LIMIT_RESULT=PASS\n'
    else
        printf '\nHPC_CHILD_LIMIT_RESULT=FAIL exit_code=%s\n' "$hpc12_rc"
    fi
    printf 'HPC_CHILD_LIMIT_REPORT=%s\n' "$HPC12_REPORT"
    trap - EXIT
    exit "$hpc12_rc"
}

trap hpc12_cleanup EXIT

# Bind installation to the exact reviewed checkout
test "$#" -eq 1
HPC12_COMMIT=$1
HPC12_SOURCE="$HPC12_REPO/dev_scratch/hpc/helper_src/config_examples/hpc-helper.json.example"
HPC12_TARGET="$HPC12_ROOT/config/hpc-helper.json"
printf 'Child-limit-twelve promotion: local\n'
printf 'Commit: %s\n' "$HPC12_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$HPC12_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -u)" -eq 0
test "$(git -c safe.directory="$HPC12_REPO" -C "$HPC12_REPO" rev-parse HEAD)" = "$HPC12_COMMIT"
test "$(git -c safe.directory="$HPC12_REPO" -C "$HPC12_REPO" branch --show-current)" = 'codex-hpc'

# Accept only the previous policy or an already promoted policy
HPC12_OLD_HASH='14290299e8d9d619a10fc1caa7d56b0a8cc7228e960e649fae20ce2ef6e210a4'
HPC12_NEW_HASH='3a85f7f69ae0a59052ea4c40fa8fc985206809fe2bc2a2b4588ec821d689b545'
HPC12_INSTALLED_HASH=$(sha256sum "$HPC12_TARGET")
HPC12_INSTALLED_HASH=${HPC12_INSTALLED_HASH%% *}
printf '%s  %s\n' "$HPC12_INSTALLED_HASH" "$HPC12_TARGET"
test "$HPC12_INSTALLED_HASH" = "$HPC12_OLD_HASH" || test "$HPC12_INSTALLED_HASH" = "$HPC12_NEW_HASH"
HPC12_SOURCE_HASH=$(sha256sum "$HPC12_SOURCE")
HPC12_SOURCE_HASH=${HPC12_SOURCE_HASH%% *}
test "$HPC12_SOURCE_HASH" = "$HPC12_NEW_HASH"
python3 -m json.tool "$HPC12_SOURCE" >/dev/null

# Install only the reviewed non-secret policy file
HPC12_CONFIG_OPEN=1
chmod 0755 "$HPC12_ROOT/config"
install -o root -g root -m 0444 "$HPC12_SOURCE" "$HPC12_TARGET"
chmod 0555 "$HPC12_ROOT/config"
HPC12_CONFIG_OPEN=0

# Verify installation directly instead of invoking a user helper as root
HPC12_INSTALLED_HASH=$(sha256sum "$HPC12_TARGET")
HPC12_INSTALLED_HASH=${HPC12_INSTALLED_HASH%% *}
test "$HPC12_INSTALLED_HASH" = "$HPC12_NEW_HASH"
python3 - "$HPC12_TARGET" <<'PY'
import json
import sys

with open(sys.argv[1]) as hpc12_file:
    hpc12_config = json.load(hpc12_file)

hpc12_limits = hpc12_config['scheduler']['limits']
assert hpc12_limits['max_child_jobs'] == 12
assert hpc12_limits['max_concurrent_jobs'] == 5
PY
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
