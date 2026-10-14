#!/bin/bash

set -Eeuo pipefail

# Capture the child-limit promotion transcript
HPC12_ROOT=/ddn/niknovikov19/hpc_codex
HPC12_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
HPC12_REPORT_DIR="$HPC12_ROOT/state/A1_OUinp/reports/promotion"
mkdir -p "$HPC12_REPORT_DIR"
chmod 0700 "$HPC12_REPORT_DIR"
HPC12_REPORT=$(mktemp "$HPC12_REPORT_DIR/hpc-child-limit-12-promotion.XXXXXX.txt")
chmod 0600 "$HPC12_REPORT"
exec > >(tee "$HPC12_REPORT") 2>&1
HPC12_CONFIG_OPEN=0
HPC12_HELPERS_OPEN=0

hpc12_cleanup() {
    local hpc12_rc=$?

    set +e
    if test "$HPC12_CONFIG_OPEN" -eq 1; then
        chmod 0555 "$HPC12_ROOT/config"
    fi
    if test "$HPC12_HELPERS_OPEN" -eq 1; then
        chmod 0555 "$HPC12_ROOT/helpers/lethe" "$HPC12_ROOT/helpers/grid"
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
HPC12_SOURCE="$HPC12_REPO/dev_scratch/hpc/helper_src/config_examples/remote-hpc-prepare.json.example"
HPC12_TARGET="$HPC12_ROOT/config/A1_OUinp-prepare.json"
printf 'Child-limit-twelve promotion: lethe\n'
printf 'Commit: %s\n' "$HPC12_COMMIT"
printf 'Started UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\n' "$HPC12_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(id -un)" = 'niknovikov19'
id -nG | tr ' ' '\n' | grep -Fxq 'salvadord'
test "$(git -C "$HPC12_REPO" rev-parse HEAD)" = "$HPC12_COMMIT"
test "$(git -C "$HPC12_REPO" branch --show-current)" = 'codex-hpc'
test -z "$(git -C "$HPC12_REPO" status --porcelain=v1)"
test ! -e "$HPC12_ROOT/state/A1_OUinp/active-run.json"

# Accept only the previous policy or an already promoted policy
HPC12_OLD_HASH='434cf03d636027e73358af04a4b5b5b7d7a93704ef9ed307e13be15bb8f8e795'
HPC12_NEW_HASH='bc7195e554103d76de6bcf8858259e7897249de7834bf7b147efeb0e376ee881'
HPC12_INSTALLED_HASH=$(sha256sum "$HPC12_TARGET")
HPC12_INSTALLED_HASH=${HPC12_INSTALLED_HASH%% *}
printf '%s  %s\n' "$HPC12_INSTALLED_HASH" "$HPC12_TARGET"
test "$HPC12_INSTALLED_HASH" = "$HPC12_OLD_HASH" || test "$HPC12_INSTALLED_HASH" = "$HPC12_NEW_HASH"
HPC12_SOURCE_HASH=$(sha256sum "$HPC12_SOURCE")
HPC12_SOURCE_HASH=${HPC12_SOURCE_HASH%% *}
test "$HPC12_SOURCE_HASH" = "$HPC12_NEW_HASH"
python3 -m json.tool "$HPC12_SOURCE" >/dev/null

# Verify the bounded completion-manifest contract before changing installed files
HPC12_CONTRACT_SOURCE="$HPC12_REPO/hpc_job.py"
HPC12_CONTRACT_OLD_HASH='22dc07fa180c35c293a995bccf9215fd50a579d7043d49fae9826aa6688063e2'
HPC12_CONTRACT_NEW_HASH='e6918280607d813cff1fc03a4f0f917793061aa0f9075d75d025b88fcd7a08f0'
HPC12_CONTRACT_HASH=$(sha256sum "$HPC12_CONTRACT_SOURCE")
HPC12_CONTRACT_HASH=${HPC12_CONTRACT_HASH%% *}
test "$HPC12_CONTRACT_HASH" = "$HPC12_CONTRACT_NEW_HASH"
for HPC12_SITE in lethe grid; do
    HPC12_CONTRACT_TARGET="$HPC12_ROOT/helpers/$HPC12_SITE/hpc_job.py"
    HPC12_CONTRACT_HASH=$(sha256sum "$HPC12_CONTRACT_TARGET")
    HPC12_CONTRACT_HASH=${HPC12_CONTRACT_HASH%% *}
    printf '%s  %s\n' "$HPC12_CONTRACT_HASH" "$HPC12_CONTRACT_TARGET"
    test "$HPC12_CONTRACT_HASH" = "$HPC12_CONTRACT_OLD_HASH" || test "$HPC12_CONTRACT_HASH" = "$HPC12_CONTRACT_NEW_HASH"
done

# Install only the reviewed non-secret policy file
HPC12_CONFIG_OPEN=1
chmod 0755 "$HPC12_ROOT/config"
install -g salvadord -m 0444 "$HPC12_SOURCE" "$HPC12_TARGET"
chmod 0555 "$HPC12_ROOT/config"
HPC12_CONFIG_OPEN=0

# Install the reviewed request contract on both remote helper sites
HPC12_HELPERS_OPEN=1
chmod 0755 "$HPC12_ROOT/helpers/lethe" "$HPC12_ROOT/helpers/grid"
for HPC12_SITE in lethe grid; do
    HPC12_CONTRACT_TARGET="$HPC12_ROOT/helpers/$HPC12_SITE/hpc_job.py"
    install -g salvadord -m 0444 "$HPC12_CONTRACT_SOURCE" "$HPC12_CONTRACT_TARGET"
    HPC12_CONTRACT_HASH=$(sha256sum "$HPC12_CONTRACT_TARGET")
    HPC12_CONTRACT_HASH=${HPC12_CONTRACT_HASH%% *}
    test "$HPC12_CONTRACT_HASH" = "$HPC12_CONTRACT_NEW_HASH"
done
chmod 0555 "$HPC12_ROOT/helpers/lethe" "$HPC12_ROOT/helpers/grid"
HPC12_HELPERS_OPEN=0

# Verify installation directly instead of invoking a user helper as root
HPC12_INSTALLED_HASH=$(sha256sum "$HPC12_TARGET")
HPC12_INSTALLED_HASH=${HPC12_INSTALLED_HASH%% *}
test "$HPC12_INSTALLED_HASH" = "$HPC12_NEW_HASH"
python3 - "$HPC12_TARGET" "$HPC12_ROOT/helpers/lethe/hpc_job.py" "$HPC12_ROOT/helpers/grid/hpc_job.py" <<'PY'
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
with open(sys.argv[1]) as hpc12_file:
    hpc12_config = json.load(hpc12_file)

hpc12_limits = hpc12_config['scheduler']['limits']
assert hpc12_limits['max_child_jobs'] == 12
assert hpc12_limits['max_concurrent_jobs'] == 5
for hpc12_path in sys.argv[2:]:
    hpc12_spec = importlib.util.spec_from_file_location('hpc12_contract', hpc12_path)
    hpc12_module = importlib.util.module_from_spec(hpc12_spec)
    hpc12_spec.loader.exec_module(hpc12_module)
    assert hpc12_module.MAX_COMPLETION_FILES == 64
PY
printf 'Completed UTC: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
