import sys
from pathlib import Path


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[3]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_xr, extract_batch_params_to_xr


CFG_PARAM_FIELDS = {
    'seed_main': 'seed_main',
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


def collect_cell_inp_stats_from_nc(dirpath_exp,
                                    cfg_param_fields=CFG_PARAM_FIELDS,
                                    chunks=None, lazy=False, load=False,
                                    cache_path=None):
    """Collect per-job cell-input NetCDF files into one batch dataset."""
    dirpath_exp = Path(dirpath_exp)
    job_idx_xr = _get_job_idx_xr(dirpath_exp, cfg_param_fields)
    cache_path = cache_path or dirpath_exp / 'cell_inp_stats_xr_combined.nc'
    open_kwargs = dict(NC_OPEN_KWARGS)
    if chunks:
        open_kwargs['chunks'] = chunks

    # Delegate job-grid stacking to sim_data_analyzer
    print('\nNC: cell_inp_stats/*.nc -> combined cell-input statistics')
    print(f'Grid: {dict(job_idx_xr.sizes)}, {job_idx_xr.size} jobs')
    dataset = collect_batch_xr(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_exp / 'cell_inp_stats',
        fname_templ='cell_inp_stats_{job:05d}_*.nc',
        data_type='dataset',
        cache_path=cache_path if lazy else None,
        lazy=lazy,
        load=load,
        chunks=chunks,
        open_kwargs=open_kwargs,
        skip_missing=True,
        overwrite=True,
    )
    if not lazy:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.to_netcdf(cache_path)
    print(f'Done: {cache_path}')
    print(f'Shape: {dict(dataset.sizes)}')
    return dataset


def collect_batch_results(dirpath_exp, cfg_param_fields=CFG_PARAM_FIELDS,
                          chunks=None, lazy=False, load=False,
                          dirpath_out=None):
    """Collect all supported batch outputs."""
    cache_path = None
    if dirpath_out is not None:
        cache_path = Path(dirpath_out) / 'cell_inp_stats_xr_combined.nc'
    return {
        'cell_inp_stats': collect_cell_inp_stats_from_nc(
            dirpath_exp,
            cfg_param_fields=cfg_param_fields,
            chunks=chunks,
            lazy=lazy,
            load=load,
            cache_path=cache_path,
        )
    }
