from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


DIR_HERE = Path(__file__).resolve().parent
FPATH_DATA = DIR_HERE / 'test_data/cell_inp_stats_00000_seed_1000.nc'
DIRPATH_FIGS = DIR_HERE / 'figures'
FPATH_POP_STATS = DIR_HERE / 'pop_stats.csv'

POPS_PRE = ['IT2', 'PV2', 'SOM2']
POPS_POST = ['IT2', 'IT3', 'ITP4', 'ITS4']
METRICS = {
    'n_pre': 'Number of presynaptic cells',
    'r_pre_mean': 'Mean presynaptic rate (Hz)',
    'w_sum': 'Sum of weights',
    'wr_sum': 'Weighted input',
    'r_pre_wmean': 'Weighted presynaptic rate (Hz)',
}
N_BINS = 40


def get_values(dataset, metric, pop_pre, pop_post):
    """Select finite metric values for one population pair. """
    is_pop_post = dataset['pop_post'].values == pop_post
    values = dataset[metric].sel(pop_pre=pop_pre).values[is_pop_post]
    return values[np.isfinite(values)]


def calc_mean_std(values):
    """Calculate mean and population standard deviation of finite values. """
    values = values[np.isfinite(values)]
    if not len(values):
        return np.nan, np.nan
    return values.mean(), values.std()


def build_pop_stats_table(dataset):
    """Build a population table of cell rate and CV statistics. """
    rows = []
    pops = list(dict.fromkeys(dataset['pop_post'].values))

    # Summarize all cells while ignoring undefined rate or CV values
    for pop in pops:
        is_pop = dataset['pop_post'].values == pop
        rates = dataset['rate'].values[is_pop]
        cvs = dataset['cv'].values[is_pop]
        r_avg, r_std = calc_mean_std(rates)
        cv_avg, cv_std = calc_mean_std(cvs)
        rows.append({
            'pop': pop,
            'ncells': int(is_pop.sum()),
            'r_avg': r_avg,
            'r_std': r_std,
            'cv_avg': cv_avg,
            'cv_std': cv_std,
        })

    return pd.DataFrame(rows).set_index('pop').round(2)


def plot_pop_pre(dataset, pop_pre, fpath_out):
    """Plot input distributions from one population. """
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), constrained_layout=True)
    axes = axes.ravel()

    # Plot post populations against common bins for a fair comparison
    for ax, (metric, label) in zip(axes, METRICS.items()):
        values_by_pop = [
            get_values(dataset, metric, pop_pre, pop_post)
            for pop_post in POPS_POST
        ]
        bins = np.histogram_bin_edges(np.concatenate(values_by_pop), bins=N_BINS)

        for pop_post, values in zip(POPS_POST, values_by_pop):
            ax.hist(
                values,
                bins=bins,
                density=True,
                histtype='step',
                linewidth=1.5,
                label=f'{pop_post} (n={len(values)})',
            )

        ax.set_xlabel(label)
        ax.set_ylabel('Density')

    axes[0].legend(frameon=False, fontsize=8)
    axes[-1].set_visible(False)
    fig.suptitle(f'Inputs from {pop_pre}')
    fig.savefig(fpath_out, dpi=150)
    plt.close(fig)


def main():
    """Plot selected cell-input distributions. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)

    # Load the small analysis result, not the simulation connectivity
    with xr.open_dataset(FPATH_DATA) as dataset:
        dataset.load()

    # Save population-level firing statistics
    pop_stats = build_pop_stats_table(dataset)
    pop_stats.to_csv(FPATH_POP_STATS, float_format='%.2f')
    print(f'Saved {FPATH_POP_STATS}')

    # Save one readable figure for each presynaptic population
    for pop_pre in POPS_PRE:
        fpath_out = DIRPATH_FIGS / f'input_distributions_{pop_pre}.png'
        plot_pop_pre(dataset, pop_pre, fpath_out)
        print(f'Saved {fpath_out}')


if __name__ == '__main__':
    main()
