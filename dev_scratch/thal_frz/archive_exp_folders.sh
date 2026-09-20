#!/usr/bin/env bash
set -euo pipefail

# Resolve the repository and configurable input/output paths
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! repo_dir=$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null); then
    repo_dir=$(cd -- "$script_dir/../.." && pwd)
fi
base_dir=${1:-"$repo_dir/exp_results/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed"}
archive_dir=${2:-"$repo_dir/dev_scratch/thal_frz/archives"}
archive="$archive_dir/selected_experiments.tar.gz"

if [[ ! -d "$base_dir" ]]; then
    printf 'Source directory does not exist: %s\n' "$base_dir" >&2
    exit 1
fi

# Select immediate experiment folders directly from the source directory
folders=()
while IFS= read -r folder; do
    case "$folder" in
        *a1*|*L2*|*ctx*) continue ;;
    esac
    folders+=("$folder")
done < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | LC_ALL=C sort)

if ((${#folders[@]} == 0)); then
    printf 'No eligible experiment folders found in %s\n' "$base_dir" >&2
    exit 1
fi

# Validate every source before creating the archive
for folder in "${folders[@]}"; do
    for subdir in cfg results; do
        if [[ ! -d "$base_dir/$folder/$subdir" ]]; then
            printf 'Missing source directory: %s\n' "$base_dir/$folder/$subdir" >&2
            exit 1
        fi
    done
done

if [[ -e "$archive" ]]; then
    printf 'Refusing to overwrite existing archive: %s\n' "$archive" >&2
    exit 1
fi

# Collect only cfg/ and results/ paths from every experiment
archive_paths=()
for folder in "${folders[@]}"; do
    archive_paths+=("$folder/cfg" "$folder/results")
done

# Create one combined archive through a temporary output
mkdir -p -- "$archive_dir"
partial="$archive.partial"
trap 'rm -f -- "$partial"' EXIT

printf 'Archiving %d experiments\n' "${#folders[@]}"
tar -C "$base_dir" -czf "$partial" -- "${archive_paths[@]}"
mv -- "$partial" "$archive"

trap - EXIT
printf 'Created %s\n' "$archive"
