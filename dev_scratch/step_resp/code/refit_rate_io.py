import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
import xarray as xr


DIR_DATA = Path(__file__).resolve().parents[1] / 'data' / 'l2_rate_sweep_j_5seeds'
PARAM_NAMES = ['A', 'K', 'B', 'M', 'nu']


def richards(x, A, K, B, M, nu):
    """Evaluate a positive-nu Richards curve without exponential overflow. """
    log_fraction = -np.logaddexp(0, -B * (np.asarray(x) - M))
    return A + (K - A) * np.exp(log_fraction / nu)


def richards_derivative(x, A, K, B, M, nu):
    """Evaluate the Richards derivative in log space, including extreme tails. """
    z = B * (np.asarray(x) - M)
    log_shape = -np.logaddexp(0, -z) / nu - np.logaddexp(0, z)
    return (K - A) * B / nu * np.exp(log_shape)


def scaled_model_and_jac(x, params, sign):
    """Evaluate a signed monotone curve and its analytic parameter Jacobian. """
    a, amplitude, b, midpoint, nu = params
    z = b * (x - midpoint)
    log_fraction = -np.logaddexp(0, -z)
    shape = np.exp(log_fraction / nu)
    shape_z = shape * np.exp(-np.logaddexp(0, z)) / nu
    fraction = shape if sign > 0 else 1 - shape
    values = a + amplitude * fraction
    jac = np.column_stack((
        np.ones_like(x), fraction,
        sign * amplitude * shape_z * (x - midpoint),
        -sign * amplitude * shape_z * b,
        -sign * amplitude * shape * log_fraction / nu ** 2,
    ))
    return values, jac


def bin_by_seed(x, y, n_bins):
    """Reduce correlated samples to count-weighted input bins within each seed. """
    edges = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), n_bins + 1)
    rows = []
    for index in range(x.shape[0]):
        valid = np.isfinite(x[index]) & np.isfinite(y[index])
        xx, yy = x[index, valid], y[index, valid]
        bins = np.minimum(np.searchsorted(edges, xx, side='right') - 1, n_bins - 1)
        for label in np.unique(bins):
            mask = bins == label
            rows.append((float(xx[mask].mean()), float(yy[mask].mean()), int(mask.sum()), index))
    return np.asarray(rows)


def fit_curve(x, y, sign, r0, n_bins=64, max_nfev=1500, logistic_fallback=True):
    """Fit a nonnegative signed Richards curve with scaled parameters and six starts. """
    binned = bin_by_seed(x, y, n_bins)
    valid = np.isfinite(x) & np.isfinite(y)
    xx, yy = x[valid], y[valid]
    x_min, x_span = float(xx.min()), float(np.ptp(xx))
    if x_span <= 0 or not xx.min() <= r0 <= xx.max():
        return {'success': False, 'reason': 'No input span or target outside data'}

    # Normalize both axes and preserve sample counts in the approximate objective
    y_scale = max(float(np.ptp(yy)), float(np.mean(yy)), 1)
    xb = (binned[:, 0] - x_min) / x_span
    yb = binned[:, 1] / y_scale
    weights = np.sqrt(binned[:, 2] / binned[:, 2].sum())
    rate_limit = max(float(yb.max()), 0.1)
    lower = np.asarray([0, 0, 0.05, -5, 0.05])
    upper = np.asarray([2 * rate_limit + 1, 4 * rate_limit + 1, 100, 5, 20])
    a0 = max(0, float(np.quantile(yb, 0.05)))
    amplitude0 = max(float(np.quantile(yb, 0.95)) - a0, 0.05)

    def residual(params):
        """Return count-weighted residuals on the binned approximation. """
        values, _ = scaled_model_and_jac(xb, params, sign)
        return weights * (values - yb)

    def jacobian(params):
        """Return the count-weighted analytic residual Jacobian. """
        _, jac = scaled_model_and_jac(xb, params, sign)
        return weights[:, None] * jac

    # Compare multiple starts without choosing a fit from connected responses
    solutions = []
    for b0 in (2, 8):
        for nu0 in (0.3, 1, 3):
            initial = [a0, amplitude0, b0, 0.5, nu0]
            solution = least_squares(residual, initial, jac=jacobian, bounds=(lower, upper),
                                     max_nfev=max_nfev, ftol=1e-9, xtol=1e-9, gtol=1e-8)
            if not solution.success or not np.all(np.isfinite(solution.x)):
                continue
            a, amplitude, b, midpoint, nu = solution.x
            A = a if sign > 0 else a + amplitude
            K = a + amplitude if sign > 0 else a
            params = [A * y_scale, K * y_scale, b / x_span,
                      x_min + midpoint * x_span, nu]
            gain = float(richards_derivative(r0, *params))
            solutions.append((float(np.sum(solution.fun ** 2)), params, gain, solution))

    # Reduce model order only when no five-parameter start converges
    family = 'richards5'
    if not solutions and logistic_fallback:
        family = 'logistic4'

        def residual_fixed(params):
            """Evaluate the nested logistic model with nu fixed to one. """
            return residual(np.append(params, 1))

        def jacobian_fixed(params):
            """Return the four free columns of the logistic residual Jacobian. """
            return jacobian(np.append(params, 1))[:, :4]

        for b0 in (2, 8):
            solution = least_squares(residual_fixed, [a0, amplitude0, b0, 0.5],
                                     jac=jacobian_fixed, bounds=(lower[:4], upper[:4]),
                                     max_nfev=max_nfev, ftol=1e-9, xtol=1e-9, gtol=1e-8)
            if not solution.success:
                continue
            solution.x = np.append(solution.x, 1)
            a, amplitude, b, midpoint, nu = solution.x
            A = a if sign > 0 else a + amplitude
            K = a + amplitude if sign > 0 else a
            params = [A * y_scale, K * y_scale, b / x_span, x_min + midpoint * x_span, nu]
            gain = float(richards_derivative(r0, *params))
            solutions.append((float(np.sum(solution.fun ** 2)), params, gain, solution))
    if not solutions:
        return {'success': False, 'reason': 'No converged multistart solution'}

    # Evaluate fit quality on every original sample, not just the fitting bins
    solutions.sort(key=lambda item: item[0])
    cost, params, gain, solution = solutions[0]
    error = yy - richards(xx, *params)
    total = float(np.sum((yy - yy.mean()) ** 2))
    r_squared = 1 - float(np.sum(error ** 2)) / total if total > 0 else None
    near = [item[2] for item in solutions if item[0] <= cost * 1.01 + 1e-12]
    distance = np.minimum(solution.x - lower, upper - solution.x) / (upper - lower)
    bound_names = ['rate_floor', 'rate_span', 'scaled_slope', 'scaled_midpoint', 'nu']
    return {
        'success': True, 'fit_family': family, **dict(zip(PARAM_NAMES, map(float, params))),
        'dR_dr_at_target': gain, 'r_at_target': float(richards(r0, *params)),
        'r_squared': r_squared, 'rmse_hz': float(np.sqrt(np.mean(error ** 2))),
        'n_points': int(xx.size), 'n_binned': int(len(binned)),
        'n_converged_starts': len(solutions),
        'near_optimal_start_gain_range': [float(min(near)), float(max(near))],
        'active_bounds': [name for name, value in zip(bound_names, distance) if value < 1e-4],
        'x_range_hz': [float(xx.min()), float(xx.max())],
        'expected_sign': sign,
    }


def local_seed_slopes(x, y, seeds, r0, width):
    """Estimate local per-seed slopes without assuming independent time bins. """
    gains = {}
    for index, seed in enumerate(seeds):
        mask = np.isfinite(x[index]) & np.isfinite(y[index]) & (np.abs(x[index] - r0) <= width)
        xx, yy = x[index, mask], y[index, mask]
        if xx.size < 20 or np.ptp(xx) == 0:
            continue
        centered = xx - xx.mean()
        gains[str(int(seed))] = float(np.sum(centered * (yy - yy.mean())) / np.sum(centered ** 2))
    values = list(gains.values())
    return {'half_width_hz': width, 'gain_by_seed': gains,
            'mean_gain': float(np.mean(values)) if values else None,
            'seed_sd': float(np.std(values, ddof=1)) if len(values) > 1 else None}


def triangle_masks(times, r0, start, period, rmax_mult, rmax_cap, margin):
    """Select known rising/falling triangle legs and exclude turning-point margins. """
    rmax = min(rmax_cap, rmax_mult * r0)
    phase = ((times - start) / period + r0 / (2 * rmax)) % 1
    distance = np.minimum.reduce((phase, np.abs(phase - 0.5), 1 - phase)) * period
    keep = (times >= start) & (distance >= margin)
    return {'pooled': keep, 'rising': keep & (phase < 0.5), 'falling': keep & (phase >= 0.5)}


def plot_pair(x, y, seeds, r0, fit, branches, local, title, path):
    """Plot pooled/branch fits and their target-rate neighborhood without axes grids. """
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for index, seed in enumerate(seeds):
        for axis in axes:
            axis.scatter(x[index, ::20], y[index, ::20], s=3, alpha=0.12, label=str(int(seed)))
    xx = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 500)
    for axis in axes:
        for name, entry in [('pooled', fit)] + list(branches.items()):
            if entry['success']:
                params = [entry[key] for key in PARAM_NAMES]
                axis.plot(xx, richards(xx, *params), linewidth=2, label=name)
        axis.axvline(r0, color='0.5', linestyle='--')
        axis.set_xlabel('Measured presynaptic rate (Hz)')
        axis.grid(False)
    left = max(float(np.nanmin(x)), r0 - 2 * r0)
    right = min(float(np.nanmax(x)), r0 + 2 * r0)
    axes[1].set_xlim(left, right)
    visible = y[(x >= left) & (x <= right)]
    low, high = np.nanquantile(visible, [0.01, 0.99])
    margin = max(float(high - low) * 0.1, 0.1)
    axes[1].set_ylim(max(0, low - margin), high + margin)
    if fit['success']:
        tangent_x = np.linspace(left, right, 100)
        tangent = fit['r_at_target'] + fit['dR_dr_at_target'] * (tangent_x - r0)
        axes[1].plot(tangent_x, tangent, color='k', linestyle=':', label='Target tangent')
    axes[0].set_ylabel('Postsynaptic rate (Hz)')
    axes[0].set_title('Full measured range')
    local_label = f"{local['mean_gain']:.3g}" if local['mean_gain'] is not None else 'unavailable'
    axes[1].set_title(f'Target neighborhood; local seed slope {local_label}')
    axes[1].legend(fontsize=7)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run_refit(args):
    """Refit every L2 pair consistently and save provenance and labelled matrices. """
    input_dir = args.data_dir / 'input'
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = args.data_dir / 'processed' / f'tau_{args.smooth_win:g}_bins_{args.bins}'
    (output / 'fits').mkdir(parents=True, exist_ok=True)
    cfg = json.loads((input_dir / 'cfg.json').read_text())['simConfig']
    rates = xr.load_dataarray(input_dir / 'rates.nc')
    rates = rates.sel(time=slice(args.start, None)).transpose('pop_pre', 'seed', 'pop', 'time')
    pops = list(cfg['subnet_params']['pops_active'])
    seeds, times = rates.seed.values, rates.time.values
    n_smooth = max(1, round(args.smooth_win / float(np.median(np.diff(times)))))
    rates = rates.rolling(time=n_smooth, center=True, min_periods=1).mean()
    matrices = {name: np.full((len(pops), len(pops)), np.nan)
                for name in ('pooled', 'rising', 'falling', 'local')}
    coefficients, rows = {}, []

    # Use the experimental triangle timing, not noisy numerical rate gradients
    for i, pre in enumerate(pops):
        r0 = cfg['target_rates'][pre]
        sign = 1 if pre in cfg['Epops'] else -1
        masks = triangle_masks(times, r0, args.start, args.period,
                               args.rmax_mult, args.rmax_cap, args.turn_margin)
        all_x = rates.sel(pop_pre=pre, pop=f'{pre}frz').values
        coefficients[pre] = {}
        for j, post in enumerate(pops):
            all_y = rates.sel(pop_pre=pre, pop=post).values
            fits = {name: fit_curve(all_x[:, mask], all_y[:, mask], sign, r0,
                                    n_bins=args.bins, max_nfev=args.max_nfev,
                                    logistic_fallback=not args.no_logistic_fallback)
                    for name, mask in masks.items()}
            pooled = fits['pooled']
            x, y = all_x[:, masks['pooled']], all_y[:, masks['pooled']]
            local = local_seed_slopes(x, y, seeds, r0, r0)
            local_wide = local_seed_slopes(x, y, seeds, r0, 2 * r0)
            entry = {**pooled, 'target_rate_hz': r0,
                     'branches': {name: fits[name] for name in ('rising', 'falling')},
                     'local': local, 'local_wide': local_wide}
            coefficients[pre][post] = entry
            for name in ('pooled', 'rising', 'falling'):
                if fits[name]['success']:
                    matrices[name][i, j] = fits[name]['dR_dr_at_target']
            if local['mean_gain'] is not None:
                matrices['local'][i, j] = local['mean_gain']
            rows.append({'pop_pre': pre, 'pop_post': post, 'success': pooled['success'],
                         'fit_family': pooled.get('fit_family'),
                         'gain': pooled.get('dR_dr_at_target'), 'r_squared': pooled.get('r_squared'),
                         'rmse_hz': pooled.get('rmse_hz'), 'local_gain': local['mean_gain'],
                         'local_seed_sd': local['seed_sd'], 'local_wide_gain': local_wide['mean_gain'],
                         'rising_gain': matrices['rising'][i, j], 'falling_gain': matrices['falling'][i, j],
                         'active_bounds': ','.join(pooled.get('active_bounds', []))})
            print(f'{pre}->{post}: {pooled.get("dR_dr_at_target")} R2={pooled.get("r_squared")}', flush=True)
            plot_pair(x, y, seeds, r0, pooled, entry['branches'], local,
                      f'{pre} -> {post}, {args.smooth_win:g}-s smoothing', output / 'fits' / f'{pre}_{post}.png')

        # Save progress by input population without touching historical artifacts
        (output / 'richards_coeffs.json').write_text(json.dumps(coefficients, indent=2))
        pd.DataFrame(rows).to_csv(output / 'fit_diagnostics.csv', index=False)

    for name, values in matrices.items():
        matrix = xr.DataArray(values, dims=('pop_pre', 'pop_post'),
                              coords={'pop_pre': pops, 'pop_post': pops}, name='J')
        matrix.attrs = {'units': 'Hz/Hz', 'orientation': 'input population x output population',
                        'estimator': name, 'smooth_win_s': args.smooth_win,
                        'status': 'Provisional refit; inspect identifiability and sensitivity'}
        matrix.to_netcdf(output / f'jmat_{name}.nc')

    # Record all analysis choices independently of the connected response data
    manifest = {'settings': {key: str(value) if isinstance(value, Path) else value
                             for key, value in vars(args).items()},
                'objective': 'Count-weighted per-seed input-bin means; approximate full-sample least squares',
                'uncertainty': 'Per-seed local slope variation is descriptive; time bins are not independent',
                'inputs': {name: hashlib.sha256((input_dir / name).read_bytes()).hexdigest()
                           for name in ('rates.nc', 'cfg.json')},
                'script_sha256': script_hash,
                'source_cache_attrs': rates.attrs,
                'finite_entries': {name: int(np.isfinite(values).sum()) for name, values in matrices.items()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest['finite_entries']), flush=True)


def main():
    """Run a reproducible local rate-rate refit without installing dependencies. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=DIR_DATA)
    parser.add_argument('--smooth-win', type=float, default=0.2)
    parser.add_argument('--bins', type=int, default=64)
    parser.add_argument('--start', type=float, default=5)
    parser.add_argument('--period', type=float, default=7.5)
    parser.add_argument('--rmax-mult', type=float, default=10)
    parser.add_argument('--rmax-cap', type=float, default=500)
    parser.add_argument('--turn-margin', type=float, default=0.1)
    parser.add_argument('--max-nfev', type=int, default=1500)
    parser.add_argument('--no-logistic-fallback', action='store_true')
    run_refit(parser.parse_args())


if __name__ == '__main__':
    main()
