from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


# Set repository import paths
DIR_HERE = Path(__file__).resolve().parent
DIR_REPO = DIR_HERE.parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.xr_io import load_xr


# User parameters
DIRPATH_DATA = DIR_HERE / 'thal_cell_rates'
N_BINS = 15
#X_LIMITS = (0, 50)
X_LIMITS = None
LOG_XSCALE = 1
THAL_POPS = ['TC', 'HTC', 'TCM', 'TI', 'TIM', 'IRE', 'IREM']
FIGSIZE = (14, 9)
DPI = 150
PLOT_STYLE = '.-'
EXP_GROUPS = {
    'References': [
        'core_full',
        'matx_full',
        'thal_ee_1',
        'thal_all_fade',
        'thal_tc_ti_fade',
        'thal_ti_tc_fade',
        'thal_unconn_nseed_15',
        'thal_unconn_nseed_5',
    ],
    'IREM interventions': [
        'irem_core_0',
        'irem_ire_0',
        'irem_tc_0',
        'irem_ti_0',
        'thal_ire_tc_0',
        'thal_ee_0_ire_tc_0',
    ],
    'Matrix/TIM interventions': [
        'matx_core_0',
        'matx_ti_0',
        'tim_core_0',
    ],
    'Other thalamic freezes': [
        'thal_ee_0',
        'thal_pe_0',
        'thal_pti_0',
        'thal_tc_ti_0',
        'thal_ti_tc_0',
    ],
}
X_LIMITS_TAG = 'all' if X_LIMITS is None else '_'.join(f'{x:g}' for x in X_LIMITS)
X_SCALE_TAG = 'log' if LOG_XSCALE else 'linear'
DIRPATH_FIGS = (
    DIR_HERE / 'figures'
    / f'thal_rate_distributions_nbins_{N_BINS}_xlim_{X_LIMITS_TAG}_xscale_{X_SCALE_TAG}'
)


def resolve_experiment_paths():
    """Resolve each concise experiment name to one rate dataset. """
    paths = {}
    for exp_names in EXP_GROUPS.values():
        for exp_name in exp_names:
            if '_nseed_' in exp_name:
                pattern = f'exp_{exp_name}_*'
            else:
                pattern = f'exp_{exp_name}_nseed_*'
            matches = sorted(DIRPATH_DATA.glob(f'{pattern}/cell_rates_xr_combined.nc'))
            if len(matches) != 1:
                raise RuntimeError(
                    f'Expected one dataset for {exp_name}, found {matches}'
                )
            paths[exp_name] = matches[0]
    return paths


def load_pooled_rates(paths):
    """Load finite per-cell rates pooled across all seeds. """
    pooled_rates = {}
    for exp_name, path in paths.items():
        with load_xr(
                path, data_type='dataset',
                engine=None,
                load=True
                ) as dataset:
            exp_rates = {}
            for pop in THAL_POPS:
                is_pop = dataset['pop'].values == pop
                if not is_pop.any():
                    continue
                values = dataset['rate'].isel(gid=is_pop).values.ravel()
                exp_rates[pop] = values[np.isfinite(values)]
            pooled_rates[exp_name] = exp_rates
    return pooled_rates


def calc_distribution(values):
    """Calculate a normalized histogram at bin centers. """
    if LOG_XSCALE:
        values = values[values > 0]
    if X_LIMITS is not None:
        values = values[(values >= X_LIMITS[0]) & (values <= X_LIMITS[1])]
    if not len(values):
        return np.array([]), np.array([])

    if LOG_XSCALE:
        x_min = values.min()
        x_max = values.max()
        if X_LIMITS is not None:
            x_min = max(x_min, X_LIMITS[0])
            x_max = X_LIMITS[1]
        bins = np.geomspace(x_min, x_max, N_BINS + 1)
        x = np.sqrt(bins[:-1] * bins[1:])
    else:
        bins = np.histogram_bin_edges(values, bins=N_BINS, range=X_LIMITS)
        x = (bins[:-1] + bins[1:]) / 2
    density, _ = np.histogram(values, bins=bins, density=True)
    return x, density


def get_experiment_colors():
    """Assign stable colors to experiments in configured order. """
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    colors = {}
    for exp_names in EXP_GROUPS.values():
        colors.update({name: color_cycle[idx] for idx, name in enumerate(exp_names)})
    return colors


def plot_population(pooled_rates, colors, pop, fpath_out):
    """Plot one population across the four experiment groups. """
    fig, axes = plt.subplots(
        2,
        2,
        figsize=FIGSIZE,
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )

    # Plot each experiment with bins adapted to its own pooled rates
    for ax, (group_name, exp_names) in zip(axes.ravel(), EXP_GROUPS.items()):
        if LOG_XSCALE:
            ax.set_xscale('log')
        for exp_name in exp_names:
            values = pooled_rates[exp_name].get(pop)
            if values is None:
                continue
            x, density = calc_distribution(values)
            if not len(x):
                continue
            ax.plot(
                x,
                density,
                PLOT_STYLE,
                color=colors[exp_name],
                linewidth=1.5,
                label=exp_name,
            )
        ax.set_title(group_name)
        ax.set_ylim(0, None)
        ax.legend(fontsize=8)

    # Apply a shared visible range after all curves have set the automatic limits
    if X_LIMITS is not None:
        x_min, x_max = X_LIMITS
        if LOG_XSCALE and x_min <= 0:
            axes[0, 0].set_xlim(right=x_max)
        else:
            axes[0, 0].set_xlim(x_min, x_max)

    fig.suptitle(f'{pop} per-cell firing rates')
    fig.supxlabel('Firing rate (Hz)')
    fig.supylabel('Density')
    fig.savefig(fpath_out, dpi=DPI)
    plt.close(fig)


def main():
    """Create one pooled rate-distribution figure per thalamic population. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)
    paths = resolve_experiment_paths()
    pooled_rates = load_pooled_rates(paths)
    colors = get_experiment_colors()

    # Save populations separately for uncluttered comparisons
    for pop in THAL_POPS:
        fpath_out = DIRPATH_FIGS / f'rate_distribution_{pop}.png'
        plot_population(pooled_rates, colors, pop, fpath_out)
        print(f'Saved {fpath_out}')


if __name__ == '__main__':
    main()
