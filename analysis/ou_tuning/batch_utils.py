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


def collect_batch_json_data(
        job_idx_xr: xr.DataArray,
        dirpath_data: str | Path,
        var_mappings: dict[str, str],
        fname_data_templ: str = 'result_{job:05d}_*.json',
        extra_dims: dict[str, list] | None = None,
        extra_coords: dict[str, tuple[str, list]] | None = None,
        skip_missing: bool = True
        ) -> xr.Dataset:
    """
    Collects batch results from JSON files into an xarray Dataset.
    
    Parameters
    ----------
    job_idx_xr : xr.DataArray
        DataArray mapping parameter grid coordinates to job IDs.
        Created by extract_batch_params_to_xr().
    dirpath_data : str | Path
        Directory containing the JSON result files.
    var_mappings : dict[str, str]
        Mapping from xarray variable names to JSON keys.
        Example: {'rate': 'rates', 'cv': 'cvs'}
        Supports nested keys with dot notation: {'rate': 'simData.popRates'}
    fname_data_templ : str, optional
        Template for result filenames with {job} placeholder.
        Default: 'result_{job:05d}_*.json'
    extra_dims : dict[str, list], optional
        Additional dimensions to add beyond job parameters.
        Example: {'pop': ['IT2', 'IT5A', 'IT5B']}
    extra_coords : dict[str, tuple[str, list]], optional
        Additional coordinates to add to specific dimensions.
        Example: {'drxe_pos': ('drxe', drxe_vals), 'rxi_pos': ('rxi', rxi_vals)}
        Keys are dimension names, values are (coord_name, coord_values) tuples.
    skip_missing : bool, optional
        If True, skip jobs with missing files. If False, raise error.
        Default: True
    
    Returns
    -------
    xr.Dataset
        Dataset with all batch results organized by parameter space dimensions.
    
    Examples
    --------
    Basic usage with population dimension:
    
    >>> job_idx_xr = batch_utils.extract_batch_params_to_xr(
    ...     'exp_results/cfg',
    ...     cfg_param_fields={'rxe': 'rxe'}
    ... )
    >>> X = batch_utils.collect_batch_json_data(
    ...     job_idx_xr,
    ...     'exp_results/results',
    ...     var_mappings={'rate': 'rates', 'cv': 'cvs'},
    ...     extra_dims={'pop': ['IT2', 'IT6frz']}
    ... )
    
    2D batch with region-specific coordinates:
    
    >>> job_idx_xr = batch_utils.extract_batch_params_to_xr(
    ...     'exp_results/cfg',
    ...     cfg_param_fields={'drxe_pos': 'drxe_num', 'rxi_pos': 'rxi_num'}
    ... )
    >>> drxe_vals = np.linspace(-10000, 0, 20)
    >>> rxi_vals = np.linspace(5000, 15000, 20)
    >>> X = batch_utils.collect_batch_json_data(
    ...     job_idx_xr,
    ...     'exp_results/results',
    ...     var_mappings={'rate': 'rates', 'vavg': 'v_thresh_avg'},
    ...     extra_dims={'pop': ['IT5A', 'IT5B']},
    ...     extra_coords={
    ...         'drxe_pos': ('drxe', drxe_vals),
    ...         'rxi_pos': ('rxi', rxi_vals)
    ...     }
    ... )
    >>> # Swap to physical coordinates
    >>> X = X.swap_dims({'drxe_pos': 'drxe', 'rxi_pos': 'rxi'})
    """
    dirpath_data = Path(dirpath_data)
    
    # Build dimensions and coordinates
    job_dims = list(job_idx_xr.dims)
    all_dims = job_dims.copy()
    all_coords = dict(job_idx_xr.coords)
    
    # Add extra dimensions if specified
    if extra_dims:
        for dim_name, dim_values in extra_dims.items():
            all_dims.append(dim_name)
            all_coords[dim_name] = dim_values
    
    # Add extra coordinates if specified
    if extra_coords:
        for dim_name, (coord_name, coord_values) in extra_coords.items():
            if dim_name not in all_dims:
                raise ValueError(f"Dimension '{dim_name}' not found. "
                                 f"Available dims: {all_dims}")
            all_coords[coord_name] = (dim_name, coord_values)
    
    # Determine array shape
    shape = [job_idx_xr.sizes[d] for d in job_dims]
    if extra_dims:
        shape.extend(len(v) for v in extra_dims.values())
    
    # Create empty Dataset
    data_vars = {
        var_name: (all_dims, np.full(shape, np.nan, dtype=np.float64))
        for var_name in var_mappings.keys()
    }
    X = xr.Dataset(data_vars, coords=all_coords)
    
    # Iterate over all parameter combinations
    n_loaded = 0
    n_skipped = 0
    for idx in np.ndindex(job_idx_xr.shape):
        job_id = job_idx_xr.values[idx]
        
        # Skip NaN job IDs (sparse parameter grids)
        if np.isnan(job_id):
            n_skipped += 1
            continue
        
        job_id = int(job_id)
        sel = {dim: idx[i] for i, dim in enumerate(job_dims)}
        
        # Generate file path
        fname_data = fname_data_templ.format(job=job_id)
        try:
            fpath_data = _get_fpath_by_templ(dirpath_data, fname_data)
        except RuntimeError:
            if skip_missing:
                n_skipped += 1
                continue
            else:
                raise
        
        # Load JSON data
        with open(fpath_data, 'r') as fid:
            result_data = json.load(fid)
        
        # Extract and assign data for each variable
        for var_name, json_key in var_mappings.items():
            # Extract nested value from JSON
            json_value = _extract_nested(result_data, json_key)
            
            # Handle different data structures
            if extra_dims:
                # If we have extra dimensions (e.g., populations),
                # assume json_value is a dict keyed by those dimension values
                for extra_dim_name, extra_dim_values in extra_dims.items():
                    for extra_dim_val in extra_dim_values:
                        if extra_dim_val in json_value:
                            extra_sel = {extra_dim_name: extra_dim_val}
                            combined_sel = {**sel, **extra_sel}
                            X[var_name].loc[combined_sel] = json_value[extra_dim_val]
            else:
                # Simple case: direct assignment
                X[var_name][sel] = json_value
        
        n_loaded += 1
    
    print(f"Loaded {n_loaded} jobs, skipped {n_skipped}")
    
    return X



if __name__ == '__main__':

    dirpath_exp = Path(
        '/ddn/niknovikov19/repo/A1_OUinp/exp_results/batch_rxbkg_state1_mech1/'
        'net_newsec_ee_fade_var_rpop/exp_L2_ee_1_frz_IT2_0.1_10_PV2_1_50_npts_15_t_3.0_5.0_wmult_0.25_ee_0.5'
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

    #R = collect_batch_xr_data(
    #    job_idx_xr, dirpath_exp / 'rates', 'rates_{job:05d}_*.nc')


