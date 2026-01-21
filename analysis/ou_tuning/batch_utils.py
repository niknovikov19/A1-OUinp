import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def _extract_nested(x: dict, key_seq: str):
    keys = key_seq.split('.')
    val = x
    for key in keys:
        val = val[key]
    return val

def extract_batch_params_to_xr(
        dirpath_exp: str | Path,
        cfg_param_fields: dict[str, str],
        fname_cfg_templ: str = '*_cfg.json',
        job_pos_in_fname: int = -2,
        ) -> xr.DataArray:
    
    dirpath_exp = Path(dirpath_exp)
    cfg_files = list(dirpath_exp.rglob(fname_cfg_templ))

    #params_by_job_id = {}
    job_idx_by_params = []

    # Read params from cfg files
    for fpath_cfg in cfg_files:
        # Read cfg file
        with open(fpath_cfg) as f:
            cfg = json.load(f)
        
        # Read values of batch params from cfg
        params = {
            par_name: _extract_nested(cfg['simConfig'], field_seq)
            for par_name, field_seq in cfg_param_fields.items()
        }

        # Params -> job ID
        par_lst = [params[par_name] for par_name in cfg_param_fields]
        job_id = int(fpath_cfg.stem.split('_')[job_pos_in_fname])
        job_idx_by_params.append(par_lst + [job_id])
    
    # Build DataFrame
    dims = list(cfg_param_fields.keys())
    job_idx_by_params = pd.DataFrame(
        data=job_idx_by_params,
        columns=dims + ['job_id']
    )

    # Sort coordinates for each dimension
    for dim in dims:
        job_idx_by_params[dim] = pd.Categorical(
            job_idx_by_params[dim],
            categories=sorted(job_idx_by_params[dim].unique()),
            ordered=True
        )

    # Create xarray of job_idx with batch params as dims
    job_idx_xr = job_idx_by_params.set_index(dims).sort_index().to_xarray()['job_id']
    return job_idx_xr


def _get_fpath_by_templ(dirpath: Path, fname_templ: str) -> str:
    files = list(dirpath.glob(fname_templ))
    if len(files) != 1:
        print(f'Path for search: {str(dirpath)}')
        print(f'Name template: {fname_templ}')
        raise RuntimeError('Should be exactly one filename match')
    return files[0]


def collect_batch_xr_data(
        job_idx_xr: xr.DataArray,
        dirpath_data: str | Path,
        fname_data_templ: str = 'rates_{job:05d}_*.nc'
        ) -> xr.DataArray:
    """Merges xarrays resulting from batch jobs to one large xarray. """
    
    dirpath_data = Path(dirpath_data)
    
    # Read one data file to get the coords
    fname_data = fname_data_templ.format(job=0)
    fpath_data = _get_fpath_by_templ(dirpath_data, fname_data)   # resolve * in fname_data
    try:
        X_ = xr.open_dataarray(fpath_data)
        is_dataset = False
    except (ValueError, OSError):
        X_ = xr.open_dataset(fpath_data)
        is_dataset = True
    data_dims, data_coords = X_.dims, X_.coords

    # Build combined dims and coords
    job_dims = list(job_idx_xr.dims)
    job_coords = job_idx_xr.coords
    stacked_dims = job_dims + list(data_dims)
    stacked_shape = ([job_idx_xr.sizes[d] for d in job_dims] + 
                     [X_.sizes[d] for d in data_dims])
    combined_coords = xr.merge([job_coords.to_dataset(),
                                data_coords.to_dataset()]).coords
    
    # Create empty container matching the detected type
    if is_dataset:
        data_vars = {
            var: (stacked_dims, np.full(stacked_shape, np.nan))
            for var in X_.data_vars
        }
        X = xr.Dataset(data_vars, coords=combined_coords)
    else:
        X = xr.DataArray(
            np.full(stacked_shape, np.nan),
            dims=stacked_dims,
            coords=combined_coords
        )

    # Iterate over all cells in job_idx_xr
    for idx in np.ndindex(job_idx_xr.shape):
        job_id = job_idx_xr.values[idx]
        
        # Generate file path for the job data
        fname_data = fname_data_templ.format(job=job_id)
        fpath_data = _get_fpath_by_templ(dirpath_data, fname_data)

        sel = {dim: idx[i] for i, dim in enumerate(job_dims)}

        # Load data and assign it to the corresponding slice in X
        if is_dataset:
            X_ = xr.open_dataset(fpath_data)
            for var in X_.data_vars:
                X[var][sel] = X_[var]
        else:
            X_ = xr.open_dataarray(fpath_data)
            X[sel] = X_
        
    return X


if __name__ == '__main__':

    dirpath_exp = Path(
    '/ddn/niknovikov19/repo/A1_OUinp/exp_results/batch_i_ou/batch_i_ou_IT5B_rx_switch_var_oumean'
    )

    cfg_param_fields = {
        'ou_ramp_offset': 'ou_ramp_offset',
        'rx': 'bkg_spike_inputs.IT5B.r',
        'wx': 'bkg_spike_inputs.IT5B.w'
    }
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_exp / 'cfg',
        cfg_param_fields,
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1
    )

    R = collect_batch_xr_data(
        job_idx_xr, dirpath_exp / 'rates', 'rates_{job:05d}_*.nc'
    )
