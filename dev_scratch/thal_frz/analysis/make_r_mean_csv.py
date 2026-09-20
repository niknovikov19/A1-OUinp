#!/home/nnovikov/conda_env/netpyne/bin/python
"""Add mean thalamic population rates to the freezing-summary table."""

import csv
import re
import sys
from pathlib import Path

import numpy as np


# Set repository import paths
DIR_ANALYSIS = Path(__file__).resolve().parent
DIR_REPO = DIR_ANALYSIS.parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.xr_io import load_xr


DIR_ROOT = DIR_ANALYSIS.parent
DIR_EXPERIMENTS = DIR_ANALYSIS / 'experiments'
DIR_COLLECTED = DIR_ANALYSIS / 'collected'
FPATH_INFO = DIR_ROOT / 'exp_frz_info.md'
FPATH_OUT = DIR_ANALYSIS / 'exp_frz_info_r_mean.csv'
THAL_POPS = ['TC', 'HTC', 'TCM', 'TI', 'TIM', 'IRE', 'IREM']


def parse_markdown_table(fpath):
    """Parse the experiment table from the Markdown summary."""
    lines = Path(fpath).read_text(encoding='utf-8').splitlines()
    header_idx = next(
        idx for idx, line in enumerate(lines)
        if line.startswith('| Experiment |')
    )
    header = [cell.strip().strip('`') for cell in lines[header_idx].strip('|').split('|')]
    rows = []
    for line in lines[header_idx + 2:]:
        if not line.startswith('|'):
            break
        rows.append([cell.strip().replace('`', '') for cell in line.strip('|').split('|')])
    return header, rows


def resolve_experiment_dir(experiment_cell):
    """Resolve a compact Markdown experiment label to its full folder."""
    label = experiment_cell.replace('`', '')
    match = re.fullmatch(r'(.+?)(?: \(nseed=(\d+)\))?', label)
    if match is None:
        raise ValueError(f'Cannot parse experiment label: {experiment_cell}')

    stem, nseed = match.groups()
    pattern = f'exp_{stem}_nseed_{nseed}_*' if nseed else f'exp_{stem}_nseed_*'
    matches = sorted(path for path in DIR_EXPERIMENTS.glob(pattern) if path.is_dir())
    if len(matches) != 1:
        raise RuntimeError(f'Expected one folder for {experiment_cell}, found {matches}')
    return matches[0]


def get_mean_rate(result_xr, pop_name):
    """Mean a real population rate, falling back to its frozen counterpart."""
    pop_values = set(str(value) for value in result_xr.coords['pop'].values)
    rate = None
    if pop_name in pop_values:
        rate = result_xr['rate'].sel(pop=pop_name)

    frozen_name = f'{pop_name}frz'
    if frozen_name in pop_values:
        frozen_rate = result_xr['rate'].sel(pop=frozen_name)
        rate = frozen_rate if rate is None else rate.fillna(frozen_rate)

    if rate is None:
        raise KeyError(f'No rate key for {pop_name}')
    value = float(rate.mean(skipna=True).item())
    if not np.isfinite(value):
        raise ValueError(f'Non-finite mean rate for {pop_name}')
    return value


def main():
    """Create the summary CSV with mean population rates."""
    header, rows = parse_markdown_table(FPATH_INFO)
    output_rows = []

    # Join each Markdown row to its collected experiment dataset
    for row in rows:
        dirpath_exp = resolve_experiment_dir(row[0])
        fpath_collected = DIR_COLLECTED / f'{dirpath_exp.name}.nc'
        result_xr = load_xr(fpath_collected, data_type='dataset', load=True)
        mean_rates = [f'{get_mean_rate(result_xr, pop_name):.2f}' for pop_name in THAL_POPS]
        result_xr.close()
        output_rows.append(row + mean_rates)

    # Write the Markdown table plus population-rate columns
    with FPATH_OUT.open('w', encoding='utf-8', newline='') as fobj:
        writer = csv.writer(fobj)
        writer.writerow(header + THAL_POPS)
        writer.writerows(output_rows)

    print(f'Created {FPATH_OUT}')


if __name__ == '__main__':
    main()
