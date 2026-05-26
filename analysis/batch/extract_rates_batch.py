"""Extract firing rates from batch simulation pkl files using sim_data_analyzer.
Two modes: direct (pkl->rates) or via intermediate spike files (pkl->spikes->rates).
"""
import os
import sys
from pathlib import Path

import xarray as xr

DIR_REPO = Path(__file__).resolve().parents[2]
if str(DIR_REPO) not in sys.path:
    sys.path.insert(0, str(DIR_REPO))

DIR_SIM_ANALYZER = DIR_REPO.parent / 'sim_data_analyzer'
if str(DIR_SIM_ANALYZER) not in sys.path:
    sys.path.insert(0, str(DIR_SIM_ANALYZER))

from sim_data_analyzer.batch_xr import (
    collect_batch_rates_from_pkl,
    collect_batch_rates_from_spike_data,
    extract_batch_params_to_xr,
    extract_batch_spike_data_from_pkl,
    load_job_json,
)


def extract_rates_direct(exp_label, cfg_param_fields, spike_t_limits=(1, None),
                         dt_bin=2e-3, tau_smooth=10e-3, rate_chunks=None,
                         lazy=True, load=False):
    """Extract rates directly from pkl files (fastest method)."""
    rate_chunks = rate_chunks or {}
    
    # Setup directories
    dirpath_exp = DIR_REPO / 'exp_results' / exp_label
    dirpath_cfg = dirpath_exp / 'cfg'
    dirpath_pkl = dirpath_exp / 'pkl'
    dirpath_cache = dirpath_exp / 'combined' / 'data_proc'
    os.makedirs(dirpath_cache, exist_ok=True)
    
    print(f"\nDIRECT: pkl -> rates")
    print(f"Exp: {exp_label}")
    
    # Build batch grid
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_cfg, cfg_param_fields=cfg_param_fields,
        fname_cfg_templ='cfg_*.json', job_pos_in_fname=1)
    print(f"Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs")
    
    # Get metadata from first job
    cfg0 = load_job_json(
        {'job_id': int(job_idx_xr.values.flat[0])},
        dirpath_cfg, 'cfg_{job:05d}_*.json')['simConfig']
    
    t_limits = list(spike_t_limits)
    if t_limits[1] is None:
        t_limits[1] = cfg0['duration'] / 1000
    
    pops_active = cfg0['subnet_params']['pops_active']
    pops_pre_frz = [f'{pop}frz' for pop in cfg0['batch_par_info']['pops_pre']]
    pops_used = pops_active + pops_pre_frz
    print(f"Time: {t_limits}, Pops: {len(pops_used)}")
    
    # Collect rates using sim_data_analyzer
    rates_cache_path = dirpath_cache / f'rates_dt_{dt_bin}_tau_{tau_smooth}_t_{t_limits[0]}_{t_limits[1]}.nc'
    rates_xr = collect_batch_rates_from_pkl(
        job_idx_xr=job_idx_xr, dirpath_data=dirpath_pkl,
        fname_templ="data_{job:05d}_*.pkl", t_limits=tuple(t_limits),
        dt_bin=dt_bin, tau_smooth=tau_smooth, avg_cells=True,
        pop_names=pops_used, cache_path=rates_cache_path,
        lazy=lazy, load=load, chunks=rate_chunks,
        open_kwargs={"chunks": rate_chunks} if rate_chunks else {},
        skip_missing=True, overwrite=True)
    
    print(f"Done: {rates_cache_path}")
    print(f"Shape: {dict(rates_xr.sizes)}")
    return rates_xr


def extract_rates_via_spikes(exp_label, cfg_param_fields, spike_t_limits=(1, None),
                              dt_bin=2e-3, tau_smooth=10e-3, rate_chunks=None,
                              lazy=True, load=False):
    """Extract rates via intermediate spike files (reusable spike cache)."""
    rate_chunks = rate_chunks or {}
    
    # Setup directories
    dirpath_exp = DIR_REPO / 'exp_results' / exp_label
    dirpath_cfg = dirpath_exp / 'cfg'
    dirpath_pkl = dirpath_exp / 'pkl'
    dirpath_cache = dirpath_exp / 'combined' / 'data_proc'
    os.makedirs(dirpath_cache, exist_ok=True)
    
    print(f"\nTWO-STEP: pkl -> spikes -> rates")
    print(f"Exp: {exp_label}")
    
    # Build batch grid
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_cfg, cfg_param_fields=cfg_param_fields,
        fname_cfg_templ='cfg_*.json', job_pos_in_fname=1)
    print(f"Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs")
    
    # Get metadata from first job
    cfg0 = load_job_json(
        {'job_id': int(job_idx_xr.values.flat[0])},
        dirpath_cfg, 'cfg_{job:05d}_*.json')['simConfig']
    
    t_limits = list(spike_t_limits)
    if t_limits[1] is None:
        t_limits[1] = cfg0['duration'] / 1000
    
    pops_active = cfg0['subnet_params']['pops_active']
    pops_pre_frz = [f'{pop}frz' for pop in cfg0['batch_par_info']['pops_pre']]
    pops_used = pops_active + pops_pre_frz
    print(f"Time: {t_limits}, Pops: {len(pops_used)}")
    
    # Step 1: Extract spikes to intermediate files
    dirpath_spikes = dirpath_cache / f'spikes_{t_limits[0]}_{t_limits[1]}'
    print(f"Extracting spikes...")
    extract_batch_spike_data_from_pkl(
        job_idx_xr=job_idx_xr, dirpath_data=dirpath_pkl,
        dirpath_spikes=dirpath_spikes, fname_data_templ="data_{job:05d}_*.pkl",
        fname_spikes_templ="spikes_{job:05d}.npz", pop_names=pops_used,
        t_limits=tuple(t_limits), combine=True, subtract_t0=False,
        ms=False, skip_missing=True)
    
    # Step 2: Collect rates from spike files
    print(f"Collecting rates...")
    rates_cache_path = dirpath_cache / f'rates_dt_{dt_bin}_tau_{tau_smooth}_t_{t_limits[0]}_{t_limits[1]}.nc'
    rates_xr = collect_batch_rates_from_spike_data(
        job_idx_xr=job_idx_xr, dirpath_data=dirpath_spikes,
        fname_templ="spikes_{job:05d}.npz", t_limits=tuple(t_limits),
        dt_bin=dt_bin, tau_smooth=tau_smooth, cache_path=rates_cache_path,
        lazy=lazy, load=load, chunks=rate_chunks,
        open_kwargs={"chunks": rate_chunks} if rate_chunks else {},
        skip_missing=True, overwrite=True)
    
    print(f"Done: {rates_cache_path}")
    print(f"Spikes: {dirpath_spikes}")
    print(f"Shape: {dict(rates_xr.sizes)}")
    return rates_xr


if __name__ == '__main__':
    # ===== Configure parameters here =====
    MODE = 'direct'  # 'direct' or 'spikes'
    
    EXP_LABEL = (
        'batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/'
        'exp_pre_L2_post_L2_nseed_5_npre_5_t_5.0_20.0_tri_t0_5000_T_7500_rmax_50_ictrl_wmult_0.25_ee_0.5'
    )
    CFG_PARAM_FIELDS = {'pop_pre': 'pop_pre', 'seed': 'seed_main'}
    
    spike_t_limits = (1, None)  # (start_sec, end_sec) - None uses full duration
    dt_bin = 2e-3  # Rate binning in seconds
    tau_smooth = 10e-3  # Smoothing time constant in seconds
    rate_chunks = {'pop_pre': 1, 'seed': 1}  # Chunk sizes for NetCDF
    
    lazy = True  # Use lazy/incremental writing (recommended)
    load = False  # Keep as dask arrays (recommended)
    
    # ===== Run extraction =====
    if MODE == 'direct':
        rates_xr = extract_rates_direct(
            exp_label=EXP_LABEL,
            cfg_param_fields=CFG_PARAM_FIELDS,
            spike_t_limits=spike_t_limits,
            dt_bin=dt_bin,
            tau_smooth=tau_smooth,
            rate_chunks=rate_chunks,
            lazy=lazy,
            load=load,
        )
    elif MODE == 'spikes':
        rates_xr = extract_rates_via_spikes(
            exp_label=EXP_LABEL,
            cfg_param_fields=CFG_PARAM_FIELDS,
            spike_t_limits=spike_t_limits,
            dt_bin=dt_bin,
            tau_smooth=tau_smooth,
            rate_chunks=rate_chunks,
            lazy=lazy,
            load=load,
        )
    else:
        raise ValueError(f"MODE must be 'direct' or 'spikes', got: {MODE}")
