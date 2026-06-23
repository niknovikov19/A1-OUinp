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


# Keep matplotlib cache out of the repo root
EXP_NAME = (
    'exp_L2_nseed_3_f_5_amp_0_0.003_4_t_5.0_50.0_lfp_0_300_50_'
    'ictrl_wmult_0.25_ee_0.5_pulse_NGF2_d_50_c_25_r_500_0_t0_5000_jit_0'
)
DIRPATH_EXP = (
    DIR_REPO / 'exp_results' / 'batch_rxbkg_state1_mech1' /
    'net_pulse_var_seed_f_amp' / EXP_NAME
)
DIRPATH_ARTIFACT = (
    DIR_REPO / 'dev_scratch' / 'artifacts' /
    'net_pulse_var_seed_f_amp' / EXP_NAME
)
OUT_DIR = DIR_THIS / 'artifacts' / EXP_NAME
os.environ.setdefault('MPLCONFIGDIR', str(OUT_DIR / 'mpl_cache'))

from phase_analysis_utils import (
    TIME_DIM,
    as_scalar,
    compute_band_metrics,
    compute_complex_spectrogram,
    compute_power_curve,
    condition_metric_rows,
    filter_analysis_pulses,
    fit_event_coefficients,
    format_fname_piece,
    format_value,
    get_job_amp,
    get_job_seed,
    get_jobs,
    get_target_f,
    get_trace_dim,
    get_trace_values,
    load_pulse_intervals,
    make_blocks,
    mask_pulse_intervals,
    open_signal_xarray,
    phase_summary,
    plot_band_metrics,
    plot_coeff_clouds,
    plot_phase_density,
    plot_spectra,
    seed_spectrum_summary,
    save_complex_spectrogram_nc,
    save_phase_events_nc,
)

import numpy as np


SIGNAL_KIND = 'rates'
POP_VALUES = 'all'
Y_VALUES = None
INPUT_PATHS = {
    'rates': DIRPATH_ARTIFACT / 'rates_xr_combined.nc',
    'lfp': DIRPATH_ARTIFACT / 'lfp_xr_combined.nc',
    'csd': DIRPATH_ARTIFACT / 'lfp_xr_combined.nc',
}
NETPAR_DIR = DIRPATH_EXP / 'netpar'

FALLBACK_F = 5
ANALYSIS_T0 = 10
PULSE_PAD = (0.02, 0.02)
BLOCK_DURATION = 5

N_CYCLES = 3
POWER_F_MARGIN = 5
POWER_DF = 0.2
POWER_OVERLAP = 0.9
FIT_INTERCEPT = 1
FIT_RCOND = None
EXCLUDE_EDGES = 1
MIN_VALID_MASS_FRAC = 0.5

BROAD_BAND = (2, 8)
TARGET_HALF_WIDTH = 0.5
PHASE_BINS = 32
PHASE_SMOOTH_SIGMA = 1

INTERP_OUTLIERS = 0
OUTLIER_KWARGS = {
    'z_thresh': 8,
    'rel_neighbor_thresh': 5,
}

PARAM_HASH_LEN = 8
DIRNAME_PARAM_KEYS = {
    'pop': 'pop_values',
    'pad': 'pulse_pad',
    'blk': 'block_duration',
    'fmarg': 'power_f_margin',
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
        'input_paths': INPUT_PATHS,
        'netpar_dir': NETPAR_DIR,
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
        'interp_outliers': INTERP_OUTLIERS,
        'outlier_kwargs': OUTLIER_KWARGS,
    }


def _get_params_hash(params):
    """Return a short stable hash from all parameters."""
    text = json.dumps(_json_ready(params), sort_keys=True)
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


def _save_params_json(signal_dir, params):
    """Save full run parameters next to analysis outputs."""
    signal_dir.mkdir(parents=True, exist_ok=True)
    out_path = signal_dir / 'params.json'
    with open(out_path, 'w', encoding='utf-8') as fobj:
        json.dump(_json_ready(params), fobj, indent=2, sort_keys=True)
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
        'seed_main': get_job_seed(job_sel),
        'f': target_f,
        'amp': get_job_amp(job_sel),
        trace_dim: trace_value,
    }


def _select_job_trace(X, job, trace_dim, trace_value):
    """Select one job and trace from the combined xarray."""
    X_job = X.isel(job['isel'])
    return X_job.sel({trace_dim: trace_value})


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

        # Store full spectra in memory and scalar block metrics in CSV rows
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
    """Analyze one job and trace."""
    signal = _select_job_trace(X, job, trace_dim, trace_value)
    tt = np.asarray(signal.coords[TIME_DIM].values, dtype=float)
    x = np.asarray(signal.values, dtype=float)
    target_f = get_target_f(job['sel'], FALLBACK_F)
    base = _base_record(job, trace_dim, trace_value, target_f)

    # Load the matching event schedule and apply the same mask to all amplitudes
    pulse_intervals = load_pulse_intervals(NETPAR_DIR, int(job['job_id']))
    x_masked = mask_pulse_intervals(x, tt, pulse_intervals, PULSE_PAD, ANALYSIS_T0)
    tt_pulse = filter_analysis_pulses(pulse_intervals, tt, ANALYSIS_T0)
    blocks = make_blocks(tt, ANALYSIS_T0, BLOCK_DURATION, target_f)

    spectrum_records, block_rows = _analyze_blocks(
        x_masked,
        tt,
        blocks,
        base,
        target_f,
        fit_params,
    )
    phases, coeffs = fit_event_coefficients(
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

    # Keep event arrays in memory for phase density and cloud plots
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
    return spectrum_records, block_rows, [phase_record], [spect_record]


def _add_phase_condition_columns(condition_rows, phase_records, trace_dim):
    """Add event counts and mean coefficient summaries to condition rows."""
    phase_lookup = {}
    for record in phase_records:
        key = (record[trace_dim], record['f'], record['amp'])
        phase_lookup.setdefault(key, []).append(record)

    # Merge compact phase summaries into existing condition rows
    for row in condition_rows:
        key = (row[trace_dim], row['f'], row['amp'])
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


def _get_plot_path(signal_dir, trace_dim, trace_value, name, f_value=None):
    """Build one output plot path."""
    plot_dir = signal_dir / name
    plot_dir.mkdir(parents=True, exist_ok=True)
    trace_part = format_fname_piece(trace_value)
    if f_value is not None:
        f_part = f'_f_{format_fname_piece(f_value)}'
    else:
        f_part = ''
    return plot_dir / f'{trace_part}{f_part}.png'


def _save_trace_plots(spectrum_records, block_rows, condition_rows,
                      phase_records, signal_dir, trace_dim, trace_value):
    """Save all plots for one selected trace."""
    f_values = sorted({
        record['f']
        for record in spectrum_records
        if record[trace_dim] == trace_value
    })
    include_f = len(f_values) > 1
    for f_value in f_values:
        summary = seed_spectrum_summary(
            spectrum_records,
            trace_dim,
            trace_value,
            f_value,
        )
        plot_spectra(
            summary,
            f_value,
            BROAD_BAND,
            TARGET_HALF_WIDTH,
            _get_plot_path(
                signal_dir,
                trace_dim,
                trace_value,
                'spectra_raw_logratio',
                f_value if include_f else None,
            ),
        )
        plot_band_metrics(
            block_rows,
            condition_rows,
            trace_dim,
            trace_value,
            f_value,
            _get_plot_path(
                signal_dir,
                trace_dim,
                trace_value,
                'band_metrics',
                f_value if include_f else None,
            ),
        )
        density_by_amp, clouds = phase_summary(
            phase_records,
            trace_dim,
            trace_value,
            f_value,
            PHASE_BINS,
            PHASE_SMOOTH_SIGMA,
        )
        plot_phase_density(
            density_by_amp,
            _get_plot_path(
                signal_dir,
                trace_dim,
                trace_value,
                'phase_density',
                f_value if include_f else None,
            ),
        )
        plot_coeff_clouds(
            clouds,
            _get_plot_path(
                signal_dir,
                trace_dim,
                trace_value,
                'coeff_clouds',
                f_value if include_f else None,
            ),
        )


def _get_nc_attrs(params):
    """Build common NetCDF attributes."""
    attrs = {
        'analysis': 'priority1_phase_analysis',
        'params_json': json.dumps(_json_ready(params), sort_keys=True),
        'signal_kind': SIGNAL_KIND,
        'pulse_pad': json.dumps(_json_ready(PULSE_PAD)),
        'block_duration': BLOCK_DURATION,
        'n_cycles': N_CYCLES,
        'power_f_margin': POWER_F_MARGIN,
        'power_df': POWER_DF,
        'power_overlap': POWER_OVERLAP,
        'fit_intercept': FIT_INTERCEPT,
        'exclude_edges': EXCLUDE_EDGES,
        'min_valid_mass_frac': MIN_VALID_MASS_FRAC,
    }
    return attrs


def _round_csv_value(value, ndigits=4):
    """Round numeric CSV values for easier reading."""
    value = as_scalar(value)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return value
        return round(float(value), ndigits)
    return value


def _append_csv_rows(path, rows, ndigits=4):
    """Append rows to a CSV file, writing a header when needed."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    need_header = not path.exists()
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


def _reset_stream_outputs(signal_dir):
    """Remove stream-written summary files from an earlier run."""
    for path in (
        signal_dir / 'block_metrics.csv',
        signal_dir / 'condition_metrics.csv',
        signal_dir / 'phase_events.nc',
        signal_dir / 'complex_spectrogram.nc',
    ):
        if path.exists():
            path.unlink()


def _save_trace_outputs(block_rows, condition_rows, spectrum_records,
                        phase_records, spectrogram_records, params,
                        signal_dir, trace_dim, trace_value):
    """Save one trace's CSV rows, NetCDF arrays, and plots."""
    signal_dir.mkdir(parents=True, exist_ok=True)
    _append_csv_rows(signal_dir / 'block_metrics.csv', block_rows)
    _append_csv_rows(signal_dir / 'condition_metrics.csv', condition_rows)
    attrs = _get_nc_attrs(params)
    save_phase_events_nc(
        phase_records,
        trace_dim,
        signal_dir / 'phase_events' / f'{format_fname_piece(trace_value)}.nc',
        attrs,
    )
    save_complex_spectrogram_nc(
        spectrogram_records,
        trace_dim,
        signal_dir / 'complex_spectrogram' / f'{format_fname_piece(trace_value)}.nc',
        attrs,
    )
    _save_trace_plots(
        spectrum_records,
        block_rows,
        condition_rows,
        phase_records,
        signal_dir,
        trace_dim,
        trace_value,
    )


def run():
    """Run the standalone Priority 1 analysis."""
    params = _get_all_params()
    signal_dir = _get_signal_dir(params)
    _save_params_json(signal_dir, params)
    _reset_stream_outputs(signal_dir)
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
        print(
            f'Signal={SIGNAL_KIND}, traces={trace_values}, jobs={len(jobs)}',
            flush=True,
        )

        # Analyze, save, and release each trace before moving on
        for trace_value in trace_values:
            spectrum_records = []
            block_rows = []
            phase_records = []
            spectrogram_records = []
            for job in jobs:
                spec_i, block_i, phase_i, spect_i = _analyze_job_trace(
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
            _, condition_rows = condition_metric_rows(block_rows, trace_dim)
            condition_rows = _add_phase_condition_columns(
                condition_rows,
                phase_records,
                trace_dim,
            )
            _save_trace_outputs(
                block_rows,
                condition_rows,
                spectrum_records,
                phase_records,
                spectrogram_records,
                params,
                signal_dir,
                trace_dim,
                trace_value,
            )
            print(f"Saved {trace_dim}={format_value(trace_value)}", flush=True)

        print(f'Saved outputs: {signal_dir}', flush=True)
    finally:
        X.close()


if __name__ == '__main__':
    run()
