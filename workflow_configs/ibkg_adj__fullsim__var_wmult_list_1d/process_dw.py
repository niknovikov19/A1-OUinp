import json
from pathlib import Path
import sys
import warnings

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning, brentq, curve_fit
from scipy.special import expit


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_json
from workflow_utils import build_job_index, load_job_records


RICHARDS_MAXFEV = 500
RICHARDS_FIT_TOL = 1e-3


def _get_pop_names(dirpath_results):
    """Read population order from the first result JSON."""
    fpath_first = sorted(Path(dirpath_results).glob('result_*.json'))[0]
    with open(fpath_first, 'r') as fid:
        payload = json.load(fid)
    return list(payload['avg_rates'])


def collect_avg_rates_batch(job_idx_xr, dirpath_results, cache_path):
    """Collect avg_rates JSON fields into a batch xarray Dataset."""
    dirpath_results = Path(dirpath_results)
    fpath_cache = Path(cache_path)
    open_kwargs = {} if fpath_cache.exists() else {'engine': 'scipy'}

    # Collect average rates from detailed per-job result files
    pop_names = _get_pop_names(dirpath_results)
    rates_xr = collect_batch_json(
        job_idx_xr,
        dirpath_results,
        var_mappings={'avg_rate': 'avg_rates'},
        fname_templ='result_{job:05d}_*.json',
        dict_dims={'pop': pop_names},
        cache_path=fpath_cache,
        lazy=False,
        load=True,
        open_kwargs=open_kwargs,
        skip_missing=False,
        overwrite=True,
        allow_cache_mismatch=1,
    )
    print(f'Done: {fpath_cache}')
    print(f'Shape: {dict(rates_xr.sizes)}')
    return rates_xr


def richards(x, a, k, b, m, nu):
    """Evaluate the five-parameter Richards curve."""
    logistic = expit(b * (np.asarray(x) - m))
    return a + (k - a) * logistic ** (1 / nu)


def _clean_xy(x, y, min_points):
    """Return finite sorted x/y arrays."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    if len(x) < min_points:
        raise ValueError(f'At least {min_points} finite points are required')
    return x, y


def _estimate_crossing_and_slope(x, y, target_rate):
    """Estimate target crossing and local slope from sampled points."""
    diff = y - target_rate
    gradients = np.gradient(y, x)
    exact = np.where(diff == 0)[0]
    if exact.size:
        idx = int(exact[0])
        return float(x[idx]), float(abs(gradients[idx]))

    # Prefer the segment that actually brackets the target
    for idx in range(len(x) - 1):
        y0 = y[idx]
        y1 = y[idx + 1]
        d0 = y0 - target_rate
        d1 = y1 - target_rate
        if d0 * d1 > 0 or y0 == y1:
            continue
        alpha = (target_rate - y0) / (y1 - y0)
        slope = (y1 - y0) / (x[idx + 1] - x[idx])
        crossing = x[idx] + alpha * (x[idx + 1] - x[idx])
        return float(crossing), float(abs(slope))

    # Fall back to the steepest sampled segment when no crossing exists
    idx = int(np.nanargmax(np.abs(gradients)))
    return float(x[idx]), float(abs(gradients[idx]))


def _build_richards_fit_setup(x, y, target_rate):
    """Build data-driven Richards bounds and starting points."""
    x_span = max(x.max() - x.min(), 1e-9)
    y_min = y.min()
    y_max = y.max()
    y_span = max(y_max - y_min, 1e-3)
    y_scale = max(y_max, target_rate, 1e-3)
    m0, slope0 = _estimate_crossing_and_slope(x, y, target_rate)
    slope0 = max(slope0, y_span / x_span, 1e-6)
    b0 = np.clip(4 * slope0 / y_span, 0.1 / x_span, 100 / x_span)
    a0 = min(0, y[0], y_min)
    k0 = max(y[-1], y_max, target_rate, 1.2 * y_scale)
    bounds = (
        [-y_scale, max(y_max, target_rate), 1e-4, x.min() - x_span, 0.25],
        [min(y_min, target_rate), 20 * y_scale, 300 / x_span, x.max() + x_span, 4],
    )

    # A small set of slope/asymmetry variants is enough for these 7-point curves
    guesses = []
    for b_mult in (0.5, 1, 2):
        for nu_guess in (1, 2):
            p0 = np.asarray([a0, k0, b0 * b_mult, m0, nu_guess])
            p0 = np.minimum(np.maximum(p0, bounds[0]), bounds[1])
            guesses.append(p0.tolist())
    return bounds, guesses


def fit_richards(x, y, target_rate=None):
    """Fit an increasing Richards curve using several initial shapes."""
    x, y = _clean_xy(x, y, min_points=6)
    if target_rate is None:
        target_rate = 0.5 * (np.nanmin(y) + np.nanmax(y))
    bounds, guesses = _build_richards_fit_setup(x, y, target_rate)
    fits = []

    # Use loose tolerances because these compensation fits are approximate
    for p0 in guesses:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', OptimizeWarning)
                params, _ = curve_fit(
                    richards,
                    x,
                    y,
                    p0=p0,
                    bounds=bounds,
                    maxfev=RICHARDS_MAXFEV,
                    ftol=RICHARDS_FIT_TOL,
                    xtol=RICHARDS_FIT_TOL,
                    gtol=RICHARDS_FIT_TOL,
                )
        except (RuntimeError, ValueError, FloatingPointError):
            continue

        residual = richards(x, *params) - y
        fits.append((np.sum(residual ** 2), params))

    if not fits:
        raise RuntimeError('Richards fit failed for all initial values')
    return min(fits, key=lambda item: item[0])[1]


def find_curve_intersection(func, params, target_rate, x_min, x_max):
    """Find the fitted curve intersection with r0 inside sampled bounds."""
    target_diff = lambda x: float(func(x, *params) - target_rate)
    y_min = target_diff(x_min)
    y_max = target_diff(x_max)
    if y_min == 0:
        return float(x_min)
    if y_max == 0:
        return float(x_max)
    if y_min * y_max > 0:
        raise ValueError('Fitted curve does not cross r0 in sampled bounds')
    return float(brentq(target_diff, x_min, x_max))


def find_target_intersection(params, target_rate, x_min, x_max):
    """Find the Richards curve intersection with r0 inside sampled bounds."""
    return find_curve_intersection(
        richards,
        params,
        target_rate,
        x_min,
        x_max,
    )


def find_sampled_intersection(x, y, target_rate):
    """Find the target crossing by linear interpolation of sampled points."""
    x, y = _clean_xy(x, y, min_points=2)
    diff = y - target_rate
    exact = np.where(diff == 0)[0]
    if exact.size:
        return float(x[exact[0]])

    # Use the sampled segment closest to the first target crossing
    for idx in range(len(x) - 1):
        y0 = y[idx]
        y1 = y[idx + 1]
        d0 = y0 - target_rate
        d1 = y1 - target_rate
        if d0 * d1 > 0 or y0 == y1:
            continue
        alpha = (target_rate - y0) / (y1 - y0)
        return float(x[idx] + alpha * (x[idx + 1] - x[idx]))

    raise ValueError('Sampled rates do not cross r0')


def fit_target_crossing(ibkg, y, target_rate):
    """Fit Richards and return target crossing diagnostics."""
    try:
        params = fit_richards(ibkg, y, target_rate=target_rate)
        ibkg_r0 = find_curve_intersection(
            richards,
            params,
            target_rate,
            ibkg.min(),
            ibkg.max(),
        )
        return ibkg_r0, richards(ibkg, *params), 'richards', ''
    except (RuntimeError, ValueError, FloatingPointError) as fit_exc:
        # Keep the workflow practical when the approximate fit is not usable
        ibkg_r0 = find_sampled_intersection(ibkg, y, target_rate)
        return ibkg_r0, None, 'sampled', str(fit_exc)


def _load_target_rates(target_rates_path):
    """Load target population rates from the configured CSV."""
    fpath = Path(target_rates_path)
    if not fpath.is_absolute():
        fpath = DIR_REPO / fpath
    df = pd.read_csv(fpath)
    return df.set_index('pop_name')['target_rate'].to_dict()


def plot_fits(rates_xr, target_rates, required_pops=None):
    """Fit and plot all population and seed curves."""
    rates = rates_xr['avg_rate']
    available_pops = [
        str(pop)
        for pop in rates.pop.values
        if 'frz' not in str(pop)
    ]
    pops_vis = available_pops
    if required_pops is not None:
        missing = sorted(set(required_pops) - set(available_pops))
        if missing:
            raise ValueError(f'Missing required populations: {missing}')
        pops_vis = list(required_pops)
    seeds = [int(seed) for seed in rates.seed_main.values]
    ibkg = np.asarray(rates.ibkg_dw_adj.values, dtype=float)

    # Set up one panel per active population
    ncols = 3
    nrows = int(np.ceil((len(pops_vis) + 1) / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(12, 3.5 * nrows),
        sharex=True,
    )
    axes = np.atleast_1d(axes).ravel()
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    table_rows = []

    # Fit each seed while preserving diagnostic plots on failures
    for n_pop, pop in enumerate(pops_vis):
        ax = axes[n_pop]
        target_rate = target_rates[pop]
        intersections = {}
        fit_errors = {}
        fit_methods = {}
        for n_seed, seed in enumerate(seeds):
            color = colors[n_seed % len(colors)]
            rate = rates.sel(pop=pop, seed_main=seed)
            y = np.asarray(rate.values, dtype=float)
            label = f'Seed {seed}' if n_pop == 0 else None
            ax.plot(ibkg, y, '-', color=color, label=label, alpha=0.5)

            try:
                ibkg_r0, y_fit, method, fit_note = fit_target_crossing(
                    ibkg,
                    y,
                    target_rate,
                )
            except (RuntimeError, ValueError, FloatingPointError) as exc:
                intersections[seed] = np.nan
                fit_errors[seed] = str(exc)
                fit_methods[seed] = 'failed'
                ax.text(
                    0.02,
                    0.92 - 0.08 * len(fit_errors),
                    f'Seed {seed}: {exc}',
                    transform=ax.transAxes,
                    fontsize=7,
                    color=color,
                    va='top',
                )
                continue

            intersections[seed] = ibkg_r0
            fit_errors[seed] = fit_note
            fit_methods[seed] = method
            if y_fit is not None:
                ax.plot(ibkg, y_fit, '--', color=color)
            ax.scatter(
                ibkg_r0,
                target_rate,
                color=color,
                edgecolor='black',
                linewidth=0.7,
                s=45,
                zorder=4,
            )

        # Add target rate and median current guides
        valid = [
            value
            for value in intersections.values()
            if np.isfinite(value)
        ]
        median_ibkg = float(np.median(valid)) if valid else np.nan
        target_label = 'r0' if n_pop == 0 else None
        median_label = 'Median Ibkg' if n_pop == 0 else None
        ax.axhline(target_rate, color='0.25', ls=':', label=target_label)
        if np.isfinite(median_ibkg):
            ax.axvline(median_ibkg, color='k', ls='--', label=median_label)
        ax.set_title(pop)
        ax.grid(alpha=0.2)

        status = 'ok' if len(valid) == len(seeds) else 'failed'
        row = {
            'pop': pop,
            'median_ibkg': median_ibkg,
            'status': status,
            'fit_error': '; '.join(
                f'{seed}: {err}'
                for seed, err in fit_errors.items()
                if err
            ),
            'fit_methods': '; '.join(
                f'{seed}: {method}'
                for seed, method in fit_methods.items()
            ),
        }
        row.update({
            f'seed_{seed}': intersections[seed]
            for seed in seeds
        })
        row.update({
            f'seed_{seed}_status': (
                'ok' if np.isfinite(intersections[seed]) else 'failed'
            )
            for seed in seeds
        })
        table_rows.append(row)

    # Use the first unused panel for the shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    for ax in axes[len(pops_vis):]:
        ax.axis('off')
    axes[-1].legend(handles, labels, loc='center')
    fig.supxlabel('Ibkg')
    fig.supylabel('Rate')
    fig.tight_layout()
    table = pd.DataFrame(table_rows).set_index('pop')
    return fig, table


def load_stage_result(stage_dir, stage_spec, target_rates_path,
                      required_pops=None):
    """Load validated median ibkg corrections from processed output."""
    fpath_csv = Path(stage_dir) / 'processed' / 'ibkg_intersections.csv'
    table = pd.read_csv(fpath_csv).set_index('pop')
    if required_pops is not None:
        missing = sorted(set(required_pops) - set(table.index))
        if missing:
            raise ValueError(f'Missing ibkg corrections: {missing}')
        table = table.loc[required_pops]
    if table['median_ibkg'].isna().any():
        missing = table.index[table['median_ibkg'].isna()].tolist()
        raise ValueError(f'Missing ibkg corrections for populations: {missing}')
    return table['median_ibkg'].astype(float).to_dict()


def process_stage(stage_dir, stage_spec, target_rates_path,
                  required_pops=None):
    """Collect rates and save compensation-current fits."""
    stage_dir = Path(stage_dir)
    dirpath_processed = stage_dir / 'processed'
    dirpath_processed.mkdir(parents=True, exist_ok=True)
    records = load_job_records(stage_dir)
    job_idx_xr = build_job_index(records, stage_spec['batch_params'])

    # Collect detailed average rates using compact job records
    rates_xr = collect_avg_rates_batch(
        job_idx_xr,
        stage_dir / 'sim_results' / 'results',
        dirpath_processed / 'avg_rates.nc',
    )
    target_rates = _load_target_rates(target_rates_path)

    # Save fitted curves and target-rate intersection summary
    fig, table = plot_fits(
        rates_xr,
        target_rates,
        required_pops=required_pops,
    )
    fpath_png = dirpath_processed / 'fits.png'
    fpath_csv = dirpath_processed / 'ibkg_intersections.csv'
    fig.savefig(fpath_png, dpi=200, bbox_inches='tight')
    plt.close(fig)
    table.to_csv(fpath_csv, index_label='pop')
    print(f'Saved: {fpath_png}')
    print(f'Saved: {fpath_csv}')
    print(table.to_string())

    outputs = [
        'processed/avg_rates.nc',
        'processed/ibkg_intersections.csv',
        'processed/fits.png',
    ]
    result = load_stage_result(
        stage_dir,
        stage_spec,
        target_rates_path,
        required_pops=required_pops,
    )
    return result, outputs
