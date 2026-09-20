import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


DIR_HERE = Path(__file__).resolve().parent
FPATH_DATA = (
    DIR_HERE / 'test_data/single/cell_inp_stats_00000_seed_1000.nc'
)
FPATH_OUT = DIR_HERE / 'pop_pair_stats.csv'

INPUT_METRICS = {
    'npre': 'n_pre',
    'rpre': 'r_pre_mean',
    'rpre_wmean': 'r_pre_wmean',
    'wsum': 'w_sum',
    'wrsum': 'wr_sum',
}
REQUIRED_VARS = set(INPUT_METRICS.values()) | {'rate'}
MIN_DECIMALS = 3
SMALL_VALUE_SIGNIFICANT_DIGITS = 4
MAX_DECIMALS = 12
SUMMARY_NAMES = (
    'r0_pre',
    'r0_post',
    'npre',
    'rpre',
    'rpre_wmean',
    'drpre_wmean',
    'wsum',
    'wrsum',
    'dinput',
)
TABLE_COLUMNS = ['pop_pre', 'pop_post', 'sz_pre', 'sz_post'] + [
    f'{name}_{stat}'
    for name in SUMMARY_NAMES
    for stat in ('avg', 'std', 'cv')
]


def calc_mean_std(values):
    """Calculate a mean and population standard deviation of finite values. """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return np.nan, np.nan
    return values.mean(), values.std(ddof=0)


def add_summary(row, name, values):
    """Add average, standard deviation, and CV columns to a table row. """
    avg, std = calc_mean_std(values)
    with np.errstate(divide='ignore', invalid='ignore'):
        cv = np.divide(std, avg)
    row[f'{name}_avg'] = avg
    row[f'{name}_std'] = std
    row[f'{name}_cv'] = float(cv)


def format_float(value):
    """Format floats with extra decimals where small values need them. """
    if not np.isfinite(value) or value == 0:
        return f'{value:.{MIN_DECIMALS}f}'
    magnitude = int(np.floor(np.log10(abs(value))))
    decimals = SMALL_VALUE_SIGNIFICANT_DIGITS - 1 - magnitude
    decimals = min(MAX_DECIMALS, max(MIN_DECIMALS, decimals))
    return f'{value:.{decimals}f}'


def validate_dataset(dataset):
    """Validate the fields needed to build the population-pair table. """
    missing_vars = REQUIRED_VARS - set(dataset.data_vars)
    missing_coords = {'gid', 'pop_pre', 'pop_post'} - set(dataset.coords)
    if missing_vars or missing_coords:
        raise ValueError(
            f'Missing variables {sorted(missing_vars)} or coordinates '
            f'{sorted(missing_coords)}'
        )
    if dataset['pop_post'].dims != ('gid',):
        raise ValueError("Expected coordinate 'pop_post' to have dimension 'gid'")


def get_population_stats(dataset):
    """Calculate size and firing-rate statistics for each cell population. """
    pop_post = dataset['pop_post'].values.astype(str)
    rates = dataset['rate'].values
    populations = list(dict.fromkeys(pop_post))
    stats = {}

    # Summarize the full populations once for reuse across connected pairs
    for pop in populations:
        is_pop = pop_post == pop
        avg, std = calc_mean_std(rates[is_pop])
        stats[pop] = {
            'size': int(is_pop.sum()),
            'avg': avg,
            'std': std,
        }
    return stats


def build_pop_pair_stats_table(dataset):
    """Build one summary-table row for every connected population pair. """
    validate_dataset(dataset)
    pop_stats = get_population_stats(dataset)
    pop_post_values = dataset['pop_post'].values.astype(str)
    pops_post = list(dict.fromkeys(pop_post_values))
    rows = []

    # Preserve dataset population order in the resulting table
    for pop_pre_value in dataset['pop_pre'].values:
        pop_pre = str(pop_pre_value)
        for pop_post in pops_post:
            is_pop_post = pop_post_values == pop_post
            pair = dataset.sel(pop_pre=pop_pre).isel(gid=is_pop_post)
            if not np.any(pair['n_pre'].values > 0):
                continue
            if pop_pre not in pop_stats:
                raise ValueError(
                    f'Population {pop_pre!r} has no cells in coordinate '
                    'pop_post; its size and full-population firing rate '
                    'cannot be calculated'
                )

            pre = pop_stats[pop_pre]
            post = pop_stats[pop_post]
            row = {
                'pop_pre': pop_pre,
                'pop_post': pop_post,
                'sz_pre': pre['size'],
                'sz_post': post['size'],
            }
            add_summary(row, 'r0_pre', dataset['rate'].values[
                pop_post_values == pop_pre
            ])
            add_summary(row, 'r0_post', pair['rate'].values)

            # Summarize the stored per-cell input metrics
            for name, variable in INPUT_METRICS.items():
                add_summary(row, name, pair[variable].values)

            # Compare each cell's weighted input rates with the source baseline
            drpre_wmean = pair['r_pre_wmean'].values - pre['avg']
            dinput = (
                pair['wr_sum'].values - pre['avg'] * pair['w_sum'].values
            )
            add_summary(row, 'drpre_wmean', drpre_wmean)
            add_summary(row, 'dinput', dinput)
            rows.append(row)

    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def parse_args():
    """Parse optional input and output paths. """
    parser = argparse.ArgumentParser(
        description='Summarize per-cell inputs by population pair.',
    )
    parser.add_argument('--input', type=Path, default=FPATH_DATA)
    parser.add_argument('--output', type=Path, default=FPATH_OUT)
    return parser.parse_args()


def main():
    """Build and save the population-pair input statistics table. """
    args = parse_args()

    # Load before closing the NetCDF file backing the dataset
    with xr.open_dataset(args.input) as dataset:
        table = build_pop_pair_stats_table(dataset)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False, float_format=format_float)
    print(f'Saved {len(table)} population pairs to {args.output}')


if __name__ == '__main__':
    main()
