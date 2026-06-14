import itertools
from pathlib import Path
import sys

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch
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


def evaluate_fitted_sinusoid(time, z_out, offset, osc_f, osc_t0,
                             harmonic=1):
    """Evaluate one fitted fixed-frequency sinusoid."""
    time = np.asarray(time, dtype=float)
    phase = (
        2 * np.pi * float(harmonic) * float(osc_f) *
        (time - float(osc_t0))
    )
    return (
        -z_out.imag * np.sin(phase) +
        z_out.real * np.cos(phase) +
        float(offset)
    )


def calc_welch_psd(rr, osc_t0, window_sec=1, fmax=50):
    """Calculate post-oscillation Welch power spectral density."""
    time = np.asarray(rr.time.values, dtype=float)
    values = np.asarray(rr.values, dtype=float)
    mask = time >= float(osc_t0)
    time = time[mask]
    values = values[mask]
    if len(time) < 2:
        raise ValueError('PSD requires at least two post-oscillation samples')

    # Derive the sampling rate and cap the requested window at trace length
    fs = 1 / float(np.median(np.diff(time)))
    nperseg = min(len(values), max(2, round(float(window_sec) * fs)))
    noverlap = nperseg // 2
    freq, power = welch(
        values,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
    )
    freq_mask = freq <= float(fmax)
    return freq[freq_mask], power[freq_mask]


def _get_active_pops(rates):
    """Return active output populations in stored order."""
    return [
        str(pop)
        for pop in rates.coords['pop'].values
        if 'frz' not in str(pop)
    ]


def _iter_selections(data, dims):
    """Yield coordinate selections over the requested dimensions."""
    values = [
        data.coords[dim].values
        for dim in dims
    ]
    for combination in itertools.product(*values):
        yield dict(zip(dims, combination))


def _format_coord(value):
    """Format one coordinate value for a compact filename."""
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)


def _selection_suffix(selection):
    """Format standard RR batch coordinates for filenames."""
    names = {
        'seed_main': 'seed',
        'pop_pre': 'pre',
        'osc_f': 'f',
        'osc_amp': 'amp',
    }
    return '_'.join(
        f'{names[name]}_{_format_coord(value)}'
        for name, value in selection.items()
    )


def _get_weight_title(stage_spec):
    """Format iteration and weight overrides for figure titles."""
    title = f'Iteration {stage_spec["iteration"]}'
    weights = stage_spec.get(
        'experiment_overrides',
        {},
    ).get('wmat_multipliers', [])
    if not weights:
        return title
    weight_text = ', '.join(
        f'{item["pre"]}->{item["post"]} x{item["mult"]:g}'
        for item in weights
    )
    return f'{title}; {weight_text}'


def _setup_axes(nplots, ncols=3, width=4.5, height=3.2):
    """Create a compact subplot grid and hide unused axes."""
    nrows = int(np.ceil(nplots / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(width * ncols, height * nrows),
        squeeze=False,
    )
    axes = axes.ravel()
    for ax in axes[nplots:]:
        ax.axis('off')
    return fig, axes


def _plot_rate_dynamics(rates_xr, dirpath_out, stage_spec, harmonic,
                        dpi):
    """Plot one input/output dynamics figure for every RR job."""
    dirpath_out.mkdir(parents=True, exist_ok=True)
    outputs = []
    dims = ['seed_main', 'pop_pre', 'osc_f', 'osc_amp']

    # Plot the driven frozen input and every active output in separate panels
    for selection in _iter_selections(rates_xr, dims):
        rates = rates_xr.sel(selection)
        pop_pre = str(selection['pop_pre'])
        pop_input = f'{pop_pre}frz'
        pop_names = [pop_input] + _get_active_pops(rates)
        missing = [
            pop
            for pop in pop_names
            if pop not in rates.coords['pop'].values
        ]
        if missing:
            raise ValueError(f'Missing dynamics populations: {missing}')

        fig, axes = _setup_axes(len(pop_names))
        osc_t0 = float(rates.attrs['OSC_T0']) / 1000
        osc_f = float(selection['osc_f'])
        for ax, pop in zip(axes, pop_names):
            rr = rates.sel(pop=pop)
            time = np.asarray(rr.time.values, dtype=float)
            z_out, offset = fit_sinusoid_fixed_freq(
                rr,
                osc_f,
                osc_t0,
                harmonic=harmonic,
            )
            fit_mask = time >= osc_t0
            fitted = evaluate_fitted_sinusoid(
                time[fit_mask],
                z_out,
                offset,
                osc_f,
                osc_t0,
                harmonic=harmonic,
            )
            ax.plot(time, rr.values, color='0.35', alpha=0.75)
            ax.plot(time[fit_mask], fitted, color='C1', lw=2)
            ax.axvline(osc_t0, color='0.6', ls=':')
            ax.set_title(pop)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Rate (Hz)')
            ax.grid(alpha=0.2)

        suffix = _selection_suffix(selection)
        fig.suptitle(
            f'Rate dynamics: {suffix}\n{_get_weight_title(stage_spec)}'
        )
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fpath = dirpath_out / f'rate_dynamics_{suffix}.png'
        fig.savefig(fpath, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        outputs.append(fpath)
    return outputs


def _select_transfer_matrix(transfer_ds, selection, harmonic):
    """Select magnitude and phase as pop-post by pop-pre matrices."""
    selected = transfer_ds.sel(
        selection,
    ).sel(harmonic=harmonic)
    magnitude = selected['transfer_magnitude'].transpose(
        'pop_post',
        'pop_pre',
    )
    phase = selected['transfer_phase'].transpose(
        'pop_post',
        'pop_pre',
    )
    return magnitude, phase


def _plot_transfer_matrices(transfer_ds, dirpath_out, stage_spec,
                            harmonic, dpi):
    """Plot first-harmonic transfer magnitude and phase matrices."""
    if harmonic not in transfer_ds.coords['harmonic'].values:
        raise ValueError(f'Transfer harmonic is unavailable: {harmonic}')
    dirpath_out.mkdir(parents=True, exist_ok=True)
    outputs = []
    dims = ['seed_main', 'osc_f', 'osc_amp']

    # Plot one full population matrix for every non-population coordinate
    for selection in _iter_selections(transfer_ds, dims):
        magnitude, phase = _select_transfer_matrix(
            transfer_ds,
            selection,
            harmonic,
        )
        pop_pre = [str(pop) for pop in magnitude.pop_pre.values]
        pop_post = [str(pop) for pop in magnitude.pop_post.values]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

        image_mag = axes[0].imshow(
            magnitude.values,
            aspect='auto',
            origin='upper',
            cmap='viridis',
        )
        axes[0].set_title('Magnitude')
        fig.colorbar(image_mag, ax=axes[0], shrink=0.85)

        image_phase = axes[1].imshow(
            phase.values,
            aspect='auto',
            origin='upper',
            cmap='twilight',
            vmin=-np.pi,
            vmax=np.pi,
        )
        axes[1].set_title('Phase (rad)')
        fig.colorbar(image_phase, ax=axes[1], shrink=0.85)

        # Use the same labeled population axes on both panels
        for ax in axes:
            ax.set_xticks(np.arange(len(pop_pre)), labels=pop_pre)
            ax.set_yticks(np.arange(len(pop_post)), labels=pop_post)
            ax.set_xlabel('pop_pre')
            ax.set_ylabel('pop_post')
            ax.tick_params(axis='x', rotation=45)

        suffix = _selection_suffix(selection)
        fig.suptitle(
            f'Transfer harmonic {harmonic}: {suffix}\n'
            f'{_get_weight_title(stage_spec)}'
        )
        fig.tight_layout(rect=(0, 0, 1, 0.9))
        fpath = dirpath_out / f'transfer_matrix_{suffix}.png'
        fig.savefig(fpath, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        outputs.append(fpath)
    return outputs


def _plot_psd(rates_xr, dirpath_out, stage_spec, fmax, window_sec,
              dpi):
    """Plot post-oscillation PSDs grouped by RR drive settings."""
    dirpath_out.mkdir(parents=True, exist_ok=True)
    outputs = []
    group_dims = ['seed_main', 'osc_f', 'osc_amp']

    # Use one subplot per driven population within each seed/frequency/amplitude
    for group_selection in _iter_selections(rates_xr, group_dims):
        rates_group = rates_xr.sel(group_selection)
        pop_pre_values = [
            str(pop)
            for pop in rates_group.coords['pop_pre'].values
        ]
        fig, axes = _setup_axes(len(pop_pre_values))
        handles = None
        labels = None
        for ax, pop_pre in zip(axes, pop_pre_values):
            rates = rates_group.sel(pop_pre=pop_pre)
            osc_t0 = float(rates.attrs['OSC_T0']) / 1000
            active_pops = _get_active_pops(rates)
            for pop in active_pops:
                freq, power = calc_welch_psd(
                    rates.sel(pop=pop),
                    osc_t0,
                    window_sec=window_sec,
                    fmax=fmax,
                )
                ax.semilogy(freq, power, label=pop)

            pop_input = f'{pop_pre}frz'
            if pop_input not in rates.coords['pop'].values:
                raise ValueError(f'Missing driven input population: {pop_input}')
            freq, power = calc_welch_psd(
                rates.sel(pop=pop_input),
                osc_t0,
                window_sec=window_sec,
                fmax=fmax,
            )
            ax.semilogy(
                freq,
                power,
                color='black',
                ls='--',
                label=pop_input,
            )
            ax.set_title(f'pop_pre={pop_pre}')
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel('PSD')
            ax.set_xlim(0, fmax)
            ax.grid(alpha=0.2)
            if handles is None:
                handles, labels = ax.get_legend_handles_labels()

        suffix = _selection_suffix(group_selection)
        fig.legend(
            handles,
            labels,
            loc='lower center',
            ncol=3,
        )
        fig.suptitle(
            f'Post-oscillation PSD: {suffix}\n'
            f'{_get_weight_title(stage_spec)}'
        )
        fig.tight_layout(rect=(0, 0.08, 1, 0.93))
        fpath = dirpath_out / f'psd_{suffix}.png'
        fig.savefig(fpath, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        outputs.append(fpath)
    return outputs


def _create_diagnostic_plots(rates_xr, transfer_ds, stage_dir,
                             stage_spec, plot_rate_dynamics,
                             plot_transfer_matrix, plot_psd,
                             plot_harmonic, psd_fmax,
                             psd_window_sec, plot_dpi):
    """Create configured RR diagnostic plots and return their paths."""
    dirpath_processed = Path(stage_dir) / 'processed'
    fpaths = []
    if plot_rate_dynamics:
        fpaths.extend(_plot_rate_dynamics(
            rates_xr,
            dirpath_processed / 'rate_dynamics',
            stage_spec,
            plot_harmonic,
            plot_dpi,
        ))
    if plot_transfer_matrix:
        fpaths.extend(_plot_transfer_matrices(
            transfer_ds,
            dirpath_processed / 'transfer_matrices',
            stage_spec,
            plot_harmonic,
            plot_dpi,
        ))
    if plot_psd:
        fpaths.extend(_plot_psd(
            rates_xr,
            dirpath_processed / 'psd',
            stage_spec,
            psd_fmax,
            psd_window_sec,
            plot_dpi,
        ))
    return [
        fpath.relative_to(stage_dir).as_posix()
        for fpath in fpaths
    ]


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


def load_stage_result(stage_dir, stage_spec, harmonics,
                      plot_rate_dynamics=False,
                      plot_transfer_matrix=False, plot_psd=False,
                      plot_harmonic=1, psd_fmax=50,
                      psd_window_sec=1, plot_dpi=200):
    """Load the persisted transfer matrix for stage resume."""
    fpath = Path(stage_dir) / 'processed' / 'transfer_matrix.nc'
    with xr.open_dataset(fpath) as transfer_ds:
        return transfer_ds.load()


def process_stage(stage_dir, stage_spec, harmonics,
                  plot_rate_dynamics=False,
                  plot_transfer_matrix=False, plot_psd=False,
                  plot_harmonic=1, psd_fmax=50,
                  psd_window_sec=1, plot_dpi=200):
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

    # Add optional plots to the durable processing output contract
    outputs.extend(_create_diagnostic_plots(
        rates_xr,
        transfer_ds,
        stage_dir,
        stage_spec,
        plot_rate_dynamics,
        plot_transfer_matrix,
        plot_psd,
        plot_harmonic,
        psd_fmax,
        psd_window_sec,
        plot_dpi,
    ))
    return transfer_ds, outputs
