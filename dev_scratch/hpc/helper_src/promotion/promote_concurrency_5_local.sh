#!/bin/bash

set -Eeuo pipefail

# Capture the local policy-promotion transcript
HPC5_REPORT=$(mktemp /tmp/hpc-concurrency-5-local-promotion.XXXXXX.txt)
chmod 0644 "$HPC5_REPORT"
exec > >(tee "$HPC5_REPORT") 2>&1
HPC5_CONFIG_OPEN=0

hpc5_cleanup() {
    local hpc5_rc=$?

    set +e
    if test "$HPC5_CONFIG_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/config
    fi
    if test "$hpc5_rc" -eq 0; then
        printf '\nHPC_CONCURRENCY_RESULT=PASS\n'
    else
        printf '\nHPC_CONCURRENCY_RESULT=FAIL exit_code=%s\n' "$hpc5_rc"
    fi
    printf 'HPC_CONCURRENCY_REPORT=%s\n' "$HPC5_REPORT"
    trap - EXIT
    exit "$hpc5_rc"
}

hpc5_check_sha256() {
    local hpc5_expected=$1
    local hpc5_path=$2
    local hpc5_actual

    hpc5_actual=$(sha256sum "$hpc5_path")
    hpc5_actual=${hpc5_actual%% *}
    printf '%s  %s\n' "$hpc5_actual" "$hpc5_path"
    test "$hpc5_actual" = "$hpc5_expected"
}

hpc5_check_sha256_one_of() {
    local hpc5_old=$1
    local hpc5_new=$2
    local hpc5_path=$3
    local hpc5_actual

    hpc5_actual=$(sha256sum "$hpc5_path")
    hpc5_actual=${hpc5_actual%% *}
    printf '%s  %s\n' "$hpc5_actual" "$hpc5_path"
    test "$hpc5_actual" = "$hpc5_old" || test "$hpc5_actual" = "$hpc5_new"
}

trap hpc5_cleanup EXIT

# Bind installation to the exact reviewed checkout
test "$#" -eq 1
HPC5_COMMIT=$1
HPC5_REPO=/home/nnovikov/repo/A1-OUinp
HPC5_SOURCE="$HPC5_REPO/dev_scratch/hpc/helper_src/config_examples/hpc-helper.json.example"
printf 'Concurrency-five promotion: local\n'
printf 'Commit: %s\n' "$HPC5_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$HPC5_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -u)" -eq 0
test "$(git -c safe.directory="$HPC5_REPO" -C "$HPC5_REPO" rev-parse HEAD)" = "$HPC5_COMMIT"
test "$(git -c safe.directory="$HPC5_REPO" -C "$HPC5_REPO" branch --show-current)" = 'codex-hpc'

# Verify the installed and reviewed configurations
hpc5_check_sha256_one_of \
    'ace578ab30da99738b392b67b46cbb5dc21db907e890149e145a47064be75e83' \
    '14290299e8d9d619a10fc1caa7d56b0a8cc7228e960e649fae20ce2ef6e210a4' \
    /opt/a1-hpc/config/hpc-helper.json
hpc5_check_sha256 \
    '14290299e8d9d619a10fc1caa7d56b0a8cc7228e960e649fae20ce2ef6e210a4' \
    "$HPC5_SOURCE"
python3 -m json.tool "$HPC5_SOURCE" >/dev/null

# Install only the local non-secret policy file
HPC5_CONFIG_OPEN=1
chmod 0755 /opt/a1-hpc/config
install -o root -g root -m 0444 \
    "$HPC5_SOURCE" \
    /opt/a1-hpc/config/hpc-helper.json
chmod 0555 /opt/a1-hpc/config
HPC5_CONFIG_OPEN=0

# Verify the installed concurrency ceiling without invoking a user helper as root
hpc5_check_sha256 \
    '14290299e8d9d619a10fc1caa7d56b0a8cc7228e960e649fae20ce2ef6e210a4' \
    /opt/a1-hpc/config/hpc-helper.json
python3 - <<'PY'
import json

with open('/opt/a1-hpc/config/hpc-helper.json') as hpc5_file:
    hpc5_config = json.load(hpc5_file)

assert hpc5_config['scheduler']['limits']['max_concurrent_jobs'] == 5
PY
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
