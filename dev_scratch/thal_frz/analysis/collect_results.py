#!/home/nnovikov/conda_env/netpyne/bin/python
"""Collect each experiment's result JSON files into one NetCDF dataset."""

import json
import sys
from pathlib import Path


# Set repository import paths
DIR_ANALYSIS = Path(__file__).resolve().parent
DIR_REPO = DIR_ANALYSIS.parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_json, extract_batch_params_to_xr


DIR_EXPERIMENTS = DIR_ANALYSIS / 'experiments'
DIR_COLLECTED = DIR_ANALYSIS / 'collected'


def get_rate_keys(dirpath_results):
    """Return the sorted union of rate keys in one experiment."""
    rate_keys = set()
    for fpath in sorted(Path(dirpath_results).glob('result_*.json')):
        with fpath.open('r', encoding='utf-8') as fobj:
            rate_keys.update(json.load(fobj)['rates'])
    return sorted(rate_keys)


def collect_experiment(dirpath_exp):
    """Collect one experiment's rates and CVs over seed_main."""
    dirpath_exp = Path(dirpath_exp)
    fpath_out = DIR_COLLECTED / f'{dirpath_exp.name}.nc'

    # Build the seed-indexed job grid from cfg files
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_exp / 'cfg',
        cfg_param_fields={'seed_main': 'seed_main'},
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=-3,
    )

    # Collect result dictionaries along population and seed dimensions
    pop_names = get_rate_keys(dirpath_exp / 'results')
    result_xr = collect_batch_json(
        job_idx_xr,
        dirpath_exp / 'results',
        var_mappings={'rate': 'rates', 'cv': 'cvs'},
        fname_templ='result_{job:05d}_*.json',
        dict_dims={'pop': pop_names},
        cache_path=fpath_out,
        load=True,
        skip_missing=False,
        overwrite=False,
    )
    result_xr.close()
    return fpath_out


def main():
    """Collect every extracted experiment."""
    DIR_COLLECTED.mkdir(parents=True, exist_ok=True)
    exp_dirs = sorted(path for path in DIR_EXPERIMENTS.glob('exp_*') if path.is_dir())
    if not exp_dirs:
        raise RuntimeError(f'No experiment folders found in {DIR_EXPERIMENTS}')

    for dirpath_exp in exp_dirs:
        fpath_out = collect_experiment(dirpath_exp)
        print(f'Collected: {fpath_out.name}')

    print(f'Collected {len(exp_dirs)} experiments in {DIR_COLLECTED}')


if __name__ == '__main__':
    main()
