import csv
import hashlib
import json
import os
import sys
from pathlib import Path


# Set import paths before importing local helpers
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
DIR_THIS = Path(__file__).resolve().parent
for path in (DIR_REPO, DIR_EXTERNAL, DIR_THIS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


# Keep matplotlib cache next to scratch outputs
EXP_NAME = (
    'exp_L2_nseed_1_f_5_amp1_0_0.04_4_amp2_0_0.3_3_dt0_0_20_t_5.0_50.0_lfp_0_300_50_ictrl_ee5_efb10_wmult_0.25_ee_0.5_2pulse_IT2_AMPA_PV2_NMDA_d_20_c_25_r_1000_0_t0_5000_jit_0_tlast_45000.0'
)
DIRPATH_ARTIFACT = (
    DIR_REPO / 'dev_scratch' / 'artifacts' /
    'net_2pulses_var_seed_f_amps_dt0' / EXP_NAME
)
DIRPATH_EXP = DIRPATH_ARTIFACT
OUT_DIR = DIR_THIS / 'artifacts' / EXP_NAME
os.environ.setdefault('MPLCONFIGDIR', str(OUT_DIR / 'mpl_cache'))

from phase_analysis_utils import (
    TIME_DIM,
    add_phase_condition_columns_by,
    as_scalar,
    compute_band_metrics,
    compute_complex_spectrogram,
    compute_epoch_mean,
    compute_power_curve,
    concat_pulse_intervals,
    condition_metric_rows_by,
    filter_analysis_pulses,
    fit_event_coefficients,
    format_fname_piece,
    format_value,
    get_jobs,
    get_pulse_pad_pair,
    get_target_f,
    get_trace_dim,
    get_trace_values,
    load_complex_spectrogram_nc_by,
    load_epoch_signals_nc_by,
    load_named_pulse_intervals,
    load_phase_events_nc_by,
    make_blocks,
    mask_pulse_intervals,
    open_signal_xarray,
    phase_summary_by,
    plot_band_metrics_by,
    plot_coeff_clouds_by,
    plot_metric_grid,
    plot_epoch_signal_metric_grid,
    plot_epoch_signals_fit_by,
    plot_epoch_signals_by,
    plot_phase_density_by,
    plot_phase_metric_grid,
    plot_spectra_by,
    plot_spectra_logratio_grid,
    pooled_condition_metric_rows,
    pooled_phase_summary,
    pooled_spectrum_summary,
    save_complex_spectrogram_nc_by,
    save_epoch_signals_nc_by,
    save_phase_events_nc_by,
    spectrum_summary_from_spectrograms,
    spectrum_summary_by,
)

import numpy as np


SIGNAL_KIND = 'rates'
#POP_VALUES = ['IT2']
POP_VALUES = 'all'
Y_VALUES = [100, 200]
NEED_RECALC = 0
INPUT_PATHS = {
    'rates': DIRPATH_ARTIFACT / 'rates_xr_combined.nc',
    'lfp': DIRPATH_ARTIFACT / 'lfp_xr_combined.nc',
    'csd': DIRPATH_ARTIFACT / 'csd_xr_combined.nc',
}
NETPAR_DIR = DIRPATH_EXP / 'netpar'

LOCK_PULSE_NAME = 'PulseSeq1'
MASK_PULSE_NAMES = ('PulseSeq1', 'PulseSeq2')
COND_DIMS = ('amp1', 'amp2')
SLICE_DIMS = ('f', 'dt0')
FALLBACK_PULSE_T0 = 5
FALLBACK_PULSE_T_LAST = 45
FALLBACK_PULSE_DURATION = 0.02

FALLBACK_F = 5
ANALYSIS_T0 = 10
PULSE_PAD = (0.02, 0.02)
BLOCK_DURATION = 5

N_CYCLES = 3
POWER_F_MARGIN = 5
POWER_DF = 1
POWER_OVERLAP = 0.5
FIT_INTERCEPT = 1
FIT_RCOND = None
EXCLUDE_EDGES = 1
MIN_VALID_MASS_FRAC = 0.5

BROAD_BAND = (2, 8)
TARGET_HALF_WIDTH = 0.5
PHASE_BINS = 32
PHASE_SMOOTH_SIGMA = 1
SAVE_EPOCH_SIGNALS = 1
EPOCH_T_WIN = (-0.6, 0.6)
EPOCH_SUBTRACT_GLOBAL_MEAN = 0

SIG_METRICS_T = [-40, -20, 0]

INTERP_OUTLIERS = 0
OUTLIER_KWARGS = {
    'z_thresh': 8,
    'rel_neighbor_thresh': 5,
}

PARAM_HASH_LEN = 8
DIRNAME_PARAM_KEYS = {
    'trace': 'trace_values',
    'pad': 'pulse_pad',
    #'blk': 'block_duration',
    #'fmarg': 'power_f_margin',
    #'lock': 'lock_pulse_name',
    'zsub': 'epoch_subtract_global_mean'
}


def _json_ready(value):
    """Convert config values to JSON-ready objects."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _json_ready(val)
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_ready(val) for val in value]
    return as_scalar(value)


def _get_all_params():
    """Return all run parameters used for hashing and JSON output."""
    return {
        'exp_name': EXP_NAME,
        'dirpath_exp': DIRPATH_EXP,
        'dirpath_artifact': DIRPATH_ARTIFACT,
        'signal_kind': SIGNAL_KIND,
        'pop_values': POP_VALUES,
        'y_values': Y_VALUES,
        'trace_values': _get_trace_values_label(),
        'need_recalc': NEED_RECALC,
        'input_paths': INPUT_PATHS,
        'netpar_dir': NETPAR_DIR,
        'lock_pulse_name': LOCK_PULSE_NAME,
        'mask_pulse_names': MASK_PULSE_NAMES,
        'cond_dims': COND_DIMS,
        'slice_dims': SLICE_DIMS,
        'fallback_pulse_t0': FALLBACK_PULSE_T0,
        'fallback_pulse_t_last': FALLBACK_PULSE_T_LAST,
        'fallback_pulse_duration': FALLBACK_PULSE_DURATION,
        'fallback_f': FALLBACK_F,
        'analysis_t0': ANALYSIS_T0,
        'pulse_pad': PULSE_PAD,
        'block_duration': BLOCK_DURATION,
        'n_cycles': N_CYCLES,
        'power_f_margin': POWER_F_MARGIN,
        'power_df': POWER_DF,
        'power_overlap': POWER_OVERLAP,
        'fit_intercept': FIT_INTERCEPT,
        'fit_rcond': FIT_RCOND,
        'exclude_edges': EXCLUDE_EDGES,
        'min_valid_mass_frac': MIN_VALID_MASS_FRAC,
        'broad_band': BROAD_BAND,
        'target_half_width': TARGET_HALF_WIDTH,
        'phase_bins': PHASE_BINS,
        'phase_smooth_sigma': PHASE_SMOOTH_SIGMA,
        'save_epoch_signals': SAVE_EPOCH_SIGNALS,
        'epoch_t_win': EPOCH_T_WIN,
        'epoch_subtract_global_mean': EPOCH_SUBTRACT_GLOBAL_MEAN,
        'sig_metrics_t': SIG_METRICS_T,
        'interp_outliers': INTERP_OUTLIERS,
        'outlier_kwargs': OUTLIER_KWARGS,
    }


def _get_params_hash(params):
    """Return a short stable hash from all parameters."""
    hash_params = dict(params)
    for key in (
        'need_recalc',
    ):
        hash_params.pop(key, None)
    text = json.dumps(_json_ready(hash_params), sort_keys=True)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:PARAM_HASH_LEN]


def _format_dir_value(value):
    """Format one dirname parameter value."""
    value = _json_ready(value)
    if value is None:
        return 'all'
    if isinstance(value, list):
        return '-'.join(_format_dir_value(item) for item in value)
    text = format_value(value)
    return str(text).replace('/', '-').replace(' ', '')


def _get_dirname_params(params):
    """Choose parameters shown in the output dirname."""
    return {
        label: params[key]
        for label, key in DIRNAME_PARAM_KEYS.items()
    }


def _get_trace_values_label():
    """Return the configured trace values for labels and dirnames."""
    if SIGNAL_KIND == 'rates':
        return POP_VALUES
    return Y_VALUES


def _get_signal_dirname(params):
    """Build the signal output dirname from selected params and full hash."""
    dirname_params = _get_dirname_params(params)
    pieces = [params['signal_kind']]
    for label, value in dirname_params.items():
        pieces.append(f'{label}_{_format_dir_value(value)}')
    pieces.append(f"h_{_get_params_hash(params)}")
    return '_'.join(pieces)


def _get_signal_dir(params=None):
    """Return the parameterized signal output directory."""
    params = _get_all_params() if params is None else params
    return OUT_DIR / _get_signal_dirname(params)


def _get_slice_dir(signal_dir, f_value, dt0_value):
    """Return one f/dt0 output directory."""
    f_part = format_fname_piece(f_value)
    dt0_part = format_fname_piece(dt0_value)
    return signal_dir / f'f_{f_part}_dt0_{dt0_part}'


def _save_params_json(out_dir, params, f_value=None, dt0_value=None):
    """Save full run parameters next to analysis outputs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    params_out = dict(params)
    if f_value is not None:
        params_out['slice_f'] = f_value
    if dt0_value is not None:
        params_out['slice_dt0'] = dt0_value
    out_path = out_dir / 'params.json'
    with open(out_path, 'w', encoding='utf-8') as fobj:
        json.dump(_json_ready(params_out), fobj, indent=2, sort_keys=True)
        fobj.write('\n')
    return out_path


def _get_trace_values_config():
    """Return the configured trace selection."""
    if SIGNAL_KIND == 'rates':
        values = POP_VALUES
    else:
        values = Y_VALUES

    # Treat the all keyword as no explicit xarray selection
    if values == 'all':
        return None
    if isinstance(values, (list, tuple)) and 'all' in values:
        return None
    return values


def _get_fit_params():
    """Return fit parameters used by spectra and event coefficients."""
    return {
        'n_cycles': N_CYCLES,
        'power_f_margin': POWER_F_MARGIN,
        'power_df': POWER_DF,
        'power_overlap': POWER_OVERLAP,
        'fit_intercept': FIT_INTERCEPT,
        'fit_rcond': FIT_RCOND,
        'exclude_edges': EXCLUDE_EDGES,
        'min_valid_mass_frac': MIN_VALID_MASS_FRAC,
    }


def _base_record(job, trace_dim, trace_value, target_f):
    """Build common CSV and grouping fields for one job trace."""
    job_sel = {
        key: as_scalar(value)
        for key, value in job['sel'].items()
    }
    return {
        'job_id': int(job['job_id']),
        'seed_main': job_sel['seed_main'],
        'f': target_f,
        'dt0': job_sel['dt0'],
        'amp1': float(job_sel['amp1']),
        'amp2': float(job_sel['amp2']),
        trace_dim: trace_value,
    }


def _select_job_trace(X, job, trace_dim, trace_value):
    """Select one job and trace from the combined xarray."""
    X_job = X.isel(job['isel'])
    return X_job.sel({trace_dim: trace_value})


def _fallback_pulse_intervals(target_f, dt0_value):
    """Build two pulse schedules when netParams are unavailable."""
    starts1 = np.arange(
        FALLBACK_PULSE_T0,
        FALLBACK_PULSE_T_LAST,
        1 / float(target_f),
    )
    starts2 = starts1 + float(dt0_value) / 1000
    return {
        'PulseSeq1': np.column_stack([
            starts1,
            starts1 + FALLBACK_PULSE_DURATION,
        ]),
        'PulseSeq2': np.column_stack([
            starts2,
            starts2 + FALLBACK_PULSE_DURATION,
        ]),
    }


def _analyze_blocks(x_masked, tt, blocks, base, target_f, fit_params):
    """Analyze all blocks for one job trace."""
    spectrum_records = []
    block_rows = []
    for block in blocks:
        keep = (tt >= block['block_t0']) & (tt < block['block_t1'])
        if np.sum(keep) < 2:
            continue
        ff, spectrum = compute_power_curve(
            x_masked[keep],
            tt[keep],
            target_f,
            fit_params,
        )
        metrics = compute_band_metrics(
            ff,
            spectrum,
            target_f,
            BROAD_BAND,
            TARGET_HALF_WIDTH,
        )

        # Store full spectra in memory only for the active pop/f/dt0 slice
        spec_record = dict(base)
        spec_record.update(block)
        spec_record.update({
            'ff': ff,
            'spectrum': spectrum,
        })
        spectrum_records.append(spec_record)

        row = dict(base)
        row.update(block)
        row.update(metrics)
        row['n_valid_time'] = int(np.isfinite(x_masked[keep]).sum())
        block_rows.append(row)
    return spectrum_records, block_rows


def _analyze_job_trace(X, job, trace_dim, trace_value, fit_params):
    """Analyze one two-stream job and trace."""
    signal = _select_job_trace(X, job, trace_dim, trace_value)
    tt = np.asarray(signal.coords[TIME_DIM].values, dtype=float)
    x = np.asarray(signal.values, dtype=float)
    target_f = get_target_f(job['sel'], FALLBACK_F)
    base = _base_record(job, trace_dim, trace_value, target_f)

    # Load stream-specific events, then mask both pulse streams
    try:
        intervals_by_name = load_named_pulse_intervals(
            NETPAR_DIR,
            int(job['job_id']),
            MASK_PULSE_NAMES,
        )
    except FileNotFoundError:
        intervals_by_name = _fallback_pulse_intervals(target_f, base['dt0'])
    mask_intervals = concat_pulse_intervals(intervals_by_name, MASK_PULSE_NAMES)
    lock_intervals = intervals_by_name[LOCK_PULSE_NAME]
    x_masked = mask_pulse_intervals(x, tt, mask_intervals, PULSE_PAD, ANALYSIS_T0)
    tt_pulse = filter_analysis_pulses(lock_intervals, tt, ANALYSIS_T0)
    blocks = make_blocks(tt, ANALYSIS_T0, BLOCK_DURATION, target_f)
    with np.errstate(invalid='ignore'):
        global_mean = float(np.nanmean(x_masked))

    spectrum_records, block_rows = _analyze_blocks(
        x_masked,
        tt,
        blocks,
        base,
        target_f,
        fit_params,
    )
    phases, coeffs = phase_fit_event_coefficients(
        x_masked,
        tt,
        tt_pulse,
        target_f,
        fit_params,
    )
    t_fit, ff_fit, coeff_tf = compute_complex_spectrogram(
        x_masked,
        tt,
        target_f,
        fit_params,
    )
    t_epoch, epoch_mean, n_epochs = compute_epoch_mean(
        x,
        tt,
        tt_pulse,
        EPOCH_T_WIN,
    )
    if EPOCH_SUBTRACT_GLOBAL_MEAN:
        epoch_plot = epoch_mean - global_mean
    else:
        epoch_plot = epoch_mean.copy()

    # Keep arrays only for the active pop/f/dt0 slice
    phase_record = dict(base)
    phase_record.update({
        'phases': phases,
        'coeffs': coeffs,
        'event_time': tt_pulse,
        'n_pulses': int(tt_pulse.size),
        'n_valid_phase': int(np.isfinite(phases).sum()),
    })
    spect_record = dict(base)
    spect_record.update({
        'freq': ff_fit,
        't_fit': t_fit,
        'coeff': coeff_tf,
    })
    epoch_record = dict(base)
    epoch_record.update({
        't_epoch': t_epoch,
        'epoch_mean': epoch_mean,
        'epoch_plot': epoch_plot,
        'global_mean': global_mean,
        'n_epochs': n_epochs,
    })
    return spectrum_records, block_rows, [phase_record], [spect_record], [epoch_record]


def phase_fit_event_coefficients(x_masked, tt, tt_pulse, target_f, fit_params):
    """Fit pulse-start phase and coefficient through the shared helper."""
    return fit_event_coefficients(
        x_masked,
        tt,
        tt_pulse,
        target_f,
        fit_params,
    )


def _get_slice_jobs(jobs, f_value, dt0_value):
    """Select jobs that belong to one f/dt0 slice."""
    out = []
    for job in jobs:
        job_f = float(as_scalar(job['sel'].get('f', FALLBACK_F)))
        job_dt0 = as_scalar(job['sel']['dt0'])
        if np.isclose(job_f, f_value) and job_dt0 == dt0_value:
            out.append(job)
    return out


def _get_slice_values(X):
    """Return available f and dt0 values from the input xarray."""
    f_values = [float(as_scalar(value)) for value in X.coords['f'].values]
    dt0_values = [as_scalar(value) for value in X.coords['dt0'].values]
    return f_values, dt0_values


def _round_csv_value(value, ndigits=4):
    """Round numeric CSV values for easier reading."""
    value = as_scalar(value)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return value
        return round(float(value), ndigits)
    return value


def _parse_csv_value(key, value):
    """Parse one CSV value into a practical Python scalar."""
    if value == '':
        return np.nan
    if key == 'pop':
        return value
    try:
        number = float(value)
    except ValueError:
        return value
    if key in ('job_id', 'seed_main', 'block_idx', 'n_seed', 'n_blocks',
               'n_pulses', 'n_valid_phase', 'n_valid_time',
               'n_source_conditions'):
        return int(round(number))
    return number


def _read_csv_rows(path):
    """Read rounded CSV rows back into dictionaries."""
    rows = []
    with open(path, 'r', encoding='utf-8', newline='') as fobj:
        reader = csv.DictReader(fobj)
        for row in reader:
            rows.append({
                key: _parse_csv_value(key, value)
                for key, value in row.items()
            })
    return rows


def _write_csv_rows(path, rows):
    """Write parsed CSV rows back to disk."""
    if not rows:
        with open(path, 'w', encoding='utf-8', newline=''):
            return
    fieldnames = list(rows[0].keys())
    with open(path, 'w', encoding='utf-8', newline='') as fobj:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _append_csv_rows(path, rows, ndigits=4):
    """Append rows to a CSV file, writing a header when needed."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    need_header = not path.exists() or path.stat().st_size == 0
    fieldnames = list(rows[0].keys())
    with open(path, 'a', encoding='utf-8', newline='') as fobj:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames)
        if need_header:
            writer.writeheader()
        for row in rows:
            out = {
                key: _round_csv_value(value, ndigits=ndigits)
                for key, value in row.items()
            }
            writer.writerow(out)


def _reset_slice_outputs(slice_dir):
    """Remove stream-written summary files from an earlier run."""
    for path in (
        slice_dir / 'block_metrics.csv',
        slice_dir / 'condition_metrics.csv',
        slice_dir / 'pooled_amp1_metrics.csv',
        slice_dir / 'pooled_amp2_metrics.csv',
    ):
        if path.exists():
            path.unlink()


def _trace_nc_paths(slice_dir, trace_value):
    """Return saved NetCDF paths for one trace."""
    stem = format_fname_piece(trace_value)
    return {
        'phase': slice_dir / 'phase_events' / f'{stem}.nc',
        'spectrogram': slice_dir / 'complex_spectrogram' / f'{stem}.nc',
        'epoch': slice_dir / 'epoch_signals' / f'{stem}.nc',
    }


def _row_matches_slice(row, trace_dim, trace_value, f_value, dt0_value):
    """Check whether one CSV row belongs to a trace/f/dt0 slice."""
    return (
        row.get(trace_dim) == trace_value and
        np.isclose(float(row.get('f', np.nan)), float(f_value)) and
        row.get('dt0') == dt0_value
    )


def _drop_trace_rows(path, trace_dim, trace_value, f_value, dt0_value):
    """Remove one trace/f/dt0 slice from a CSV if present."""
    if not path.exists():
        return
    rows = [
        row for row in _read_csv_rows(path)
        if not _row_matches_slice(row, trace_dim, trace_value, f_value, dt0_value)
    ]
    _write_csv_rows(path, rows)


def _drop_trace_table_rows(slice_dir, trace_dim, trace_value, f_value, dt0_value):
    """Remove one trace from all slice-level CSV tables."""
    for name in (
        'block_metrics.csv',
        'condition_metrics.csv',
        'pooled_amp1_metrics.csv',
        'pooled_amp2_metrics.csv',
    ):
        _drop_trace_rows(slice_dir / name, trace_dim, trace_value, f_value, dt0_value)


def _load_cached_trace(slice_dir, trace_dim, trace_value, f_value, dt0_value):
    """Load cached arrays and tables for one trace when all exist."""
    paths = _trace_nc_paths(slice_dir, trace_value)
    table_paths = {
        'block': slice_dir / 'block_metrics.csv',
        'condition': slice_dir / 'condition_metrics.csv',
        'pooled_amp1': slice_dir / 'pooled_amp1_metrics.csv',
        'pooled_amp2': slice_dir / 'pooled_amp2_metrics.csv',
    }
    required = [paths['phase'], paths['spectrogram'], table_paths['block'],
                table_paths['condition'], table_paths['pooled_amp1'],
                table_paths['pooled_amp2']]
    if SAVE_EPOCH_SIGNALS:
        required.append(paths['epoch'])
    if any(not path.exists() for path in required):
        return None

    # Load only the active trace from slice-level CSV tables
    block_rows = [
        row for row in _read_csv_rows(table_paths['block'])
        if _row_matches_slice(row, trace_dim, trace_value, f_value, dt0_value)
    ]
    condition_rows = [
        row for row in _read_csv_rows(table_paths['condition'])
        if _row_matches_slice(row, trace_dim, trace_value, f_value, dt0_value)
    ]
    seed_rows, _ = condition_metric_rows_by(
        block_rows,
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    phase_records = load_phase_events_nc_by(
        paths['phase'],
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    condition_rows = add_phase_condition_columns_by(
        condition_rows,
        phase_records,
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    spectrogram_records = load_complex_spectrogram_nc_by(
        paths['spectrogram'],
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    epoch_records = []
    if SAVE_EPOCH_SIGNALS:
        epoch_records = load_epoch_signals_nc_by(
            paths['epoch'],
            trace_dim,
            COND_DIMS,
            SLICE_DIMS,
        )
    return block_rows, seed_rows, condition_rows, phase_records, spectrogram_records, epoch_records


def _get_nc_attrs(params, f_value, dt0_value):
    """Build common NetCDF attributes."""
    return {
        'analysis': 'two_stream_phase_analysis',
        'params_json': json.dumps(_json_ready(params), sort_keys=True),
        'signal_kind': SIGNAL_KIND,
        'slice_f': f_value,
        'slice_dt0': dt0_value,
        'lock_pulse_name': LOCK_PULSE_NAME,
        'mask_pulse_names': json.dumps(_json_ready(MASK_PULSE_NAMES)),
        'pulse_pad': json.dumps(_json_ready(PULSE_PAD)),
        'block_duration': BLOCK_DURATION,
        'n_cycles': N_CYCLES,
        'power_f_margin': POWER_F_MARGIN,
        'power_df': POWER_DF,
        'power_overlap': POWER_OVERLAP,
        'fit_intercept': FIT_INTERCEPT,
        'exclude_edges': EXCLUDE_EDGES,
        'min_valid_mass_frac': MIN_VALID_MASS_FRAC,
        'epoch_t_win': json.dumps(_json_ready(EPOCH_T_WIN)),
        'epoch_subtract_global_mean': EPOCH_SUBTRACT_GLOBAL_MEAN,
    }


def _plot_path(slice_dir, name, trace_value):
    """Build a plot path under a named plot family."""
    plot_dir = slice_dir / name
    plot_dir.mkdir(parents=True, exist_ok=True)
    return plot_dir / f'{format_fname_piece(trace_value)}.png'


def _get_pulse_duration():
    """Return the first lock pulse duration in seconds."""
    jobs = sorted(NETPAR_DIR.glob('netParams_*.json'))
    if not jobs:
        return FALLBACK_PULSE_DURATION
    with open(jobs[0], 'r', encoding='utf-8') as fobj:
        netpar = json.load(fobj)
    pulses = netpar['net']['params']['popParams'][LOCK_PULSE_NAME]['params']['pulses']
    pulse = pulses[0]
    return (float(pulse['end']) - float(pulse['start'])) / 1000


def _save_pooled_plots(summary, phase_records, block_seed_rows, pooled_rows,
                       slice_dir, trace_dim, trace_value, f_value, dt0_value,
                       keep_dim):
    """Save one set of pooled one-dimensional plots."""
    baseline_key = (0,)
    cond_dims = (keep_dim,)
    prefix = f'pooled_{keep_dim}'
    pooled_summary = pooled_spectrum_summary(summary, keep_dim, COND_DIMS)
    plot_spectra_by(
        pooled_summary,
        baseline_key,
        cond_dims,
        f_value,
        BROAD_BAND,
        TARGET_HALF_WIDTH,
        _plot_path(slice_dir, f'{prefix}/spectra_raw_logratio', trace_value),
    )
    plot_band_metrics_by(
        block_seed_rows,
        block_seed_rows,
        pooled_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        cond_dims,
        _plot_path(slice_dir, f'{prefix}/band_metrics', trace_value),
    )
    density_by_cond, clouds = pooled_phase_summary(
        phase_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        keep_dim,
        PHASE_BINS,
        PHASE_SMOOTH_SIGMA,
        COND_DIMS,
    )
    plot_phase_density_by(
        density_by_cond,
        baseline_key,
        cond_dims,
        _plot_path(slice_dir, f'{prefix}/phase_density', trace_value),
    )
    plot_coeff_clouds_by(
        clouds,
        baseline_key,
        cond_dims,
        _plot_path(slice_dir, f'{prefix}/coeff_clouds', trace_value),
    )


def _save_epoch_extra_plots(epoch_records, phase_records, slice_dir, trace_dim,
                            trace_value, f_value, dt0_value):
    """Save epoch-fit overlays and epoch signal metric grids."""
    if not SAVE_EPOCH_SIGNALS or not epoch_records:
        return

    # Reuse saved epoch traces and phase coefficients for fitted overlays
    plot_epoch_signals_fit_by(
        epoch_records,
        phase_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        _plot_path(slice_dir, 'epoch_signals_fit_group_amp1', trace_value),
        'amp1',
        _get_pulse_duration(),
        PULSE_PAD,
        bool(EPOCH_SUBTRACT_GLOBAL_MEAN),
    )
    plot_epoch_signals_fit_by(
        epoch_records,
        phase_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        _plot_path(slice_dir, 'epoch_signals_fit_group_amp2', trace_value),
        'amp2',
        _get_pulse_duration(),
        PULSE_PAD,
        bool(EPOCH_SUBTRACT_GLOBAL_MEAN),
    )
    plot_epoch_signal_metric_grid(
        epoch_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        _plot_path(slice_dir, 'grid_sig_metrics', trace_value),
        SIG_METRICS_T,
    )


def _save_trace_arrays(block_rows, condition_rows, phase_records,
                       spectrogram_records, epoch_records, params, slice_dir,
                       trace_dim, trace_value, f_value, dt0_value):
    """Save one pop/f/dt0 slice's tables and arrays."""
    _append_csv_rows(slice_dir / 'block_metrics.csv', block_rows)
    _append_csv_rows(slice_dir / 'condition_metrics.csv', condition_rows)

    # Save self-describing arrays before plotting derived summaries
    attrs = _get_nc_attrs(params, f_value, dt0_value)
    save_phase_events_nc_by(
        phase_records,
        trace_dim,
        COND_DIMS,
        slice_dir / 'phase_events' / f'{format_fname_piece(trace_value)}.nc',
        attrs,
        SLICE_DIMS,
    )
    save_complex_spectrogram_nc_by(
        spectrogram_records,
        trace_dim,
        COND_DIMS,
        slice_dir / 'complex_spectrogram' / f'{format_fname_piece(trace_value)}.nc',
        attrs,
        SLICE_DIMS,
    )
    if SAVE_EPOCH_SIGNALS:
        save_epoch_signals_nc_by(
            epoch_records,
            trace_dim,
            COND_DIMS,
            slice_dir / 'epoch_signals' / f'{format_fname_piece(trace_value)}.nc',
            attrs,
            SLICE_DIMS,
        )


def _save_trace_outputs(block_rows, seed_rows, condition_rows, phase_records,
                        spectrogram_records, spectrum_records, epoch_records,
                        params, slice_dir, trace_dim, trace_value, f_value,
                        dt0_value):
    """Save one pop/f/dt0 slice's arrays, tables, and plots."""
    slice_dir.mkdir(parents=True, exist_ok=True)
    pooled_amp1_seed_rows, pooled_amp1_rows = pooled_condition_metric_rows(
        seed_rows,
        trace_dim,
        'amp1',
        COND_DIMS,
        SLICE_DIMS,
        return_seed_rows=True,
    )
    pooled_amp2_seed_rows, pooled_amp2_rows = pooled_condition_metric_rows(
        seed_rows,
        trace_dim,
        'amp2',
        COND_DIMS,
        SLICE_DIMS,
        return_seed_rows=True,
    )
    _append_csv_rows(slice_dir / 'pooled_amp1_metrics.csv', pooled_amp1_rows)
    _append_csv_rows(slice_dir / 'pooled_amp2_metrics.csv', pooled_amp2_rows)
    _save_trace_arrays(
        block_rows,
        condition_rows,
        phase_records,
        spectrogram_records,
        epoch_records,
        params,
        slice_dir,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
    )

    # Save full-combo one-dimensional plots
    baseline_key = (0, 0)
    summary = spectrum_summary_by(
        spectrum_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
    )
    plot_spectra_by(
        summary,
        baseline_key,
        COND_DIMS,
        f_value,
        BROAD_BAND,
        TARGET_HALF_WIDTH,
        _plot_path(slice_dir, 'spectra_raw_logratio', trace_value),
    )
    plot_band_metrics_by(
        block_rows,
        seed_rows,
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        _plot_path(slice_dir, 'band_metrics', trace_value),
    )
    density_by_cond, clouds = phase_summary_by(
        phase_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        PHASE_BINS,
        PHASE_SMOOTH_SIGMA,
    )
    plot_phase_density_by(
        density_by_cond,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'phase_density', trace_value),
    )
    plot_coeff_clouds_by(
        clouds,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'coeff_clouds', trace_value),
    )

    # Save pooled and 2D amplitude-grid plots
    _save_pooled_plots(
        summary,
        phase_records,
        pooled_amp1_seed_rows,
        pooled_amp1_rows,
        slice_dir,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        'amp1',
    )
    _save_pooled_plots(
        summary,
        phase_records,
        pooled_amp2_seed_rows,
        pooled_amp2_rows,
        slice_dir,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        'amp2',
    )
    plot_metric_grid(
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        _plot_path(slice_dir, 'grid_band_metrics', trace_value),
    )
    plot_phase_metric_grid(
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        _plot_path(slice_dir, 'grid_phase_metrics', trace_value),
    )
    plot_spectra_logratio_grid(
        summary,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'grid_spectra_logratio', trace_value),
    )
    if SAVE_EPOCH_SIGNALS:
        plot_epoch_signals_by(
            epoch_records,
            trace_dim,
            trace_value,
            f_value,
            dt0_value,
            COND_DIMS,
            _plot_path(slice_dir, 'epoch_signals', trace_value),
            _get_pulse_duration(),
            PULSE_PAD,
            bool(EPOCH_SUBTRACT_GLOBAL_MEAN),
        )
        _save_epoch_extra_plots(
            epoch_records,
            phase_records,
            slice_dir,
            trace_dim,
            trace_value,
            f_value,
            dt0_value,
        )


def _plot_cached_trace_outputs(block_rows, seed_rows, condition_rows,
                               phase_records, spectrogram_records,
                               epoch_records, slice_dir, trace_dim,
                               trace_value, f_value, dt0_value):
    """Rebuild plots from saved tables and NetCDF arrays."""
    pooled_amp1_seed_rows, pooled_amp1_rows = pooled_condition_metric_rows(
        seed_rows,
        trace_dim,
        'amp1',
        COND_DIMS,
        SLICE_DIMS,
        return_seed_rows=True,
    )
    pooled_amp2_seed_rows, pooled_amp2_rows = pooled_condition_metric_rows(
        seed_rows,
        trace_dim,
        'amp2',
        COND_DIMS,
        SLICE_DIMS,
        return_seed_rows=True,
    )
    baseline_key = (0, 0)
    summary = spectrum_summary_from_spectrograms(
        spectrogram_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
    )

    # Rebuild full-combo plots from cached products
    plot_spectra_by(
        summary,
        baseline_key,
        COND_DIMS,
        f_value,
        BROAD_BAND,
        TARGET_HALF_WIDTH,
        _plot_path(slice_dir, 'spectra_raw_logratio', trace_value),
    )
    plot_band_metrics_by(
        block_rows,
        seed_rows,
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        _plot_path(slice_dir, 'band_metrics', trace_value),
    )
    density_by_cond, clouds = phase_summary_by(
        phase_records,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        COND_DIMS,
        PHASE_BINS,
        PHASE_SMOOTH_SIGMA,
    )
    plot_phase_density_by(
        density_by_cond,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'phase_density', trace_value),
    )
    plot_coeff_clouds_by(
        clouds,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'coeff_clouds', trace_value),
    )

    # Rebuild pooled and grid plots from cached products
    _save_pooled_plots(
        summary,
        phase_records,
        pooled_amp1_seed_rows,
        pooled_amp1_rows,
        slice_dir,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        'amp1',
    )
    _save_pooled_plots(
        summary,
        phase_records,
        pooled_amp2_seed_rows,
        pooled_amp2_rows,
        slice_dir,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        'amp2',
    )
    plot_metric_grid(
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        _plot_path(slice_dir, 'grid_band_metrics', trace_value),
    )
    plot_phase_metric_grid(
        condition_rows,
        trace_dim,
        trace_value,
        f_value,
        dt0_value,
        _plot_path(slice_dir, 'grid_phase_metrics', trace_value),
    )
    plot_spectra_logratio_grid(
        summary,
        baseline_key,
        COND_DIMS,
        _plot_path(slice_dir, 'grid_spectra_logratio', trace_value),
    )
    if SAVE_EPOCH_SIGNALS and epoch_records:
        plot_epoch_signals_by(
            epoch_records,
            trace_dim,
            trace_value,
            f_value,
            dt0_value,
            COND_DIMS,
            _plot_path(slice_dir, 'epoch_signals', trace_value),
            _get_pulse_duration(),
            PULSE_PAD,
            bool(EPOCH_SUBTRACT_GLOBAL_MEAN),
        )
        _save_epoch_extra_plots(
            epoch_records,
            phase_records,
            slice_dir,
            trace_dim,
            trace_value,
            f_value,
            dt0_value,
        )


def _analyze_trace_slice(X, jobs, trace_dim, trace_value, fit_params):
    """Analyze one active pop/f/dt0 slice."""
    spectrum_records = []
    block_rows = []
    phase_records = []
    spectrogram_records = []
    epoch_records = []
    for job in jobs:
        spec_i, block_i, phase_i, spect_i, epoch_i = _analyze_job_trace(
            X,
            job,
            trace_dim,
            trace_value,
            fit_params,
        )
        spectrum_records.extend(spec_i)
        block_rows.extend(block_i)
        phase_records.extend(phase_i)
        spectrogram_records.extend(spect_i)
        epoch_records.extend(epoch_i)
    seed_rows, condition_rows = condition_metric_rows_by(
        block_rows,
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    condition_rows = add_phase_condition_columns_by(
        condition_rows,
        phase_records,
        trace_dim,
        COND_DIMS,
        SLICE_DIMS,
    )
    return block_rows, seed_rows, condition_rows, phase_records, spectrogram_records, spectrum_records, epoch_records


def run():
    """Run the standalone two-stream phase analysis."""
    params = _get_all_params()
    signal_dir = _get_signal_dir(params)
    _save_params_json(signal_dir, params)
    input_path = INPUT_PATHS[SIGNAL_KIND]
    trace_values_config = _get_trace_values_config()
    fit_params = _get_fit_params()
    X = open_signal_xarray(
        input_path,
        SIGNAL_KIND,
        trace_values=trace_values_config,
        interp_outliers=bool(INTERP_OUTLIERS),
        outlier_kwargs=OUTLIER_KWARGS,
    )

    try:
        trace_dim = get_trace_dim(SIGNAL_KIND)
        trace_values = get_trace_values(X, SIGNAL_KIND)
        jobs = get_jobs(X)
        f_values, dt0_values = _get_slice_values(X)
        pad_pair = get_pulse_pad_pair(PULSE_PAD)
        print(
            f'Signal={SIGNAL_KIND}, traces={trace_values}, jobs={len(jobs)}, '
            f'pad={pad_pair}',
            flush=True,
        )

        # Stream one f/dt0 folder and one trace at a time
        for f_value in f_values:
            for dt0_value in dt0_values:
                slice_jobs = _get_slice_jobs(jobs, f_value, dt0_value)
                slice_dir = _get_slice_dir(signal_dir, f_value, dt0_value)
                _save_params_json(slice_dir, params, f_value, dt0_value)
                if NEED_RECALC:
                    _reset_slice_outputs(slice_dir)
                for trace_value in trace_values:
                    cached = None
                    if not NEED_RECALC:
                        cached = _load_cached_trace(
                            slice_dir,
                            trace_dim,
                            trace_value,
                            f_value,
                            dt0_value,
                        )
                    if cached is not None:
                        _plot_cached_trace_outputs(
                            *cached,
                            slice_dir,
                            trace_dim,
                            trace_value,
                            f_value,
                            dt0_value,
                        )
                        action = 'Loaded'
                    else:
                        if not NEED_RECALC:
                            _drop_trace_table_rows(
                                slice_dir,
                                trace_dim,
                                trace_value,
                                f_value,
                                dt0_value,
                            )
                        results = _analyze_trace_slice(
                            X,
                            slice_jobs,
                            trace_dim,
                            trace_value,
                            fit_params,
                        )
                        _save_trace_outputs(
                            *results,
                            params,
                            slice_dir,
                            trace_dim,
                            trace_value,
                            f_value,
                            dt0_value,
                        )
                        action = 'Saved'
                    print(
                        f"{action} f={format_value(f_value)}, "
                        f"dt0={format_value(dt0_value)}, "
                        f"{trace_dim}={format_value(trace_value)}",
                        flush=True,
                    )
        print(f'Saved outputs: {signal_dir}', flush=True)
    finally:
        X.close()


if __name__ == '__main__':
    run()
