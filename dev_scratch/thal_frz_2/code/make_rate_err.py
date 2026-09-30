from pathlib import Path
import csv
import sys

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


# Input and output paths
FPATH_DATA = DIR_ROOT / 'data' / 'tc_loops_1' / 'cell_inp_stats_xr_combined.nc'
FPATH_TARGET = (
    DIR_REPO / 'exp_configs' / 'batch_rxbkg_state1_mech1'
    / 'net_newsec_var_seed_frzconns' / 'target_state_1.csv'
)
FPATH_OUT = DIR_ROOT / 'artifacts' / 'tc_loops_1' / 'pop_rate_err.csv'
THAL_POPS = ['TC', 'HTC', 'TCM', 'TI', 'TIM', 'IRE', 'IREM']


# Active projections encoded by each freezing-group name
ACTIVE_CONNS = {
    'act__none': [],
    'act__ire_tc': ['IRE->TC'],
    'act__irem_tc': ['IREM->TC'],
    'act__ti_tc': ['TI->TC'],
    'act__tc_i__tc_re': ['TC->TI', 'TC->IRE'],
    'act__tc_ire_tc': ['TC->IRE', 'IRE->TC'],
    'act__tc_irem_tc': ['TC->IREM', 'IREM->TC'],
    'act__tc_ti_tc': ['TC->TI', 'TI->TC'],
    'act__irem_ire_tc': ['IREM->IRE', 'IRE->TC'],
    'act__irem_ire_tc_ire': ['IREM->IRE', 'IRE->TC', 'TC->IRE'],
    'act__irem_ire_tc_irem': ['IREM->IRE', 'IRE->TC', 'TC->IREM'],
    'act__irem_ti_tc': ['IREM->TI', 'TI->TC'],
    'act__irem_ti_tc_irem': ['IREM->TI', 'TI->TC', 'TC->IREM'],
    'act__irem_ti_tc_ti': ['IREM->TI', 'TI->TC', 'TC->TI'],
}


def load_targets():
    """Load target rates for the seven thalamic populations. """
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


def format_err(values):
    """Format mean plus-minus sample standard deviation over seeds. """
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    mean = 0 if round(mean, 2) == 0 else mean
    std = 0 if round(std, 2) == 0 else std
    return f'{mean:.2f} +- {std:.2f}'


def make_rows(dataset, targets):
    """Build one rate-error row per freezing group. """
    available = set(dataset['frz_conn_group'].values.tolist())
    missing = set(ACTIVE_CONNS) - available
    if missing:
        raise ValueError(f'Missing freezing groups: {sorted(missing)}')

    rows = []
    for group, conns in ACTIVE_CONNS.items():
        row = {
            'frz_group': group,
            'active_conns': f"[{'; '.join(conns)}]",
        }
        for pop in THAL_POPS:
            is_pop = dataset['pop_post'].values == pop
            seed_rates = dataset['rate'].sel(
                frz_conn_group=group
            ).isel(gid=is_pop).mean('gid').values
            row[pop] = format_err(seed_rates - targets[pop])
        rows.append(row)
    return rows


def main():
    """Save population rate errors relative to target state 1. """
    targets = load_targets()
    with load_xr(
            FPATH_DATA, data_type='dataset',
            engine='scipy', load=True
            ) as dataset:
        rows = make_rows(dataset, targets)

    # Write metadata columns followed by unmodified population names
    FPATH_OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ['frz_group', 'active_conns'] + THAL_POPS
    with FPATH_OUT.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved {FPATH_OUT}')


if __name__ == '__main__':
    main()
