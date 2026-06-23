import csv
import json
import os
import sys
from pathlib import Path


# Set paths before importing local packages
DIR_REPO = Path(__file__).resolve().parents[3]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

EXP_NAME = 'exp_L2_nseed_3_f_5_amp1_0_0.04_4_amp2_0_0.2_4_dt0_0_t_5.0_50.0_lfp_0_300_50_ictrl_wmult_0.25_ee_0.5_2pulse_IT2_NGF2_d_20_c_25_r_1000_0_t0_5000_jit_0_tlast_49995.0'
DIRPATH_EXP = (
    DIR_REPO / 'exp_results' / 'batch_rxbkg_state1_mech1' /
    'net_2pulses_var_seed_f_amps_dt0' / EXP_NAME
)
DIRPATH_ARTIFACT = (
    DIR_REPO / 'dev_scratch' / 'artifacts' /
    'net_2pulses_var_seed_f_amps_dt0' / EXP_NAME
)
#SIGNAL_KINDS = ('lfp', 'csd')
SIGNAL_KINDS = ('rates',)
INPUT_PATHS = {
    'rates': DIRPATH_ARTIFACT / 'rates_xr_combined.nc',
    'lfp': DIRPATH_ARTIFACT / 'lfp_xr_combined.nc',
    'csd': DIRPATH_ARTIFACT / 'lfp_xr_combined.nc',
}
NETPAR_DIR = DIRPATH_EXP / 'netpar'

AVG_OVER_SEEDS = 1
RUN_PER_JOB = 0
RUN_COMBINED = 1
Y_VALUES = None
OUT_DIR = DIRPATH_ARTIFACT / 'phase_lock'
SIGNAL_KIND = SIGNAL_KINDS[0]
INPUT_PATH = INPUT_PATHS[SIGNAL_KIND]

os.environ.setdefault('MPLCONFIGDIR', str(DIRPATH_ARTIFACT / 'mpl_cache'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter1d

from analysis.phase_utils.spect_proc import (
    itc,
    morlet_power_freqs,
    sinusoid_fit_itc,
    sinusoid_fit_power_freqs,
)
from sim_data_analyzer.batch_xr import iter_batch_jobs
from sim_data_analyzer.xr_diff import calc_xr_csd
from sim_data_analyzer.xr_signal import interp_time_outliers


TIME_DIM = 'time'
JOB_ID_COORD = 'job_id'
SEED_DIM = 'seed_main'
Y_DIM = 'y'
METHOD = 'fit'
FALLBACK_F = 5
LOCK_PULSE_NAME = 'PulseSeq1'
MASK_PULSE_NAMES = ('PulseSeq1', 'PulseSeq2')
N_CYCLES = 3
ANALYSIS_T0 = 10
PULSE_PAD = 0.005
INTERP_OUTLIERS = 1
OUTLIER_Z_THRESH = 8
OUTLIER_REL_NEIGHBOR_THRESH = 5

POWER_OVERLAP = 0.9
POWER_FBAND = 10
POWER_DF = 0.2
POWER_MODE = 'amp2'

FIT_INTERCEPT = 1
FIT_RCOND = None
SUBTRACT_LOCAL_MEAN = 1
EXCLUDE_EDGES = 1
MIN_VALID_MASS_FRAC = 0.5

EPOCH_T_WIN = (-0.2, 0.2)
PLOT_T_WIN = (10, 30)
#PHASE_PROGRESSION_PLOT = 'wrapped_strip'
PHASE_PROGRESSION_PLOT = 'unwrapped'
PHASE_PROGRESS_YLIM = (-2 * np.pi, 2 * np.pi)
PHASE_BINS = 32
PHASE_SMOOTH_SIGMA = 1
FIG_DPI = 150


def _as_scalar(value):
    """Convert numpy scalar values to plain Python values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray) and value.size == 1:
        return value.item()
    return value


def _format_value(value):
    """Format one coordinate value for labels and folder names."""
    value = _as_scalar(value)
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)


def _format_sel(sel):
    """Format a coordinate selector."""
    return ', '.join(
        f'{key}={_format_value(value)}'
        for key, value in sel.items()
    )


def _format_fname_piece(value):
    """Format one safe filename fragment."""
    text = _format_value(value)
    return text.replace('.', 'p').replace('-', 'm').replace('/', '_')


def _get_trace_color(idx):
    """Choose a repeatable matplotlib color."""
    return f'C{idx % 10}'


def _format_condition_label(job_sel):
    """Format the non-frequency batch condition."""
    cond_sel = {
        key: value
        for key, value in job_sel.items()
        if key != 'f'
    }
    return _format_sel(cond_sel) if cond_sel else _format_sel(job_sel)


def _get_out_dir(signal_kind):
    """Build the output root for one signal kind."""
    suffix = '_avgseed' if AVG_OVER_SEEDS else ''
    if signal_kind == 'rates':
        dirname = f'phase_lock{suffix}'
    else:
        dirname = f'phase_lock_{signal_kind}{suffix}'
    return DIRPATH_ARTIFACT / dirname


def _set_signal_kind(signal_kind):
    """Update global input and output paths for one signal kind."""
    global INPUT_PATH, OUT_DIR, SIGNAL_KIND
    if signal_kind not in INPUT_PATHS:
        raise ValueError(f'Unknown signal kind: {signal_kind}')
    SIGNAL_KIND = signal_kind
    INPUT_PATH = INPUT_PATHS[signal_kind]
    OUT_DIR = _get_out_dir(signal_kind)


def _get_trace_file_stem(trace_sel):
    """Build a filename stem for one trace selector."""
    if not trace_sel:
        return 'signal'
    if len(trace_sel) == 1:
        key, value = next(iter(trace_sel.items()))
        if key == 'pop':
            return _format_fname_piece(value)
        return f'{key}_{_format_fname_piece(value)}'
    parts = [
        f'{key}_{_format_fname_piece(value)}'
        for key, value in trace_sel.items()
    ]
    return '_'.join(parts)


def _find_netpar_path(job_id):
    """Find the netParams JSON file for one batch job."""
    matches = sorted(NETPAR_DIR.glob(f'netParams_{job_id:05d}_*.json'))
    if len(matches) != 1:
        raise FileNotFoundError(
            f'Expected one netParams file for job {job_id}, found {len(matches)}'
        )
    return matches[0]


def _extract_pulse_intervals(pop_params, pulse_name, netpar_path):
    """Extract one VecStim pulse interval array in seconds."""
    if pulse_name not in pop_params:
        raise KeyError(f'{pulse_name} not found in {netpar_path}')
    pulse_seq = pop_params[pulse_name]
    pulses = pulse_seq['params']['pulses']
    intervals = [
        (float(pulse['start']) / 1000, float(pulse['end']) / 1000)
        for pulse in pulses
    ]
    return np.asarray(intervals, dtype=float)


def _load_pulse_intervals(job_id):
    """Load locking and masking pulse intervals for one batch job."""
    netpar_path = _find_netpar_path(job_id)
    with open(netpar_path, 'r', encoding='utf-8') as fobj:
        netpar = json.load(fobj)

    # Read all saved VecStim pulse windows needed by analysis
    pop_params = netpar['net']['params']['popParams']
    intervals_by_name = {
        pulse_name: _extract_pulse_intervals(
            pop_params,
            pulse_name,
            netpar_path,
        )
        for pulse_name in MASK_PULSE_NAMES
    }
    lock_intervals = intervals_by_name[LOCK_PULSE_NAME]
    mask_intervals = np.concatenate(
        [intervals_by_name[name] for name in MASK_PULSE_NAMES],
        axis=0,
    )
    order = np.argsort(mask_intervals[:, 0])
    mask_intervals = mask_intervals[order]
    return lock_intervals, mask_intervals, intervals_by_name, netpar_path


def _open_input_xarray():
    """Open the configured input xarray without preprocessing it."""
    X = xr.open_dataarray(INPUT_PATH)
    if TIME_DIM not in X.dims:
        raise ValueError(f'Missing time dimension {TIME_DIM!r}')
    if JOB_ID_COORD not in X.coords:
        raise ValueError(f'Missing auxiliary coord {JOB_ID_COORD!r}')
    if Y_VALUES is not None and Y_DIM in X.dims:
        _validate_y_values(X)

    # Keep the time axis last for downstream 1D kernels
    dim_order = [dim for dim in X.dims if dim != TIME_DIM] + [TIME_DIM]
    return X.transpose(*dim_order)


def _get_y_values():
    """Return configured y values as a plain list."""
    if Y_VALUES is None:
        return None
    return [_as_scalar(value) for value in Y_VALUES]


def _validate_y_values(X):
    """Validate selected y values against the input coordinates."""
    y_values = _get_y_values()
    if y_values is None or Y_DIM not in X.dims:
        return
    available = set(_as_scalar(value) for value in X.coords[Y_DIM].values)
    missing = [value for value in y_values if value not in available]
    if missing:
        raise ValueError(f'Requested y values are absent: {missing}')


def _select_y_values(X):
    """Select configured y values when this signal has a y axis."""
    y_values = _get_y_values()
    if y_values is None or Y_DIM not in X.dims:
        return X
    return X.sel({Y_DIM: y_values})


def _select_preprocess_trace(X, trace_sel):
    """Select trace dims that are safe before signal preprocessing."""
    if not trace_sel:
        return X
    sel = {}
    for dim, value in trace_sel.items():
        if dim not in X.dims:
            continue
        if SIGNAL_KIND == 'csd' and dim == Y_DIM:
            continue
        sel[dim] = value
    if not sel:
        return X
    return X.sel(sel)


def _select_output_trace(X, trace_sel):
    """Select the final trace dims after preprocessing."""
    if not trace_sel:
        return X
    sel = {
        dim: value
        for dim, value in trace_sel.items()
        if dim in X.dims
    }
    if not sel:
        return X
    return X.sel(sel)


def _interp_xarray(X):
    """Interpolate isolated time outliers when enabled."""
    if not INTERP_OUTLIERS:
        return X

    # Delegate isolated outlier handling to sim_data_analyzer
    return interp_time_outliers(
        X,
        time_dim=TIME_DIM,
        z_thresh=OUTLIER_Z_THRESH,
        rel_neighbor_thresh=OUTLIER_REL_NEIGHBOR_THRESH,
    )


def _prepare_job_xarray(X, job, trace_sel=None):
    """Select and preprocess one job-sized xarray slice."""
    trace_sel = trace_sel or {}
    X_job = X.isel(job['isel'])
    X_job = _select_preprocess_trace(X_job, trace_sel)

    # For LFP/rates, y can be selected before preprocessing
    if SIGNAL_KIND != 'csd':
        X_job = _select_y_values(X_job)

    X_job = _interp_xarray(X_job)

    # Derive CSD after interpolation, keeping neighboring depths until here
    if SIGNAL_KIND == 'csd':
        if Y_DIM not in X_job.dims:
            raise ValueError(f'Missing CSD depth dimension {Y_DIM!r}')
        X_job = calc_xr_csd(X_job, ydim=Y_DIM)
        X_job = _select_y_values(X_job)

    X_job = _select_output_trace(X_job, trace_sel)

    # Exclude the initial analysis interval without cropping coordinates
    tt = X_job.coords[TIME_DIM]
    X_job = X_job.where(tt >= ANALYSIS_T0)
    X_job.name = SIGNAL_KIND
    return X_job


def _get_job_dim_names(X):
    """Return the xarray dimensions covered by job_id."""
    job_id_xr = X.coords[JOB_ID_COORD]
    return tuple(job_id_xr.dims)


def _get_trace_dim_names(X, job_dims):
    """Return non-time dimensions that are not batch job dimensions."""
    return [
        dim for dim in X.dims
        if dim != TIME_DIM and dim not in job_dims
    ]


def _get_trace_coord_values(X, dim):
    """Return coordinate values for one trace dimension."""
    if dim == Y_DIM and Y_VALUES is not None:
        return _get_y_values()
    return [_as_scalar(value) for value in X.coords[dim].values]


def _get_trace_selectors(X, job_dims):
    """Build all trace selectors requested by constants."""
    trace_dims = _get_trace_dim_names(X, job_dims)
    if len(trace_dims) == 0:
        return [{}]

    coord_values = [
        _get_trace_coord_values(X, dim)
        for dim in trace_dims
    ]
    selectors = []
    for idx_tuple in np.ndindex(*[len(values) for values in coord_values]):
        selector = {
            dim: coord_values[idx][idx_tuple[idx]]
            for idx, dim in enumerate(trace_dims)
        }
        selectors.append(selector)
    return selectors


def _iter_trace_signals(X_job, job_dims):
    """Yield every 1D trace orthogonal to time."""
    trace_dims = _get_trace_dim_names(X_job, job_dims)
    if len(trace_dims) == 0:
        yield {}, X_job
        return

    # Iterate over the remaining non-time coordinate grid
    shape = [X_job.sizes[dim] for dim in trace_dims]
    for idx in np.ndindex(*shape):
        isel = {dim: idx[n] for n, dim in enumerate(trace_dims)}
        sel = {
            dim: _as_scalar(X_job.coords[dim].values[idx[n]])
            for n, dim in enumerate(trace_dims)
        }
        yield sel, X_job.isel(isel)


def _get_target_f(job_sel):
    """Resolve the target frequency for one batch job."""
    if 'f' in job_sel:
        return float(job_sel['f'])
    return float(FALLBACK_F)


def _get_power_fband(target_f):
    """Clamp the frequency band to positive frequencies."""
    return min(float(POWER_FBAND), 0.5 * float(target_f))


def _mask_pulse_intervals(x, tt, pulse_intervals):
    """Mask pulse intervals and their surroundings."""
    x_masked = np.asarray(x, dtype=float).copy()
    x_masked[tt < ANALYSIS_T0] = np.nan
    for t_start, t_end in pulse_intervals:
        mask = (tt >= t_start - PULSE_PAD) & (tt <= t_end + PULSE_PAD)
        x_masked[mask] = np.nan
    return x_masked


def _filter_analysis_pulses(pulse_intervals, tt):
    """Keep pulse starts that belong to the analysis interval."""
    pulse_starts = pulse_intervals[:, 0]
    keep = (
        (pulse_starts >= ANALYSIS_T0) &
        (pulse_starts >= tt[0]) &
        (pulse_starts <= tt[-1])
    )
    return pulse_starts[keep]


def _compute_itc(x_masked, tt, tt_pulse, target_f):
    """Compute phase-locking with the selected local estimator."""
    if METHOD == 'morlet':
        return itc(
            x_masked,
            tt,
            tt_pulse,
            target_f,
            N_CYCLES,
            drop_win=None,
            subtract_local_mean=bool(SUBTRACT_LOCAL_MEAN),
            exclude_edges=bool(EXCLUDE_EDGES),
            min_valid_mass_frac=MIN_VALID_MASS_FRAC,
        )

    if METHOD != 'fit':
        raise ValueError(f'Unknown METHOD: {METHOD}')
    return sinusoid_fit_itc(
        x_masked,
        tt,
        tt_pulse,
        target_f,
        N_CYCLES,
        drop_win=None,
        fit_intercept=bool(FIT_INTERCEPT),
        exclude_edges=bool(EXCLUDE_EDGES),
        min_valid_mass_frac=MIN_VALID_MASS_FRAC,
        rcond=FIT_RCOND,
    )


def _compute_power_curve(x_masked, tt, target_f):
    """Compute mean sliding power over a frequency band."""
    fband = _get_power_fband(target_f)
    if METHOD == 'morlet':
        _, ff, power = morlet_power_freqs(
            x_masked,
            tt,
            target_f,
            fband,
            POWER_DF,
            N_CYCLES,
            overlap=POWER_OVERLAP,
            power_mode=POWER_MODE,
            subtract_local_mean=bool(SUBTRACT_LOCAL_MEAN),
            exclude_edges=bool(EXCLUDE_EDGES),
            min_valid_mass_frac=MIN_VALID_MASS_FRAC,
        )
    else:
        _, ff, power = sinusoid_fit_power_freqs(
            x_masked,
            tt,
            target_f,
            fband,
            POWER_DF,
            N_CYCLES,
            overlap=POWER_OVERLAP,
            fit_intercept=bool(FIT_INTERCEPT),
            exclude_edges=bool(EXCLUDE_EDGES),
            min_valid_mass_frac=MIN_VALID_MASS_FRAC,
            rcond=FIT_RCOND,
        )

    # Collapse the sliding windows while keeping frequency structure
    with np.errstate(invalid='ignore'):
        power_curve = np.nanmean(power, axis=1)
    return ff, power_curve, power


def _summarize_power(ff, power_curve, power):
    """Summarize power values for the metrics table."""
    valid_curve = np.isfinite(power_curve)
    if np.any(valid_curve):
        peak_idx = int(np.nanargmax(power_curve))
        peak_freq = float(ff[peak_idx])
        peak_power = float(power_curve[peak_idx])
    else:
        peak_freq = np.nan
        peak_power = np.nan

    power_mean = np.nan
    if np.any(np.isfinite(power)):
        power_mean = float(np.nanmean(power))
    return power_mean, peak_freq, peak_power


def _get_epoch_mean(x, tt, tt_pulse):
    """Compute a pulse-triggered average for one trace."""
    if tt.size < 2:
        return np.array([], dtype=float), np.array([], dtype=float), 0

    dt = float(tt[1] - tt[0])
    t_epoch = np.arange(EPOCH_T_WIN[0], EPOCH_T_WIN[1], dt)
    n_epoch = t_epoch.size
    epochs = []
    for t0 in tt_pulse:
        idx0 = int(np.round((t0 + EPOCH_T_WIN[0] - tt[0]) / dt))
        idx1 = idx0 + n_epoch
        if idx0 < 0 or idx1 > x.size:
            continue
        epochs.append(x[idx0:idx1])

    if len(epochs) == 0:
        return t_epoch, np.full(t_epoch.shape, np.nan), 0
    return t_epoch, np.nanmean(np.stack(epochs, axis=0), axis=0), len(epochs)


def _get_job_dir_stem(job_id, job_sel):
    """Build the folder stem for one analyzed result."""
    if job_id is None:
        parts = ['avgseed']
    else:
        parts = [f'job_{int(job_id):05d}']
    for key, value in job_sel.items():
        parts.append(f'{key}_{_format_fname_piece(value)}')
    return '_'.join(parts)


def _build_job_out_dir(job_id, job_sel):
    """Build the output folder for one job."""
    job_dir = OUT_DIR / 'per_job' / _get_job_dir_stem(job_id, job_sel)
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def _plot_pulse_starts(axis, intervals_by_name, t0, t1):
    """Mark pulse starts from each configured stream."""
    colors = ('0.65', '0.35')
    for idx, pulse_name in enumerate(MASK_PULSE_NAMES):
        intervals = intervals_by_name.get(pulse_name, [])
        color = colors[idx % len(colors)]
        label = pulse_name
        for n, (t_start, _t_end) in enumerate(intervals):
            if t0 <= t_start <= t1:
                axis.axvline(
                    t_start,
                    color=color,
                    linestyle='--',
                    linewidth=0.7,
                    label=label if n == 0 else None,
                )


def _plot_signals(job_result, out_path):
    """Plot raw signals and pulse-triggered averages."""
    tt = job_result['tt']
    tt_pulse = job_result['tt_pulse']
    trace_results = job_result['traces']
    pulse_duration = job_result['pulse_duration']
    t0, t1 = PLOT_T_WIN
    keep = (tt >= t0) & (tt <= t1)

    # Build the raw and epoch panels
    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=False)
    for idx, result in enumerate(trace_results):
        color = _get_trace_color(idx)
        label = result['label']
        ax[0].plot(
            tt[keep],
            result['x_raw'][keep],
            color=color,
            linewidth=1,
            label=label,
        )
        ax[1].plot(
            result['t_epoch'],
            result['epoch_mean'],
            color=color,
            linewidth=1.2,
            label=label,
        )

    # Mark all pulse streams and the lock-stream epoch interval
    _plot_pulse_starts(ax[0], job_result['pulse_intervals_by_name'], t0, t1)
    ax[1].axvline(0, color='k', linestyle='--', linewidth=1)
    ax[1].axvspan(
        -PULSE_PAD,
        pulse_duration + PULSE_PAD,
        color='0.8',
        alpha=0.4,
    )
    ax[1].axvspan(0, pulse_duration, color='0.6', alpha=0.2)

    ax[0].set_xlim(t0, t1)
    ax[0].set_xlabel('Time (s)')
    ax[0].set_ylabel('Signal')
    ax[0].set_title(f"Signals, {job_result['job_label']}")
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].set_xlabel('Time from pulse start (s)')
    ax[1].set_ylabel('Pulse-triggered mean')
    ax[1].set_title(f"Pulse-triggered averages, n={job_result['n_pulses']}")
    ax[1].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _phase_progression(phases):
    """Unwrap valid phases while preserving NaNs."""
    phases = np.asarray(phases, dtype=float)
    out = np.full(phases.shape, np.nan)
    valid = np.isfinite(phases)
    if np.any(valid):
        out[valid] = np.unwrap(phases[valid])
    return out


def _phase_progression_strip_coords(tt_valid, phases_valid, ymin, ymax):
    """Replicate wrapped phases across the visible strip."""
    tt_valid = np.asarray(tt_valid, dtype=float)
    phases_valid = np.asarray(phases_valid, dtype=float)
    if phases_valid.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    k_min = int(np.floor((ymin - np.max(phases_valid)) / (2 * np.pi)))
    k_max = int(np.ceil((ymax - np.min(phases_valid)) / (2 * np.pi)))
    x_plot = []
    y_plot = []
    for k in range(k_min, k_max + 1):
        phase_k = phases_valid + 2 * np.pi * k
        keep = (phase_k >= ymin) & (phase_k <= ymax)
        if np.any(keep):
            x_plot.append(tt_valid[keep])
            y_plot.append(phase_k[keep])

    if not x_plot:
        return np.array([], dtype=float), np.array([], dtype=float)
    return np.concatenate(x_plot), np.concatenate(y_plot)


def _setup_phase_progression_axis(axis):
    """Configure phase-progression axis guides."""
    if PHASE_PROGRESSION_PLOT not in ('wrapped_strip', 'unwrapped'):
        raise ValueError(f'Unknown PHASE_PROGRESSION_PLOT: {PHASE_PROGRESSION_PLOT}')

    # Use a fixed strip for wrapped phase and autoscale unwrapped traces
    if PHASE_PROGRESSION_PLOT == 'wrapped_strip':
        y_min, y_max = PHASE_PROGRESS_YLIM
    else:
        y_min, y_max = axis.get_ylim()

    pi_k_min = int(np.floor(y_min / np.pi))
    pi_k_max = int(np.ceil(y_max / np.pi))
    for k in range(pi_k_min, pi_k_max + 1):
        axis.axhline(
            k * np.pi,
            color='k' if abs(k) % 2 == 0 else 'r',
            linestyle='--',
            linewidth=1,
            alpha=0.5,
        )
    if PHASE_PROGRESSION_PLOT == 'wrapped_strip':
        axis.set_ylim(y_min, y_max)


def _plot_phase_progression(axis, tt_pulse, phases, color, label):
    """Plot phase progression in the selected display mode."""
    phases = np.asarray(phases, dtype=float)
    valid = np.isfinite(phases)
    tt_valid = np.asarray(tt_pulse, dtype=float)[valid]
    phases_valid = phases[valid]

    # Dispatch to wrapped-strip or unwrapped progression
    if PHASE_PROGRESSION_PLOT == 'wrapped_strip':
        y_min, y_max = PHASE_PROGRESS_YLIM
        xx, yy = _phase_progression_strip_coords(
            tt_valid, phases_valid, y_min, y_max
        )
        axis.plot(
            xx,
            yy,
            linestyle='None',
            marker='o',
            markersize=2.5,
            color=color,
            label=label,
        )
        return

    phase_prog = _phase_progression(phases)
    axis.plot(
        tt_pulse,
        phase_prog,
        'o-',
        color=color,
        markersize=2.5,
        linewidth=1,
        label=label,
    )


def _plot_itc(job_result, out_path):
    """Plot stimulus phases and ITC summaries."""
    tt_pulse = job_result['tt_pulse']
    trace_results = job_result['traces']

    # Build phase-progression, complex-plane, and ITC panels
    fig, ax = plt.subplots(
        1,
        3,
        figsize=(14, 4.5),
        gridspec_kw={'width_ratios': [2.2, 1.1, 1.3]},
    )
    theta = np.linspace(0, 2 * np.pi, 400)
    ax[1].plot(np.cos(theta), np.sin(theta), color='0.8', linewidth=1)

    labels = []
    itc_vals = []
    for idx, result in enumerate(trace_results):
        color = _get_trace_color(idx)
        label = result['label']
        phases = result['phases']
        valid = np.isfinite(phases)
        _plot_phase_progression(ax[0], tt_pulse, phases, color, label)
        ax[1].scatter(
            np.cos(phases[valid]),
            np.sin(phases[valid]),
            color=color,
            s=12,
            alpha=0.25,
        )
        if np.isfinite(result['phi']) and np.isfinite(result['itc']):
            ax[1].plot(
                [0, result['itc'] * np.cos(result['phi'])],
                [0, result['itc'] * np.sin(result['phi'])],
                color=color,
                linewidth=2,
            )
        labels.append(label)
        itc_vals.append(result['itc'])

    _setup_phase_progression_axis(ax[0])

    y_pos = np.arange(len(labels))
    ax[2].barh(y_pos, itc_vals, color=[_get_trace_color(i) for i in y_pos])
    ax[2].set_yticks(y_pos, labels=labels)
    ax[2].set_xlim(0, 1)
    ax[2].set_xlabel('ITC')
    ax[2].set_title('ITC by trace')

    ax[0].set_xlabel('Pulse start (s)')
    ax[0].set_ylabel('Phase progression')
    ax[0].set_title(
        f"Phase progression ({PHASE_PROGRESSION_PLOT}), {job_result['job_label']}"
    )
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].set_aspect('equal', 'box')
    ax[1].set_xlim(-1.1, 1.1)
    ax[1].set_ylim(-1.1, 1.1)
    ax[1].set_xlabel('Real')
    ax[1].set_ylabel('Imag')
    ax[1].set_title('Phase vectors')
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _plot_power(job_result, out_path):
    """Plot mean power versus frequency."""
    trace_results = job_result['traces']

    # Plot one power curve per trace
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for idx, result in enumerate(trace_results):
        ax.plot(
            result['ff'],
            result['power_curve'],
            'o-',
            color=_get_trace_color(idx),
            linewidth=1.2,
            markersize=3,
            label=result['label'],
        )

    ax.axvline(job_result['target_f'], color='k', linestyle='--', linewidth=1)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Mean power')
    ax.set_title(f"Power by frequency, {job_result['job_label']}")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _plot_phase_distr(job_result, out_path):
    """Plot phase distributions at pulse starts."""
    bins = np.linspace(-np.pi, np.pi, PHASE_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])

    # Plot wrapped phase histograms for every trace
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for idx, result in enumerate(job_result['traces']):
        phases = np.asarray(result['phases'], dtype=float)
        phases = phases[np.isfinite(phases)]
        if phases.size == 0:
            continue
        phases = np.angle(np.exp(1j * phases))
        counts, _ = np.histogram(phases, bins=bins)
        probs = counts / counts.sum() if counts.sum() else counts.astype(float)
        if PHASE_SMOOTH_SIGMA:
            probs = gaussian_filter1d(probs, PHASE_SMOOTH_SIGMA, mode='nearest')
            if probs.sum() > 0:
                probs = probs / probs.sum()
        ax.plot(
            centers,
            probs,
            color=_get_trace_color(idx),
            linewidth=1.2,
            label=result['label'],
        )

    ax.set_xlim(-np.pi, np.pi)
    ax.set_xlabel('Phase (rad)')
    ax.set_ylabel('Probability')
    ax.set_title(f"Phase distribution, {job_result['job_label']}")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _analyze_trace(signal, trace_sel, pulse_intervals, tt_pulse, target_f):
    """Run all phase-locking analyses for one 1D signal."""
    tt = np.asarray(signal.coords[TIME_DIM].values, dtype=float)
    x_raw = np.asarray(signal.values, dtype=float)
    x_masked = _mask_pulse_intervals(x_raw, tt, pulse_intervals)
    itc_value, phi, phases = _compute_itc(x_masked, tt, tt_pulse, target_f)
    ff, power_curve, power = _compute_power_curve(x_masked, tt, target_f)
    power_mean, peak_freq, peak_power = _summarize_power(ff, power_curve, power)
    t_epoch, epoch_mean, n_epochs = _get_epoch_mean(x_raw, tt, tt_pulse)
    label = _format_sel(trace_sel) if trace_sel else 'signal'

    # Package trace-level arrays and scalar metrics
    trace_result = {
        'trace_sel': trace_sel,
        'label': label,
        'x_raw': x_raw,
        'x_masked': x_masked,
        'phases': phases,
        'itc': itc_value,
        'phi': phi,
        'ff': ff,
        'power_curve': power_curve,
        'power_mean': power_mean,
        'power_peak_freq': peak_freq,
        'power_peak': peak_power,
        't_epoch': t_epoch,
        'epoch_mean': epoch_mean,
        'n_epochs': n_epochs,
    }
    return trace_result


def _make_metric_row(job_id, job_sel, trace_result, target_f, n_pulses):
    """Build one CSV metrics row."""
    row = {
        key: _as_scalar(value)
        for key, value in job_sel.items()
    }
    row.update({
        key: _as_scalar(value)
        for key, value in trace_result['trace_sel'].items()
    })
    job_id_value = 'avgseed' if job_id is None else int(job_id)
    row.update({
        'job_id': job_id_value,
        'target_f': float(target_f),
        'n_pulses': int(n_pulses),
        'n_valid_phase': int(np.isfinite(trace_result['phases']).sum()),
        'itc': float(trace_result['itc']),
        'phi': float(trace_result['phi']),
        'power_mean': float(trace_result['power_mean']),
        'power_peak_freq': float(trace_result['power_peak_freq']),
        'power_peak': float(trace_result['power_peak']),
        'n_epochs': int(trace_result['n_epochs']),
    })
    if 'n_seed' in trace_result:
        row['n_seed'] = int(trace_result['n_seed'])
    return row


class _MetricWriter:
    """Write metrics incrementally with a stable header."""

    def __init__(self, out_path, fieldnames):
        self.out_path = out_path
        self.fieldnames = fieldnames
        self.row_count = 0
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.fobj = open(self.out_path, 'w', encoding='utf-8', newline='')
        self.writer = csv.DictWriter(
            self.fobj,
            fieldnames=self.fieldnames,
            extrasaction='ignore',
        )
        self.writer.writeheader()

    def write_rows(self, rows):
        """Write metric rows and return the number written."""
        if not rows:
            return 0
        self.writer.writerows(rows)
        self.fobj.flush()
        self.row_count += len(rows)
        return len(rows)

    def close(self):
        """Close the underlying CSV file."""
        self.fobj.close()


def _get_metric_fieldnames(X, job_dims):
    """Build stable CSV field names from batch and trace dimensions."""
    metric_fields = [
        'job_id',
        'target_f',
        'n_pulses',
        'n_valid_phase',
        'itc',
        'phi',
        'power_mean',
        'power_peak_freq',
        'power_peak',
        'n_epochs',
        'n_seed',
    ]
    coord_fields = list(job_dims)
    for dim in _get_trace_dim_names(X, job_dims):
        if dim not in coord_fields:
            coord_fields.append(dim)
    return coord_fields + metric_fields


def _analyze_job(X, job, job_dims, trace_key=None):
    """Run all analyses for one batch job."""
    job_id = int(job['job_id'])
    job_sel = {
        key: _as_scalar(value)
        for key, value in job['sel'].items()
    }
    trace_sel = dict(trace_key) if trace_key is not None else None
    X_job = _prepare_job_xarray(X, job, trace_sel=trace_sel)
    tt = np.asarray(X_job.coords[TIME_DIM].values, dtype=float)
    lock_intervals, mask_intervals, intervals_by_name, netpar_path = (
        _load_pulse_intervals(job_id)
    )
    tt_pulse = _filter_analysis_pulses(lock_intervals, tt)
    pulse_duration = float(np.nanmedian(lock_intervals[:, 1] - lock_intervals[:, 0]))
    target_f = _get_target_f(job_sel)
    job_label = _format_sel(job_sel)

    # Analyze each trace under the same batch job
    traces = []
    metrics = []
    if trace_key is None:
        trace_iter = _iter_trace_signals(X_job, job_dims)
    else:
        trace_iter = [(trace_sel, X_job)]

    for trace_sel, signal in trace_iter:
        trace_result = _analyze_trace(
            signal,
            trace_sel,
            mask_intervals,
            tt_pulse,
            target_f,
        )
        traces.append(trace_result)
        metrics.append(
            _make_metric_row(
                job_id,
                job_sel,
                trace_result,
                target_f,
                len(tt_pulse),
            )
        )

    return {
        'job_id': job_id,
        'job_sel': job_sel,
        'job_label': job_label,
        'target_f': target_f,
        'tt': tt,
        'tt_pulse': tt_pulse,
        'n_pulses': len(tt_pulse),
        'pulse_duration': pulse_duration,
        'pulse_intervals': mask_intervals,
        'lock_pulse_intervals': lock_intervals,
        'pulse_intervals_by_name': intervals_by_name,
        'netpar_path': netpar_path,
        'traces': traces,
        'metrics': metrics,
    }


def _save_job_plots(job_result):
    """Save all per-job summary plots."""
    job_id = job_result['job_id']
    job_dir = _build_job_out_dir(job_id, job_result['job_sel'])
    win = _format_fname_piece(PULSE_PAD)

    # Save the four toy-style summaries for this job
    paths = {
        'signals': job_dir / f'signals_w_{win}.png',
        'itc': job_dir / f'itc_w_{win}.png',
        'power': job_dir / f'pow_fband_w_{win}.png',
        'phase_distr': job_dir / f'phase_distr_w_{win}.png',
    }
    _plot_signals(job_result, paths['signals'])
    _plot_itc(job_result, paths['itc'])
    _plot_power(job_result, paths['power'])
    _plot_phase_distr(job_result, paths['phase_distr'])
    return paths


def _nanmean_arrays(arrays):
    """Average equal-shape arrays while ignoring NaNs."""
    stack = np.stack([np.asarray(arr, dtype=float) for arr in arrays], axis=0)
    valid = np.isfinite(stack)
    count = valid.sum(axis=0)
    total = np.nansum(stack, axis=0)
    out = np.full(count.shape, np.nan, dtype=float)
    np.divide(total, count, out=out, where=count > 0)
    return out


def _nanmean_scalar(values):
    """Average scalar values while ignoring NaNs."""
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(values)
    if not np.any(valid):
        return np.nan
    return float(np.mean(values[valid]))


def _circmean_arrays(arrays):
    """Circular-average equal-shape angle arrays while ignoring NaNs."""
    stack = np.stack([np.asarray(arr, dtype=float) for arr in arrays], axis=0)
    valid = np.isfinite(stack)
    z = np.where(valid, np.exp(1j * stack), 0)
    count = valid.sum(axis=0)
    total = z.sum(axis=0)
    mean_z = np.full(count.shape, np.nan + 1j * np.nan, dtype=complex)
    np.divide(total, count, out=mean_z, where=count > 0)
    return np.where(count > 0, np.angle(mean_z), np.nan)


def _circmean_scalar(values):
    """Circular-average scalar angles while ignoring NaNs."""
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(values)
    if not np.any(valid):
        return np.nan
    mean_z = np.mean(np.exp(1j * values[valid]))
    return float(np.angle(mean_z))


def _avg_job_key(job_sel):
    """Build a seedless grouping key for seed averaging."""
    return tuple(
        (key, _as_scalar(value))
        for key, value in job_sel.items()
        if key != SEED_DIM
    )


def _group_jobs_for_seed_average(jobs):
    """Group batch job dicts by all non-seed coordinates."""
    groups = {}
    for job in jobs:
        key = _avg_job_key(job['sel'])
        groups.setdefault(key, []).append(job)
    return list(groups.values())


def _get_job_f_value(job):
    """Return the frequency coordinate for a batch job."""
    if 'f' in job['sel']:
        return _as_scalar(job['sel']['f'])
    return float(FALLBACK_F)


def _group_jobs_by_f(jobs):
    """Group batch job dicts by target frequency."""
    groups = {}
    for job in jobs:
        key = _get_job_f_value(job)
        groups.setdefault(key, []).append(job)
    return groups


def _avg_trace_result(trace_results, n_seed):
    """Average matching trace results over seeds."""
    ref = trace_results[0]
    phases = _circmean_arrays([result['phases'] for result in trace_results])
    power_curve = _nanmean_arrays([
        result['power_curve']
        for result in trace_results
    ])
    if np.any(np.isfinite(power_curve)):
        peak_idx = int(np.nanargmax(power_curve))
    else:
        peak_idx = None
    if peak_idx is None:
        peak_freq = np.nan
        peak_power = np.nan
    else:
        peak_freq = float(ref['ff'][peak_idx])
        peak_power = float(power_curve[peak_idx])

    # Keep one averaged trace result with the same plotting interface
    trace_result = {
        'trace_sel': ref['trace_sel'],
        'label': ref['label'],
        'x_raw': _nanmean_arrays([result['x_raw'] for result in trace_results]),
        'x_masked': _nanmean_arrays([
            result['x_masked']
            for result in trace_results
        ]),
        'phases': phases,
        'itc': _nanmean_scalar([result['itc'] for result in trace_results]),
        'phi': _circmean_scalar([result['phi'] for result in trace_results]),
        'ff': ref['ff'],
        'power_curve': power_curve,
        'power_mean': _nanmean_scalar([
            result['power_mean']
            for result in trace_results
        ]),
        'power_peak_freq': peak_freq,
        'power_peak': peak_power,
        't_epoch': ref['t_epoch'],
        'epoch_mean': _nanmean_arrays([
            result['epoch_mean']
            for result in trace_results
        ]),
        'n_epochs': int(np.round(_nanmean_scalar([
            result['n_epochs']
            for result in trace_results
        ]))),
        'n_seed': n_seed,
    }
    return trace_result


def _average_job_group(job_results):
    """Average one seed group of analyzed jobs."""
    ref_job = job_results[0]
    job_sel = dict(_avg_job_key(ref_job['job_sel']))
    n_seed = len(job_results)
    target_f = _get_target_f(job_sel)
    label_base = _format_sel(job_sel)
    if label_base:
        job_label = f'{label_base}, n_seed={n_seed}'
    else:
        job_label = f'n_seed={n_seed}'
    trace_groups = {}

    # Group matching traces across seed jobs
    for job_result in job_results:
        for trace_result in job_result['traces']:
            trace_key = tuple(trace_result['trace_sel'].items())
            trace_groups.setdefault(trace_key, []).append(trace_result)

    traces = [
        _avg_trace_result(trace_results, n_seed)
        for trace_results in trace_groups.values()
    ]
    metrics = [
        _make_metric_row(
            None,
            job_sel,
            trace_result,
            target_f,
            len(ref_job['tt_pulse']),
        )
        for trace_result in traces
    ]
    return {
        'job_id': None,
        'job_sel': job_sel,
        'job_label': job_label,
        'target_f': target_f,
        'tt': ref_job['tt'],
        'tt_pulse': ref_job['tt_pulse'],
        'n_pulses': len(ref_job['tt_pulse']),
        'pulse_duration': _nanmean_scalar([
            job_result['pulse_duration']
            for job_result in job_results
        ]),
        'pulse_intervals': ref_job['pulse_intervals'],
        'lock_pulse_intervals': ref_job['lock_pulse_intervals'],
        'pulse_intervals_by_name': ref_job['pulse_intervals_by_name'],
        'netpar_path': None,
        'traces': traces,
        'metrics': metrics,
        'n_seed': n_seed,
    }


def _average_results_over_seeds(job_results):
    """Average analyzed job results over the seed dimension."""
    groups = {}
    for job_result in job_results:
        key = _avg_job_key(job_result['job_sel'])
        groups.setdefault(key, []).append(job_result)
    return [
        _average_job_group(group_jobs)
        for group_jobs in groups.values()
    ]


def _print_job_progress(job_result):
    """Print one analyzed job progress line."""
    print(
        f"Analyzed job {job_result['job_id']:05d}: "
        f"{job_result['job_label']}, traces={len(job_result['traces'])}",
        flush=True,
    )


def _iter_result_jobs(X, jobs, job_dims, trace_key=None):
    """Yield job-style results one at a time."""
    if AVG_OVER_SEEDS:
        for job_group in _group_jobs_for_seed_average(jobs):
            job_results = []
            for job in job_group:
                job_result = _analyze_job(
                    X,
                    job,
                    job_dims,
                    trace_key=trace_key,
                )
                job_results.append(job_result)
                _print_job_progress(job_result)
            yield _average_job_group(job_results), len(job_results)
        return

    for job in jobs:
        job_result = _analyze_job(
            X,
            job,
            job_dims,
            trace_key=trace_key,
        )
        _print_job_progress(job_result)
        yield job_result, 1


def _get_combined_plot_groups(job_results):
    """Group trace results by frequency and trace selector."""
    groups = {}
    for job_result in job_results:
        f_value = job_result['job_sel'].get('f', job_result['target_f'])
        for trace_result in job_result['traces']:
            trace_sel = trace_result['trace_sel']
            trace_key = tuple(trace_sel.items())
            key = (_as_scalar(f_value), trace_key)
            if key not in groups:
                groups[key] = {
                    'f': _as_scalar(f_value),
                    'trace_sel': trace_sel,
                    'items': [],
                }
            groups[key]['items'].append({
                'job_result': job_result,
                'trace_result': trace_result,
                'label': _format_condition_label(job_result['job_sel']),
            })
    return groups


def _get_combined_title(group, title_prefix):
    """Build a title for one combined trace plot."""
    f_value = _format_value(group['f'])
    trace_label = _format_sel(group['trace_sel']) if group['trace_sel'] else 'signal'
    return f'{title_prefix}, f={f_value}, {trace_label}'


def _get_combined_paths(group):
    """Build combined output paths for one frequency and trace."""
    win = _format_fname_piece(PULSE_PAD)
    f_dir = OUT_DIR / 'combined' / f"f_{_format_fname_piece(group['f'])}"
    fname = f"{_get_trace_file_stem(group['trace_sel'])}.png"
    paths = {
        'signals': f_dir / f'signals_w_{win}' / fname,
        'itc': f_dir / f'itc_w_{win}' / fname,
        'power': f_dir / f'pow_fband_w_{win}' / fname,
        'phase_distr': f_dir / f'phase_distr_w_{win}' / fname,
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def _plot_combined_signals(group, out_path):
    """Plot one trace across seed and amplitude conditions."""
    ref_job = group['items'][0]['job_result']
    pulse_duration = ref_job['pulse_duration']
    t0, t1 = PLOT_T_WIN

    # Build the raw and epoch panels
    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=False)
    for idx, item in enumerate(group['items']):
        job_result = item['job_result']
        trace_result = item['trace_result']
        tt = job_result['tt']
        keep = (tt >= t0) & (tt <= t1)
        color = _get_trace_color(idx)
        ax[0].plot(
            tt[keep],
            trace_result['x_raw'][keep],
            color=color,
            linewidth=1,
            label=item['label'],
        )
        ax[1].plot(
            trace_result['t_epoch'],
            trace_result['epoch_mean'],
            color=color,
            linewidth=1.2,
            label=item['label'],
        )

    # Mark both pulse streams from the first condition
    _plot_pulse_starts(ax[0], ref_job['pulse_intervals_by_name'], t0, t1)
    ax[1].axvline(0, color='k', linestyle='--', linewidth=1)
    ax[1].axvspan(
        -PULSE_PAD,
        pulse_duration + PULSE_PAD,
        color='0.8',
        alpha=0.4,
    )
    ax[1].axvspan(0, pulse_duration, color='0.6', alpha=0.2)

    ax[0].set_xlim(t0, t1)
    ax[0].set_xlabel('Time (s)')
    ax[0].set_ylabel('Signal')
    ax[0].set_title(_get_combined_title(group, 'Signals'))
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].set_xlabel('Time from pulse start (s)')
    ax[1].set_ylabel('Pulse-triggered mean')
    ax[1].set_title(f"Pulse-triggered averages, n={ref_job['n_pulses']}")
    ax[1].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _plot_combined_itc(group, out_path):
    """Plot phase locking across seed and amplitude conditions."""
    fig, ax = plt.subplots(
        1,
        3,
        figsize=(14, 4.5),
        gridspec_kw={'width_ratios': [2.2, 1.1, 1.3]},
    )
    theta = np.linspace(0, 2 * np.pi, 400)
    ax[1].plot(np.cos(theta), np.sin(theta), color='0.8', linewidth=1)

    labels = []
    itc_vals = []
    for idx, item in enumerate(group['items']):
        job_result = item['job_result']
        trace_result = item['trace_result']
        phases = trace_result['phases']
        valid = np.isfinite(phases)
        color = _get_trace_color(idx)
        _plot_phase_progression(
            ax[0],
            job_result['tt_pulse'],
            phases,
            color,
            item['label'],
        )
        ax[1].scatter(
            np.cos(phases[valid]),
            np.sin(phases[valid]),
            color=color,
            s=12,
            alpha=0.25,
        )
        if np.isfinite(trace_result['phi']) and np.isfinite(trace_result['itc']):
            ax[1].plot(
                [0, trace_result['itc'] * np.cos(trace_result['phi'])],
                [0, trace_result['itc'] * np.sin(trace_result['phi'])],
                color=color,
                linewidth=2,
            )
        labels.append(item['label'])
        itc_vals.append(trace_result['itc'])

    _setup_phase_progression_axis(ax[0])

    y_pos = np.arange(len(labels))
    ax[2].barh(y_pos, itc_vals, color=[_get_trace_color(i) for i in y_pos])
    ax[2].set_yticks(y_pos)
    ax[2].set_yticklabels([])
    for y, label in zip(y_pos, labels):
        ax[2].text(
            0.02,
            y,
            label,
            va='center',
            ha='left',
            fontsize=8,
            bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': 0.65},
        )
    ax[2].set_xlim(0, 1)
    ax[2].set_xlabel('ITC')
    ax[2].set_title('ITC by condition')

    ax[0].set_xlabel('Pulse start (s)')
    ax[0].set_ylabel('Phase progression')
    ax[0].set_title(
        _get_combined_title(
            group,
            f'Phase progression ({PHASE_PROGRESSION_PLOT})',
        )
    )
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].set_aspect('equal', 'box')
    ax[1].set_xlim(-1.1, 1.1)
    ax[1].set_ylim(-1.1, 1.1)
    ax[1].set_xlabel('Real')
    ax[1].set_ylabel('Imag')
    ax[1].set_title('Phase vectors')
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _plot_combined_power(group, out_path):
    """Plot power curves across seed and amplitude conditions."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for idx, item in enumerate(group['items']):
        trace_result = item['trace_result']
        ax.plot(
            trace_result['ff'],
            trace_result['power_curve'],
            'o-',
            color=_get_trace_color(idx),
            linewidth=1.2,
            markersize=3,
            label=item['label'],
        )

    ax.axvline(group['f'], color='k', linestyle='--', linewidth=1)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Mean power')
    ax.set_title(_get_combined_title(group, 'Power by frequency'))
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _plot_combined_phase_distr(group, out_path):
    """Plot phase distributions across seed and amplitude conditions."""
    bins = np.linspace(-np.pi, np.pi, PHASE_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])

    # Plot one distribution per seed and amplitude condition
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for idx, item in enumerate(group['items']):
        phases = np.asarray(item['trace_result']['phases'], dtype=float)
        phases = phases[np.isfinite(phases)]
        if phases.size == 0:
            continue
        phases = np.angle(np.exp(1j * phases))
        counts, _ = np.histogram(phases, bins=bins)
        probs = counts / counts.sum() if counts.sum() else counts.astype(float)
        if PHASE_SMOOTH_SIGMA:
            probs = gaussian_filter1d(probs, PHASE_SMOOTH_SIGMA, mode='nearest')
            if probs.sum() > 0:
                probs = probs / probs.sum()
        ax.plot(
            centers,
            probs,
            color=_get_trace_color(idx),
            linewidth=1.2,
            label=item['label'],
        )

    ax.set_xlim(-np.pi, np.pi)
    ax.set_xlabel('Phase (rad)')
    ax.set_ylabel('Probability')
    ax.set_title(_get_combined_title(group, 'Phase distribution'))
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def _save_combined_plot_group(group):
    """Save one combined plot group."""
    paths = _get_combined_paths(group)
    _plot_combined_signals(group, paths['signals'])
    _plot_combined_itc(group, paths['itc'])
    _plot_combined_power(group, paths['power'])
    _plot_combined_phase_distr(group, paths['phase_distr'])
    return paths


def _save_combined_plots(job_results):
    """Save plots grouped by frequency, trace, and condition."""
    groups = _get_combined_plot_groups(job_results)
    all_paths = []

    # Save one file per frequency, plot type, and trace selector
    for group in groups.values():
        paths = _save_combined_plot_group(group)
        all_paths.append(paths)
    return all_paths


def _save_metrics(metrics):
    """Save all trace-level metrics to CSV."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / 'phase_metrics.csv'
    metric_fields = [
        'job_id',
        'target_f',
        'n_pulses',
        'n_valid_phase',
        'itc',
        'phi',
        'power_mean',
        'power_peak_freq',
        'power_peak',
        'n_epochs',
    ]
    all_fields = {key for row in metrics for key in row}
    coord_fields = sorted(all_fields.difference(metric_fields))
    fieldnames = coord_fields + metric_fields

    # Write scalar rows with stable field order
    with open(out_path, 'w', encoding='utf-8', newline='') as fobj:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics)
    return out_path


def _get_trace_key(trace_sel):
    """Convert a trace selector to a stable tuple key."""
    return tuple(trace_sel.items())


def _run_per_job_branch(X, jobs, job_dims, metrics_writer):
    """Run and save the per-job output branch."""
    saved_paths = []
    source_jobs = 0
    metric_rows = 0

    # Save each job-style result as soon as it is ready
    for job_result, n_source in _iter_result_jobs(X, jobs, job_dims):
        source_jobs += n_source
        paths = _save_job_plots(job_result)
        saved_paths.append(paths)
        if metrics_writer is not None:
            metric_rows += metrics_writer.write_rows(job_result['metrics'])
        result_stem = _get_job_dir_stem(
            job_result['job_id'],
            job_result['job_sel'],
        )
        print(
            f"Saved per_job {result_stem}: "
            f"traces={len(job_result['traces'])}",
            flush=True,
        )

    return {
        'source_jobs': source_jobs,
        'saved_groups': len(saved_paths),
        'metric_rows': metric_rows,
    }


def _run_combined_branch(X, jobs, job_dims, trace_selectors, metrics_writer):
    """Run and save the combined output branch."""
    saved_paths = []
    source_jobs = 0
    metric_rows = 0
    jobs_by_f = _group_jobs_by_f(jobs)

    # Build and save one combined trace group at a time
    for f_value, f_jobs in jobs_by_f.items():
        for trace_sel in trace_selectors:
            trace_key = _get_trace_key(trace_sel)
            trace_label = _format_sel(trace_sel) if trace_sel else 'signal'
            print(
                f"Combined group f={_format_value(f_value)}, "
                f"{trace_label}",
                flush=True,
            )
            group = {
                'f': f_value,
                'trace_sel': trace_sel,
                'items': [],
            }
            result_iter = _iter_result_jobs(
                X,
                f_jobs,
                job_dims,
                trace_key=trace_key,
            )
            for job_result, n_source in result_iter:
                source_jobs += n_source
                if not job_result['traces']:
                    continue
                trace_result = job_result['traces'][0]
                group['items'].append({
                    'job_result': job_result,
                    'trace_result': trace_result,
                    'label': _format_condition_label(job_result['job_sel']),
                })
                if metrics_writer is not None:
                    metric_rows += metrics_writer.write_rows(job_result['metrics'])

            if not group['items']:
                continue
            paths = _save_combined_plot_group(group)
            saved_paths.append(paths)
            print(
                f"Saved combined f={_format_value(f_value)}, "
                f"{trace_label}: items={len(group['items'])}",
                flush=True,
            )

    return {
        'source_jobs': source_jobs,
        'saved_groups': len(saved_paths),
        'metric_rows': metric_rows,
    }


def _run_signal_kind(signal_kind):
    """Run batch phase-locking analysis for one signal kind."""
    _set_signal_kind(signal_kind)
    if not RUN_PER_JOB and not RUN_COMBINED:
        raise ValueError('At least one of RUN_PER_JOB or RUN_COMBINED should be on')

    print(f'\nSignal kind: {SIGNAL_KIND}', flush=True)
    print(f'Input: {INPUT_PATH}', flush=True)
    X = _open_input_xarray()
    metrics_writer = None
    try:
        job_dims = _get_job_dim_names(X)
        job_id_xr = X.coords[JOB_ID_COORD]
        jobs = list(iter_batch_jobs(job_id_xr))
        trace_selectors = _get_trace_selectors(X, job_dims)
        metric_fields = _get_metric_fieldnames(X, job_dims)
        metrics_writer = _MetricWriter(
            OUT_DIR / 'phase_metrics.csv',
            metric_fields,
        )
        print(
            f'Jobs={len(jobs)}, requested traces={len(trace_selectors)}, '
            f'avgseed={AVG_OVER_SEEDS}',
            flush=True,
        )

        per_job_counts = {
            'source_jobs': 0,
            'saved_groups': 0,
            'metric_rows': 0,
        }
        if RUN_PER_JOB:
            per_job_counts = _run_per_job_branch(
                X,
                jobs,
                job_dims,
                metrics_writer,
            )

        # Avoid duplicate metrics when per-job and combined branches both run
        combined_writer = None if RUN_PER_JOB else metrics_writer
        combined_counts = {
            'source_jobs': 0,
            'saved_groups': 0,
            'metric_rows': 0,
        }
        if RUN_COMBINED:
            combined_counts = _run_combined_branch(
                X,
                jobs,
                job_dims,
                trace_selectors,
                combined_writer,
            )

        print(f"Saved {metrics_writer.out_path}", flush=True)
        print(
            f"Per-job groups: {per_job_counts['saved_groups']}, "
            f"combined groups: {combined_counts['saved_groups']}",
            flush=True,
        )
        print(
            f"Source job analyses: "
            f"{per_job_counts['source_jobs'] + combined_counts['source_jobs']}",
            flush=True,
        )
        print(f'Metric rows: {metrics_writer.row_count}', flush=True)
    finally:
        if metrics_writer is not None:
            metrics_writer.close()
        X.close()


def main():
    """Run configured batch phase-locking analyses."""
    for signal_kind in SIGNAL_KINDS:
        _run_signal_kind(signal_kind)


if __name__ == '__main__':
    main()
