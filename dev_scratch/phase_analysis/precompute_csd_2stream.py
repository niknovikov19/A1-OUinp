import os
import sys
from pathlib import Path


# Set import paths before importing external helpers
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
DIR_THIS = Path(__file__).resolve().parent
for path in (DIR_REPO, DIR_EXTERNAL, DIR_THIS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


# Reuse the active two-stream analysis target to avoid config drift
import run_2stream as analysis_cfg

EXP_NAME = analysis_cfg.EXP_NAME
DIRPATH_ARTIFACT = analysis_cfg.DIRPATH_ARTIFACT
os.environ.setdefault('MPLCONFIGDIR', str(DIR_THIS / 'artifacts' / EXP_NAME / 'mpl_cache'))

import xarray as xr

from sim_data_analyzer.xr_diff import calc_xr_csd


LFP_PATH = DIRPATH_ARTIFACT / 'lfp_xr_combined.nc'
CSD_PATH = DIRPATH_ARTIFACT / 'csd_xr_combined.nc'
Y_DIM = 'y'
OVERWRITE = 1
COMPUTE = 0


def run():
    """Precompute CSD from the combined two-stream LFP xarray."""
    if CSD_PATH.exists() and not OVERWRITE:
        print(f'Exists: {CSD_PATH}', flush=True)
        return CSD_PATH
    if not LFP_PATH.exists():
        raise FileNotFoundError(f'Missing LFP input: {LFP_PATH}')

    # Load the combined LFP xarray and derive CSD along depth
    X_lfp = xr.open_dataarray(LFP_PATH)
    try:
        if Y_DIM not in X_lfp.dims:
            raise ValueError(f'Missing depth dimension {Y_DIM!r}')
        X_csd = calc_xr_csd(X_lfp, ydim=Y_DIM, compute=bool(COMPUTE))
        X_csd.attrs.update({
            'source_file': str(LFP_PATH),
            'signal_kind': 'csd',
            'csd_ydim': Y_DIM,
        })

        # Save CSD beside LFP so downstream analysis can stay precomputed-only
        CSD_PATH.parent.mkdir(parents=True, exist_ok=True)
        X_csd.to_netcdf(CSD_PATH)
        X_csd.close()
    finally:
        X_lfp.close()

    print(f'Saved: {CSD_PATH}', flush=True)
    return CSD_PATH


if __name__ == '__main__':
    run()
