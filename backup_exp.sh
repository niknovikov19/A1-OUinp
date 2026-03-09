#!/usr/bin/env bash
set -euo pipefail

backup_dir="BACKUP"
mkdir -p "$backup_dir"

stamp="$(date +%F_%H-%M-%S)"
archive="$backup_dir/backup_exp_json_and_configs_${stamp}.tar.gz"
tmpfile="$backup_dir/filelist_${stamp}.tmp"
listfile="$backup_dir/backup_filelist_${stamp}.txt"

trap 'rm -f "$tmpfile"' EXIT

if [ ! -d "exp_results" ] || [ ! -d "exp_configs" ]; then
    echo "Run this script from the project root"
    exit 1
fi

process() {
    local label="$1"
    shift
    echo "Processing: $label"
    "$@" >> "$tmpfile"
}

# exp_results batch
process "exp_results/batch_rxbkg_unconn_state1_mech1" \
    find exp_results/batch_rxbkg_unconn_state1_mech1 \
    -type f \( -name 'regions_*.json' -o -name 'cfg_*.json' -o -name 'result_*.json' \) \
    -print0

process "exp_results/batch_unconn" \
    find exp_results/batch_unconn \
    -type f \( -name 'regions_*.json' -o -name '*_cfg.json' -o -name '*_result.json' \) \
    -print0

# exp_results single
process "exp_results/single_rxbkg_unconn_state1_mech1" \
    find exp_results/single_rxbkg_unconn_state1_mech1 \
    -type f \( -name '*_cfg.json' -o -name '*_result.json' \) \
    -print0

process "exp_results/single_unconn" \
    find exp_results/single_unconn \
    -type f \( -name '*_cfg.json' -o -name '*_result.json' \) \
    -print0

# exp_configs
process "exp_configs/batch_rxbkg_unconn_state1_mech1" \
    find exp_configs/batch_rxbkg_unconn_state1_mech1 \
    \( -path '*/__pycache__' -prune \) -o \
    \( -type f ! -name '*.pyc' -print0 \)

process "exp_configs/batch_unconn" \
    find exp_configs/batch_unconn \
    \( -path '*/__pycache__' -prune \) -o \
    \( -type f ! -name '*.pyc' -print0 \)

process "exp_configs/single_rxbkg_unconn_state1_mech1" \
    find exp_configs/single_rxbkg_unconn_state1_mech1 \
    \( -path '*/__pycache__' -prune \) -o \
    \( -type f ! -name '*.pyc' -print0 \)

process "exp_configs/single_unconn" \
    find exp_configs/single_unconn \
    \( -path '*/__pycache__' -prune \) -o \
    \( -type f ! -name '*.pyc' -print0 \)

tr '\0' '\n' < "$tmpfile" | sort -u > "$listfile"

nfiles=$(wc -l < "$listfile")
echo "Found $nfiles files to archive"

tar --null -czvf "$archive" --files-from="$tmpfile" \
| awk -v total="$nfiles" '
{
    n++
    if (n % 1000 == 0 || n == total) {
        printf("\rProgress: %d/%d (%.1f%%)", n, total, 100*n/total)
        fflush(stdout)
    }
}
END {
    print ""
}'

echo "Created: $archive"