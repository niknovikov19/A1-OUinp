import argparse
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning, brentq, curve_fit
from scipy.special import expit


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[3]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import (
    collect_batch_json,
)
from workflow_utils import build_job_index, load_job_records, read_json


# Experiment paths
EXP_GROUP = 'batch_rxbkg_unconn_state1_mech1'
EXP_NAME = 'net_inpsur_dw_var_seed_ibkg'
DIRPATH_CFG = DIR_REPO / 'exp_configs' / EXP_GROUP / EXP_NAME


def _get_pop_names(dirpath_results):
    """Read population order from the first result JSON."""
    fpath_first = sorted(Path(dirpath_results).glob('result_*.json'))[0]
    with open(fpath_first, 'r') as fid:
        payload = json.load(fid)
    return list(payload['avg_rates'])


def collect_avg_rates_batch(job_idx_xr, dirpath_results, cache_path,
                            chunks=None, lazy=True, load=False):
    """Collect avg_rates JSON fields into a batch xarray Dataset."""
    dirpath_results = Path(dirpath_results)
    fpath_cache = Path(cache_path)
    open_kwargs = {} if fpath_cache.exists() else {'engine': 'scipy'}

    # Collect average rates from result JSON files
    pop_names = _get_pop_names(dirpath_results)
    rates_xr = collect_batch_json(
        job_idx_xr,
        dirpath_results,
        var_mappings={'avg_rate': 'avg_rates'},
        fname_templ='result_{job:05d}_*.json',
        dict_dims={'pop': pop_names},
        cache_path=fpath_cache,
        lazy=lazy,
        load=load,
        chunks=chunks,
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


def load_target_rates(dirpath_cfg=DIRPATH_CFG):
    """Load target population rates from the experiment CSV."""
    df = pd.read_csv(Path(dirpath_cfg) / 'target_state_1.csv')
    return df.set_index('pop_name')['target_rate'].to_dict()


def plot_fits(rates_xr, target_rates):
    """Fit and plot all population and seed curves."""
    rates = rates_xr['avg_rate']
    pops_vis = [str(pop) for pop in rates.pop.values if 'frz' not in str(pop)]
    seeds = [int(seed) for seed in rates.seed_main.values]
    ibkg = np.asarray(rates.ibkg_dw_adj.values, dtype=float)
    ibkg_fit = np.linspace(ibkg.min(), ibkg.max(), 500)

    # Set up one panel per active population
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharex=True)
    axes = axes.ravel()
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    table_rows = []

    # Fit each seed and annotate its r0 intersection
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

    # Use the empty panel for the shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    axes[-1].axis('off')
    axes[-1].legend(handles, labels, loc='center')
    fig.supxlabel('Ibkg')
    fig.supylabel('Rate')
    fig.tight_layout()
    table = pd.DataFrame(table_rows).set_index('pop')
    return fig, table


def process_stage(dirpath_stage):
    """Collect one workflow stage and save compensation-current fits."""
    dirpath_stage = Path(dirpath_stage)
    dirpath_processed = dirpath_stage / 'processed'
    dirpath_processed.mkdir(parents=True, exist_ok=True)
    stage_spec = read_json(dirpath_stage / 'meta' / 'stage_spec.json')
    records = load_job_records(dirpath_stage)
    job_idx_xr = build_job_index(records, stage_spec['batch_params'])

    # Collect detailed average rates using compact job records
    rates_xr = collect_avg_rates_batch(
        job_idx_xr=job_idx_xr,
        dirpath_results=dirpath_stage / 'sim_results' / 'results',
        cache_path=dirpath_processed / 'avg_rates.nc',
        lazy=False,
        load=True,
    )
    target_rates = load_target_rates()

    # Save fitted curves and r0 intersection summary
    fig, table = plot_fits(rates_xr, target_rates)
    fpath_png = dirpath_processed / 'fits.png'
    fpath_csv = dirpath_processed / 'ibkg_intersections.csv'
    fig.savefig(fpath_png, dpi=200, bbox_inches='tight')
    plt.close(fig)
    table.to_csv(fpath_csv, index_label='pop')

    print(f'Saved: {fpath_png}')
    print(f'Saved: {fpath_csv}')
    print(table.to_string())
    return [
        'processed/avg_rates.nc',
        'processed/ibkg_intersections.csv',
        'processed/fits.png',
    ]


def main():
    """Process a workflow DW stage from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage-dir', required=True)
    args = parser.parse_args()
    process_stage(args.stage_dir)


if __name__ == '__main__':
    main()
