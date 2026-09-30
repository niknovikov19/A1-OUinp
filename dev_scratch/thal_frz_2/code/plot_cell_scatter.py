from pathlib import Path
import csv
import sys

import matplotlib.pyplot as plt
import numpy as np


# Set repository import paths
DIR_HERE = Path(__file__).resolve().parent
DIR_ROOT = DIR_HERE.parent
DIR_REPO = DIR_HERE.parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.xr_io import load_xr


# User parameters
DIRPATH_DATA = DIR_ROOT / 'data' / 'tc_loops_1'
DIRPATH_ARTIFACTS = DIR_ROOT / 'artifacts' / 'tc_loops_1'
DX = 0
JITTER_STD = 0.15
JITTER_SEED = 0
Y_LIMITS = (0.5, 200)
LOG_YSCALE = 1
SHOW_SEED_MEAN = 1
SHOW_SEED_AVG = 1
PLOT_ALL_POPS = 1
THAL_POPS = ['TC', 'TI', 'IRE', 'IREM']
FIGSIZE = (16, 8)
FIGSIZE_ALL = (24, 14)
DPI = 150
POINT_SIZE = 80
POINT_ALPHA = 0.3
MEAN_WIDTH = 0.3
MEAN_ALPHA = 1
AVG_WIDTH = 0.8
AVG_ALPHA = 1
PLOT_NAME = 'tcre'
FRZ_GROUPS = [
    'act__none',
    'act__ire_tc',
    'act__irem_tc',
    #'act__ti_tc',
    'act__tc_i__tc_re',
    'act__tc_ire_tc',
    'act__tc_irem_tc',
    #'act__tc_ti_tc',
    'act__irem_ire_tc',
    #'act__irem_ire_tc_ire',
    'act__irem_ire_tc_irem',
    #'act__irem_ti_tc',
    #'act__irem_ti_tc_irem',
    #'act__irem_ti_tc_ti',
]
Y_LIMITS_TAG = 'all' if Y_LIMITS is None else '_'.join(
    f'{y:g}' for y in Y_LIMITS
)
Y_SCALE_TAG = 'log' if LOG_YSCALE else 'lin'
DIRPATH_FIGS = (
    DIRPATH_ARTIFACTS
    / f'rate_scatter_{PLOT_NAME}_dx_{DX:g}_ylim_{Y_LIMITS_TAG}_{Y_SCALE_TAG}'
)
FPATH_TARGET = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1'
    / 'net_newsec_var_seed_frzconns' / 'target_state_1.csv'
)


def load_targets():
    """Load target rates for the selected populations. """
    with FPATH_TARGET.open(encoding='utf-8-sig', newline='') as file:
        targets = {
            row['pop_name']: float(row['target_rate'])
            for row in csv.DictReader(file)
            if row['pop_name'] in THAL_POPS
        }
    missing = set(THAL_POPS) - set(targets)
    if missing:
        raise ValueError(f'Missing target rates: {sorted(missing)}')
    return targets


def load_rates():
    """Load cell rates with their seed and freezing-group dimensions. """
    fpath = DIRPATH_DATA / 'cell_inp_stats_xr_combined.nc'
    with load_xr(
            fpath, data_type='dataset',
            engine='scipy', load=True
            ) as dataset:
        available = set(dataset['frz_conn_group'].values.tolist())
        missing = set(FRZ_GROUPS) - available
        if missing:
            raise ValueError(f'Missing freezing groups: {sorted(missing)}')
        return dataset[['rate']].copy(deep=True)


def get_seed_x(n_seeds):
    """Return centered seed offsets separated by DX. """
    return (np.arange(n_seeds) - (n_seeds - 1) / 2) * DX


def plot_pop(ax, dataset, targets, colors, pop, rng, all_pops=False):
    """Plot one population on the supplied axis. """
    is_pop = dataset['pop_post'].values == pop
    seed_dx = get_seed_x(dataset.sizes['seed_main'])

    # Draw per-cell points and optional mean dashes
    for group_idx, group in enumerate(FRZ_GROUPS):
        group_rates = dataset['rate'].sel(
            frz_conn_group=group
        ).isel(gid=is_pop)
        color = colors[group_idx]
        seed_means = []
        for seed_idx, dx in enumerate(seed_dx):
            values = group_rates.isel(seed_main=seed_idx).values
            values = values[np.isfinite(values)]
            x = group_idx + dx
            shown = values[values > 0] if LOG_YSCALE else values
            point_x = rng.normal(x, JITTER_STD, shown.size)
            ax.scatter(
                point_x,
                shown,
                s=POINT_SIZE,
                color=color,
                alpha=POINT_ALPHA,
                edgecolors='none',
                zorder=2,
            )
            mean = values.mean()
            seed_means.append(mean)
            if SHOW_SEED_MEAN:
                label = 'seed mean' if group_idx == 0 and seed_idx == 0 else None
                ax.plot(
                    [x - MEAN_WIDTH / 2, x + MEAN_WIDTH / 2],
                    [mean, mean],
                    color=color,
                    alpha=MEAN_ALPHA,
                    linewidth=5,
                    label=label,
                    zorder=3,
                )

        if SHOW_SEED_AVG:
            mean = np.mean(seed_means)
            label = 'seed-avg mean' if group_idx == 0 else None
            ax.plot(
                [group_idx - AVG_WIDTH / 2, group_idx + AVG_WIDTH / 2],
                [mean, mean],
                color=color,
                alpha=AVG_ALPHA,
                linewidth=8,
                label=label,
                zorder=4,
            )

    # Mark the population target across all freezing groups
    ax.axhline(
        targets[pop],
        color='black',
        linestyle='--',
        linewidth=1.5,
        label=f'target = {targets[pop]:g} Hz',
        zorder=5,
    )
    if LOG_YSCALE:
        ax.set_yscale('log')
    if Y_LIMITS is not None:
        y_min, y_max = Y_LIMITS
        if LOG_YSCALE and y_min <= 0:
            ax.set_ylim(top=y_max)
        else:
            ax.set_ylim(y_min, y_max)

    x_labels = [group.removeprefix('act__') for group in FRZ_GROUPS]
    fontsize = 10 if all_pops else 16
    ax.set_xticks(np.arange(len(FRZ_GROUPS)), x_labels,
                  rotation=25, ha='center', fontsize=fontsize)
    ax.set_xlim(-0.5, len(FRZ_GROUPS) - 0.5)
    ax.set_ylabel('Firing rate (Hz)')
    ax.set_title(f'{pop} per-cell firing rates')
    ax.grid(axis='y', alpha=0.2)
    ax.legend()


def plot_separate(dataset, targets, colors, rng):
    """Save one figure per selected population. """
    for pop in THAL_POPS:
        fig, ax = plt.subplots(figsize=FIGSIZE, constrained_layout=True)
        plot_pop(ax, dataset, targets, colors, pop, rng)
        fpath_out = DIRPATH_FIGS / f'rate_scatter_{pop}.png'
        fig.savefig(fpath_out, dpi=DPI)
        plt.close(fig)
        print(f'Saved {fpath_out}')


def plot_all(dataset, targets, colors, rng):
    """Save all selected populations as subpanels of one figure. """
    n_cols = 2
    n_rows = int(np.ceil(len(THAL_POPS) / n_cols))
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=FIGSIZE_ALL,
        sharex=True,
        sharey=True,
        constrained_layout=True,
        squeeze=False,
    )
    for ax, pop in zip(axes.ravel(), THAL_POPS):
        plot_pop(ax, dataset, targets, colors, pop, rng, all_pops=True)
    for ax in axes.ravel()[len(THAL_POPS):]:
        ax.set_visible(False)

    fpath_out = DIRPATH_FIGS / 'rate_scatter_all.png'
    fig.savefig(fpath_out, dpi=DPI)
    plt.close(fig)
    print(f'Saved {fpath_out}')


def main():
    """Create separate or combined per-cell rate scatter figures. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)
    dataset = load_rates()
    targets = load_targets()
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    colors = [color_cycle[idx % len(color_cycle)] for idx in range(len(FRZ_GROUPS))]
    rng = np.random.default_rng(JITTER_SEED)

    # Select separate figures or a shared multi-panel figure
    if PLOT_ALL_POPS:
        plot_all(dataset, targets, colors, rng)
    else:
        plot_separate(dataset, targets, colors, rng)
    dataset.close()


if __name__ == '__main__':
    main()
