import os
from pathlib import Path

import numpy as np


# Paths
DIR_THIS = Path(__file__).resolve().parent
DIR_OUT = DIR_THIS / 'periodic_mask_fit_demo'
os.environ.setdefault('MPLCONFIGDIR', str(DIR_OUT / 'mpl_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# Time and event params
DT = 0.005
T_STOP = 50
EVENT_T0 = 5
EVENT_T_ANALYSIS = 10
EVENT_FREQ = 5
PULSE_WIDTH = 0.05
PULSE_PAD = 0.02

# Fit params
TARGET_FREQ = 5
N_CYCLES = 3
FREQ_MIN = 2.5
FREQ_MAX = 7.5
FREQ_STEP = 0.2
FIT_OVERLAP = 0.5
MIN_VALID_MASS = 0.5

# Signal params
RNG_SEED = 12345
NOISE_STD = 1
SLOW_FREQ = 0.8
SLOW_AMP = 1
N_NOISE_POWER = 16

# Plot params
FOLD_BINS = 80
PHASE_BINS = 36
FIG_DPI = 150


def make_time():
    """Create the regular time axis."""
    return np.arange(0, T_STOP + 0.5 * DT, DT)


def make_events():
    """Create the periodic event starts."""
    period = 1 / EVENT_FREQ
    return np.arange(EVENT_T0, T_STOP + 0.5 * period, period)


def make_valid_mask(tt, events):
    """Create a periodic pulse-exclusion mask."""
    valid = np.ones(tt.shape, dtype=bool)
    valid[tt < EVENT_T_ANALYSIS] = False
    for t0 in events:
        t1 = t0 + PULSE_WIDTH
        bad = (tt >= t0 - PULSE_PAD) & (tt <= t1 + PULSE_PAD)
        valid[bad] = False
    return valid


def apply_mask(x, valid):
    """Set excluded samples to NaN."""
    out = np.asarray(x, dtype=float).copy()
    out[~valid] = np.nan
    return out


def fit_half_width(freq):
    """Return local Gaussian support half-width."""
    sigma_t = N_CYCLES / (2 * np.pi * freq)
    return 4 * sigma_t


def fit_sinusoid_local(x, tt, t0, freq):
    """Fit one local Gaussian-weighted sinusoid."""
    sigma_t = N_CYCLES / (2 * np.pi * freq)
    half_width = 4 * sigma_t
    tau = tt - t0
    support = np.abs(tau) <= half_width
    valid = support & np.isfinite(x)
    if not np.any(valid):
        return np.nan, np.nan, np.nan

    # Reject fits with too much masked Gaussian mass
    w_all = np.exp(-0.5 * (tau[support] / sigma_t) ** 2)
    w = np.exp(-0.5 * (tau[valid] / sigma_t) ** 2)
    valid_mass = np.sum(w) / np.sum(w_all)
    if valid_mass < MIN_VALID_MASS:
        return np.nan, np.nan, valid_mass

    # Solve weighted least squares for cos, sin, and intercept
    omega = 2 * np.pi * freq
    cos_col = np.cos(omega * tau[valid])
    sin_col = np.sin(omega * tau[valid])
    X = np.column_stack([cos_col, sin_col, np.ones(valid.sum())])
    y = x[valid]
    sqrt_w = np.sqrt(w)
    beta, _, rank, _ = np.linalg.lstsq(X * sqrt_w[:, None], y * sqrt_w, rcond=None)
    if rank < 3:
        return np.nan, np.nan, valid_mass

    # Convert coefficients to phase and fitted oscillatory power
    a, b, _ = beta
    phase = np.arctan2(-b, a)
    x_osc = a * cos_col + b * sin_col
    power = np.sum(w * x_osc**2) / np.sum(w)
    return float(phase), float(power), float(valid_mass)


def fit_phases_at_events(x, tt, events):
    """Fit target-frequency phase at each event."""
    phases = []
    masses = []
    for t0 in events:
        phase, _, mass = fit_sinusoid_local(x, tt, t0, TARGET_FREQ)
        phases.append(phase)
        masses.append(mass)
    return np.asarray(phases), np.asarray(masses)


def make_eval_centers(tt, freq):
    """Create sparse centers for sliding power."""
    half_width = fit_half_width(freq)
    full_samples = 2 * int(np.ceil(half_width / DT)) + 1
    step = max(1, int(round(full_samples * (1 - FIT_OVERLAP))))
    centers = tt[::step]
    if centers[-1] != tt[-1]:
        centers = np.append(centers, tt[-1])
    return centers


def mean_power_at_freq(x, tt, freq):
    """Calculate mean local fitted power at one frequency."""
    centers = make_eval_centers(tt, freq)
    powers = []
    for t0 in centers:
        _, power, _ = fit_sinusoid_local(x, tt, t0, freq)
        powers.append(power)
    return float(np.nanmean(powers))


def power_spectrum(x, tt):
    """Calculate local-fit power over a small frequency grid."""
    freqs = np.arange(FREQ_MIN, FREQ_MAX + 0.5 * FREQ_STEP, FREQ_STEP)
    powers = np.asarray([
        mean_power_at_freq(x, tt, freq)
        for freq in freqs
    ])
    return freqs, powers


def make_signals(tt, rng):
    """Create simple surrogate signals."""
    slow = SLOW_AMP * np.sin(2 * np.pi * SLOW_FREQ * tt)
    return {
        'white': rng.normal(0, NOISE_STD, tt.size),
        'slow': slow,
        'white_plus_slow': slow + rng.normal(0, NOISE_STD, tt.size),
    }


def fold_by_period(tt, values, period):
    """Fold values over the event period."""
    phase_t = (tt - EVENT_T0) % period
    bins = np.linspace(0, period, FOLD_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    folded = np.full(centers.shape, np.nan)
    for idx, (left, right) in enumerate(zip(bins[:-1], bins[1:])):
        keep = (phase_t >= left) & (phase_t < right)
        keep = keep & np.isfinite(values)
        if np.any(keep):
            folded[idx] = np.nanmean(values[keep])
    return centers, folded


def plot_mask_geometry(tt, valid, out_path):
    """Plot the periodic mask geometry."""
    period = 1 / EVENT_FREQ
    t_fold, valid_fold = fold_by_period(tt, valid.astype(float), period)
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=False)

    # Show the full timeline and the folded event-period mask
    keep = (tt >= EVENT_T_ANALYSIS) & (tt <= EVENT_T_ANALYSIS + 2)
    ax[0].plot(tt[keep], valid[keep].astype(float), color='C0', linewidth=1)
    ax[0].set_ylabel('Valid')
    ax[0].set_title('Periodic mask in time')
    ax[1].plot(t_fold, valid_fold, color='C1', linewidth=1.5)
    ax[1].set_ylim(-0.05, 1.05)
    ax[1].set_xlabel('Time within event period (s)')
    ax[1].set_ylabel('Valid fraction')
    ax[1].set_title('Folded mask')
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def plot_example_signal(tt, events, x, x_masked, out_path):
    """Plot one signal before and after masking."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 4))

    # Draw the surrogate trace and its masked version
    keep = (tt >= EVENT_T_ANALYSIS) & (tt <= EVENT_T_ANALYSIS + 2)
    ax.plot(tt[keep], x[keep], color='0.75', linewidth=1, label='raw white')
    ax.plot(tt[keep], x_masked[keep], color='C0', linewidth=1.2, label='masked white')
    for t0 in events:
        if EVENT_T_ANALYSIS <= t0 <= EVENT_T_ANALYSIS + 2:
            ax.axvline(t0, color='0.6', linestyle='--', linewidth=0.7)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Signal')
    ax.set_title('White noise with periodic missing windows')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def plot_phase_hist(phases_by_signal, out_path):
    """Plot phase distributions from local fits."""
    bins = np.linspace(-np.pi, np.pi, PHASE_BINS + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))

    # Compare event-phase estimates across simple signals
    for name, phases in phases_by_signal.items():
        phases = phases[np.isfinite(phases)]
        phases = np.angle(np.exp(1j * phases))
        counts, _ = np.histogram(phases, bins=bins)
        prob = counts / counts.sum() if counts.sum() else counts.astype(float)
        ax.plot(centers, prob, linewidth=1.3, label=name)
    ax.set_xlabel('Fitted phase at event')
    ax.set_ylabel('Probability')
    ax.set_title('Phase estimates under periodic masking')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def plot_power_spectra(freqs, spectra, out_path):
    """Plot mean local-fit power spectra."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))

    # Plot spectra from actual surrogates and averaged white-noise controls
    for name, powers in spectra.items():
        ax.plot(freqs, powers, 'o-', linewidth=1.3, markersize=3, label=name)
    ax.axvline(TARGET_FREQ, color='k', linestyle='--', linewidth=1)
    ax.set_xlabel('Fit frequency (Hz)')
    ax.set_ylabel('Mean fitted power')
    ax.set_title('Periodic mask creates a target-frequency power peak')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI)
    plt.close(fig)


def write_summary(out_path, rows):
    """Write a compact text summary."""
    lines = [
        '# Periodic Mask Fit Demo',
        '',
        '## Parameters',
        f'- Event frequency: `{EVENT_FREQ} Hz`',
        f'- Event period: `{1 / EVENT_FREQ:.4g} s`',
        f'- Pulse width: `{PULSE_WIDTH:.4g} s`',
        f'- Pulse pad: `{PULSE_PAD:.4g} s`',
        f'- Clean interval: `{1 / EVENT_FREQ - PULSE_WIDTH - 2 * PULSE_PAD:.4g} s`',
        f'- Fit target frequency: `{TARGET_FREQ} Hz`',
        f'- Fit half-width: `{fit_half_width(TARGET_FREQ):.4g} s`',
        '',
        '## Results',
        '| signal | ITC | random floor | median valid mass | peak freq | peak/median power |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['itc']:.3g} | {row['floor']:.3g} | "
            f"{row['mass_median']:.3g} | {row['peak_freq']:.3g} | "
            f"{row['peak_ratio']:.3g} |"
        )
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    """Run the periodic-mask fitting demo."""
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    tt = make_time()
    events = make_events()
    analysis_events = events[events >= EVENT_T_ANALYSIS]
    valid = make_valid_mask(tt, events)
    signals = make_signals(tt, rng)
    rows = []
    phases_by_signal = {}
    spectra = {}

    # Analyze one realization of each simple surrogate signal
    for name, x in signals.items():
        x_masked = apply_mask(x, valid)
        phases, masses = fit_phases_at_events(x_masked, tt, analysis_events)
        freqs, powers = power_spectrum(x_masked, tt)
        phases_by_signal[name] = phases
        spectra[name] = powers
        n_phase = np.isfinite(phases).sum()
        peak_idx = int(np.nanargmax(powers))
        rows.append({
            'name': name,
            'itc': float(np.abs(np.nanmean(np.exp(1j * phases)))),
            'floor': float(1 / np.sqrt(n_phase)),
            'mass_median': float(np.nanmedian(masses)),
            'peak_freq': float(freqs[peak_idx]),
            'peak_ratio': float(np.nanmax(powers) / np.nanmedian(powers)),
        })

    # Average many white-noise spectra and phases to expose mask-induced bias
    white_spectra = []
    white_phases = []
    for _ in range(N_NOISE_POWER):
        x = rng.normal(0, NOISE_STD, tt.size)
        x_masked = apply_mask(x, valid)
        phases, _ = fit_phases_at_events(x_masked, tt, analysis_events)
        _, powers = power_spectrum(x_masked, tt)
        white_phases.append(phases)
        white_spectra.append(powers)
    white_many_name = f'white_many_{N_NOISE_POWER}'
    phases_by_signal[white_many_name] = np.concatenate(white_phases)
    spectra[f'white_mean_{N_NOISE_POWER}'] = np.nanmean(
        np.stack(white_spectra),
        axis=0,
    )

    # Save focused plots and summary
    plot_mask_geometry(tt, valid, DIR_OUT / 'mask_geometry.png')
    plot_example_signal(
        tt,
        events,
        signals['white'],
        apply_mask(signals['white'], valid),
        DIR_OUT / 'white_signal_masked.png',
    )
    plot_phase_hist(phases_by_signal, DIR_OUT / 'phase_hist.png')
    plot_power_spectra(freqs, spectra, DIR_OUT / 'power_spectrum.png')
    write_summary(DIR_OUT / 'summary.md', rows)
    print(f'Saved {DIR_OUT}', flush=True)


if __name__ == '__main__':
    main()
