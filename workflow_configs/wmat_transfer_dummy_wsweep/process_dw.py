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


def fit_richards(x, y):
    """Fit an increasing Richards curve using several initial shapes."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 6:
        raise ValueError('At least six finite points are required')

    # Bound asymptotes and shape while allowing a late upper plateau
    x_span = x.max() - x.min()
    y_min = y.min()
    y_max = y.max()
    y_scale = max(y_max, 1e-3)
    bounds = (
        [-y_scale, y_max, 1e-3, x.min() - 5 * x_span, 0.05],
        [y_min, 100 * y_scale, 1000, x.max() + 5 * x_span, 100],
    )

    # Try several inflection points and asymmetry values
    fits = []
    m_guesses = [np.median(x), x.max(), x.max() + x_span]
    for m_guess in m_guesses:
        for nu_guess in (0.5, 1, 2):
            p0 = [min(0, y_min), 1.5 * y_scale, 20, m_guess, nu_guess]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', OptimizeWarning)
                    params, _ = curve_fit(
                        richards,
                        x,
                        y,
                        p0=p0,
                        bounds=bounds,
                        maxfev=100000,
                    )
            except (RuntimeError, ValueError, FloatingPointError):
                continue

            residual = richards(x, *params) - y
            fits.append((np.sum(residual ** 2), params))

    if not fits:
        raise RuntimeError('Richards fit failed for all initial values')
    return min(fits, key=lambda item: item[0])[1]


def find_target_intersection(params, target_rate, x_min, x_max):
    """Find the fitted curve intersection with r0 inside sampled bounds."""
    target_diff = lambda x: float(richards(x, *params) - target_rate)
    y_min = target_diff(x_min)
    y_max = target_diff(x_max)
    if y_min == 0:
        return float(x_min)
    if y_max == 0:
        return float(x_max)
    if y_min * y_max > 0:
        raise ValueError('Fitted curve does not cross r0 in sampled bounds')
    return float(brentq(target_diff, x_min, x_max))


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
    ibkg_fit = np.linspace(ibkg.min(), ibkg.max(), 500)

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

    # Fit each seed and require its target-rate crossing
    for n_pop, pop in enumerate(pops_vis):
        ax = axes[n_pop]
        target_rate = target_rates[pop]
        intersections = {}
        for n_seed, seed in enumerate(seeds):
            color = colors[n_seed % len(colors)]
            rate = rates.sel(pop=pop, seed_main=seed)
            y = np.asarray(rate.values, dtype=float)
            params = fit_richards(ibkg, y)
            ibkg_r0 = find_target_intersection(
                params,
                target_rate,
                ibkg.min(),
                ibkg.max(),
            )
            intersections[seed] = ibkg_r0

            label = f'Seed {seed}' if n_pop == 0 else None
            ax.plot(ibkg, y, '-', color=color, label=label, alpha=0.5)
            ax.plot(ibkg_fit, richards(ibkg_fit, *params), color=color)
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
        median_ibkg = float(np.median(list(intersections.values())))
        target_label = 'r0' if n_pop == 0 else None
        median_label = 'Median Ibkg' if n_pop == 0 else None
        ax.axhline(target_rate, color='0.25', ls=':', label=target_label)
        ax.axvline(median_ibkg, color='k', ls='--', label=median_label)
        ax.set_title(pop)
        ax.grid(alpha=0.2)

        row = {'pop': pop, 'median_ibkg': median_ibkg}
        row.update({
            f'seed_{seed}': intersections[seed]
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
