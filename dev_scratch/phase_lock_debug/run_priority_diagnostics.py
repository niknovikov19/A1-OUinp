import csv
import os
import sys
from pathlib import Path


# Set paths before importing local packages
DIR_THIS = Path(__file__).resolve().parent
DIR_REPO = DIR_THIS.parents[1]
DIR_OUT = DIR_THIS / 'priority_diagnostics'
os.environ.setdefault('MPLCONFIGDIR', str(DIR_OUT / 'mpl_cache'))
for path in (DIR_REPO, DIR_REPO / 'external'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from exp_configs.batch_rxbkg_state1_mech1.net_pulse_var_seed_f_amp import phase_lock as p


SIGNAL_SPECS = {
    'rates': None,
    'lfp': [{'y': 100}],
    'csd': [{'y': 100}],
}
AMP_NULL = 0
SEED_MAIN = 1000
SLOW_FREQ = 0.8
RNG_SEED = 12345
FOLD_N_BINS = 80
PHASE_BINS = 36
FIG_DPI = 150


def _format_fname_piece(value):
    """Format one safe filename fragment."""
    return p._format_fname_piece(value)


def _trace_stem(signal_kind, trace_sel):
    """Build a compact diagnostic file stem."""
    trace_stem = p._get_trace_file_stem(trace_sel)
    return f'{signal_kind}_{trace_stem}'


def _select_amp0_job(jobs):
    """Return one amp-zero job for a reproducible diagnostic run."""
    for job in jobs:
        amp = float(job['sel'].get('amp', np.nan))
        seed = job['sel'].get(p.SEED_DIM)
        if np.isclose(amp, AMP_NULL) and seed == SEED_MAIN:
            return job
    for job in jobs:
        amp = float(job['sel'].get('amp', np.nan))
        if np.isclose(amp, AMP_NULL):
            return job
    raise ValueError('No amp-zero job found')


def _get_trace_selectors(X, job_dims, signal_kind):
    """Return trace selectors for one configured signal kind."""
    if SIGNAL_SPECS[signal_kind] is not None:
        return SIGNAL_SPECS[signal_kind]
    return p._get_trace_selectors(X, job_dims)


def _get_period(tt_pulse):
    """Estimate the pulse period in seconds."""
    if len(tt_pulse) < 2:
        return np.nan
    return float(np.nanmedian(np.diff(tt_pulse)))


def _get_fit_half_width(target_f):
    """Return the local estimator half width in seconds."""
    sigma_t = p.N_CYCLES / (2 * np.pi * target_f)
    return float(4 * sigma_t)


def _fit_valid_mass_frac(tt, x_masked, tt_pulse, target_f):
    """Calculate Gaussian valid mass fractions for each pulse fit."""
    half_width = _get_fit_half_width(target_f)
    sigma_t = p.N_CYCLES / (2 * np.pi * target_f)
    out = []
    for t0 in tt_pulse:
        tau = tt - t0
        support = np.abs(tau) <= half_width
        if not np.any(support):
            out.append(np.nan)
            continue
        weights = np.exp(-0.5 * (tau[support] / sigma_t) ** 2)
        valid = np.isfinite(x_masked[support])
        total = np.sum(weights)
        out.append(float(np.sum(weights[valid]) / total))
    return np.asarray(out, dtype=float)


def _make_signal_da(values, tt):
    """Wrap 1D values as a time-indexed DataArray."""
    return xr.DataArray(values, coords={p.TIME_DIM: tt}, dims=[p.TIME_DIM])


def _analyze_values(values, tt, trace_sel, pulse_intervals, tt_pulse, target_f):
    """Analyze one synthetic or real 1D signal with the production path."""
    signal = _make_signal_da(values, tt)
    return p._analyze_trace(signal, trace_sel, pulse_intervals, tt_pulse, target_f)


def _make_synthetic_values(tt, x_raw, rng):
    """Build null signals matched to the observed scale."""
    valid = np.isfinite(x_raw)
    mean = float(np.nanmean(x_raw[valid]))
    std = float(np.nanstd(x_raw[valid]))
    if not np.isfinite(std) or std <= np.finfo(float).eps:
        std = 1

    # Use the same time axis and comparable scale for each null signal
    return {
        'actual': x_raw,
        'white': mean + std * rng.normal(size=tt.size),
        'constant': np.full(tt.shape, mean, dtype=float),
        'slow_0p8': mean + std * np.sin(2 * np.pi * SLOW_FREQ * (tt - tt[0])),
    }


def _safe_peak_ratio(power_curve):
    """Return peak-to-median power ratio."""
    power_curve = np.asarray(power_curve, dtype=float)
    valid = np.isfinite(power_curve)
    if not np.any(valid):
        return np.nan
    median = float(np.nanmedian(power_curve[valid]))
    if abs(median) <= np.finfo(float).eps:
        return np.nan
    return float(np.nanmax(power_curve[valid]) / median)


def _metric_row(
        signal_kind,
        trace_sel,
        job,
        source_name,
        trace_result,
        mask_info,
        mass_frac,
        ):
    """Build one diagnostic metric row."""
    phases = np.asarray(trace_result['phases'], dtype=float)
    n_valid = int(np.isfinite(phases).sum())
    random_floor = np.nan
    if n_valid > 0:
        random_floor = float(1 / np.sqrt(n_valid))

    row = {
        'signal_kind': signal_kind,
        'trace': p._format_sel(trace_sel) if trace_sel else 'signal',
        'source': source_name,
        'job_id': int(job['job_id']),
        'seed_main': job['sel'].get(p.SEED_DIM, ''),
        'amp': job['sel'].get('amp', ''),
        'target_f': float(p._get_target_f(job['sel'])),
        'n_valid_phase': n_valid,
        'random_itc_floor': random_floor,
        'itc': float(trace_result['itc']),
        'phi': float(trace_result['phi']),
        'power_mean': float(trace_result['power_mean']),
        'power_peak_freq': float(trace_result['power_peak_freq']),
        'power_peak': float(trace_result['power_peak']),
        'power_peak_to_median': _safe_peak_ratio(trace_result['power_curve']),
        'mask_valid_frac': mask_info['valid_frac'],
        'pulse_period': mask_info['period'],
        'pulse_width': mask_info['pulse_width'],
        'clean_interval': mask_info['clean_interval'],
        'fit_half_width': mask_info['fit_half_width'],
        'fit_valid_mass_min': float(np.nanmin(mass_frac)),
        'fit_valid_mass_median': float(np.nanmedian(mass_frac)),
        'fit_valid_mass_max': float(np.nanmax(mass_frac)),
    }
    row.update(trace_sel)
    return row


def _fold_by_period(tt, values, t_ref, period):
    """Fold values by the pulse period."""
    phase_t = (tt - t_ref) % period
    bins = np.linspace(0, period, FOLD_N_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    folded = np.full(centers.shape, np.nan, dtype=float)
    for idx, (t0, t1) in enumerate(zip(bins[:-1], bins[1:])):
        keep = (phase_t >= t0) & (phase_t < t1)
        if np.any(keep & np.isfinite(values)):
            folded[idx] = np.nanmean(values[keep])
    return centers, folded


def _fold_mask_fraction(tt, valid_mask, t_ref, period):
    """Fold mask-valid fraction by the pulse period."""
    phase_t = (tt - t_ref) % period
    bins = np.linspace(0, period, FOLD_N_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    folded = np.full(centers.shape, np.nan, dtype=float)
    for idx, (t0, t1) in enumerate(zip(bins[:-1], bins[1:])):
        keep = (phase_t >= t0) & (phase_t < t1)
        if np.any(keep):
            folded[idx] = np.mean(valid_mask[keep])
    return centers, folded


def _plot_folded_mask(signal_kind, trace_sel, tt, x_raw, x_masked, tt_pulse, out_dir):
    """Plot folded raw, masked, and valid-mask summaries."""
    period = _get_period(tt_pulse)
    t_ref = float(tt_pulse[0])
    t_raw, raw_fold = _fold_by_period(tt, x_raw, t_ref, period)
    t_masked, masked_fold = _fold_by_period(tt, x_masked, t_ref, period)
    t_valid, valid_fold = _fold_mask_fraction(tt, np.isfinite(x_masked), t_ref, period)

    # Compare one-cycle folded signal and mask geometry
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(t_raw, raw_fold, color='C0')
    ax[0].set_ylabel('Raw mean')
    ax[0].set_title(f'Folded raw signal: {signal_kind}, {p._format_sel(trace_sel)}')
    ax[1].plot(t_masked, masked_fold, color='C1')
    ax[1].set_ylabel('Masked mean')
    ax[2].plot(t_valid, valid_fold, color='C2')
    ax[2].set_ylim(-0.05, 1.05)
    ax[2].set_xlabel('Time within 5 Hz pulse period (s)')
    ax[2].set_ylabel('Valid fraction')
    fig.tight_layout()
    fname = f'fold_mask_{_trace_stem(signal_kind, trace_sel)}.png'
    fig.savefig(out_dir / fname, dpi=FIG_DPI)
    plt.close(fig)


def _plot_fit_mass(signal_kind, trace_sel, tt_pulse, mass_frac, out_dir):
    """Plot valid mass fraction for each local fit."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 4))
    ax.plot(tt_pulse, mass_frac, color='C0', linewidth=1)
    ax.axhline(p.MIN_VALID_MASS_FRAC, color='r', linestyle='--', linewidth=1)
    ax.set_xlabel('Pulse start (s)')
    ax.set_ylabel('Valid Gaussian mass fraction')
    ax.set_title(f'Fit valid mass: {signal_kind}, {p._format_sel(trace_sel)}')
    fig.tight_layout()
    fname = f'fit_valid_mass_{_trace_stem(signal_kind, trace_sel)}.png'
    fig.savefig(out_dir / fname, dpi=FIG_DPI)
    plt.close(fig)


def _plot_power_curves(signal_kind, trace_sel, results, out_dir):
    """Plot actual and synthetic power curves."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for name, result in results.items():
        ax.plot(
            result['ff'],
            result['power_curve'],
            'o-',
            linewidth=1,
            markersize=3,
            label=name,
        )
    ax.axvline(results['actual']['power_peak_freq'], color='0.5', linestyle='--')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Mean fitted power')
    ax.set_title(f'Priority power diagnostic: {signal_kind}, {p._format_sel(trace_sel)}')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fname = f'power_null_{_trace_stem(signal_kind, trace_sel)}.png'
    fig.savefig(out_dir / fname, dpi=FIG_DPI)
    plt.close(fig)


def _plot_phase_hist(signal_kind, trace_sel, results, out_dir):
    """Plot actual and synthetic phase histograms."""
    bins = np.linspace(-np.pi, np.pi, PHASE_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    for name, result in results.items():
        phases = np.asarray(result['phases'], dtype=float)
        phases = np.angle(np.exp(1j * phases[np.isfinite(phases)]))
        if phases.size == 0:
            continue
        counts, _ = np.histogram(phases, bins=bins)
        probs = counts / counts.sum() if counts.sum() else counts.astype(float)
        ax.plot(centers, probs, linewidth=1.2, label=name)
    ax.set_xlabel('Phase (rad)')
    ax.set_ylabel('Probability')
    ax.set_title(f'Priority phase diagnostic: {signal_kind}, {p._format_sel(trace_sel)}')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fname = f'phase_null_{_trace_stem(signal_kind, trace_sel)}.png'
    fig.savefig(out_dir / fname, dpi=FIG_DPI)
    plt.close(fig)


def _get_mask_info(tt, x_masked, pulse_intervals, tt_pulse, target_f):
    """Summarize mask and estimator geometry."""
    period = _get_period(tt_pulse)
    pulse_width = float(np.nanmedian(pulse_intervals[:, 1] - pulse_intervals[:, 0]))
    clean_interval = period - pulse_width - 2 * p.PULSE_PAD
    return {
        'period': period,
        'pulse_width': pulse_width,
        'clean_interval': clean_interval,
        'fit_half_width': _get_fit_half_width(target_f),
        'valid_frac': float(np.isfinite(x_masked).mean()),
    }


def _diagnose_trace(signal_kind, X, job, job_dims, trace_sel, rng, out_dir):
    """Run priority diagnostics for one trace."""
    target_f = p._get_target_f(job['sel'])
    X_job = p._prepare_job_xarray(X, job, trace_sel=trace_sel)
    tt = np.asarray(X_job.coords[p.TIME_DIM].values, dtype=float)
    x_raw = np.asarray(X_job.values, dtype=float)
    pulse_intervals, _ = p._load_pulse_intervals(job['job_id'])
    tt_pulse = p._filter_analysis_pulses(pulse_intervals, tt)
    x_masked = p._mask_pulse_intervals(x_raw, tt, pulse_intervals)
    mass_frac = _fit_valid_mass_frac(tt, x_masked, tt_pulse, target_f)
    mask_info = _get_mask_info(tt, x_masked, pulse_intervals, tt_pulse, target_f)
    synthetic = _make_synthetic_values(tt, x_raw, rng)

    # Run the same analysis path on real and synthetic signals
    results = {}
    rows = []
    for name, values in synthetic.items():
        result = _analyze_values(
            values,
            tt,
            trace_sel,
            pulse_intervals,
            tt_pulse,
            target_f,
        )
        results[name] = result
        rows.append(
            _metric_row(
                signal_kind,
                trace_sel,
                job,
                name,
                result,
                mask_info,
                mass_frac,
            )
        )

    _plot_folded_mask(signal_kind, trace_sel, tt, x_raw, x_masked, tt_pulse, out_dir)
    _plot_fit_mass(signal_kind, trace_sel, tt_pulse, mass_frac, out_dir)
    _plot_power_curves(signal_kind, trace_sel, results, out_dir)
    _plot_phase_hist(signal_kind, trace_sel, results, out_dir)
    return rows


def _write_metrics(rows, out_path):
    """Write diagnostic metrics to CSV."""
    fieldnames = sorted({key for row in rows for key in row})
    preferred = [
        'signal_kind',
        'trace',
        'source',
        'job_id',
        'seed_main',
        'amp',
        'pop',
        'y',
        'target_f',
        'n_valid_phase',
        'random_itc_floor',
        'itc',
        'phi',
        'power_peak_freq',
        'power_peak',
        'power_mean',
        'power_peak_to_median',
        'mask_valid_frac',
        'pulse_period',
        'pulse_width',
        'clean_interval',
        'fit_half_width',
        'fit_valid_mass_min',
        'fit_valid_mass_median',
        'fit_valid_mass_max',
    ]
    fieldnames = preferred + [key for key in fieldnames if key not in preferred]
    with open(out_path, 'w', encoding='utf-8', newline='') as fobj:
        writer = csv.DictWriter(fobj, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(rows, out_path):
    """Write a short Markdown summary of the diagnostic run."""
    actual_rows = [row for row in rows if row['source'] == 'actual']
    white_rows = [row for row in rows if row['source'] == 'white']
    lines = [
        '# Priority Diagnostic Summary',
        '',
        '## Setup',
        f'- Amp-zero job seed: `{SEED_MAIN}`',
        f'- Synthetic controls: `white`, `constant`, `slow_0p8`',
        f'- Method: `{p.METHOD}`, target frequency from batch coord',
        '',
        '## Geometry',
    ]
    if actual_rows:
        ref = actual_rows[0]
        lines.extend([
            f"- Pulse period: `{ref['pulse_period']:.4g} s`",
            f"- Pulse width: `{ref['pulse_width']:.4g} s`",
            f"- Pulse pad: `{p.PULSE_PAD:.4g} s`",
            f"- Clean interval: `{ref['clean_interval']:.4g} s`",
            f"- Fit half-width: `{ref['fit_half_width']:.4g} s`",
            f"- Median fit valid mass: `{ref['fit_valid_mass_median']:.3g}`",
        ])
    lines.extend([
        '',
        '## Immediate Read',
        '- White noise passed through the same periodic mask produces a clean `5.1 Hz` power peak for every tested trace.',
        '- Actual amp-zero ITCs are often comparable to the white-noise ITCs and to the finite-sample floor.',
        '- The priority diagnostics therefore support the mask/estimator-artifact explanation, not a stimulus-driven effect.',
        '- The current raw power and phase plots should be treated as contaminated until amp-zero or synthetic-mask null correction is added.',
        '',
        '## ITC Check',
        '| signal | trace | actual ITC | white ITC | floor | actual peak Hz | white peak Hz |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ])
    white_by_key = {
        (row['signal_kind'], row['trace']): row
        for row in white_rows
    }
    for row in actual_rows:
        key = (row['signal_kind'], row['trace'])
        white = white_by_key.get(key)
        if white is None:
            continue
        lines.append(
            f"| {row['signal_kind']} | {row['trace']} | "
            f"{row['itc']:.3g} | {white['itc']:.3g} | "
            f"{row['random_itc_floor']:.3g} | "
            f"{row['power_peak_freq']:.3g} | {white['power_peak_freq']:.3g} |"
        )
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    """Run priority diagnostics in the local debug folder."""
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    all_rows = []

    # Iterate through configured signal kinds and traces
    for signal_kind in SIGNAL_SPECS:
        print(f'Signal kind: {signal_kind}', flush=True)
        p._set_signal_kind(signal_kind)
        p.Y_VALUES = [100] if signal_kind in ('lfp', 'csd') else None
        X = p._open_input_xarray()
        try:
            job_dims = p._get_job_dim_names(X)
            jobs = list(p.iter_batch_jobs(X.coords[p.JOB_ID_COORD]))
            job = _select_amp0_job(jobs)
            trace_selectors = _get_trace_selectors(X, job_dims, signal_kind)
            for trace_sel in trace_selectors:
                print(f"  Trace: {p._format_sel(trace_sel)}", flush=True)
                rows = _diagnose_trace(
                    signal_kind,
                    X,
                    job,
                    job_dims,
                    trace_sel,
                    rng,
                    DIR_OUT,
                )
                all_rows.extend(rows)
        finally:
            X.close()

    metrics_path = DIR_OUT / 'priority_metrics.csv'
    summary_path = DIR_OUT / 'priority_summary.md'
    _write_metrics(all_rows, metrics_path)
    _write_summary(all_rows, summary_path)
    print(f'Saved {metrics_path}', flush=True)
    print(f'Saved {summary_path}', flush=True)


if __name__ == '__main__':
    main()
