import sys
from pathlib import Path


DIR_REPO = Path(__file__).resolve().parents[3]
if str(DIR_REPO) not in sys.path:
    sys.path.insert(0, str(DIR_REPO))
print(f'DIR_REPO: {DIR_REPO}')

DIR_EXTERNAL = DIR_REPO / 'external'
if str(DIR_EXTERNAL) not in sys.path:
    sys.path.insert(0, str(DIR_EXTERNAL))

from sim_data_analyzer.batch_xr import (
    collect_batch_xr,
    extract_batch_params_to_xr,
)


def collect_rvec_batch_from_nc(dirpath_exp, cfg_param_fields, chunks=None,
                               lazy=False, load=False):
    dirpath_exp = Path(dirpath_exp)
    dirpath_cfg = dirpath_exp / 'cfg'
    dirpath_rvec = dirpath_exp / 'rvec_xr'
    cache_path = dirpath_exp / 'rvec_xr_combined.nc'
    open_kwargs = {} if cache_path.exists() else {'engine': 'scipy'}

    print('\nDIRECT: rvec_xr/*.nc -> combined batch nc')
    print(f'Exp dir: {dirpath_exp}')

    job_idx_xr = extract_batch_params_to_xr(
        dirpath_cfg,
        cfg_param_fields=cfg_param_fields,
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1,
    )
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')

    rvec_batch_xr = collect_batch_xr(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_rvec,
        fname_templ='rvec_{job:05d}_*.nc',
        cache_path=cache_path,
        lazy=lazy,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )

    print(f'Done: {cache_path}')
    print(f'Shape: {dict(rvec_batch_xr.sizes)}')
    return rvec_batch_xr


if __name__ == '__main__':

    DIRPATH_EXP = (
        DIR_REPO / 'exp_results' / 
        'batch_rxbkg_unconn_state1_mech1' /
        'net_inpsur_hr_osc_var_seed_f_amp' /
        'exp_hr_osc_L2_nseed_5_nf_1_namp_20_t_5.0_20.0_osc_t0_5000_ictrl_wmult_0.25_ee_0.5'
    )
    CFG_PARAM_FIELDS = {
        'seed_main': 'seed_main',
        'osc_f': 'osc_f',
        'osc_amp': 'osc_amp',
    }

    chunks = None
    lazy = False
    load = False

    collect_rvec_batch_from_nc(
        dirpath_exp=DIRPATH_EXP,
        cfg_param_fields=CFG_PARAM_FIELDS,
        chunks=chunks,
        lazy=lazy,
        load=load,
    )
