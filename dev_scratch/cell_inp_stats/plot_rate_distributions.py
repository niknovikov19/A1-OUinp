from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


DIR_HERE = Path(__file__).resolve().parent
FPATH_DATA = DIR_HERE / 'test_data' / 'batch' / 'cell_inp_stats_xr_combined.nc'
N_BINS = 15
DIRPATH_FIGS = DIR_HERE / 'figures' / f'rate_distributions_nbins_{N_BINS}'


def get_pop_rate_values(dataset, pop):
    """Return finite rates pooled across cells and batch dimensions. """
    is_pop = dataset['pop_post'].values == pop
    values = dataset['rate'].isel(gid=is_pop).values.ravel()
    return values[np.isfinite(values)]


def plot_rate_distribution(values, pop, fpath_out):
    """Plot one population's pooled firing-rate distribution. """
    density, bins = np.histogram(values, bins=N_BINS, density=True)

    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    ax.plot(bins[:-1], density, '.-', linewidth=1.5)
    ax.set_xlabel('Firing rate (Hz)')
    ax.set_ylabel('Density')
    ax.set_ylim(0, None)
    ax.set_title(f'{pop} firing rates (n={len(values)})')
    fig.savefig(fpath_out, dpi=150)
    plt.close(fig)


def main():
    """Plot pooled firing-rate distributions for all populations. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)

    # Load only the variables needed for the pooled rate plots
    with xr.open_dataset(FPATH_DATA) as dataset:
        dataset = dataset[['rate']].load()

    # Preserve the population order used in the source dataset
    pops = list(dict.fromkeys(dataset['pop_post'].values))
    for pop in pops:
        values = get_pop_rate_values(dataset, pop)
        fpath_out = DIRPATH_FIGS / f'rate_distribution_{pop}.png'
        plot_rate_distribution(values, pop, fpath_out)
        print(f'Saved {fpath_out}')


if __name__ == '__main__':
    main()
