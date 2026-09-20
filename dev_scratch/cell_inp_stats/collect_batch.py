import sys
from pathlib import Path


# Set import paths
DIR_HERE = Path(__file__).resolve().parent
DIR_REPO = DIR_HERE.parents[1]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_xr, extract_batch_params_to_xr


DIRPATH_BATCH = DIR_HERE / 'test_data' / 'batch'
DIRPATH_CFG = DIRPATH_BATCH / 'cfg'
DIRPATH_DATA = DIRPATH_BATCH / 'cell_inp_stats'
FPATH_OUT = DIRPATH_BATCH / 'cell_inp_stats_xr_combined.nc'


def collect_cell_inp_stats_batch(dirpath_cfg=DIRPATH_CFG,
                                 dirpath_data=DIRPATH_DATA,
                                 fpath_out=FPATH_OUT):
    """Collect per-job cell-input datasets into one seed-indexed NetCDF file. """
    job_idx_xr = extract_batch_params_to_xr(
        dirpath_cfg,
        cfg_param_fields={'seed_main': 'seed_main'},
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1,
    )

    # Delegate batch stacking to sim_data_analyzer
    dataset = collect_batch_xr(
        job_idx_xr=job_idx_xr,
        dirpath_data=dirpath_data,
        fname_templ='cell_inp_stats_{job:05d}_*.nc',
        data_type='dataset',
        cache_path=None,
        lazy=False,
        load=False,
        open_kwargs={'engine': 'scipy'},
        skip_missing=False,
        overwrite=True,
    )
    Path(fpath_out).parent.mkdir(parents=True, exist_ok=True)
    dataset.to_netcdf(fpath_out)
    return dataset


def main():
    """Collect the test batch and print the output schema. """
    dataset = collect_cell_inp_stats_batch()
    print(f'Saved {FPATH_OUT}')
    print(f'Sizes: {dict(dataset.sizes)}')
    dataset.close()


if __name__ == '__main__':
    main()
