from pathlib import Path


DIR_REPO = Path(__file__).resolve().parents[3]

# Preserve historical manifest paths without modifying saved provenance
DATASET_RENAMES = {
    'l2_sym_slow_pilot': 'l2_current_sweep_5seeds_pm100pa_t40s',
    'j_l2_refit': 'l2_rate_sweep_j_5seeds',
    'l2_hstep_amplitude5': 'l2_connected_steps_5seeds_15_30pa_100s',
    'l2_hstep_pilot2': '_old/l2_connected_steps_2seeds_30pa_100s',
    'l2_connected_steps_2seeds_30pa_100s': '_old/l2_connected_steps_2seeds_30pa_100s',
    'l2_pilot2': '_old/l2_current_sweep_1seed_pm100pa_t7p5s',
    'l2_slow_pilot': '_old/l2_current_sweep_2seeds_pm100pa_t15s',
    'l2_asym_pilot': '_old/l2_current_sweep_5seeds_m50_p200pa_t20s',
    'l2_hstep_pilot1': '_old/l2_connected_steps_2seeds_5pa_40s',
}


def resolve_dataset_path(path, repo_dir=DIR_REPO):
    """Resolve a moved local dataset path while preserving existing paths and source hashes. """
    path = Path(path)
    if not path.is_absolute():
        path = repo_dir / path
    if path.exists():
        return path

    # Match only this repository's former dataset root, never HPC or external paths
    data_dir = repo_dir / 'dev_scratch/step_resp/data'
    for old, new in DATASET_RENAMES.items():
        try:
            suffix = path.relative_to(data_dir / old)
        except ValueError:
            continue
        return data_dir / new / suffix
    return path
