#!/usr/bin/env bash
set -euo pipefail

# =====================================================================
# Params
# =====================================================================

backup_dir="BACKUP"

# Used in output filenames:
#   backup_<backup_label>_<timestamp>.tar.gz
backup_label="net_newsec_var_seed__all"

# Experiment folders present under both:
#   exp_results/<name>
#   exp_configs/<name>
exp_dirs=(
    "batch_rxbkg_state1_mech1"
)

# From exp_results/<exp_dir>/...
# Include only files with these extensions.
# Extensions are written without dot.
result_exts=(
    "json"
    "png"
    "nc"
    "pkl"
)

# Optional restriction inside each exp_results/<exp_dir>.
# (backup all if empty)
result_subdirs=(
    "net_newsec_var_seed"
)

# From exp_configs/<exp_dir>:
# include all files except *.pyc and skip __pycache__.
include_configs=1
include_results=1

# =====================================================================
# Script
# =====================================================================

mkdir -p "$backup_dir"

stamp="$(date +%F_%H-%M-%S)"
archive="$backup_dir/backup_${backup_label}_${stamp}.tar.gz"
tmpfile="$backup_dir/filelist_${backup_label}_${stamp}.tmp"
tmpfile_sorted="$backup_dir/filelist_${backup_label}_${stamp}_sorted.tmp"
listfile="$backup_dir/backup_filelist_${backup_label}_${stamp}.txt"

trap 'rm -f "$tmpfile" "$tmpfile_sorted"' EXIT

: > "$tmpfile"

if [ ! -d "exp_results" ] || [ ! -d "exp_configs" ]; then
    echo "Run this script from the project root"
    exit 1
fi

add_result_tree() {
    local root="$1"
    local find_expr=()

    echo "Processing results: $root"

    if [ ! -d "$root" ]; then
        echo "Warning: missing folder: $root"
        return
    fi

    # Include all directories, including empty ones.
    find_expr+=( \( -type d -print0 \) )

    # Include only selected file extensions.
    if [ "${#result_exts[@]}" -gt 0 ]; then
        find_expr+=( -o \( -type f \( )

        for i in "${!result_exts[@]}"; do
            if [ "$i" -gt 0 ]; then
                find_expr+=( -o )
            fi
            find_expr+=( -name "*.${result_exts[$i]}" )
        done

        find_expr+=( \) -print0 \) )
    fi

    find "$root" "${find_expr[@]}" >> "$tmpfile"
}

add_config_tree() {
    local root="$1"

    echo "Processing configs: $root"

    if [ ! -d "$root" ]; then
        echo "Warning: missing folder: $root"
        return
    fi

    find "$root" \
        \( -path '*/__pycache__' -prune \) -o \
        \( -type d -print0 \) -o \
        \( -type f ! -name '*.pyc' -print0 \) \
        >> "$tmpfile"
}

for exp_dir in "${exp_dirs[@]}"; do
    if [ "$include_results" -eq 1 ]; then
        if [ "${#result_subdirs[@]}" -eq 0 ]; then
            add_result_tree "exp_results/$exp_dir"
        else
            for subdir in "${result_subdirs[@]}"; do
                add_result_tree "exp_results/$exp_dir/$subdir"
            done
        fi
    fi

    if [ "$include_configs" -eq 1 ]; then
        add_config_tree "exp_configs/$exp_dir"
    fi
done

# Sort and remove duplicates while preserving null-delimited format.
sort -zu "$tmpfile" > "$tmpfile_sorted"

# Human-readable file/dir list.
tr '\0' '\n' < "$tmpfile_sorted" > "$listfile"

nitems=$(wc -l < "$listfile")
echo "Found $nitems items to archive"

if [ "$nitems" -eq 0 ]; then
    echo "No files/directories found; archive not created"
    exit 1
fi

# --no-recursion is important:
# directories are archived as directory entries only,
# so empty dirs are preserved but unwanted files are not pulled in.
tar --null --no-recursion -czvf "$archive" --files-from="$tmpfile_sorted" \
| awk -v total="$nitems" '
{
    n++
    if (n % 50 == 0 || n == total) {
        printf("\rProgress: %d/%d (%.1f%%)", n, total, 100*n/total)
        fflush(stdout)
    }
}
END {
    print ""
}'

echo "Created: $archive"
echo "File list: $listfile"