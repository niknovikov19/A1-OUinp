from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


DIR_HERE = Path(__file__).resolve().parent
FPATH_DATA = DIR_HERE / 'test_data' / 'batch' / 'cell_inp_stats_xr_combined.nc'
N_BINS = 15
SKIP_EXISTING = 0
LOG_XSCALE = 0
DIRNAME_FIGS = f'inp_stats_nbins_{N_BINS}'
if LOG_XSCALE:
    DIRNAME_FIGS += '_log'
DIRPATH_FIGS = DIR_HERE / 'figures' / DIRNAME_FIGS

METRICS = {
    'n_pre': 'Number of presynaptic cells',
    'r_pre_mean': 'Mean presynaptic rate (Hz)',
    'w_sum': 'Sum of weights',
    'wr_sum': 'Weighted input',
    'r_pre_wmean': 'Weighted presynaptic rate (Hz)',
}
POP_GROUPS = {
    'it': ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6'],
    'ct': ['CT5A', 'CT5B', 'CT6', 'PT5B'],
    'pv': ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6'],
    'som': ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6'],
    'vip': ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6'],
    'ngf': ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6'],
    'thal': ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM'],
}


def get_values(dataset, metric, pop_pre, is_pop_post):
    """Select positive-weight finite values pooled across seeds and post cells. """
    values = dataset[metric].sel(pop_pre=pop_pre).isel(gid=is_pop_post).values
    values = values.ravel()
    w_sum = dataset['w_sum'].sel(pop_pre=pop_pre).isel(gid=is_pop_post).values
    has_weight = w_sum.ravel() > 0
    return values[has_weight & np.isfinite(values)]


def has_weighted_inputs(dataset, pop_pre, is_pop_post):
    """Return whether a population pair has any positive-weight inputs. """
    return len(get_values(dataset, 'n_pre', pop_pre, is_pop_post)) > 0


def get_population_sizes(dataset):
    """Return the cell count of every population. """
    pop_post = dataset['pop_post'].values
    return {
        pop: int(np.sum(pop_post == pop))
        for pop in dict.fromkeys(pop_post)
    }


def get_weighted_pops(dataset, pop_post, pops_pre):
    """Return presynaptic populations with positive-weight input samples. """
    is_pop_post = dataset['pop_post'].values == pop_post
    return [
        pop_pre
        for pop_pre in pops_pre
        if has_weighted_inputs(dataset, pop_pre, is_pop_post)
    ]


def calc_distribution(values, metric, log_xscale=False):
    """Calculate one density curve with population-specific linear bins. """
    values = np.asarray(values)
    if log_xscale:
        values = values[values > 0]
    if not len(values):
        return values, np.array([]), np.array([])

    # Treat presynaptic-cell counts as a discrete integer distribution
    if metric == 'n_pre':
        value_min = int(values.min())
        value_max = int(values.max())
        bins = np.arange(value_min - 0.5, value_max + 1.5, 1)
    else:
        bins = np.histogram_bin_edges(values, bins=N_BINS)

    x = (bins[:-1] + bins[1:]) / 2
    density, _ = np.histogram(values, bins=bins, density=True)
    return values, x, density


def plot_group(dataset, pop_sizes, pop_post, group_pre, pops_pre, fpath_out,
               log_xscale=False):
    """Plot five pooled input distributions for one post population and pre group. """
    is_pop_post = dataset['pop_post'].values == pop_post

    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes = axes.ravel()

    # Plot each presynaptic population with bins adapted to its own values
    for ax, (metric, label) in zip(axes, METRICS.items()):
        values_by_pop = {
            pop_pre: get_values(dataset, metric, pop_pre, is_pop_post)
            for pop_pre in pops_pre
        }
        n_lines = 0
        for pop_pre, values in values_by_pop.items():
            values, x, density = calc_distribution(values, metric, log_xscale)
            if not len(values):
                continue
            line, = ax.plot(
                x,
                density,
                '.-',
                linewidth=1.5,
                label=f'{pop_pre} (n={pop_sizes[pop_pre]})',
            )
            ax.axvline(values.mean(), color=line.get_color(), alpha=0.5)
            n_lines += 1

        if not n_lines:
            ax.text(
                0.5,
                0.5,
                'No positive values',
                ha='center',
                va='center',
                transform=ax.transAxes,
            )

        ax.set_title(label)
        ax.set_ylabel('Density')
        ax.set_ylim(0, None)
        if log_xscale:
            ax.set_xscale('log')
        elif metric in {'w_sum', 'wr_sum'}:
            ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))

    axes[0].legend(frameon=False, fontsize=8)
    axes[-1].set_visible(False)
    fig.suptitle(f'Inputs to {pop_post} from {group_pre.upper()} populations')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.subplots_adjust(top=0.82)
    fig.savefig(fpath_out, dpi=150)
    plt.close(fig)


def build_group_figure(dataset, pop_sizes, pop_post, group_pre, pops_pre,
                       fpath_out, skip_existing=SKIP_EXISTING,
                       log_xscale=LOG_XSCALE):
    """Build one figure unless it is empty or already exists. """
    pops_weighted = get_weighted_pops(dataset, pop_post, pops_pre)
    if not pops_weighted:
        if fpath_out.exists():
            fpath_out.unlink()
        print(
            f'Building {pop_post}/{group_pre}: '
            'skipped (no positive-weight inputs)',
            flush=True,
        )
        return 'no_connections'
    if skip_existing and fpath_out.exists():
        print(f'Building {pop_post}/{group_pre}: skipped (exists)', flush=True)
        return 'exists'

    print(f'Building {pop_post}/{group_pre}: {fpath_out}', flush=True)
    plot_group(
        dataset,
        pop_sizes,
        pop_post,
        group_pre,
        pops_weighted,
        fpath_out,
        log_xscale=log_xscale,
    )
    print(f'Saved {fpath_out}', flush=True)
    return 'saved'


def main():
    """Plot grouped input distributions pooled across all seeds. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)

    # Load the five metrics once before generating all population-group figures
    with xr.open_dataset(FPATH_DATA) as dataset:
        dataset = dataset[list(METRICS)].load()
    print(f'Loaded {FPATH_DATA}', flush=True)

    # Preserve the postsynaptic population order used in the source dataset
    pops_post = list(dict.fromkeys(dataset['pop_post'].values))
    pop_sizes = get_population_sizes(dataset)
    for pop_post in pops_post:
        for group_pre, pops_pre in POP_GROUPS.items():
            fpath_out = DIRPATH_FIGS / f'{pop_post.lower()}_{group_pre}.png'
            build_group_figure(
                dataset,
                pop_sizes,
                pop_post,
                group_pre,
                pops_pre,
                fpath_out,
                skip_existing=SKIP_EXISTING,
                log_xscale=LOG_XSCALE,
            )


if __name__ == '__main__':
    main()
