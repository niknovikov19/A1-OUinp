import argparse
import json
from pathlib import Path
import re
import warnings

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit
import xarray as xr


DIR_STEP_RESP = Path(__file__).resolve().parents[1]


# Configuration
DATASET_NAME = 'l2_asym_pilot'
DIR_DATA_DEFAULT = DIR_STEP_RESP / 'data' / DATASET_NAME

# Time range and smoothing used in fitting
T_LIMITS_USED = (5, None)
SMOOTH_WIN_S = 0.2
TURN_MARGIN_S = 0.1
MIN_FIT_POINTS = 40

NEED_PLOT = 1
JOB_PATTERN = re.compile(r'rvec_(\d+)_seed_(\d+)\.nc$')


def richards(x, A, K, B, M, nu):
    """Evaluate the Richards input-output curve."""
    exponent = np.clip(-B * (x - M), -700, 700)
    return A + (K - A) / (1 + np.exp(exponent)) ** (1 / nu)


def richards_derivative(x, A, K, B, M, nu):
    """Evaluate the Richards derivative."""
    exponent = np.clip(-B * (x - M), -700, 700)
    exp_term = np.exp(exponent)
    base = 1 + exp_term
    return (K - A) * B * exp_term / (nu * base ** (1 + 1 / nu))


def fit_richards_function(x_fit, y_fit):
    """Fit a monotone Richards curve using several stable initial values."""
    x_fit = np.asarray(x_fit, dtype=float)
    y_fit = np.asarray(y_fit, dtype=float)
    x_span = float(np.ptp(x_fit))
    y_span = max(float(np.ptp(y_fit)), 1)
    if x_fit.size < MIN_FIT_POINTS or x_span <= 0:
        return None, None, False

    x_min = float(np.min(x_fit))
    x_max = float(np.max(x_fit))
    y_min = float(np.min(y_fit))
    y_max = float(np.max(y_fit))
    lower = [max(0, y_min - y_span), 0, 1e-6, x_min - x_span, 0.05]
    upper = [y_max, y_max + 2 * y_span, 100 / x_span,
             x_max + x_span, 20]

    # Try several slopes and asymmetry values to reduce initialization bias
    fits = []
    for b_scale in (1, 4, 10):
        for nu_init in (0.5, 1, 2):
            p0 = [max(0, y_min), y_max, b_scale / x_span,
                  float(np.median(x_fit)), nu_init]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', OptimizeWarning)
                    popt, pcov = curve_fit(
                        richards,
                        x_fit,
                        y_fit,
                        p0=p0,
                        bounds=(lower, upper),
                        maxfev=50000,
                    )
            except (RuntimeError, ValueError, FloatingPointError):
                continue
            if popt[1] <= popt[0]:
                continue
            residual = y_fit - richards(x_fit, *popt)
            fits.append((float(np.sum(residual ** 2)), popt, pcov))

    if not fits:
        return None, None, False
    _, popt, pcov = min(fits, key=lambda item: item[0])
    return popt, pcov, True


def parse_job_path(fpath):
    """Extract the job number and seed from one rate filename."""
    match = JOB_PATTERN.fullmatch(fpath.name)
    if match is None:
        raise ValueError(f'Unexpected rate filename: {fpath.name}')
    return int(match.group(1)), int(match.group(2))


def _load_dataarray(fpath):
    """Load one small DataArray and close its NetCDF file."""
    with xr.open_dataarray(fpath) as data:
        return data.load()


def _validate_job_pair(rvec, hvec, rpath, hpath):
    """Validate one rate/current pair before combining jobs."""
    expected_dims = {'pop', 'time'}
    if set(rvec.dims) != expected_dims:
        raise ValueError(f'Unexpected rate dimensions in {rpath}: {rvec.dims}')
    if set(hvec.dims) != expected_dims:
        raise ValueError(f'Unexpected h dimensions in {hpath}: {hvec.dims}')

    rvec = rvec.transpose('pop', 'time')
    hvec = hvec.transpose('pop', 'time')
    if not np.array_equal(rvec['pop'].values, hvec['pop'].values):
        raise ValueError(f'Population mismatch between {rpath} and {hpath}')
    if not np.array_equal(rvec['time'].values, hvec['time'].values):
        raise ValueError(f'Time mismatch between {rpath} and {hpath}')
    if not np.isfinite(rvec.values).all():
        raise ValueError(f'Non-finite rates in {rpath}')
    if not np.isfinite(hvec.values).all():
        raise ValueError(f'Non-finite currents in {hpath}')
    return rvec, hvec


def collect_h_rate_data(dirpath_data):
    """Collect paired h/r files over every available seed."""
    dirpath_input = dirpath_data / 'input'
    dirpath_rvec = dirpath_input / 'rvec_xr'
    dirpath_hvec = dirpath_input / 'hvec_xr'
    rpaths = sorted(dirpath_rvec.glob('rvec_*_seed_*.nc'))
    if not rpaths:
        raise FileNotFoundError(f'No rate files found under {dirpath_rvec}')

    rates = []
    currents = []
    seeds = []
    jobs = []
    seen_seeds = set()
    reference_pop = None
    reference_time = None
    for rpath in rpaths:
        job, seed = parse_job_path(rpath)
        if seed in seen_seeds:
            raise ValueError(f'Duplicate seed {seed} in {dirpath_rvec}')
        hpath = dirpath_hvec / rpath.name.replace('rvec_', 'hvec_', 1)
        if not hpath.is_file():
            raise FileNotFoundError(f'Missing current file paired with {rpath}')

        rvec = _load_dataarray(rpath)
        hvec = _load_dataarray(hpath)
        rvec, hvec = _validate_job_pair(rvec, hvec, rpath, hpath)
        if reference_pop is None:
            reference_pop = rvec['pop'].values
            reference_time = rvec['time'].values
        if not np.array_equal(reference_pop, rvec['pop'].values):
            raise ValueError(f'Population coordinates differ in {rpath}')
        if not np.array_equal(reference_time, rvec['time'].values):
            raise ValueError(f'Time coordinates differ in {rpath}')

        rates.append(rvec.expand_dims(seed=[seed]))
        currents.append(hvec.expand_dims(seed=[seed]))
        seeds.append(seed)
        jobs.append(job)
        seen_seeds.add(seed)

    rate = xr.concat(rates, dim='seed').transpose('seed', 'pop', 'time')
    current = xr.concat(currents, dim='seed').transpose('seed', 'pop', 'time')
    rate = rate.assign_coords(job=('seed', jobs))
    current = current.assign_coords(job=('seed', jobs))
    dataset = xr.Dataset({'rate': rate, 'h': current})
    dataset.attrs['source'] = 'paired rvec_xr and hvec_xr files'
    dataset.attrs['seed_count'] = len(seeds)
    return dataset


def smooth_rates(rate, smooth_win_s):
    """Apply the additional rolling average used by the static fitter."""
    time = np.asarray(rate['time'].values, dtype=float)
    if time.size < 2:
        raise ValueError('At least two rate samples are required')
    dt = float(np.median(np.diff(time)))
    if dt <= 0:
        raise ValueError('Rate time must be strictly increasing')
    smooth_win_n = max(1, int(round(smooth_win_s / dt)))
    smoothed = rate.rolling(
        time=smooth_win_n,
        center=True,
        min_periods=1,
    ).mean()
    smoothed.attrs.update(rate.attrs)
    smoothed.attrs['fit_smooth_win_s'] = float(smooth_win_s)
    return smoothed, smooth_win_n


def get_branch_masks(time, current, turn_margin_s):
    """Identify rising/falling triangle branches away from turning points."""
    time = np.asarray(time, dtype=float)
    current = np.asarray(current, dtype=float)
    derivative = np.gradient(current, time)
    max_slope = float(np.max(np.abs(derivative)))
    if max_slope <= 0:
        raise ValueError('Current trace is constant')

    tolerance = max_slope * 1e-6
    branch = np.zeros(current.size, dtype=int)
    branch[derivative > tolerance] = 1
    branch[derivative < -tolerance] = -1

    # Remove points close to flat samples and slope reversals
    transition = np.flatnonzero(branch == 0).tolist()
    transition += (
        np.flatnonzero(branch[1:] * branch[:-1] < 0) + 1
    ).tolist()
    away_from_turns = np.ones(current.size, dtype=bool)
    for index in transition:
        away_from_turns &= np.abs(time - time[index]) > turn_margin_s
    rising = (branch == 1) & away_from_turns
    falling = (branch == -1) & away_from_turns
    return rising, falling


def collect_population_points(dataset, rate_sm, pop, t_limits,
                              turn_margin_s):
    """Collect pooled seed points and branch labels for one population."""
    time = np.asarray(dataset['time'].values, dtype=float)
    start, stop = t_limits
    time_mask = time >= start
    if stop is not None:
        time_mask &= time <= stop

    x_parts = []
    y_parts = []
    seed_parts = []
    branch_parts = []
    for seed in dataset['seed'].values:
        current = dataset['h'].sel(seed=seed, pop=pop).values
        rate = rate_sm.sel(seed=seed, pop=pop).values
        rising, falling = get_branch_masks(time, current, turn_margin_s)
        branch = np.zeros(time.size, dtype=int)
        branch[rising] = 1
        branch[falling] = -1
        valid = time_mask & (branch != 0)
        valid &= np.isfinite(current) & np.isfinite(rate)
        x_parts.append(current[valid])
        y_parts.append(rate[valid])
        seed_parts.append(np.full(np.sum(valid), int(seed), dtype=int))
        branch_parts.append(branch[valid])

    return {
        'x': np.concatenate(x_parts),
        'y': np.concatenate(y_parts),
        'seed': np.concatenate(seed_parts),
        'branch': np.concatenate(branch_parts),
    }


def get_fit_summary(x, y, popt, pcov):
    """Build serializable coefficients and fit-quality values."""
    fitted = richards(x, *popt)
    residual = y - fitted
    ss_res = float(np.sum(residual ** 2))
    ss_total = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = np.nan if ss_total == 0 else 1 - ss_res / ss_total
    stderr = np.sqrt(np.maximum(0, np.diag(pcov)))
    names = ('A', 'K', 'B', 'M', 'nu')
    summary = {name: float(value) for name, value in zip(names, popt)}
    summary['stderr'] = {
        name: float(value) for name, value in zip(names, stderr)
    }
    summary['n_points'] = int(x.size)
    summary['rmse'] = float(np.sqrt(np.mean(residual ** 2)))
    summary['r_squared'] = float(r_squared)
    summary['dR_dh_at_0'] = float(richards_derivative(0, *popt))
    return summary


def fit_one_curve(x, y):
    """Fit one curve and return its serializable summary."""
    popt, pcov, success = fit_richards_function(x, y)
    if not success:
        return None, None
    return popt, get_fit_summary(x, y, popt, pcov)


def get_baseline_rates(dataset, rate_sm, pop, fit_start):
    """Measure each seed's mean rate before the h sweep begins."""
    baseline = rate_sm.sel(pop=pop).where(
        dataset['time'] < fit_start,
        drop=True,
    ).mean('time')
    return {
        str(int(seed)): float(baseline.sel(seed=seed).values)
        for seed in dataset['seed'].values
    }


def plot_population_fit(pop, points, popt, summary, fpath):
    """Plot seed/branch samples, the fitted curve, and zero-current tangent."""
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = {1: 'C0', -1: 'C1'}
    names = {1: 'rising', -1: 'falling'}
    for n_seed, seed in enumerate(np.unique(points['seed'])):
        for branch in (1, -1):
            mask = (points['seed'] == seed) & (points['branch'] == branch)
            label = names[branch] if n_seed == 0 else None
            ax.plot(
                points['x'][mask],
                points['y'][mask],
                '.',
                color=colors[branch],
                alpha=0.12,
                markersize=3,
                label=label,
            )

    x_range = np.linspace(np.min(points['x']), np.max(points['x']), 500)
    y_fit = richards(x_range, *popt)
    ax.plot(x_range, y_fit, 'k-', linewidth=2, label='Richards fit')

    # Show branch fits so hysteresis remains visible in the primary figure
    param_names = ('A', 'K', 'B', 'M', 'nu')
    for branch, name in ((1, 'rising'), (-1, 'falling')):
        branch_fit = summary['branches'].get(name)
        if branch_fit is None:
            continue
        branch_params = [branch_fit[key] for key in param_names]
        ax.plot(
            x_range,
            richards(x_range, *branch_params),
            '--',
            color=colors[branch],
            linewidth=1.5,
            label=f'{name} fit',
        )

    q_value = summary['dR_dh_at_0']
    r_at_zero = float(richards(0, *popt))
    y_tangent = q_value * x_range + r_at_zero
    ax.plot(x_range, y_tangent, 'k--', linewidth=1.5, label='tangent at h=0')
    ax.axvline(0, color='0.5', linestyle=':', linewidth=1)
    ax.set_xlabel('h (nA)')
    ax.set_ylabel('Firing rate (Hz)')
    q_rising = summary['branches'].get('rising')
    q_falling = summary['branches'].get('falling')
    branch_title = ''
    if q_rising is not None and q_falling is not None:
        branch_title = (
            f'; branches {q_rising["dR_dh_at_0"]:.3g}, '
            f'{q_falling["dR_dh_at_0"]:.3g}'
        )
    ax.set_title(f'{pop}: dR/dh = {q_value:.3g} Hz/nA{branch_title}')
    ax.grid(False)
    ax.legend()
    fig.tight_layout()
    fig.savefig(fpath, dpi=150, bbox_inches='tight')
    plt.close(fig)


def fit_h_rate_curves(dataset, smooth_win_s, t_limits, turn_margin_s,
                      dirpath_plots=None):
    """Fit diagonal h-to-rate curves and return coefficients and Q."""
    rate_sm, smooth_win_n = smooth_rates(dataset['rate'], smooth_win_s)
    pops_h = [str(pop) for pop in dataset['h']['pop'].values]
    pops_post = [str(pop) for pop in dataset['rate']['pop'].values]
    if pops_h != pops_post:
        raise ValueError('h and rate populations must have identical ordering')

    coefficients = {}
    q_values = np.full(len(pops_h), np.nan)
    for index, pop in enumerate(pops_h):
        points = collect_population_points(
            dataset,
            rate_sm,
            pop,
            t_limits,
            turn_margin_s,
        )
        popt, summary = fit_one_curve(points['x'], points['y'])
        coefficients[pop] = {pop: {'success': summary is not None}}
        entry = coefficients[pop][pop]
        entry['baseline_rate_by_seed'] = get_baseline_rates(
            dataset,
            rate_sm,
            pop,
            t_limits[0],
        )
        entry['h_min'] = float(np.min(points['x']))
        entry['h_max'] = float(np.max(points['x']))
        if summary is None:
            continue

        entry.update(summary)
        q_values[index] = summary['dR_dh_at_0']

        # Fit rising and falling branches independently as a hysteresis check
        entry['branches'] = {}
        for branch, name in ((1, 'rising'), (-1, 'falling')):
            mask = points['branch'] == branch
            _, branch_summary = fit_one_curve(
                points['x'][mask],
                points['y'][mask],
            )
            entry['branches'][name] = branch_summary

        rising = entry['branches']['rising']
        falling = entry['branches']['falling']
        if rising is not None and falling is not None:
            q_rising = rising['dR_dh_at_0']
            q_falling = falling['dR_dh_at_0']
            denominator = max(0.5 * (abs(q_rising) + abs(q_falling)), 1e-12)
            entry['branch_relative_difference'] = (
                abs(q_rising - q_falling) / denominator
            )

        if dirpath_plots is not None:
            plot_population_fit(
                pop,
                points,
                popt,
                entry,
                dirpath_plots / f'{pop}.png',
            )

    # Keep the r-r convention: input population first, output population second
    q_matrix = np.zeros((len(pops_h), len(pops_post)))
    np.fill_diagonal(q_matrix, q_values)
    q_xr = xr.DataArray(
        q_matrix,
        dims=('pop_h', 'pop_post'),
        coords={'pop_h': pops_h, 'pop_post': pops_post},
        name='Q',
    )
    q_xr.attrs['units'] = 'Hz/nA'
    q_xr.attrs['orientation'] = 'input population x output population'
    q_xr.attrs['off_diagonal'] = 'structural zero in decoupled experiment'
    q_xr.attrs['evaluation_h_nA'] = 0
    q_xr.attrs['smooth_win_s'] = float(smooth_win_s)
    q_xr.attrs['smooth_win_n'] = int(smooth_win_n)
    q_xr.attrs['fit_t_start_s'] = float(t_limits[0])
    if t_limits[1] is not None:
        q_xr.attrs['fit_t_stop_s'] = float(t_limits[1])
    q_xr.attrs['turn_margin_s'] = float(turn_margin_s)
    return coefficients, q_xr


def save_results(dataset, coefficients, q_xr, dirpath_data, smooth_win_s):
    """Save combined inputs, coefficients, and the labelled Q matrix."""
    dirpath_processed = dirpath_data / 'processed'
    dirpath_results = dirpath_processed / f'tau_{smooth_win_s:g}'
    dirpath_processed.mkdir(parents=True, exist_ok=True)
    dirpath_results.mkdir(parents=True, exist_ok=True)

    fpath_combined = dirpath_processed / 'h_rate.nc'
    dataset.to_netcdf(fpath_combined)

    fpath_coeffs = dirpath_results / 'richards_coeffs.json'
    with fpath_coeffs.open('w', encoding='utf-8') as fid:
        json.dump(coefficients, fid, indent=2)

    fpath_q_nc = dirpath_results / 'qmat.nc'
    fpath_q_json = dirpath_results / 'qmat.json'
    q_xr.to_netcdf(fpath_q_nc)
    q_dict = {
        'pop_h': [str(pop) for pop in q_xr['pop_h'].values],
        'pop_post': [str(pop) for pop in q_xr['pop_post'].values],
        'Q': q_xr.values.tolist(),
        'attrs': dict(q_xr.attrs),
    }
    with fpath_q_json.open('w', encoding='utf-8') as fid:
        json.dump(q_dict, fid, indent=2)
    return fpath_combined, fpath_coeffs, fpath_q_nc, fpath_q_json


def build_parser():
    """Build the local h-r fitting command line."""
    parser = argparse.ArgumentParser(
        description='Fit static population-rate responses to h IClamp sweeps.',
    )
    parser.add_argument('--data-dir', type=Path, default=DIR_DATA_DEFAULT)
    parser.add_argument('--fit-start', type=float, default=T_LIMITS_USED[0])
    parser.add_argument('--fit-stop', type=float, default=T_LIMITS_USED[1])
    parser.add_argument('--smooth-win', type=float, default=SMOOTH_WIN_S)
    parser.add_argument('--turn-margin', type=float, default=TURN_MARGIN_S)
    parser.add_argument('--no-plot', action='store_true')
    return parser


def main():
    """Collect local h/r files, fit Q, and save diagnostics."""
    args = build_parser().parse_args()
    dirpath_data = args.data_dir.resolve()
    dirpath_results = (
        dirpath_data / 'processed' / f'tau_{args.smooth_win:g}'
    )
    dirpath_plots = dirpath_results / 'fits'
    need_plot = NEED_PLOT and not args.no_plot
    if need_plot:
        dirpath_plots.mkdir(parents=True, exist_ok=True)

    # Collect the compact HPC outputs without reading the raw simulation PKLs
    dataset = collect_h_rate_data(dirpath_data)
    coefficients, q_xr = fit_h_rate_curves(
        dataset,
        args.smooth_win,
        (args.fit_start, args.fit_stop),
        args.turn_margin,
        dirpath_plots if need_plot else None,
    )
    outputs = save_results(
        dataset,
        coefficients,
        q_xr,
        dirpath_data,
        args.smooth_win,
    )

    n_success = sum(
        coefficients[pop][pop]['success']
        for pop in coefficients
    )
    print(f'Seeds: {dataset.sizes["seed"]}')
    print(f'Fits: {n_success}/{len(coefficients)}')
    print(q_xr)
    for fpath in outputs:
        print(f'Saved: {fpath}')
    if need_plot:
        print(f'Saved plots: {dirpath_plots}')


if __name__ == '__main__':
    main()
