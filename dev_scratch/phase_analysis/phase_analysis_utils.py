import csv
import json
import sys
from pathlib import Path


# Set import paths for repo-local and external helpers
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter1d

from analysis.phase_utils.spect_proc import (
    sinusoid_fit_coeff_freqs,
    sinusoid_fit_local,
    sinusoid_fit_power_freqs,
)
from sim_data_analyzer.batch_xr import iter_batch_jobs
from sim_data_analyzer.xr_signal import interp_time_outliers


JOB_ID_COORD = 'job_id'
TIME_DIM = 'time'
SEED_DIM = 'seed_main'
AMP_DIM = 'amp'
F_DIM = 'f'
TRACE_DIMS = {
    'rates': 'pop',
    'lfp': 'y',
    'csd': 'y',
}


def as_scalar(value):
    """Convert numpy scalar values to plain Python values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray) and value.size == 1:
        return value.item()
    return value


def format_value(value):
    """Format one value for labels and filenames."""
    value = as_scalar(value)
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)


def format_fname_piece(value):
    """Format one safe filename fragment."""
    text = format_value(value)
    return text.replace('.', 'p').replace('-', 'm').replace('/', '_')


def get_trace_dim(signal_kind):
    """Return the trace dimension for one signal kind."""
    if signal_kind not in TRACE_DIMS:
        raise ValueError(f'Unknown signal kind: {signal_kind}')
    return TRACE_DIMS[signal_kind]


def open_signal_xarray(input_path, signal_kind, trace_values=None,
                       interp_outliers=False, outlier_kwargs=None):
    """Open and optionally subset one combined signal xarray."""
    X = xr.open_dataarray(input_path)
    trace_dim = get_trace_dim(signal_kind)
    if TIME_DIM not in X.dims:
        raise ValueError(f'Missing time dimension {TIME_DIM!r}')
    if JOB_ID_COORD not in X.coords:
        raise ValueError(f'Missing coordinate {JOB_ID_COORD!r}')
    if trace_dim not in X.dims:
        raise ValueError(f'Missing trace dimension {trace_dim!r}')

    # Keep only requested traces before any expensive preprocessing
    if trace_values is not None:
        X = X.sel({trace_dim: list(trace_values)})

    # Delegate optional outlier interpolation to sim_data_analyzer
    if interp_outliers:
        kwargs = dict(outlier_kwargs or {})
        X = interp_time_outliers(X, time_dim=TIME_DIM, **kwargs)

    # Keep time last for 1D numpy kernels
    dim_order = [dim for dim in X.dims if dim != TIME_DIM] + [TIME_DIM]
    return X.transpose(*dim_order)


def get_jobs(X):
    """Return batch job descriptors from the xarray job coordinate."""
    return list(iter_batch_jobs(X.coords[JOB_ID_COORD]))


def get_trace_values(X, signal_kind):
    """Return available trace coordinate values."""
    trace_dim = get_trace_dim(signal_kind)
    return [as_scalar(value) for value in X.coords[trace_dim].values]


def get_target_f(job_sel, fallback_f):
    """Resolve the target frequency for one job selector."""
    if F_DIM in job_sel:
        return float(job_sel[F_DIM])
    return float(fallback_f)


def get_job_seed(job_sel):
    """Return a seed value for grouping and CSV output."""
    return as_scalar(job_sel.get(SEED_DIM, np.nan))


def get_job_amp(job_sel):
    """Return an amplitude value for grouping and CSV output."""
    return float(job_sel.get(AMP_DIM, np.nan))


def find_netpar_path(netpar_dir, job_id):
    """Find the netParams JSON file for one batch job."""
    matches = sorted(Path(netpar_dir).glob(f'netParams_{job_id:05d}_*.json'))
    if len(matches) != 1:
        raise FileNotFoundError(
            f'Expected one netParams file for job {job_id}, found {len(matches)}'
        )
    return matches[0]


def load_pulse_intervals(netpar_dir, job_id):
    """Load saved PulseSeq intervals in seconds."""
    netpar_path = find_netpar_path(netpar_dir, job_id)
    with open(netpar_path, 'r', encoding='utf-8') as fobj:
        netpar = json.load(fobj)

    # Read the saved VecStim pulse windows
    pop_params = netpar['net']['params']['popParams']
    pulse_seq = pop_params['PulseSeq']
    pulses = pulse_seq['params']['pulses']
    intervals = [
        (float(pulse['start']) / 1000, float(pulse['end']) / 1000)
        for pulse in pulses
    ]
    return np.asarray(intervals, dtype=float)


def get_pulse_pad_pair(pulse_pad):
    """Return pre/post pulse padding values."""
    if np.isscalar(pulse_pad):
        value = float(pulse_pad)
        return value, value

    values = np.asarray(pulse_pad, dtype=float).ravel()
    if values.size != 2:
        raise ValueError('pulse_pad should be a scalar or two values')
    if not np.all(np.isfinite(values)):
        raise ValueError('pulse_pad values should be finite')
    if np.any(values < 0):
        raise ValueError('pulse_pad values should be non-negative')
    return float(values[0]), float(values[1])


def mask_pulse_intervals(x, tt, pulse_intervals, pulse_pad, analysis_t0):
    """Mask pulse intervals and their surroundings."""
    pad_pre, pad_post = get_pulse_pad_pair(pulse_pad)
    x_masked = np.asarray(x, dtype=float).copy()
    x_masked[tt < analysis_t0] = np.nan
    for t_start, t_end in pulse_intervals:
        mask = (tt >= t_start - pad_pre) & (tt <= t_end + pad_post)
        x_masked[mask] = np.nan
    return x_masked


def filter_analysis_pulses(pulse_intervals, tt, analysis_t0):
    """Keep pulse starts inside the analyzed trace range."""
    pulse_starts = pulse_intervals[:, 0]
    keep = (
        (pulse_starts >= analysis_t0) &
        (pulse_starts >= tt[0]) &
        (pulse_starts <= tt[-1])
    )
    return pulse_starts[keep]


def get_fit_limits(target_f, power_f_margin):
    """Return an asymmetric frequency range around the target."""
    left_margin = min(float(power_f_margin), 0.5 * float(target_f))
    f_min = float(target_f) - left_margin
    f_max = float(target_f) + float(power_f_margin)
    return f_min, f_max


def make_blocks(tt, analysis_t0, block_duration, target_f):
    """Build nonoverlapping blocks with an integer number of periods."""
    period = 1 / float(target_f)
    n_periods = max(1, int(round(float(block_duration) / period)))
    block_len = n_periods * period
    t0 = max(float(analysis_t0), float(tt[0]))
    t1_max = float(tt[-1])

    # Step through complete nonoverlapping blocks only
    blocks = []
    block_idx = 0
    t_left = t0
    while t_left + block_len <= t1_max + 1e-12:
        blocks.append({
            'block_idx': block_idx,
            'block_t0': t_left,
            'block_t1': t_left + block_len,
        })
        block_idx += 1
        t_left += block_len
    return blocks


def compute_power_curve(x_masked, tt, target_f, params):
    """Compute a masked fitted-power spectrum."""
    f_min, f_max = get_fit_limits(target_f, params['power_f_margin'])
    f_center = 0.5 * (f_min + f_max)
    fband = 0.5 * (f_max - f_min)
    _, ff, power = sinusoid_fit_power_freqs(
        x_masked,
        tt,
        f_center,
        fband,
        params['power_df'],
        params['n_cycles'],
        overlap=params['power_overlap'],
        fit_intercept=bool(params['fit_intercept']),
        exclude_edges=bool(params['exclude_edges']),
        min_valid_mass_frac=params['min_valid_mass_frac'],
        rcond=params['fit_rcond'],
    )

    # Collapse sliding centers while keeping the frequency axis
    with np.errstate(invalid='ignore'):
        power_curve = np.nanmean(power, axis=1)
    return ff, power_curve


def compute_complex_spectrogram(x_masked, tt, target_f, params):
    """Compute a masked fitted complex spectrogram."""
    f_min, f_max = get_fit_limits(target_f, params['power_f_margin'])
    f_center = 0.5 * (f_min + f_max)
    fband = 0.5 * (f_max - f_min)
    t_fit, ff, coeff = sinusoid_fit_coeff_freqs(
        x_masked,
        tt,
        f_center,
        fband,
        params['power_df'],
        params['n_cycles'],
        overlap=params['power_overlap'],
        fit_intercept=bool(params['fit_intercept']),
        exclude_edges=bool(params['exclude_edges']),
        min_valid_mass_frac=params['min_valid_mass_frac'],
        rcond=params['fit_rcond'],
    )
    return t_fit, ff, coeff


def compute_band_metrics(ff, spectrum, target_f, broad_band,
                         target_half_width):
    """Compute band-power and concentration summaries."""
    ff = np.asarray(ff, dtype=float)
    spectrum = np.asarray(spectrum, dtype=float)
    valid = np.isfinite(ff) & np.isfinite(spectrum)
    broad = valid & (ff >= broad_band[0]) & (ff <= broad_band[1])
    target = valid & (ff >= target_f - target_half_width)
    target &= ff <= target_f + target_half_width

    # Integrate power on the available frequency grid
    p_band = np.nan
    p_target = np.nan
    concentration = np.nan
    centroid = np.nan
    width = np.nan
    if np.sum(broad) >= 2:
        p_band = float(np.trapz(spectrum[broad], ff[broad]))
        weighted_freq = float(np.trapz(ff[broad] * spectrum[broad], ff[broad]))
        if p_band > 0:
            centroid = weighted_freq / p_band
            var_num = np.trapz((ff[broad] - centroid) ** 2 * spectrum[broad],
                               ff[broad])
            width = float(np.sqrt(max(var_num / p_band, 0)))
    if np.sum(target) >= 2:
        p_target = float(np.trapz(spectrum[target], ff[target]))
    if np.isfinite(p_band) and p_band > 0 and np.isfinite(p_target):
        concentration = p_target / p_band

    return {
        'p_band': p_band,
        'p_target': p_target,
        'concentration': concentration,
        'centroid': centroid,
        'centroid_offset': centroid - target_f if np.isfinite(centroid) else np.nan,
        'width': width,
    }


def fit_event_coefficients(x_masked, tt, tt_pulse, target_f, params):
    """Fit pulse-start phases and complex coefficients."""
    phases = np.full(tt_pulse.shape, np.nan, dtype=float)
    coeffs = np.full(tt_pulse.shape, np.nan + 1j * np.nan, dtype=complex)
    for idx, t0 in enumerate(tt_pulse):
        fit = sinusoid_fit_local(
            x_masked,
            tt,
            t0,
            target_f,
            params['n_cycles'],
            fit_intercept=bool(params['fit_intercept']),
            exclude_edges=bool(params['exclude_edges']),
            min_valid_mass_frac=params['min_valid_mass_frac'],
            rcond=params['fit_rcond'],
        )
        phases[idx] = fit['phase']
        if np.isfinite(fit['a']) and np.isfinite(fit['b']):
            coeffs[idx] = fit['a'] - 1j * fit['b']
    return phases, coeffs


def phase_density(phases, n_bins, smooth_sigma):
    """Estimate a circular phase density."""
    bins = np.linspace(-np.pi, np.pi, n_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    phases = np.asarray(phases, dtype=float)
    phases = np.angle(np.exp(1j * phases[np.isfinite(phases)]))
    if phases.size == 0:
        return centers, np.full(centers.shape, np.nan)

    # Normalize smoothed counts as a density over radians
    counts, _ = np.histogram(phases, bins=bins)
    density = counts.astype(float)
    if smooth_sigma:
        density = gaussian_filter1d(density, smooth_sigma, mode='wrap')
    bin_width = float(bins[1] - bins[0])
    total = density.sum() * bin_width
    if total > 0:
        density = density / total
    return centers, density


def _round_csv_value(value, ndigits=4):
    """Round numeric CSV values for easier reading."""
    value = as_scalar(value)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return value
        return round(float(value), ndigits)
    return value


def write_csv(path, rows, ndigits=4):
    """Write rows to a CSV file with a stable union header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with open(path, 'w', encoding='utf-8', newline=''):
            return path

    # Keep insertion order from rows while allowing sparse dicts
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(path, 'w', encoding='utf-8', newline='') as fobj:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {
                key: _round_csv_value(value, ndigits=ndigits)
                for key, value in row.items()
            }
            writer.writerow(out)
    return path


def save_phase_events_nc(records, trace_dim, out_path, attrs):
    """Save pulse-time complex coefficients to a NetCDF dataset."""
    trace_values = sorted(set(record[trace_dim] for record in records))
    seed_values = sorted(set(record['seed_main'] for record in records))
    f_values = sorted(set(record['f'] for record in records))
    amp_values = sorted(set(record['amp'] for record in records))
    n_event = max(len(record['phases']) for record in records)
    shape = (
        len(trace_values),
        len(seed_values),
        len(f_values),
        len(amp_values),
        n_event,
    )
    phase = np.full(shape, np.nan, dtype=float)
    coeff_re = np.full(shape, np.nan, dtype=float)
    coeff_im = np.full(shape, np.nan, dtype=float)
    event_time = np.full(shape, np.nan, dtype=float)
    idx_maps = [
        {value: idx for idx, value in enumerate(values)}
        for values in (trace_values, seed_values, f_values, amp_values)
    ]

    # Fill event arrays with NaNs where events are absent or invalid
    for record in records:
        idx = (
            idx_maps[0][record[trace_dim]],
            idx_maps[1][record['seed_main']],
            idx_maps[2][record['f']],
            idx_maps[3][record['amp']],
        )
        n = len(record['phases'])
        coeffs = np.asarray(record['coeffs'], dtype=complex)
        phase[idx + (slice(0, n),)] = record['phases']
        coeff_re[idx + (slice(0, n),)] = coeffs.real
        coeff_im[idx + (slice(0, n),)] = coeffs.imag
        event_time[idx + (slice(0, n),)] = record['event_time']

    coords = {
        trace_dim: trace_values,
        'seed_main': seed_values,
        'f': f_values,
        'amp': amp_values,
        'event': np.arange(n_event),
    }
    dims = (trace_dim, 'seed_main', 'f', 'amp', 'event')
    ds = xr.Dataset(
        data_vars={
            'phase': (dims, phase),
            'coeff_re': (dims, coeff_re),
            'coeff_im': (dims, coeff_im),
            'event_time': (dims, event_time),
        },
        coords=coords,
        attrs=attrs,
    )
    ds['phase'].attrs.update({
        'long_name': 'Fitted phase at pulse starts',
        'units': 'rad',
    })
    ds['coeff_re'].attrs['long_name'] = 'Real part of z = a - i b'
    ds['coeff_im'].attrs['long_name'] = 'Imaginary part of z = a - i b'
    ds['event_time'].attrs.update({
        'long_name': 'Pulse start time',
        'units': 's',
    })
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out_path)
    ds.close()
    return out_path


def save_complex_spectrogram_nc(records, trace_dim, out_path, attrs):
    """Save fitted complex spectrograms to a NetCDF dataset."""
    trace_values = sorted(set(record[trace_dim] for record in records))
    seed_values = sorted(set(record['seed_main'] for record in records))
    f_values = sorted(set(record['f'] for record in records))
    amp_values = sorted(set(record['amp'] for record in records))
    n_freq = max(len(record['freq']) for record in records)
    n_time = max(len(record['t_fit']) for record in records)
    base_shape = (
        len(trace_values),
        len(seed_values),
        len(f_values),
        len(amp_values),
        n_freq,
        n_time,
    )
    coeff_re = np.full(base_shape, np.nan, dtype=float)
    coeff_im = np.full(base_shape, np.nan, dtype=float)
    freq = np.full((len(f_values), n_freq), np.nan, dtype=float)
    t_fit = np.full((len(f_values), n_time), np.nan, dtype=float)
    idx_maps = [
        {value: idx for idx, value in enumerate(values)}
        for values in (trace_values, seed_values, f_values, amp_values)
    ]
    f_idx = {value: idx for idx, value in enumerate(f_values)}

    # Fill spectrogram arrays and keep frequency/time grids self-describing
    for record in records:
        idx = (
            idx_maps[0][record[trace_dim]],
            idx_maps[1][record['seed_main']],
            idx_maps[2][record['f']],
            idx_maps[3][record['amp']],
        )
        coeff = np.asarray(record['coeff'], dtype=complex)
        nf, nt = coeff.shape
        coeff_re[idx + (slice(0, nf), slice(0, nt))] = coeff.real
        coeff_im[idx + (slice(0, nf), slice(0, nt))] = coeff.imag
        kf = f_idx[record['f']]
        freq[kf, :len(record['freq'])] = record['freq']
        t_fit[kf, :len(record['t_fit'])] = record['t_fit']

    coords = {
        trace_dim: trace_values,
        'seed_main': seed_values,
        'f': f_values,
        'amp': amp_values,
        'freq_idx': np.arange(n_freq),
        't_fit_idx': np.arange(n_time),
    }
    dims = (trace_dim, 'seed_main', 'f', 'amp', 'freq_idx', 't_fit_idx')
    ds = xr.Dataset(
        data_vars={
            'coeff_re': (dims, coeff_re),
            'coeff_im': (dims, coeff_im),
            'freq': (('f', 'freq_idx'), freq),
            't_fit': (('f', 't_fit_idx'), t_fit),
        },
        coords=coords,
        attrs=attrs,
    )
    ds['coeff_re'].attrs['long_name'] = 'Real part of z = a - i b'
    ds['coeff_im'].attrs['long_name'] = 'Imaginary part of z = a - i b'
    ds['freq'].attrs.update({
        'long_name': 'Fitted frequency grid',
        'units': 'Hz',
    })
    ds['t_fit'].attrs.update({
        'long_name': 'Sliding fit center time',
        'units': 's',
    })
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out_path)
    ds.close()
    return out_path


def mean_finite(values):
    """Average finite values or return NaN."""
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(values)
    if not np.any(valid):
        return np.nan
    return float(np.mean(values[valid]))


def mean_complex(values):
    """Average finite complex values or return NaN."""
    values = np.asarray(values, dtype=complex)
    valid = np.isfinite(values.real) & np.isfinite(values.imag)
    if not np.any(valid):
        return np.nan + 1j * np.nan
    return complex(np.mean(values[valid]))


def group_records(records, keys):
    """Group dictionaries by selected keys."""
    groups = {}
    for record in records:
        key = tuple(record[name] for name in keys)
        groups.setdefault(key, []).append(record)
    return groups


def seed_spectrum_summary(spectrum_records, trace_dim, trace_value, f_value):
    """Summarize block spectra by seed and condition."""
    selected = [
        record for record in spectrum_records
        if record[trace_dim] == trace_value and record['f'] == f_value
    ]
    seed_groups = group_records(selected, ['seed_main', 'amp'])
    seed_curves = []
    for (seed, amp), records in seed_groups.items():
        stack = np.stack([record['spectrum'] for record in records], axis=0)
        with np.errstate(invalid='ignore'):
            curve = np.nanmean(stack, axis=0)
        seed_curves.append({
            'seed_main': seed,
            'amp': amp,
            'ff': records[0]['ff'],
            'spectrum': curve,
        })

    # Average seed curves equally within each amplitude
    amp_groups = group_records(seed_curves, ['amp'])
    out = {}
    for (amp,), records in amp_groups.items():
        stack = np.stack([record['spectrum'] for record in records], axis=0)
        with np.errstate(invalid='ignore'):
            mean_curve = np.nanmean(stack, axis=0)
        out[float(amp)] = {
            'ff': records[0]['ff'],
            'mean': mean_curve,
            'seed_curves': records,
        }
    return out


def condition_metric_rows(block_rows, trace_dim):
    """Build seed-balanced condition metric rows."""
    metric_names = [
        'p_band',
        'p_target',
        'concentration',
        'centroid_offset',
        'width',
    ]
    seed_rows = []
    seed_groups = group_records(block_rows, [trace_dim, 'f', 'amp', 'seed_main'])
    for (trace_value, f_value, amp, seed), rows in seed_groups.items():
        row = {
            trace_dim: trace_value,
            'f': f_value,
            'amp': amp,
            'seed_main': seed,
            'n_blocks': len(rows),
        }
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        seed_rows.append(row)

    # Average seed summaries equally for the condition rows
    condition_rows = []
    cond_groups = group_records(seed_rows, [trace_dim, 'f', 'amp'])
    for (trace_value, f_value, amp), rows in cond_groups.items():
        row = {
            trace_dim: trace_value,
            'f': f_value,
            'amp': amp,
            'n_seed': len(rows),
            'n_blocks': int(np.sum([item['n_blocks'] for item in rows])),
        }
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        condition_rows.append(row)
    return seed_rows, condition_rows


def phase_summary(phase_records, trace_dim, trace_value, f_value, n_bins,
                  smooth_sigma):
    """Summarize phase densities and coefficient clouds."""
    selected = [
        record for record in phase_records
        if record[trace_dim] == trace_value and record['f'] == f_value
    ]
    seed_groups = group_records(selected, ['seed_main', 'amp'])
    seed_density_rows = []
    coeff_by_amp = {}
    for (seed, amp), records in seed_groups.items():
        phases = np.concatenate([record['phases'] for record in records])
        coeffs = np.concatenate([record['coeffs'] for record in records])
        centers, density = phase_density(phases, n_bins, smooth_sigma)
        seed_density_rows.append({
            'seed_main': seed,
            'amp': amp,
            'phase_centers': centers,
            'density': density,
        })
        coeff_by_amp.setdefault(float(amp), []).append(coeffs)

    # Average densities equally across seeds
    density_by_amp = {}
    amp_groups = group_records(seed_density_rows, ['amp'])
    for (amp,), rows in amp_groups.items():
        stack = np.stack([row['density'] for row in rows], axis=0)
        with np.errstate(invalid='ignore'):
            density = np.nanmean(stack, axis=0)
        density_by_amp[float(amp)] = {
            'phase_centers': rows[0]['phase_centers'],
            'density': density,
            'seed_densities': rows,
        }

    # Pool clouds for visualization only
    clouds = {}
    for amp, coeff_lists in coeff_by_amp.items():
        coeffs = np.concatenate(coeff_lists)
        valid = np.isfinite(coeffs.real) & np.isfinite(coeffs.imag)
        clouds[amp] = coeffs[valid]
    return density_by_amp, clouds


def plot_spectra(summary, target_f, broad_band, target_half_width, out_path):
    """Plot raw masked spectra and zero-relative log spectra."""
    if 0 not in summary:
        raise ValueError('Cannot plot log ratio without amp=0')
    amps = sorted(summary)
    eps = np.finfo(float).tiny
    baseline = np.maximum(summary[0]['mean'], eps)

    # Draw raw spectra and baseline-relative spectra together
    fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for idx, amp in enumerate(amps):
        item = summary[amp]
        color = f'C{idx % 10}'
        for seed_curve in item['seed_curves']:
            ax[0].plot(
                seed_curve['ff'],
                seed_curve['spectrum'],
                color=color,
                alpha=0.22,
                linewidth=0.8,
            )
        ax[0].plot(
            item['ff'],
            item['mean'],
            color=color,
            linewidth=2,
            label=f'amp={format_value(amp)}',
        )
        log_ratio = np.log(np.maximum(item['mean'], eps) / baseline)
        ax[1].plot(
            item['ff'],
            log_ratio,
            color=color,
            linewidth=2,
            label=f'amp={format_value(amp)}',
        )

    for axis in ax:
        axis.axvline(target_f, color='k', linestyle='--', linewidth=1)
        axis.axvspan(
            target_f - target_half_width,
            target_f + target_half_width,
            color='0.8',
            alpha=0.35,
        )
        axis.axvspan(broad_band[0], broad_band[1], color='0.9', alpha=0.18)
        axis.legend(fontsize=8, ncol=2)
        axis.set_xlim(summary[amps[0]]['ff'][0], summary[amps[0]]['ff'][-1])
    ax[0].set_ylabel('Fitted power')
    ax[0].set_title('Raw masked spectra')
    ax[1].set_xlabel('Frequency (Hz)')
    ax[1].set_ylabel('log(S / S0)')
    ax[1].set_title('Zero-strength relative spectra')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_band_metrics(block_rows, condition_rows, trace_dim, trace_value,
                      f_value, out_path):
    """Plot block, seed, and condition band metrics."""
    metric_specs = [
        ('p_band', 'Total band power'),
        ('concentration', 'Target concentration'),
        ('centroid_offset', 'Centroid offset (Hz)'),
        ('width', 'Spectral width (Hz)'),
    ]
    rows = [
        row for row in block_rows
        if row[trace_dim] == trace_value and row['f'] == f_value
    ]
    seed_rows, _ = condition_metric_rows(rows, trace_dim)
    cond_rows = [
        row for row in condition_rows
        if row[trace_dim] == trace_value and row['f'] == f_value
    ]

    # Plot all metrics with block points, seed means, and condition means
    fig, ax = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    ax = ax.ravel()
    seed_values = sorted(set(row['seed_main'] for row in seed_rows))
    seed_colors = {
        seed: f'C{idx % 10}'
        for idx, seed in enumerate(seed_values)
    }
    for axis, (name, ylabel) in zip(ax, metric_specs):
        for row in rows:
            axis.plot(
                row['amp'],
                row[name],
                'o',
                color='0.65',
                alpha=0.35,
                markersize=3,
                label='_nolegend_',
            )
        for seed in seed_values:
            seed_items = [
                row for row in seed_rows
                if row['seed_main'] == seed
            ]
            seed_items = sorted(seed_items, key=lambda item: item['amp'])
            axis.plot(
                [row['amp'] for row in seed_items],
                [row[name] for row in seed_items],
                'o-',
                color=seed_colors[seed],
                linewidth=1,
                markersize=4,
                alpha=0.75,
                label=f'seed {format_value(seed)}',
            )
        cond_items = sorted(cond_rows, key=lambda item: item['amp'])
        axis.plot(
            [row['amp'] for row in cond_items],
            [row[name] for row in cond_items],
            'o-',
            color='k',
            linewidth=2.4,
            markersize=5,
            label='seed-balanced mean',
        )
        axis.set_title(ylabel)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
    ax[-2].set_xlabel('Pulse strength')
    ax[-1].set_xlabel('Pulse strength')
    handles, labels = ax[0].get_legend_handles_labels()
    ax[0].legend(handles, labels, fontsize=8)
    fig.suptitle(
        f"Band metrics, {trace_dim}={format_value(trace_value)}, "
        f"f={format_value(f_value)} Hz"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_phase_density(density_by_amp, out_path):
    """Plot raw phase densities and zero-relative enrichment."""
    if 0 not in density_by_amp:
        raise ValueError('Cannot plot phase enrichment without amp=0')
    amps = sorted(density_by_amp)
    centers = density_by_amp[0]['phase_centers']
    baseline = density_by_amp[0]['density']
    enrichment = []

    # Plot density overlays, enrichment curves, and enrichment heat map
    fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True,
                           constrained_layout=True)
    for idx, amp in enumerate(amps):
        item = density_by_amp[amp]
        color = '0.15' if amp == 0 else f'C{idx % 10}'
        width = 2.5 if amp == 0 else 1.6
        diff = item['density'] - baseline
        ax[0].plot(
            item['phase_centers'],
            item['density'],
            color=color,
            linewidth=width,
            label=f'amp={format_value(amp)}',
        )
        ax[1].plot(
            item['phase_centers'],
            diff,
            color=color,
            linewidth=width,
            label=f'amp={format_value(amp)}',
        )
        enrichment.append(diff)

    enrichment = np.asarray(enrichment)
    finite_abs = np.abs(enrichment[np.isfinite(enrichment)])
    vmax = float(np.max(finite_abs)) if finite_abs.size else 1
    if vmax <= np.finfo(float).eps:
        vmax = 1
    im = ax[2].imshow(
        enrichment,
        aspect='auto',
        origin='lower',
        extent=(-np.pi, np.pi, -0.5, len(amps) - 0.5),
        cmap='RdBu_r',
        vmin=-vmax,
        vmax=vmax,
    )
    ax[2].set_yticks(np.arange(len(amps)))
    ax[2].set_yticklabels([f'amp={format_value(amp)}' for amp in amps])
    fig.colorbar(im, ax=ax, label='Density - amp=0 density')
    ax[0].set_ylabel('Density')
    ax[0].set_title('Phase density')
    ax[0].legend(fontsize=8, ncol=2)
    ax[0].set_xlim(-np.pi, np.pi)
    ax[1].axhline(0, color='0.35', linestyle='--', linewidth=1)
    ax[1].set_ylim(-vmax, vmax)
    ax[1].set_ylabel('Density - amp=0')
    ax[1].set_title('Phase enrichment curves')
    ax[1].legend(fontsize=8, ncol=2)
    ax[2].set_xlabel('Phase (rad)')
    ax[2].set_ylabel('Pulse strength')
    ax[2].set_title('Phase enrichment by amp vs amp=0')
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _fit_gaussian_cloud(cloud):
    """Fit a mean and covariance to one complex cloud."""
    cloud = np.asarray(cloud, dtype=complex)
    valid = np.isfinite(cloud.real) & np.isfinite(cloud.imag)
    points = np.column_stack([cloud.real[valid], cloud.imag[valid]])
    if points.shape[0] < 3:
        return None, None
    mu = points.mean(axis=0)
    cov = np.cov(points, rowvar=False)
    if not np.all(np.isfinite(cov)):
        return None, None
    cov = cov + np.eye(2) * np.finfo(float).eps
    return mu, cov


def _plot_gaussian_contours(axis, mu, cov):
    """Plot 95% and 99% Gaussian null contours."""
    if mu is None or cov is None:
        return
    theta = np.linspace(0, 2 * np.pi, 240)
    circle = np.column_stack([np.cos(theta), np.sin(theta)])
    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, np.finfo(float).eps)
    transform = vecs @ np.diag(np.sqrt(vals))
    levels = [
        (5.9915, '0.25', '--', 'null 95%'),
        (9.2103, '0.05', ':', 'null 99%'),
    ]
    for q_value, color, linestyle, label in levels:
        pts = mu + np.sqrt(q_value) * circle @ transform.T
        axis.plot(
            pts[:, 0],
            pts[:, 1],
            color=color,
            linestyle=linestyle,
            linewidth=1.3,
            label=label,
        )


def plot_coeff_clouds(clouds, out_path):
    """Plot complex coefficient clouds by amplitude."""
    amps = sorted(clouds)
    n_cols = min(4, len(amps))
    n_rows = int(np.ceil(len(amps) / n_cols))
    zero_cloud = clouds.get(0, np.array([], dtype=complex))

    # Draw each condition against the zero-strength cloud
    fig, ax = plt.subplots(
        n_rows,
        n_cols,
        figsize=(3.4 * n_cols, 3.2 * n_rows),
        squeeze=False,
    )
    axes = ax.ravel()
    null_mu, null_cov = _fit_gaussian_cloud(zero_cloud)
    for idx, amp in enumerate(amps):
        axis = axes[idx]
        cloud = clouds[amp]
        if zero_cloud.size:
            axis.scatter(
                zero_cloud.real,
                zero_cloud.imag,
                s=8,
                color='0.7',
                alpha=0.22,
                label='amp=0',
            )
        _plot_gaussian_contours(axis, null_mu, null_cov)
        color = '0.15' if amp == 0 else f'C{idx % 10}'
        axis.scatter(
            cloud.real,
            cloud.imag,
            s=10,
            color=color,
            alpha=0.35,
            label=f'amp={format_value(amp)}',
        )
        mean_z = mean_complex(cloud)
        if np.isfinite(mean_z.real) and np.isfinite(mean_z.imag):
            axis.plot([0, mean_z.real], [0, mean_z.imag], color=color, linewidth=2)
        axis.axhline(0, color='0.85', linewidth=0.8)
        axis.axvline(0, color='0.85', linewidth=0.8)
        axis.set_aspect('equal', adjustable='box')
        axis.set_title(f'amp={format_value(amp)}')
        axis.set_xlabel('Re z')
        axis.set_ylabel('Im z')
        axis.legend(fontsize=7)
    for axis in axes[len(amps):]:
        axis.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def load_named_pulse_intervals(netpar_dir, job_id, pulse_names):
    """Load named PulseSeq interval arrays in seconds."""
    netpar_path = find_netpar_path(netpar_dir, job_id)
    with open(netpar_path, 'r', encoding='utf-8') as fobj:
        netpar = json.load(fobj)

    # Read each requested VecStim pulse schedule from netParams
    pop_params = netpar['net']['params']['popParams']
    intervals_by_name = {}
    for pulse_name in pulse_names:
        if pulse_name not in pop_params:
            raise KeyError(f'{pulse_name} not found in {netpar_path}')
        pulses = pop_params[pulse_name]['params']['pulses']
        intervals_by_name[pulse_name] = np.asarray([
            (float(pulse['start']) / 1000, float(pulse['end']) / 1000)
            for pulse in pulses
        ], dtype=float)
    return intervals_by_name


def concat_pulse_intervals(intervals_by_name, pulse_names):
    """Concatenate and sort named pulse interval arrays."""
    arrays = [intervals_by_name[name] for name in pulse_names]
    intervals = np.concatenate(arrays, axis=0)
    order = np.argsort(intervals[:, 0])
    return intervals[order]


def condition_label(key, cond_dims):
    """Format a multidimensional condition label."""
    if not isinstance(key, tuple):
        key = (key,)
    return ', '.join(
        f'{dim}={format_value(value)}'
        for dim, value in zip(cond_dims, key)
    )


def get_condition_key(record, cond_dims):
    """Return one record's condition key."""
    return tuple(record[dim] for dim in cond_dims)


def get_condition_colors(keys, cond_dims):
    """Return red-blue colors keyed by condition values."""
    keys = [tuple(key) for key in keys]
    if not keys:
        return {}
    if 'amp1' in cond_dims and 'amp2' in cond_dims:
        idx1 = list(cond_dims).index('amp1')
        idx2 = list(cond_dims).index('amp2')
        vals1 = sorted(set(key[idx1] for key in keys))
        vals2 = sorted(set(key[idx2] for key in keys))
        den1 = max(len(vals1) - 1, 1)
        den2 = max(len(vals2) - 1, 1)
        return {
            key: (
                vals1.index(key[idx1]) / den1,
                0,
                vals2.index(key[idx2]) / den2,
            )
            for key in keys
        }
    if len(cond_dims) == 1 and cond_dims[0] == 'amp1':
        vals = sorted(set(key[0] for key in keys))
        den = max(len(vals) - 1, 1)
        return {
            key: (vals.index(key[0]) / den, 0, 0)
            for key in keys
        }
    if len(cond_dims) == 1 and cond_dims[0] == 'amp2':
        vals = sorted(set(key[0] for key in keys))
        den = max(len(vals) - 1, 1)
        return {
            key: (0, 0, vals.index(key[0]) / den)
            for key in keys
        }
    return {
        key: f'C{idx % 10}'
        for idx, key in enumerate(keys)
    }


def condition_metric_rows_by(block_rows, trace_dim, cond_dims,
                             extra_dims=('f', 'dt0')):
    """Build seed-balanced condition metric rows for generic conditions."""
    metric_names = [
        'p_band',
        'p_target',
        'concentration',
        'centroid_offset',
        'width',
    ]
    group_dims = [trace_dim] + list(extra_dims) + list(cond_dims)
    seed_rows = []
    seed_groups = group_records(block_rows, group_dims + ['seed_main'])
    for key, rows in seed_groups.items():
        row = {
            dim: value
            for dim, value in zip(group_dims + ['seed_main'], key)
        }
        row['n_blocks'] = len(rows)
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        seed_rows.append(row)

    # Average seed summaries equally for condition rows
    condition_rows = []
    cond_groups = group_records(seed_rows, group_dims)
    for key, rows in cond_groups.items():
        row = {
            dim: value
            for dim, value in zip(group_dims, key)
        }
        row['n_seed'] = len(rows)
        row['n_blocks'] = int(np.sum([item['n_blocks'] for item in rows]))
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        condition_rows.append(row)
    return seed_rows, condition_rows


def pooled_condition_metric_rows(seed_rows, trace_dim, keep_dim,
                                 cond_dims=('amp1', 'amp2'),
                                 extra_dims=('f', 'dt0'),
                                 return_seed_rows=False):
    """Pool seed rows over the other condition dimension."""
    metric_names = [
        'p_band',
        'p_target',
        'concentration',
        'centroid_offset',
        'width',
    ]
    group_dims = [trace_dim] + list(extra_dims) + [keep_dim]
    per_seed_dims = group_dims + ['seed_main']
    per_seed_rows = []
    per_seed_groups = group_records(seed_rows, per_seed_dims)
    for key, rows in per_seed_groups.items():
        row = {
            dim: value
            for dim, value in zip(per_seed_dims, key)
        }
        row['n_source_conditions'] = len(rows)
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        per_seed_rows.append(row)

    # Keep seed balance after pooling across the dropped amplitude dimension
    out_rows = []
    cond_groups = group_records(per_seed_rows, group_dims)
    for key, rows in cond_groups.items():
        row = {
            dim: value
            for dim, value in zip(group_dims, key)
        }
        row['n_seed'] = len(rows)
        row['n_source_conditions'] = int(np.sum([
            item['n_source_conditions']
            for item in rows
        ]))
        for name in metric_names:
            row[name] = mean_finite([item[name] for item in rows])
        out_rows.append(row)
    if return_seed_rows:
        return per_seed_rows, out_rows
    return out_rows


def spectrum_summary_by(spectrum_records, trace_dim, trace_value, f_value,
                        dt0_value, cond_dims):
    """Summarize block spectra by seed and generic condition."""
    selected = [
        record for record in spectrum_records
        if record[trace_dim] == trace_value
        and record['f'] == f_value
        and record['dt0'] == dt0_value
    ]
    seed_keys = ['seed_main'] + list(cond_dims)
    seed_groups = group_records(selected, seed_keys)
    seed_curves = []
    for key, records in seed_groups.items():
        stack = np.stack([record['spectrum'] for record in records], axis=0)
        with np.errstate(invalid='ignore'):
            curve = np.nanmean(stack, axis=0)
        row = {
            dim: value
            for dim, value in zip(seed_keys, key)
        }
        row.update({
            'ff': records[0]['ff'],
            'spectrum': curve,
        })
        seed_curves.append(row)

    # Average seed curves equally within each condition
    out = {}
    cond_groups = group_records(seed_curves, cond_dims)
    for key, records in cond_groups.items():
        stack = np.stack([record['spectrum'] for record in records], axis=0)
        with np.errstate(invalid='ignore'):
            mean_curve = np.nanmean(stack, axis=0)
        out[tuple(key)] = {
            'ff': records[0]['ff'],
            'mean': mean_curve,
            'seed_curves': records,
        }
    return out


def pooled_spectrum_summary(summary, keep_dim, cond_dims=('amp1', 'amp2')):
    """Pool spectrum summaries over the other condition dimension."""
    keep_idx = list(cond_dims).index(keep_dim)
    seed_groups = {}
    for key, item in summary.items():
        keep_value = key[keep_idx]
        for seed_curve in item['seed_curves']:
            group_key = (seed_curve['seed_main'], keep_value)
            seed_groups.setdefault(group_key, []).append(seed_curve)

    # Average the dropped amplitude dimension within seed first
    seed_curves = []
    for (seed, keep_value), curves in seed_groups.items():
        stack = np.stack([curve['spectrum'] for curve in curves], axis=0)
        with np.errstate(invalid='ignore'):
            mean_curve = np.nanmean(stack, axis=0)
        seed_curves.append({
            'seed_main': seed,
            keep_dim: keep_value,
            'ff': curves[0]['ff'],
            'spectrum': mean_curve,
        })

    out = {}
    keep_groups = group_records(seed_curves, [keep_dim])
    for (keep_value,), records in keep_groups.items():
        stack = np.stack([record['spectrum'] for record in records], axis=0)
        with np.errstate(invalid='ignore'):
            mean_curve = np.nanmean(stack, axis=0)
        out[(keep_value,)] = {
            'ff': records[0]['ff'],
            'mean': mean_curve,
            'seed_curves': records,
        }
    return out


def phase_summary_by(phase_records, trace_dim, trace_value, f_value,
                     dt0_value, cond_dims, n_bins, smooth_sigma):
    """Summarize phase densities and clouds by generic condition."""
    selected = [
        record for record in phase_records
        if record[trace_dim] == trace_value
        and record['f'] == f_value
        and record['dt0'] == dt0_value
    ]
    seed_keys = ['seed_main'] + list(cond_dims)
    seed_groups = group_records(selected, seed_keys)
    seed_density_rows = []
    coeff_by_cond = {}
    for key, records in seed_groups.items():
        phases = np.concatenate([record['phases'] for record in records])
        coeffs = np.concatenate([record['coeffs'] for record in records])
        centers, density = phase_density(phases, n_bins, smooth_sigma)
        row = {
            dim: value
            for dim, value in zip(seed_keys, key)
        }
        row.update({
            'phase_centers': centers,
            'density': density,
        })
        seed_density_rows.append(row)
        cond_key = tuple(key[1:])
        coeff_by_cond.setdefault(cond_key, []).append(coeffs)

    # Average densities equally across seeds
    density_by_cond = {}
    cond_groups = group_records(seed_density_rows, cond_dims)
    for key, rows in cond_groups.items():
        stack = np.stack([row['density'] for row in rows], axis=0)
        with np.errstate(invalid='ignore'):
            density = np.nanmean(stack, axis=0)
        density_by_cond[tuple(key)] = {
            'phase_centers': rows[0]['phase_centers'],
            'density': density,
            'seed_densities': rows,
        }

    # Pool clouds for visualization and summary
    clouds = {}
    for key, coeff_lists in coeff_by_cond.items():
        coeffs = np.concatenate(coeff_lists)
        valid = np.isfinite(coeffs.real) & np.isfinite(coeffs.imag)
        clouds[key] = coeffs[valid]
    return density_by_cond, clouds


def pooled_phase_summary(phase_records, trace_dim, trace_value, f_value,
                         dt0_value, keep_dim, n_bins, smooth_sigma,
                         cond_dims=('amp1', 'amp2')):
    """Pool phase summaries over the other condition dimension."""
    selected = [
        record for record in phase_records
        if record[trace_dim] == trace_value
        and record['f'] == f_value
        and record['dt0'] == dt0_value
    ]
    seed_groups = group_records(selected, ['seed_main', keep_dim])
    seed_density_rows = []
    coeff_by_cond = {}
    for (seed, keep_value), records in seed_groups.items():
        phases = np.concatenate([record['phases'] for record in records])
        coeffs = np.concatenate([record['coeffs'] for record in records])
        centers, density = phase_density(phases, n_bins, smooth_sigma)
        seed_density_rows.append({
            'seed_main': seed,
            keep_dim: keep_value,
            'phase_centers': centers,
            'density': density,
        })
        coeff_by_cond.setdefault((keep_value,), []).append(coeffs)

    # Average densities equally across seeds
    density_by_cond = {}
    cond_groups = group_records(seed_density_rows, [keep_dim])
    for key, rows in cond_groups.items():
        stack = np.stack([row['density'] for row in rows], axis=0)
        with np.errstate(invalid='ignore'):
            density = np.nanmean(stack, axis=0)
        density_by_cond[tuple(key)] = {
            'phase_centers': rows[0]['phase_centers'],
            'density': density,
            'seed_densities': rows,
        }

    clouds = {}
    for key, coeff_lists in coeff_by_cond.items():
        coeffs = np.concatenate(coeff_lists)
        valid = np.isfinite(coeffs.real) & np.isfinite(coeffs.imag)
        clouds[key] = coeffs[valid]
    return density_by_cond, clouds


def add_phase_condition_columns_by(condition_rows, phase_records, trace_dim,
                                   cond_dims, extra_dims=('f', 'dt0')):
    """Add event counts and mean coefficient summaries to condition rows."""
    lookup_dims = [trace_dim] + list(extra_dims) + list(cond_dims)
    phase_lookup = {}
    for record in phase_records:
        key = tuple(record[dim] for dim in lookup_dims)
        phase_lookup.setdefault(key, []).append(record)

    # Merge compact phase summaries into existing condition rows
    for row in condition_rows:
        key = tuple(row[dim] for dim in lookup_dims)
        records = phase_lookup.get(key, [])
        if not records:
            continue
        coeffs = np.concatenate([record['coeffs'] for record in records])
        valid = np.isfinite(coeffs.real) & np.isfinite(coeffs.imag)
        row['n_pulses'] = int(np.sum([record['n_pulses'] for record in records]))
        row['n_valid_phase'] = int(np.sum([
            record['n_valid_phase']
            for record in records
        ]))
        if np.any(valid):
            z_mean = complex(np.mean(coeffs[valid]))
            row['z_mean_re'] = float(z_mean.real)
            row['z_mean_im'] = float(z_mean.imag)
            row['z_mean_abs'] = float(abs(z_mean))
    return condition_rows


def save_phase_events_nc_by(records, trace_dim, cond_dims, out_path, attrs,
                            extra_dims=('f', 'dt0')):
    """Save pulse-time complex coefficients for generic conditions."""
    coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
    coord_values = [
        sorted(set(record[dim] for record in records))
        for dim in coord_dims
    ]
    n_event = max(len(record['phases']) for record in records)
    shape = tuple(len(values) for values in coord_values) + (n_event,)
    phase = np.full(shape, np.nan, dtype=float)
    coeff_re = np.full(shape, np.nan, dtype=float)
    coeff_im = np.full(shape, np.nan, dtype=float)
    event_time = np.full(shape, np.nan, dtype=float)
    idx_maps = [
        {value: idx for idx, value in enumerate(values)}
        for values in coord_values
    ]

    # Fill event arrays with NaNs where events are absent or invalid
    for record in records:
        idx = tuple(
            idx_maps[i][record[dim]]
            for i, dim in enumerate(coord_dims)
        )
        n = len(record['phases'])
        coeffs = np.asarray(record['coeffs'], dtype=complex)
        phase[idx + (slice(0, n),)] = record['phases']
        coeff_re[idx + (slice(0, n),)] = coeffs.real
        coeff_im[idx + (slice(0, n),)] = coeffs.imag
        event_time[idx + (slice(0, n),)] = record['event_time']

    coords = {
        dim: values
        for dim, values in zip(coord_dims, coord_values)
    }
    coords['event'] = np.arange(n_event)
    dims = tuple(coord_dims) + ('event',)
    ds = xr.Dataset(
        data_vars={
            'phase': (dims, phase),
            'coeff_re': (dims, coeff_re),
            'coeff_im': (dims, coeff_im),
            'event_time': (dims, event_time),
        },
        coords=coords,
        attrs=attrs,
    )
    ds['phase'].attrs.update({
        'long_name': 'Fitted phase at pulse starts',
        'units': 'rad',
    })
    ds['coeff_re'].attrs['long_name'] = 'Real part of z = a - i b'
    ds['coeff_im'].attrs['long_name'] = 'Imaginary part of z = a - i b'
    ds['event_time'].attrs.update({
        'long_name': 'Pulse start time',
        'units': 's',
    })
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out_path)
    ds.close()
    return out_path


def save_complex_spectrogram_nc_by(records, trace_dim, cond_dims, out_path,
                                   attrs, extra_dims=('f', 'dt0')):
    """Save fitted complex spectrograms for generic conditions."""
    coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
    coord_values = [
        sorted(set(record[dim] for record in records))
        for dim in coord_dims
    ]
    n_freq = max(len(record['freq']) for record in records)
    n_time = max(len(record['t_fit']) for record in records)
    shape = tuple(len(values) for values in coord_values) + (n_freq, n_time)
    coeff_re = np.full(shape, np.nan, dtype=float)
    coeff_im = np.full(shape, np.nan, dtype=float)
    freq = np.full((n_freq,), np.nan, dtype=float)
    t_fit = np.full((n_time,), np.nan, dtype=float)
    idx_maps = [
        {value: idx for idx, value in enumerate(values)}
        for values in coord_values
    ]

    # Fill spectrogram arrays and keep frequency/time grids self-describing
    for record in records:
        idx = tuple(
            idx_maps[i][record[dim]]
            for i, dim in enumerate(coord_dims)
        )
        coeff = np.asarray(record['coeff'], dtype=complex)
        nf, nt = coeff.shape
        coeff_re[idx + (slice(0, nf), slice(0, nt))] = coeff.real
        coeff_im[idx + (slice(0, nf), slice(0, nt))] = coeff.imag
        freq[:len(record['freq'])] = record['freq']
        t_fit[:len(record['t_fit'])] = record['t_fit']

    coords = {
        dim: values
        for dim, values in zip(coord_dims, coord_values)
    }
    coords.update({
        'freq_idx': np.arange(n_freq),
        't_fit_idx': np.arange(n_time),
    })
    dims = tuple(coord_dims) + ('freq_idx', 't_fit_idx')
    ds = xr.Dataset(
        data_vars={
            'coeff_re': (dims, coeff_re),
            'coeff_im': (dims, coeff_im),
            'freq': (('freq_idx',), freq),
            't_fit': (('t_fit_idx',), t_fit),
        },
        coords=coords,
        attrs=attrs,
    )
    ds['coeff_re'].attrs['long_name'] = 'Real part of z = a - i b'
    ds['coeff_im'].attrs['long_name'] = 'Imaginary part of z = a - i b'
    ds['freq'].attrs.update({
        'long_name': 'Fitted frequency grid',
        'units': 'Hz',
    })
    ds['t_fit'].attrs.update({
        'long_name': 'Sliding fit center time',
        'units': 's',
    })
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out_path)
    ds.close()
    return out_path


def load_phase_events_nc_by(path, trace_dim, cond_dims, extra_dims=('f', 'dt0')):
    """Load pulse-time coefficients from a generic NetCDF file."""
    records = []
    with xr.open_dataset(path) as ds:
        coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
        for idx in np.ndindex(*(ds.sizes[dim] for dim in coord_dims)):
            record = {
                dim: as_scalar(ds.coords[dim].values[i])
                for dim, i in zip(coord_dims, idx)
            }
            phase = ds['phase'].values[idx + (slice(None),)]
            coeff_re = ds['coeff_re'].values[idx + (slice(None),)]
            coeff_im = ds['coeff_im'].values[idx + (slice(None),)]
            event_time = ds['event_time'].values[idx + (slice(None),)]
            valid_event = np.isfinite(event_time)
            coeffs = coeff_re + 1j * coeff_im
            record.update({
                'phases': phase[valid_event],
                'coeffs': coeffs[valid_event],
                'event_time': event_time[valid_event],
                'n_pulses': int(np.sum(valid_event)),
                'n_valid_phase': int(np.isfinite(phase[valid_event]).sum()),
            })
            records.append(record)
    return records


def load_complex_spectrogram_nc_by(path, trace_dim, cond_dims,
                                   extra_dims=('f', 'dt0')):
    """Load fitted complex spectrogram records from NetCDF."""
    records = []
    with xr.open_dataset(path) as ds:
        coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
        freq = ds['freq'].values
        t_fit = ds['t_fit'].values
        valid_freq = np.isfinite(freq)
        valid_time = np.isfinite(t_fit)
        for idx in np.ndindex(*(ds.sizes[dim] for dim in coord_dims)):
            record = {
                dim: as_scalar(ds.coords[dim].values[i])
                for dim, i in zip(coord_dims, idx)
            }
            coeff_re = ds['coeff_re'].values[idx + (slice(None), slice(None))]
            coeff_im = ds['coeff_im'].values[idx + (slice(None), slice(None))]
            coeff = coeff_re + 1j * coeff_im
            record.update({
                'freq': freq[valid_freq],
                't_fit': t_fit[valid_time],
                'coeff': coeff[np.ix_(valid_freq, valid_time)],
            })
            records.append(record)
    return records


def spectrum_summary_from_spectrograms(records, trace_dim, trace_value,
                                       f_value, dt0_value, cond_dims):
    """Summarize spectra from saved complex spectrogram coefficients."""
    selected = [
        record for record in records
        if record[trace_dim] == trace_value
        and record['f'] == f_value
        and record['dt0'] == dt0_value
    ]
    seed_keys = ['seed_main'] + list(cond_dims)
    seed_groups = group_records(selected, seed_keys)
    seed_curves = []
    for key, group in seed_groups.items():
        curves = []
        for record in group:
            with np.errstate(invalid='ignore'):
                curves.append(np.nanmean(np.abs(record['coeff']) ** 2, axis=1))
        stack = np.stack(curves, axis=0)
        with np.errstate(invalid='ignore'):
            curve = np.nanmean(stack, axis=0)
        row = {
            dim: value
            for dim, value in zip(seed_keys, key)
        }
        row.update({
            'ff': group[0]['freq'],
            'spectrum': curve,
        })
        seed_curves.append(row)

    # Average seed curves equally within each condition
    out = {}
    cond_groups = group_records(seed_curves, cond_dims)
    for key, group in cond_groups.items():
        stack = np.stack([record['spectrum'] for record in group], axis=0)
        with np.errstate(invalid='ignore'):
            mean_curve = np.nanmean(stack, axis=0)
        out[tuple(key)] = {
            'ff': group[0]['ff'],
            'mean': mean_curve,
            'seed_curves': group,
        }
    return out


def compute_epoch_mean(x, tt, tt_pulse, epoch_t_win):
    """Compute one pulse-triggered average."""
    if tt.size < 2:
        return np.array([], dtype=float), np.array([], dtype=float), 0
    dt = float(tt[1] - tt[0])
    k0 = int(np.round(float(epoch_t_win[0]) / dt))
    k1 = int(np.round(float(epoch_t_win[1]) / dt))
    t_epoch = np.arange(k0, k1) * dt
    pulse_idx = np.round((np.asarray(tt_pulse) - tt[0]) / dt).astype(int)
    pulse_idx = pulse_idx[
        (pulse_idx + k0 >= 0) &
        (pulse_idx + k1 <= x.size)
    ]

    # Average equal-length epochs around valid pulse starts
    if pulse_idx.size == 0:
        return t_epoch, np.full(t_epoch.shape, np.nan), 0
    epochs = np.stack([
        x[idx + k0:idx + k1]
        for idx in pulse_idx
    ], axis=0)
    with np.errstate(invalid='ignore'):
        epoch_mean = np.nanmean(epochs, axis=0)
    return t_epoch, epoch_mean, int(pulse_idx.size)


def save_epoch_signals_nc_by(records, trace_dim, cond_dims, out_path, attrs,
                             extra_dims=('f', 'dt0')):
    """Save pulse-triggered epoch averages for generic conditions."""
    coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
    coord_values = [
        sorted(set(record[dim] for record in records))
        for dim in coord_dims
    ]
    n_time = max(len(record['t_epoch']) for record in records)
    shape = tuple(len(values) for values in coord_values) + (n_time,)
    epoch_mean = np.full(shape, np.nan, dtype=float)
    epoch_plot = np.full(shape, np.nan, dtype=float)
    global_mean = np.full(tuple(len(values) for values in coord_values),
                          np.nan, dtype=float)
    n_epochs = np.zeros(tuple(len(values) for values in coord_values), dtype=int)
    t_epoch = np.full(n_time, np.nan, dtype=float)
    idx_maps = [
        {value: idx for idx, value in enumerate(values)}
        for values in coord_values
    ]

    # Fill epoch arrays while preserving missing conditions as NaNs
    for record in records:
        idx = tuple(
            idx_maps[i][record[dim]]
            for i, dim in enumerate(coord_dims)
        )
        n = len(record['t_epoch'])
        epoch_mean[idx + (slice(0, n),)] = record['epoch_mean']
        epoch_plot[idx + (slice(0, n),)] = record['epoch_plot']
        global_mean[idx] = record['global_mean']
        n_epochs[idx] = int(record['n_epochs'])
        t_epoch[:n] = record['t_epoch']

    coords = {
        dim: values
        for dim, values in zip(coord_dims, coord_values)
    }
    coords['t_epoch'] = t_epoch
    dims = tuple(coord_dims) + ('t_epoch',)
    ds = xr.Dataset(
        data_vars={
            'epoch_mean': (dims, epoch_mean),
            'epoch_plot': (dims, epoch_plot),
            'global_mean': (tuple(coord_dims), global_mean),
            'n_epochs': (tuple(coord_dims), n_epochs),
        },
        coords=coords,
        attrs=attrs,
    )
    ds['epoch_mean'].attrs['long_name'] = 'Raw pulse-triggered average'
    ds['epoch_plot'].attrs['long_name'] = 'Plotted pulse-triggered average'
    ds['global_mean'].attrs['long_name'] = 'Global mean subtracted from epoch_plot'
    ds['t_epoch'].attrs.update({
        'long_name': 'Time from pulse start',
        'units': 's',
    })
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out_path)
    ds.close()
    return out_path


def load_epoch_signals_nc_by(path, trace_dim, cond_dims, extra_dims=('f', 'dt0')):
    """Load pulse-triggered epoch averages from NetCDF."""
    records = []
    with xr.open_dataset(path) as ds:
        coord_dims = [trace_dim, 'seed_main'] + list(extra_dims) + list(cond_dims)
        t_epoch = ds.coords['t_epoch'].values
        valid_time = np.isfinite(t_epoch)
        for idx in np.ndindex(*(ds.sizes[dim] for dim in coord_dims)):
            record = {
                dim: as_scalar(ds.coords[dim].values[i])
                for dim, i in zip(coord_dims, idx)
            }
            record.update({
                't_epoch': t_epoch[valid_time],
                'epoch_mean': ds['epoch_mean'].values[idx + (slice(None),)][valid_time],
                'epoch_plot': ds['epoch_plot'].values[idx + (slice(None),)][valid_time],
                'global_mean': float(ds['global_mean'].values[idx]),
                'n_epochs': int(ds['n_epochs'].values[idx]),
            })
            records.append(record)
    return records


def plot_epoch_signals_by(records, trace_dim, trace_value, f_value, dt0_value,
                          cond_dims, out_path, pulse_duration, pulse_pad,
                          subtract_global_mean):
    """Plot seed-balanced pulse-triggered epoch averages."""
    selected = [
        record for record in records
        if record[trace_dim] == trace_value
        and record['f'] == f_value
        and record['dt0'] == dt0_value
    ]
    cond_groups = group_records(selected, cond_dims)
    keys = sorted(tuple(key) for key in cond_groups)
    colors = get_condition_colors(keys, cond_dims)
    pad_pre, pad_post = get_pulse_pad_pair(pulse_pad)
    title_suffix = 'global mean subtracted' if subtract_global_mean else 'raw mean'

    # Draw seed-balanced epoch traces for all amplitude conditions
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for key in keys:
        group = cond_groups[key]
        stack = np.stack([record['epoch_plot'] for record in group], axis=0)
        with np.errstate(invalid='ignore'):
            y = np.nanmean(stack, axis=0)
        n_epochs = int(np.sum([record['n_epochs'] for record in group]))
        label = f'{condition_label(key, cond_dims)}; n={n_epochs}'
        ax.plot(group[0]['t_epoch'], y, color=colors[key], linewidth=1.7,
                label=label)
    ax.axvline(0, color='k', linestyle='--', linewidth=1)
    ax.axvspan(-pad_pre, pulse_duration + pad_post, color='0.8', alpha=0.35)
    ax.axvspan(0, pulse_duration, color='0.55', alpha=0.22)
    ax.set_xlabel('Time from PulseSeq1 start (s)')
    ax.set_ylabel('Pulse-triggered mean')
    ax.set_title(f'Pulse-triggered averages ({title_suffix})')
    ax.legend(fontsize=7, ncol=2)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_spectra_by(summary, baseline_key, cond_dims, target_f, broad_band,
                    target_half_width, out_path):
    """Plot spectra for generic condition keys."""
    if baseline_key not in summary:
        raise ValueError(f'Cannot plot log ratio without baseline {baseline_key}')
    keys = sorted(summary)
    eps = np.finfo(float).tiny
    baseline = np.maximum(summary[baseline_key]['mean'], eps)

    # Draw raw spectra and baseline-relative spectra together
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    colors = get_condition_colors(keys, cond_dims)
    for key in keys:
        item = summary[key]
        color = colors[key]
        label = condition_label(key, cond_dims)
        for seed_curve in item['seed_curves']:
            ax[0].plot(
                seed_curve['ff'],
                seed_curve['spectrum'],
                color=color,
                alpha=0.14,
                linewidth=0.7,
            )
        ax[0].plot(item['ff'], item['mean'], color=color, linewidth=1.8,
                   label=label)
        log_ratio = np.log(np.maximum(item['mean'], eps) / baseline)
        ax[1].plot(item['ff'], log_ratio, color=color, linewidth=1.8,
                   label=label)

    for axis in ax:
        axis.axvline(target_f, color='k', linestyle='--', linewidth=1)
        axis.axvspan(
            target_f - target_half_width,
            target_f + target_half_width,
            color='0.8',
            alpha=0.35,
        )
        axis.axvspan(broad_band[0], broad_band[1], color='0.9', alpha=0.18)
        axis.set_xlim(summary[keys[0]]['ff'][0], summary[keys[0]]['ff'][-1])
        axis.grid(True, alpha=0.2)
    ax[0].set_ylabel('Fitted power')
    ax[0].set_title('Raw masked spectra')
    ax[1].set_xlabel('Frequency (Hz)')
    ax[1].set_ylabel('log(S / S0)')
    ax[1].set_title('Baseline-relative spectra')
    ax[1].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_band_metrics_by(block_rows, seed_rows, condition_rows, trace_dim,
                         trace_value, f_value, dt0_value, cond_dims,
                         out_path):
    """Plot metrics for generic condition keys on a 1D condition axis."""
    metric_specs = [
        ('p_band', 'Total band power'),
        ('concentration', 'Target concentration'),
        ('centroid_offset', 'Centroid offset (Hz)'),
        ('width', 'Spectral width (Hz)'),
    ]
    keys = sorted({
        tuple(row[dim] for dim in cond_dims)
        for row in condition_rows
        if row[trace_dim] == trace_value
        and row['f'] == f_value
        and row['dt0'] == dt0_value
    })
    xpos = {key: idx for idx, key in enumerate(keys)}
    labels = [condition_label(key, cond_dims) for key in keys]
    colors = get_condition_colors(keys, cond_dims)
    rows = [
        row for row in block_rows
        if row[trace_dim] == trace_value
        and row['f'] == f_value
        and row['dt0'] == dt0_value
    ]
    seeds = sorted(set(row['seed_main'] for row in seed_rows))

    # Plot all metrics with block points, seed means, and condition means
    fig, ax = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    ax = ax.ravel()
    for axis, (name, ylabel) in zip(ax, metric_specs):
        for row in rows:
            key = tuple(row[dim] for dim in cond_dims)
            axis.plot(
                xpos[key],
                row[name],
                'o',
                color='0.65',
                alpha=0.25,
                markersize=2.5,
            )
        for seed in seeds:
            items = [
                row for row in seed_rows
                if row[trace_dim] == trace_value
                and row['f'] == f_value
                and row['dt0'] == dt0_value
                and row['seed_main'] == seed
            ]
            items = sorted(items, key=lambda row: xpos[
                tuple(row[dim] for dim in cond_dims)
            ])
            axis.plot(
                [xpos[tuple(row[dim] for dim in cond_dims)] for row in items],
                [row[name] for row in items],
                'o-',
                linewidth=0.9,
                markersize=3,
                alpha=0.55,
                label=f'seed {format_value(seed)}',
            )
        items = [
            row for row in condition_rows
            if row[trace_dim] == trace_value
            and row['f'] == f_value
            and row['dt0'] == dt0_value
        ]
        items = sorted(items, key=lambda row: xpos[
            tuple(row[dim] for dim in cond_dims)
        ])
        for row in items:
            key = tuple(row[dim] for dim in cond_dims)
            axis.plot(
                xpos[key],
                row[name],
                'o',
                color=colors[key],
                markersize=5,
                label='_nolegend_',
            )
        axis.plot(
            [xpos[tuple(row[dim] for dim in cond_dims)] for row in items],
            [row[name] for row in items],
            '-',
            color='0.15',
            linewidth=1.4,
            label='seed-balanced mean',
        )
        axis.set_title(ylabel)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
    for axis in ax[-2:]:
        axis.set_xlabel('Condition')
    for axis in ax:
        axis.set_xticks(range(len(labels)))
        axis.set_xticklabels(labels, rotation=60, ha='right', fontsize=7)
    handles, labels_legend = ax[0].get_legend_handles_labels()
    ax[0].legend(handles, labels_legend, fontsize=7)
    fig.suptitle(
        f"{trace_dim}={format_value(trace_value)}, f={format_value(f_value)} Hz, "
        f"dt0={format_value(dt0_value)}"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_phase_density_by(density_by_cond, baseline_key, cond_dims, out_path):
    """Plot phase densities and baseline-relative enrichment."""
    if baseline_key not in density_by_cond:
        raise ValueError(f'Cannot plot phase enrichment without {baseline_key}')
    keys = sorted(density_by_cond)
    baseline = density_by_cond[baseline_key]['density']
    enrichment = []

    # Plot density overlays, enrichment curves, and enrichment heat map
    fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True,
                           constrained_layout=True)
    colors = get_condition_colors(keys, cond_dims)
    for key in keys:
        item = density_by_cond[key]
        color = colors[key]
        width = 2.5 if key == baseline_key else 1.5
        label = condition_label(key, cond_dims)
        diff = item['density'] - baseline
        ax[0].plot(item['phase_centers'], item['density'], color=color,
                   linewidth=width, label=label)
        ax[1].plot(item['phase_centers'], diff, color=color,
                   linewidth=width, label=label)
        enrichment.append(diff)

    enrichment = np.asarray(enrichment)
    finite_abs = np.abs(enrichment[np.isfinite(enrichment)])
    vmax = float(np.max(finite_abs)) if finite_abs.size else 1
    if vmax <= np.finfo(float).eps:
        vmax = 1
    im = ax[2].imshow(
        enrichment,
        aspect='auto',
        origin='lower',
        extent=(-np.pi, np.pi, -0.5, len(keys) - 0.5),
        cmap='RdBu_r',
        vmin=-vmax,
        vmax=vmax,
    )
    ax[2].set_yticks(np.arange(len(keys)))
    ax[2].set_yticklabels([condition_label(key, cond_dims) for key in keys],
                          fontsize=7)
    fig.colorbar(im, ax=ax, label='Density - baseline density')
    ax[0].set_ylabel('Density')
    ax[0].set_title('Phase density')
    ax[0].legend(fontsize=7, ncol=2)
    ax[0].set_xlim(-np.pi, np.pi)
    ax[1].axhline(0, color='0.35', linestyle='--', linewidth=1)
    ax[1].set_ylim(-vmax, vmax)
    ax[1].set_ylabel('Density - baseline')
    ax[1].set_title('Phase enrichment curves')
    ax[1].legend(fontsize=7, ncol=2)
    ax[2].set_xlabel('Phase (rad)')
    ax[2].set_ylabel('Condition')
    ax[2].set_title('Phase enrichment by condition')
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_coeff_clouds_by(clouds, baseline_key, cond_dims, out_path):
    """Plot coefficient clouds for generic condition keys."""
    keys = sorted(clouds)
    n_cols = min(4, len(keys))
    n_rows = int(np.ceil(len(keys) / n_cols))
    baseline_cloud = clouds.get(baseline_key, np.array([], dtype=complex))

    # Draw each condition against the baseline cloud
    fig, ax = plt.subplots(
        n_rows,
        n_cols,
        figsize=(3.4 * n_cols, 3.2 * n_rows),
        squeeze=False,
    )
    axes = ax.ravel()
    null_mu, null_cov = _fit_gaussian_cloud(baseline_cloud)
    colors = get_condition_colors(keys, cond_dims)
    for idx, key in enumerate(keys):
        axis = axes[idx]
        cloud = clouds[key]
        label = condition_label(key, cond_dims)
        if baseline_cloud.size:
            axis.scatter(
                baseline_cloud.real,
                baseline_cloud.imag,
                s=8,
                color='0.7',
                alpha=0.18,
                label='baseline',
            )
        _plot_gaussian_contours(axis, null_mu, null_cov)
        color = colors[key]
        axis.scatter(cloud.real, cloud.imag, s=10, color=color, alpha=0.32,
                     label=label)
        mean_z = mean_complex(cloud)
        if np.isfinite(mean_z.real) and np.isfinite(mean_z.imag):
            axis.plot([0, mean_z.real], [0, mean_z.imag], color=color,
                      linewidth=2)
        axis.axhline(0, color='0.85', linewidth=0.8)
        axis.axvline(0, color='0.85', linewidth=0.8)
        axis.set_aspect('equal', adjustable='box')
        axis.set_title(label)
        axis.set_xlabel('Re z')
        axis.set_ylabel('Im z')
        axis.legend(fontsize=6)
    for axis in axes[len(keys):]:
        axis.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_metric_grid(condition_rows, trace_dim, trace_value, f_value,
                     dt0_value, out_path):
    """Plot condition metrics as amp1-by-amp2 heatmaps."""
    metric_specs = [
        ('p_band', 'Total band power'),
        ('concentration', 'Target concentration'),
        ('centroid_offset', 'Centroid offset (Hz)'),
        ('width', 'Spectral width (Hz)'),
    ]
    rows = [
        row for row in condition_rows
        if row[trace_dim] == trace_value
        and row['f'] == f_value
        and row['dt0'] == dt0_value
    ]
    amp1_values = sorted(set(row['amp1'] for row in rows))
    amp2_values = sorted(set(row['amp2'] for row in rows))

    # Draw one heatmap per metric on the same amp grid
    fig, ax = plt.subplots(2, 2, figsize=(9, 7), constrained_layout=True)
    ax = ax.ravel()
    for axis, (name, title) in zip(ax, metric_specs):
        grid = np.full((len(amp2_values), len(amp1_values)), np.nan)
        for row in rows:
            i = amp2_values.index(row['amp2'])
            j = amp1_values.index(row['amp1'])
            grid[i, j] = row.get(name, np.nan)
        im = axis.imshow(grid, origin='lower', aspect='auto')
        axis.set_title(title)
        axis.set_xticks(np.arange(len(amp1_values)))
        axis.set_yticks(np.arange(len(amp2_values)))
        axis.set_xticklabels([format_value(v) for v in amp1_values])
        axis.set_yticklabels([format_value(v) for v in amp2_values])
        axis.set_xlabel('amp1')
        axis.set_ylabel('amp2')
        fig.colorbar(im, ax=axis)
    fig.suptitle(
        f"{trace_dim}={format_value(trace_value)}, f={format_value(f_value)} Hz, "
        f"dt0={format_value(dt0_value)}"
    )
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_phase_metric_grid(condition_rows, trace_dim, trace_value, f_value,
                           dt0_value, out_path):
    """Plot phase/coefficient summaries as amp1-by-amp2 heatmaps."""
    metric_specs = [
        ('z_mean_abs', '|mean z|'),
        ('z_mean_re', 'mean Re z'),
        ('z_mean_im', 'mean Im z'),
        ('n_valid_phase', 'Valid phases'),
    ]
    rows = [
        row for row in condition_rows
        if row[trace_dim] == trace_value
        and row['f'] == f_value
        and row['dt0'] == dt0_value
    ]
    amp1_values = sorted(set(row['amp1'] for row in rows))
    amp2_values = sorted(set(row['amp2'] for row in rows))

    # Draw one heatmap per phase/coefficient summary
    fig, ax = plt.subplots(2, 2, figsize=(9, 7), constrained_layout=True)
    ax = ax.ravel()
    for axis, (name, title) in zip(ax, metric_specs):
        grid = np.full((len(amp2_values), len(amp1_values)), np.nan)
        for row in rows:
            i = amp2_values.index(row['amp2'])
            j = amp1_values.index(row['amp1'])
            grid[i, j] = row.get(name, np.nan)
        im = axis.imshow(grid, origin='lower', aspect='auto')
        axis.set_title(title)
        axis.set_xticks(np.arange(len(amp1_values)))
        axis.set_yticks(np.arange(len(amp2_values)))
        axis.set_xticklabels([format_value(v) for v in amp1_values])
        axis.set_yticklabels([format_value(v) for v in amp2_values])
        axis.set_xlabel('amp1')
        axis.set_ylabel('amp2')
        fig.colorbar(im, ax=axis)
    fig.suptitle(
        f"{trace_dim}={format_value(trace_value)}, f={format_value(f_value)} Hz, "
        f"dt0={format_value(dt0_value)}"
    )
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_spectra_logratio_grid(summary, baseline_key, cond_dims, out_path):
    """Plot baseline-relative spectra as a condition-by-frequency heatmap."""
    if baseline_key not in summary:
        raise ValueError(f'Cannot plot log ratio without baseline {baseline_key}')
    keys = sorted(summary)
    ff = summary[keys[0]]['ff']
    eps = np.finfo(float).tiny
    baseline = np.maximum(summary[baseline_key]['mean'], eps)
    data = []
    for key in keys:
        ratio = np.log(np.maximum(summary[key]['mean'], eps) / baseline)
        data.append(ratio)
    data = np.asarray(data)
    finite_abs = np.abs(data[np.isfinite(data)])
    vmax = float(np.max(finite_abs)) if finite_abs.size else 1
    if vmax <= np.finfo(float).eps:
        vmax = 1

    # Draw all amplitude pairs on one shared frequency axis
    fig, ax = plt.subplots(figsize=(9, 6), constrained_layout=True)
    im = ax.imshow(
        data,
        aspect='auto',
        origin='lower',
        extent=(ff[0], ff[-1], -0.5, len(keys) - 0.5),
        cmap='RdBu_r',
        vmin=-vmax,
        vmax=vmax,
    )
    ax.set_yticks(np.arange(len(keys)))
    ax.set_yticklabels([condition_label(key, cond_dims) for key in keys],
                       fontsize=7)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Condition')
    ax.set_title('log(S / S00)')
    fig.colorbar(im, ax=ax, label='log ratio')
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
