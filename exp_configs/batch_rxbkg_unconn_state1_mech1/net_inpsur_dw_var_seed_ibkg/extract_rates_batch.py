import json
import sys
from pathlib import Path


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[3]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import (
    collect_batch_json,
    extract_batch_params_to_xr,
)


def _get_pop_names(dirpath_results):
    """Read population order from the first result JSON."""
    fpath_first = sorted(Path(dirpath_results).glob('result_*.json'))[0]
    with open(fpath_first, 'r') as fid:
        payload = json.load(fid)
    return list(payload['avg_rates'])


def collect_avg_rates_batch(dirpath_exp, cfg_param_fields, chunks=None,
                            lazy=True, load=False):
    """Collect avg_rates JSON fields into a batch xarray Dataset."""
    dirpath_exp = Path(dirpath_exp)
    dirpath_cfg = dirpath_exp / 'cfg'
    dirpath_results = dirpath_exp / 'results'
    fpath_cache = dirpath_exp / 'analysis' / 'avg_rates.nc'
    open_kwargs = {} if fpath_cache.exists() else {'engine': 'scipy'}

    # Build the job grid from saved cfg files
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_cfg,
        cfg_param_fields=cfg_param_fields,
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1,
    )

    # Collect avg_rates from job result JSON files
    pop_names = _get_pop_names(dirpath_results)
    rates_xr = collect_batch_json(
        job_idx_xr,
        dirpath_results,
        var_mappings={'avg_rate': 'avg_rates'},
        fname_templ='result_{job:05d}_*.json',
        dict_dims={'pop': pop_names},
        cache_path=fpath_cache,
        lazy=lazy,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )

    print(f'Done: {fpath_cache}')
    print(f'Shape: {dict(rates_xr.sizes)}')
    return rates_xr


if __name__ == '__main__':
    DIRPATH_EXP = (
        DIR_REPO / 'exp_results' /
        'batch_rxbkg_unconn_state1_mech1' /
        'net_inpsur_dw_var_seed_ibkg' /
        'exp_dw_adj_L2_nseed_5_nibkg_25_t_5.0_20.0_ictrl_wmult_0.25_ee_0.5'
    )
    CFG_PARAM_FIELDS = {
        'seed_main': 'seed_main',
        'ibkg_dw_adj': 'ibkg_dw_adj',
    }

    collect_avg_rates_batch(
        dirpath_exp=DIRPATH_EXP,
        cfg_param_fields=CFG_PARAM_FIELDS,
    )
