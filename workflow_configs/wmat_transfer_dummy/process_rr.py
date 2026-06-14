from pathlib import Path
import sys

import numpy as np
import xarray as xr


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_xr
from sim_data_analyzer.xr_io import save_xr
from workflow_utils import build_job_index, load_job_records


def fit_sinusoid_fixed_freq(rr, osc_f, osc_t0, harmonic=1):
    """Fit one fixed-frequency harmonic and a constant baseline."""
    tt = np.asarray(rr.time.values, dtype=float)
    yy = np.asarray(rr.values, dtype=float)
    mask = tt >= float(osc_t0)
    tt = tt[mask]
    yy = yy[mask]
    phase = (
        2 * np.pi * float(harmonic) * float(osc_f) *
        (tt - float(osc_t0))
    )
    design = np.column_stack([
        np.sin(phase),
        np.cos(phase),
        np.ones_like(phase),
    ])
    coef, _, _, _ = np.linalg.lstsq(design, yy, rcond=None)
    a_sin, a_cos, offset = coef
    z_out = a_cos - 1j * a_sin
    return z_out, float(offset)


def _fit_job_transfer(rates, osc_f, osc_amp, osc_t0, harmonics):
    """Fit all output populations and requested harmonics for one job."""
    pop_names = [
        str(pop)
        for pop in rates.coords['pop'].values
        if 'frz' not in str(pop)
    ]
    shape = (len(pop_names), len(harmonics))
    response = np.full(shape, np.nan + 1j * np.nan)
    transfer = np.full(shape, np.nan + 1j * np.nan)
    baseline = np.full(len(pop_names), np.nan)
    z_in = -1j * float(osc_amp)

    # Fit each response independently
    for n_pop, pop in enumerate(pop_names):
        rr = rates.sel(pop=pop)
        for n_harmonic, harmonic in enumerate(harmonics):
            z_out, offset = fit_sinusoid_fixed_freq(
                rr,
                osc_f,
                osc_t0,
                harmonic=harmonic,
            )
            response[n_pop, n_harmonic] = z_out
            if harmonic == 1:
                baseline[n_pop] = offset
            if z_in != 0:
                transfer[n_pop, n_harmonic] = z_out / z_in
    return pop_names, response, transfer, baseline


def fit_transfer_dataset(rates_xr, harmonics):
    """Fit transfer coefficients over every batch coordinate."""
    batch_dims = [
        dim
        for dim in rates_xr.dims
        if dim not in {'pop', 'time'}
    ]
    batch_shape = tuple(rates_xr.sizes[dim] for dim in batch_dims)
    first_sel = {
        dim: rates_xr.coords[dim].values[0]
        for dim in batch_dims
    }
    first_rates = rates_xr.sel(first_sel)
    pop_names, _, _, _ = _fit_job_transfer(
        first_rates,
        first_sel['osc_f'],
        first_sel['osc_amp'],
        float(first_rates.attrs['OSC_T0']) / 1000,
        harmonics,
    )
    fit_shape = batch_shape + (len(pop_names), len(harmonics))
    response = np.full(fit_shape, np.nan + 1j * np.nan)
    transfer = np.full(fit_shape, np.nan + 1j * np.nan)
    baseline = np.full(batch_shape + (len(pop_names),), np.nan)

    # Iterate the batch grid while retaining labeled output dimensions
    for index in np.ndindex(batch_shape):
        selection = {
            dim: rates_xr.coords[dim].values[index[n]]
            for n, dim in enumerate(batch_dims)
        }
        rates = rates_xr.sel(selection)
        osc_t0 = float(rates.attrs['OSC_T0']) / 1000
        _, z_out, coeff, offset = _fit_job_transfer(
            rates,
            selection['osc_f'],
            selection['osc_amp'],
            osc_t0,
            harmonics,
        )
        response[index] = z_out
        transfer[index] = coeff
        baseline[index] = offset

    coords = {
        dim: rates_xr.coords[dim].values
        for dim in batch_dims
    }
    coords['pop_post'] = pop_names
    coords['harmonic'] = harmonics
    harmonic_dims = batch_dims + ['pop_post', 'harmonic']
    baseline_dims = batch_dims + ['pop_post']
    return xr.Dataset(
        {
            'response_real': (harmonic_dims, response.real),
            'response_imag': (harmonic_dims, response.imag),
            'transfer_real': (harmonic_dims, transfer.real),
            'transfer_imag': (harmonic_dims, transfer.imag),
            'transfer_magnitude': (harmonic_dims, np.abs(transfer)),
            'transfer_phase': (harmonic_dims, np.angle(transfer)),
            'baseline_rate': (baseline_dims, baseline),
        },
        coords=coords,
    )


def load_stage_result(stage_dir, stage_spec, harmonics):
    """Load the persisted transfer matrix for stage resume."""
    fpath = Path(stage_dir) / 'processed' / 'transfer_matrix.nc'
    with xr.open_dataset(fpath) as transfer_ds:
        return transfer_ds.load()


def process_stage(stage_dir, stage_spec, harmonics):
    """Collect rate dynamics and save canonical transfer artifacts."""
    stage_dir = Path(stage_dir)
    dirpath_processed = stage_dir / 'processed'
    dirpath_processed.mkdir(parents=True, exist_ok=True)
    records = load_job_records(stage_dir)
    job_idx_xr = build_job_index(records, stage_spec['batch_params'])

    # Collect per-job rate vectors into one labeled batch array
    fpath_rates = dirpath_processed / 'combined_rates.nc'
    rates_xr = collect_batch_xr(
        job_idx_xr,
        stage_dir / 'sim_results' / 'rvec_xr',
        fname_templ='rvec_{job:05d}_*.nc',
        data_type='dataarray',
        cache_path=fpath_rates,
        lazy=False,
        load=True,
        skip_missing=False,
        overwrite=True,
    )

    # Save real-valued NetCDF fields and a flattened inspection table
    transfer_ds = fit_transfer_dataset(rates_xr, list(harmonics))
    transfer_ds.attrs['stage_spec_hash'] = stage_spec['stage_spec_hash']
    fpath_netcdf = dirpath_processed / 'transfer_matrix.nc'
    fpath_csv = dirpath_processed / 'transfer_matrix.csv'
    save_xr(transfer_ds, fpath_netcdf)
    transfer_ds.to_dataframe().reset_index().to_csv(
        fpath_csv,
        index=False,
    )
    outputs = [
        'processed/combined_rates.nc',
        'processed/transfer_matrix.nc',
        'processed/transfer_matrix.csv',
    ]
    return transfer_ds, outputs
