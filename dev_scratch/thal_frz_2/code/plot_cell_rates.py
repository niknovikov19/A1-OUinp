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
N_BINS = 15
#X_LIMITS = None
X_LIMITS = (0, 10)
LOG_XSCALE = 0
SHARE_BINS = 1
THAL_POPS = ['TC', 'TI', 'IRE', 'IREM']
FIGSIZE = (14, 9)
DPI = 150
PLOT_STYLE = '.-'
EXP_GROUPS = {
    'Single loops': [
        'act__none',
        'act__ire_tc',
        'act__irem_tc',
        'act__ti_tc',
    ],
    'TC combinations': [
        'act__none',
        'act__tc_i__tc_re',
        'act__tc_ire_tc',
        'act__tc_irem_tc',
        'act__tc_ti_tc',
    ],
    'IREM combinations': [
        'act__none',
        'act__irem_ire_tc',
        'act__irem_ire_tc_ire',
        'act__irem_ire_tc_irem',
        'act__irem_ti_tc',
        'act__irem_ti_tc_irem',
        'act__irem_ti_tc_ti',
    ],
}
X_LIMITS_TAG = 'all' if X_LIMITS is None else '_'.join(
    f'{x:g}' for x in X_LIMITS
)
X_SCALE_TAG = 'log' if LOG_XSCALE else 'lin'
DIRPATH_FIGS = (
    DIRPATH_ARTIFACTS
    / f'rate_distr_nbins_{N_BINS}'
      f'_xlim_{X_LIMITS_TAG}_{X_SCALE_TAG}'
      f'_sb_{SHARE_BINS}'
)


def get_exp_names():
    """Return experiment names in plotting order. """
    return [name for names in EXP_GROUPS.values() for name in names]


def load_rates():
    """Load finite per-cell rates pooled across seeds. """
    fpath = DIRPATH_DATA / 'cell_inp_stats_xr_combined.nc'
    with load_xr(
            fpath, data_type='dataset',
            engine='scipy', load=True
            ) as dataset:
        exp_names = get_exp_names()
        available = set(dataset['frz_conn_group'].values.tolist())
        missing = set(exp_names) - available
        if missing:
            raise ValueError(f'Missing experiment groups: {sorted(missing)}')

        # Pool every population and experiment over seeds and cells
        rates = {}
        for exp_name in exp_names:
            exp_rates = {}
            for pop in THAL_POPS:
                is_pop = dataset['pop_post'].values == pop
                values = dataset['rate'].sel(
                    frz_conn_group=exp_name
                ).isel(gid=is_pop).values.ravel()
                exp_rates[pop] = values[np.isfinite(values)]
            rates[exp_name] = exp_rates
    return rates


def filter_values(values):
    """Apply the visible rate range and log-scale requirements. """
    if LOG_XSCALE:
        values = values[values > 0]
    if X_LIMITS is not None:
        values = values[(values >= X_LIMITS[0]) & (values <= X_LIMITS[1])]
    return values


def make_bins(values):
    """Make linear or logarithmic histogram bins. """
    values = filter_values(values)
    if not len(values):
        return np.array([])

    if not LOG_XSCALE:
        return np.histogram_bin_edges(values, bins=N_BINS, range=X_LIMITS)

    x_min = values.min()
    x_max = values.max()
    if X_LIMITS is not None:
        x_min = max(x_min, X_LIMITS[0])
        x_max = X_LIMITS[1]
    if x_min == x_max:
        x_min /= np.sqrt(2)
        x_max *= np.sqrt(2)
    return np.geomspace(x_min, x_max, N_BINS + 1)


def calc_distribution(values, bins=None):
    """Calculate a normalized histogram at bin centers. """
    values = filter_values(values)
    if not len(values):
        return np.array([]), np.array([])
    if bins is None:
        bins = make_bins(values)

    if LOG_XSCALE:
        x = np.sqrt(bins[:-1] * bins[1:])
    else:
        x = (bins[:-1] + bins[1:]) / 2
    density, _ = np.histogram(values, bins=bins, density=True)
    return x, density


def get_shared_bins(rates):
    """Make common bins for every population when requested. """
    if not SHARE_BINS:
        return {}

    shared = {}
    exp_names = get_exp_names()
    for pop in THAL_POPS:
        values = np.concatenate([rates[name][pop] for name in exp_names])
        shared[pop] = make_bins(values)
    return shared


def get_colors():
    """Assign stable colors within each experiment group. """
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    colors = {}
    for exp_names in EXP_GROUPS.values():
        colors.update({name: color_cycle[idx] for idx, name in enumerate(exp_names)})
    return colors


def plot_population(rates, colors, bins, pop, fpath_out):
    """Plot one population across the four experiment groups. """
    fig, axes = plt.subplots(
        2,
        2,
        figsize=FIGSIZE,
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )

    # Plot the configured experiment groups in separate panels
    for ax, (group_name, exp_names) in zip(axes.ravel(), EXP_GROUPS.items()):
        if LOG_XSCALE:
            ax.set_xscale('log')
        for exp_name in exp_names:
            x, density = calc_distribution(rates[exp_name][pop], bins=bins)
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

    # Apply one visible range after all panels set their automatic limits
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


def save_silent_fractions(rates):
    """Save zero-rate fractions by experiment and population. """
    fpath = DIRPATH_ARTIFACTS / 'silent_frac.csv'
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with fpath.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['frz_conn_group'] + THAL_POPS)
        writer.writeheader()
        for exp_name in get_exp_names():
            row = {'frz_conn_group': exp_name}
            for pop in THAL_POPS:
                values = rates[exp_name][pop]
                row[pop] = np.mean(values == 0)
            writer.writerow(row)
    print(f'Saved {fpath}')


def main():
    """Create pooled rate distributions and silent-cell fractions. """
    DIRPATH_FIGS.mkdir(parents=True, exist_ok=True)
    rates = load_rates()
    shared_bins = get_shared_bins(rates)
    colors = get_colors()

    # Save populations separately for uncluttered comparisons
    for pop in THAL_POPS:
        fpath_out = DIRPATH_FIGS / f'rate_distr_{pop}.png'
        plot_population(rates, colors, shared_bins.get(pop), pop, fpath_out)
        print(f'Saved {fpath_out}')

    save_silent_fractions(rates)


if __name__ == '__main__':
    main()
