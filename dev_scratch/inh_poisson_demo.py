from pathlib import Path
import sys

dirpath_root = Path(__file__).resolve().parents[1]
sys.path.append(str(dirpath_root))
print(dirpath_root)

import matplotlib.pyplot as plt
import numpy as np

from utils.inh_poisson import inh_poisson_generator, generate_trains


# ---------------------------------------------------------------------------
# Rate estimation (for validation)
# ---------------------------------------------------------------------------

def estimate_rate(trains, t_start, t_stop, bin_ms=50.0, smooth_ms=None):
    """
    Estimate mean population firing rate (Hz) from spike trains via PSTH.

    Parameters
    ----------
    trains    : list of spike-time lists
    t_start   : float  - start time (ms)
    t_stop    : float  - stop time (ms)
    bin_ms    : float  - histogram bin width (ms)
    smooth_ms : float | None - Gaussian smoothing sigma (ms); None = no smoothing

    Returns
    -------
    t_centres : np.ndarray - bin centre times (ms)
    rate_hz   : np.ndarray - estimated rate (Hz)
    """
    edges = np.arange(t_start, t_stop + bin_ms, bin_ms)
    counts = np.zeros(len(edges) - 1)
    n_cells = len(trains)

    for train in trains:
        if len(train):
            c, _ = np.histogram(train, bins=edges)
            counts += c

    rate_hz = counts / (n_cells * bin_ms * 1e-3)  # Hz
    t_centres = 0.5 * (edges[:-1] + edges[1:])

    if smooth_ms is not None:
        from scipy.ndimage import gaussian_filter1d
        rate_hz = gaussian_filter1d(rate_hz, sigma=smooth_ms / bin_ms)

    return t_centres, rate_hz


# ---------------------------------------------------------------------------
# Named rate profiles used in tests and plots
# ---------------------------------------------------------------------------

# Per-scenario PSTH parameters.
# bin_ms and smooth_ms must be small enough that the smoothing kernel does not
# attenuate the signal's dominant frequencies.
# For a Gaussian smoother with sigma=s ms on a sinusoid at frequency f Hz:
#   amplitude retention = exp(-s^2 * (2*pi*f/1000)^2 / 2)
# At f=4 Hz, s=80 ms -> retention ~0.13 (87% attenuation). s=15 ms -> ~0.97.
SCENARIO_PSTH_PARAMS = {
    'constant':      {'bin_ms': 50.0, 'smooth_ms': 80.0},
    'ramp_up':       {'bin_ms': 50.0, 'smooth_ms': 80.0},
    'ramp_down':     {'bin_ms': 50.0, 'smooth_ms': 80.0},
    'sinusoidal':    {'bin_ms': 10.0, 'smooth_ms': 15.0},  # 4 Hz -> period 250 ms
    'step':          {'bin_ms': 30.0, 'smooth_ms': 40.0},
    'gaussian_bump': {'bin_ms': 30.0, 'smooth_ms': 40.0},
}


def make_rate_signal(kind, t):
    """Return a rate array (Hz) for the given named profile over times t (ms)."""
    t = np.asarray(t, dtype=float)
    if kind == 'constant':
        return np.full_like(t, 20.0)
    if kind == 'ramp_up':
        return np.linspace(5.0, 80.0, len(t))
    if kind == 'ramp_down':
        return np.linspace(80.0, 5.0, len(t))
    if kind == 'sinusoidal':
        return 30.0 + 25.0 * np.sin(2 * np.pi * 4.0 * t * 1e-3)
    if kind == 'step':
        r = np.full_like(t, 10.0)
        r[t >= t[-1] / 2] = 60.0
        return r
    if kind == 'gaussian_bump':
        c, s = t[-1] / 2, t[-1] / 8
        return 5.0 + 70.0 * np.exp(-0.5 * ((t - c) / s) ** 2)
    raise ValueError(f'Unknown rate kind: {kind!r}')


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_poisson_statistics(n_cells=500, duration=5000.0, rate_val=20.0, seed=0):
    """For constant rate: CV of ISI should be ~1, mean rate should match target."""
    dt = 5.0
    t = np.arange(0, duration, dt)
    rate = np.full_like(t, rate_val)
    trains = generate_trains(rate, t, t_stop=duration,
                             n_cells=n_cells, base_seed=seed)

    all_isi = np.concatenate([np.diff(np.sort(tr))
                               for tr in trains if len(tr) > 1])
    cv = float(np.std(all_isi) / np.mean(all_isi))
    mean_rate_meas = float(1000.0 / np.mean(all_isi))
    return cv, mean_rate_meas


def test_seed_independence(n_cells=50, duration=5000.0, seed=99):
    """Mean pairwise spike-count correlation should be close to zero."""
    dt = 5.0
    t = np.arange(0, duration, dt)
    rate = make_rate_signal('sinusoidal', t)
    trains = generate_trains(rate, t, t_stop=duration,
                             n_cells=n_cells, base_seed=seed)

    edges = np.arange(0, duration + 1, 1.0)
    vecs = np.array([np.histogram(tr, bins=edges)[0].astype(float)
                     for tr in trains])
    corr = np.corrcoef(vecs)
    np.fill_diagonal(corr, np.nan)
    return float(np.nanmean(corr))


def test_rate_accuracy(kind, n_cells=200, duration=2000.0, dt=5.0,
                       bin_ms=None, smooth_ms=None, seed=42):
    """Return MAE (Hz) between target rate and PSTH-estimated rate."""
    psth_par = SCENARIO_PSTH_PARAMS.get(kind, {'bin_ms': 50.0, 'smooth_ms': 80.0})
    if bin_ms is None:
        bin_ms = psth_par['bin_ms']
    if smooth_ms is None:
        smooth_ms = psth_par['smooth_ms']
    t = np.arange(0, duration, dt)
    rate = make_rate_signal(kind, t)
    trains = generate_trains(rate, t, t_stop=duration,
                             n_cells=n_cells, base_seed=seed)
    t_est, rate_est = estimate_rate(trains, 0.0, duration, bin_ms, smooth_ms)
    target_at_bins = np.interp(t_est, t, rate)
    return float(np.mean(np.abs(rate_est - target_at_bins)))


def test_empty_train_zero_rate():
    """Generator must return [] without error for zero-rate input."""
    t = np.linspace(0, 1000, 100)
    rate = np.zeros(100)
    result = inh_poisson_generator(rate, t, t_stop=1000.0, seed=0)
    assert result == [], f'Expected [], got {result}'


def test_shape_mismatch():
    """Mismatched t and rate shapes must raise ValueError."""
    import sys
    try:
        inh_poisson_generator(np.ones(10), np.ones(5), 1000.0)
        assert False, 'Should have raised ValueError'
    except ValueError:
        pass


def test_reproducibility():
    """Same seed must produce identical trains."""
    t = np.linspace(0, 2000, 400)
    rate = make_rate_signal('sinusoidal', t)
    a = inh_poisson_generator(rate, t, 2000.0, seed=123)
    b = inh_poisson_generator(rate, t, 2000.0, seed=123)
    assert a == b, 'Same seed gave different trains'


def test_different_seeds_differ():
    """Different seeds should produce different trains."""
    t = np.linspace(0, 2000, 400)
    rate = make_rate_signal('sinusoidal', t)
    a = inh_poisson_generator(rate, t, 2000.0, seed=1)
    b = inh_poisson_generator(rate, t, 2000.0, seed=2)
    assert a != b, 'Different seeds gave identical trains'


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_scenarios(out_path=None, n_cells=300, duration=2000.0):
    """
    6-panel figure: one panel per rate scenario.
    Each panel shows the target rate and the PSTH-estimated rate.
    """
    scenarios = ['constant', 'ramp_up', 'ramp_down',
                 'sinusoidal', 'step', 'gaussian_bump']
    dt = 5.0
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))

    for ax, kind in zip(axes.flatten(), scenarios):
        t = np.arange(0, duration, dt)
        rate = make_rate_signal(kind, t)
        trains = generate_trains(rate, t, t_stop=duration,
                                 n_cells=n_cells, base_seed=42)
        psth_par = SCENARIO_PSTH_PARAMS.get(kind, {'bin_ms': 50.0, 'smooth_ms': 80.0})
        t_est, rate_est = estimate_rate(trains, 0.0, duration, **psth_par)
        mae = np.mean(np.abs(rate_est - np.interp(t_est, t, rate)))

        ax.plot(t, rate, 'k-', lw=1.5, label='target')
        ax.plot(t_est, rate_est, 'r-', lw=1.5,
                label=f'estimated (n={n_cells})')
        ax.set_title(f'{kind}   MAE={mae:.1f} Hz')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('Rate (Hz)')
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=8)

    fig.suptitle('inh_poisson_generator – rate accuracy across scenarios',
                 fontsize=13)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150)
        print(f'  saved {out_path}')
    else:
        plt.show()
    plt.close(fig)


def plot_raster_and_rate(kind='sinusoidal', n_cells=80, duration=2000.0,
                         dt=5.0, seed=0, out_path=None):
    """
    Two-panel figure: spike raster (top) and rate overlay (bottom).
    Demonstrates that measured population rate matches the target signal.
    """
    t = np.arange(0, duration, dt)
    rate = make_rate_signal(kind, t)
    trains = generate_trains(rate, t, t_stop=duration,
                             n_cells=n_cells, base_seed=seed)
    psth_par = SCENARIO_PSTH_PARAMS.get(kind, {'bin_ms': 30.0, 'smooth_ms': 60.0})
    t_est, rate_est = estimate_rate(trains, 0.0, duration, **psth_par)

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True,
                              gridspec_kw={'height_ratios': [3, 2]})

    ax = axes[0]
    for i, train in enumerate(trains):
        if train:
            ax.scatter(train, np.full(len(train), i),
                       s=1, c='k', alpha=0.4, rasterized=True)
    ax.set_ylabel('Cell index')
    ax.set_title(f'Spike raster – {kind}  (n={n_cells})')

    ax = axes[1]
    ax.plot(t, rate, 'k-', lw=2, label='target rate')
    ax.plot(t_est, rate_est, 'r-', lw=2, label='PSTH estimate')
    ax.set_xlabel('Time (ms)')
    ax.set_ylabel('Rate (Hz)')
    ax.set_ylim(bottom=0)
    ax.legend()

    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150)
        print(f'  saved {out_path}')
    else:
        plt.show()
    plt.close(fig)


def plot_isi_distribution(n_cells=500, duration=5000.0, rate_val=30.0,
                          seed=7, out_path=None):
    """
    ISI histogram vs theoretical exponential distribution.
    Sanity-checks that the generator produces genuine Poisson statistics
    for a constant-rate signal.
    """
    dt = 5.0
    t = np.arange(0, duration, dt)
    rate = np.full_like(t, rate_val)
    trains = generate_trains(rate, t, t_stop=duration,
                             n_cells=n_cells, base_seed=seed)

    all_isi = np.concatenate([np.diff(np.sort(tr))
                               for tr in trains if len(tr) > 1])
    cv = np.std(all_isi) / np.mean(all_isi)
    mean_isi = np.mean(all_isi)

    fig, ax = plt.subplots(figsize=(7, 5))
    bins = np.linspace(0, 5 * mean_isi, 60)
    ax.hist(all_isi, bins=bins, density=True, alpha=0.6,
            color='steelblue', label=f'measured  CV={cv:.3f}')
    lam = rate_val / 1000.0          # spikes/ms -> 1/ms
    x = np.linspace(0, bins[-1], 300)
    ax.plot(x, lam * np.exp(-lam * x), 'r-', lw=2,
            label=f'Exponential ({rate_val} Hz)')
    ax.set_xlabel('ISI (ms)')
    ax.set_ylabel('Density')
    ax.set_title(f'ISI distribution – constant {rate_val} Hz  (n={n_cells})')
    ax.legend()
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=150)
        print(f'  saved {out_path}')
    else:
        plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    out_dir = Path(__file__).parent

    # ------------------------------------------------------------------
    print('=== Test: zero-rate input ===')
    test_empty_train_zero_rate()
    print('  PASS')

    print('=== Test: shape mismatch raises ValueError ===')
    test_shape_mismatch()
    print('  PASS')

    print('=== Test: reproducibility (same seed) ===')
    test_reproducibility()
    print('  PASS')

    print('=== Test: different seeds differ ===')
    test_different_seeds_differ()
    print('  PASS')

    # ------------------------------------------------------------------
    print('\n=== Test: Poisson statistics (constant rate, 500 cells) ===')
    cv, rate_meas = test_poisson_statistics()
    print(f'  CV = {cv:.3f}  (expect ~1.0)')
    print(f'  mean rate = {rate_meas:.2f} Hz  (expect ~20.0 Hz)')
    assert abs(cv - 1.0) < 0.05,        f'CV out of range: {cv:.3f}'
    assert abs(rate_meas - 20.0) < 1.0, f'Rate out of range: {rate_meas:.2f}'
    print('  PASS')

    # ------------------------------------------------------------------
    print('\n=== Test: seed independence ===')
    mean_cc = test_seed_independence()
    print(f'  Mean pairwise CC = {mean_cc:.4f}  (expect |CC| < 0.05)')
    assert abs(mean_cc) < 0.05, f'Cells not independent: CC={mean_cc:.4f}'
    print('  PASS')

    # ------------------------------------------------------------------
    print('\n=== Test: rate accuracy per scenario ===')
    for kind in ['constant', 'ramp_up', 'sinusoidal', 'step', 'gaussian_bump']:
        mae = test_rate_accuracy(kind)
        print(f'  {kind:20s}  MAE = {mae:.2f} Hz')

    # ------------------------------------------------------------------
    print('\n=== Generating plots ===')
    plot_scenarios(
        out_path=str(out_dir / 'inh_poisson_scenarios.png'),
        n_cells=300, duration=2000.0)
    plot_raster_and_rate(
        kind='sinusoidal', n_cells=80,
        out_path=str(out_dir / 'inh_poisson_raster.png'))
    plot_isi_distribution(
        out_path=str(out_dir / 'inh_poisson_isi.png'))

    print('\nAll done.')
