#!/bin/bash

set -Eeuo pipefail

# Capture the local policy-promotion transcript
L2R_REPORT=$(mktemp /tmp/l2-resources-local-promotion.XXXXXX.txt)
chmod 0644 "$L2R_REPORT"
exec > >(tee "$L2R_REPORT") 2>&1
L2R_CONFIG_OPEN=0

l2r_cleanup() {
    local l2r_rc=$?

    set +e
    if test "$L2R_CONFIG_OPEN" -eq 1; then
        chmod 0555 /opt/a1-hpc/config
    fi
    if test "$l2r_rc" -eq 0; then
        printf '\nL2_RESOURCES_RESULT=PASS\n'
    else
        printf '\nL2_RESOURCES_RESULT=FAIL exit_code=%s\n' "$l2r_rc"
    fi
    printf 'L2_RESOURCES_REPORT=%s\n' "$L2R_REPORT"
    trap - EXIT
    exit "$l2r_rc"
}

l2r_check_sha256() {
    local l2r_expected=$1
    local l2r_path=$2
    local l2r_actual

    l2r_actual=$(sha256sum "$l2r_path")
    l2r_actual=${l2r_actual%% *}
    printf '%s  %s\n' "$l2r_actual" "$l2r_path"
    test "$l2r_actual" = "$l2r_expected"
}

trap l2r_cleanup EXIT

# Bind installation to the exact reviewed checkout
test "$#" -eq 1
L2R_COMMIT=$1
L2R_REPO=/home/nnovikov/repo/A1-OUinp
L2R_SOURCE="$L2R_REPO/dev_scratch/hpc/helper_src/config_examples/hpc-helper.json.example"
printf 'L2 resource-ceiling promotion: local\n'
printf 'Commit: %s\n' "$L2R_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$L2R_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -u)" -eq 0
test "$(git -c safe.directory="$L2R_REPO" -C "$L2R_REPO" rev-parse HEAD)" = "$L2R_COMMIT"
test "$(git -c safe.directory="$L2R_REPO" -C "$L2R_REPO" branch --show-current)" = 'codex-hpc'

# Verify the old and reviewed configurations
l2r_check_sha256 \
    '96d5a72cc211ff524761b51d1eb2c7fb638ea362a507f0ecd7b048fe2a96fa22' \
    /opt/a1-hpc/config/hpc-helper.json
l2r_check_sha256 \
    'ace578ab30da99738b392b67b46cbb5dc21db907e890149e145a47064be75e83' \
    "$L2R_SOURCE"
python3 -m json.tool "$L2R_SOURCE" >/dev/null

# Install only the local non-secret policy file
L2R_CONFIG_OPEN=1
chmod 0755 /opt/a1-hpc/config
install -o root -g root -m 0444 \
    "$L2R_SOURCE" \
    /opt/a1-hpc/config/hpc-helper.json
chmod 0555 /opt/a1-hpc/config
L2R_CONFIG_OPEN=0

# Verify the installed resource ceiling
l2r_check_sha256 \
    'ace578ab30da99738b392b67b46cbb5dc21db907e890149e145a47064be75e83' \
    /opt/a1-hpc/config/hpc-helper.json
/opt/a1-hpc/bin/hpc-helper-info info
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
