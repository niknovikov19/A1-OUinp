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
    collect_batch_lfp_from_pkl,
    collect_batch_rates_from_pkl,
    collect_batch_xr,
    extract_batch_params_to_xr,
)


CFG_PARAM_FIELDS = {
    'seed_main': 'seed_main',
    'f': 'f',
    'amp1': 'amp1',
    'amp2': 'amp2',
    'dt0': 'dt0',
}
NC_OPEN_KWARGS = {
    'engine': 'scipy',
}


def _get_job_idx_xr(dirpath_exp, cfg_param_fields):
    """Read the batch job grid from saved cfg JSON files."""
    return extract_batch_params_to_xr(
        Path(dirpath_exp) / 'cfg',
        cfg_param_fields=cfg_param_fields,
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1,
    )


def _load_first_cfg(dirpath_exp):
    """Load one cfg JSON to recover processing defaults."""
    cfg_files = sorted((Path(dirpath_exp) / 'cfg').glob('cfg_*.json'))
    if len(cfg_files) == 0:
        raise FileNotFoundError(f'No cfg_*.json files found in {dirpath_exp}')
    with open(cfg_files[0], 'r') as fid:
        return json.load(fid)['simConfig']


def _get_rate_params(dirpath_exp, t_limits, dt_bin, tau_smooth, pop_names):
    """Fill missing rate-extraction params from saved cfg metadata."""
    cfg0 = _load_first_cfg(dirpath_exp)
    proc_params = cfg0['runtime_params']['proc']

    # Use the same defaults as exp_cfg.py for rate dynamics
    if t_limits is None:
        t_limits = proc_params['rate_t_limits']
    if t_limits is None:
        t_limits = (cfg0['t0_calc'] / 1000, cfg0['duration'] / 1000)
    if t_limits[1] is None:
        t_limits = (t_limits[0], cfg0['duration'] / 1000)
    if dt_bin is None:
        dt_bin = proc_params['rate_dt_bin']
    if tau_smooth is None:
        tau_smooth = proc_params['rate_tau_smooth']
    if pop_names is None:
        pop_names = list(cfg0['pops_used'])
    return tuple(t_limits), dt_bin, tau_smooth, pop_names


def _get_open_kwargs(chunks=None):
    """Choose xarray kwargs for reading per-job NetCDF data."""
    open_kwargs = dict(NC_OPEN_KWARGS)
    if chunks:
        open_kwargs['chunks'] = chunks
    return open_kwargs


def _save_combined_nc(X, cache_path):
    """Save a combined xarray object when a cache path is requested."""
    if cache_path is None:
        return

    # Save after eager collection to keep input/output engines separate
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    X.to_netcdf(cache_path)


def collect_rates_from_nc(dirpath_exp, cfg_param_fields=CFG_PARAM_FIELDS,
                          chunks=None, lazy=False, load=False,
                          cache_path=None):
    """Collect per-job rate NetCDF files into one batch xarray."""
    dirpath_exp = Path(dirpath_exp)
    job_idx_xr = _get_job_idx_xr(dirpath_exp, cfg_param_fields)
    cache_path = cache_path or dirpath_exp / 'rvec_xr_combined.nc'
    open_kwargs = _get_open_kwargs(chunks=chunks)

    # Delegate batch stacking to sim_data_analyzer
    print('\nNC: rvec_xr/*.nc -> combined rates')
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')
    rates_xr = collect_batch_xr(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_exp / 'rvec_xr',
        fname_templ='rvec_{job:05d}_*.nc',
        cache_path=None,
        lazy=False,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )
    _save_combined_nc(rates_xr, cache_path)
    print(f'Done: {cache_path}')
    print(f'Shape: {dict(rates_xr.sizes)}')
    return rates_xr


def collect_lfp_from_nc(dirpath_exp, cfg_param_fields=CFG_PARAM_FIELDS,
                        chunks=None, lazy=False, load=False,
                        cache_path=None):
    """Collect per-job LFP NetCDF files into one batch xarray."""
    dirpath_exp = Path(dirpath_exp)
    job_idx_xr = _get_job_idx_xr(dirpath_exp, cfg_param_fields)
    cache_path = cache_path or dirpath_exp / 'lfp_xr_combined.nc'
    open_kwargs = _get_open_kwargs(chunks=chunks)

    # Delegate batch stacking to sim_data_analyzer
    print('\nNC: lfp_xr/*.nc -> combined LFP')
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')
    lfp_xr = collect_batch_xr(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_exp / 'lfp_xr',
        fname_templ='lfp_{job:05d}_*.nc',
        cache_path=None,
        lazy=False,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )
    _save_combined_nc(lfp_xr, cache_path)
    print(f'Done: {cache_path}')
    print(f'Shape: {dict(lfp_xr.sizes)}')
    return lfp_xr


def collect_rates_from_pkl(dirpath_exp, cfg_param_fields=CFG_PARAM_FIELDS,
                           t_limits=None, dt_bin=None, tau_smooth=None,
                           pop_names=None, chunks=None, lazy=False,
                           load=False, cache_path=None):
    """Collect rate dynamics from raw per-job pkl files."""
    dirpath_exp = Path(dirpath_exp)
    job_idx_xr = _get_job_idx_xr(dirpath_exp, cfg_param_fields)
    t_limits, dt_bin, tau_smooth, pop_names = _get_rate_params(
        dirpath_exp,
        t_limits=t_limits,
        dt_bin=dt_bin,
        tau_smooth=tau_smooth,
        pop_names=pop_names,
    )
    cache_path = cache_path or dirpath_exp / 'rvec_xr_combined.nc'
    open_kwargs = {'chunks': chunks} if chunks else {}

    # Delegate pkl reading and batch stacking to sim_data_analyzer
    print('\nPKL: pkl/*.pkl -> combined rates')
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')
    print(f'Time: {t_limits}, pops: {len(pop_names)}')
    rates_xr = collect_batch_rates_from_pkl(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_exp / 'pkl',
        fname_templ='data_{job:05d}_*.pkl',
        t_limits=t_limits,
        dt_bin=dt_bin,
        tau_smooth=tau_smooth,
        avg_cells=True,
        pop_names=pop_names,
        cache_path=cache_path,
        lazy=lazy,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )
    print(f'Done: {cache_path}')
    print(f'Shape: {dict(rates_xr.sizes)}')
    return rates_xr


def collect_lfp_from_pkl(dirpath_exp, cfg_param_fields=CFG_PARAM_FIELDS,
                         chunks=None, lazy=False, load=False,
                         cache_path=None):
    """Collect LFP dynamics from raw per-job pkl files."""
    dirpath_exp = Path(dirpath_exp)
    job_idx_xr = _get_job_idx_xr(dirpath_exp, cfg_param_fields)
    cache_path = cache_path or dirpath_exp / 'lfp_xr_combined.nc'
    open_kwargs = {'chunks': chunks} if chunks else {}

    # Delegate pkl reading and batch stacking to sim_data_analyzer
    print('\nPKL: pkl/*.pkl -> combined LFP')
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')
    lfp_xr = collect_batch_lfp_from_pkl(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_exp / 'pkl',
        fname_templ='data_{job:05d}_*.pkl',
        cache_path=cache_path,
        lazy=lazy,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )
    print(f'Done: {cache_path}')
    print(f'Shape: {dict(lfp_xr.sizes)}')
    return lfp_xr


def collect_batch_results(dirpath_exp, source='pkl', targets=('rates', 'lfp'),
                          cfg_param_fields=CFG_PARAM_FIELDS, chunks=None,
                          lazy=False, load=False, dirpath_out=None, **kwargs):
    """Collect selected batch outputs from nc or pkl sources."""
    if isinstance(targets, str):
        targets = (targets,)
    if dirpath_out is not None:
        dirpath_out = Path(dirpath_out)
        dirpath_out.mkdir(parents=True, exist_ok=True)

    # Dispatch only to thin source-specific wrappers
    out = {}
    for target in targets:
        key = (source, target)
        cache_path = None
        if dirpath_out is not None:
            cache_path = dirpath_out / f'{target}_xr_combined.nc'
        if key == ('nc', 'rates'):
            out[target] = collect_rates_from_nc(
                dirpath_exp,
                cfg_param_fields=cfg_param_fields,
                chunks=chunks,
                lazy=lazy,
                load=load,
                cache_path=cache_path
            )
        elif key == ('nc', 'lfp'):
            out[target] = collect_lfp_from_nc(
                dirpath_exp,
                cfg_param_fields=cfg_param_fields,
                chunks=chunks,
                lazy=lazy,
                load=load,
                cache_path=cache_path
            )
        elif key == ('pkl', 'rates'):
            out[target] = collect_rates_from_pkl(
                dirpath_exp,
                cfg_param_fields=cfg_param_fields,
                chunks=chunks,
                lazy=lazy,
                load=load,
                cache_path=cache_path,
                **kwargs
            )
        elif key == ('pkl', 'lfp'):
            out[target] = collect_lfp_from_pkl(
                dirpath_exp,
                cfg_param_fields=cfg_param_fields,
                chunks=chunks,
                lazy=lazy,
                load=load,
                cache_path=cache_path
            )
        else:
            raise ValueError(f'Unsupported source/target pair: {key}')
    return out


if __name__ == '__main__':

    EXP_NAME = 'exp_L2_nseed_1_f_5_amp1_0_0.04_4_amp2_0_0.3_3_dt0_0_20_t_5.0_50.0_lfp_0_300_50_ictrl_ee5_efb10_wmult_0.25_ee_0.5_2pulse_IT2_AMPA_PV2_NMDA_d_20_c_25_r_1000_0_t0_5000_jit_0_tlast_45000.0'

    DIRPATH_EXP = (
        DIR_REPO / 'exp_results' / 'batch_rxbkg_state1_mech1' /
        'net_2pulses_var_seed_f_amps_dt0' / EXP_NAME
    )

    SOURCE = 'nc'
    TARGETS = ('rates', 'lfp')
    CHUNKS = None
    LAZY = 1
    LOAD = 0
    DIRPATH_OUT = (
        DIR_REPO / 'dev_scratch' / 'artifacts' /
        'net_2pulses_var_seed_f_amps_dt0' / EXP_NAME
    )

    collect_batch_results(
        dirpath_exp=DIRPATH_EXP,
        source=SOURCE,
        targets=TARGETS,
        chunks=CHUNKS,
        lazy=LAZY,
        load=LOAD,
        dirpath_out=DIRPATH_OUT,
        tau_smooth=0.005
    )
