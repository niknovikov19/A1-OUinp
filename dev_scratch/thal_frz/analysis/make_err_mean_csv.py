#!/home/nnovikov/conda_env/netpyne/bin/python
"""Create mean thalamic rate errors relative to target state 1."""

import csv

from make_r_mean_csv import (
    DIR_ANALYSIS,
    DIR_COLLECTED,
    FPATH_INFO,
    THAL_POPS,
    get_mean_rate,
    load_xr,
    parse_markdown_table,
    resolve_experiment_dir,
)


FPATH_TARGET = DIR_ANALYSIS / 'target_state_1.csv'
FPATH_OUT = DIR_ANALYSIS / 'exp_frz_info_err_mean.csv'


def load_target_rates(fpath):
    """Load target rates keyed by population name."""
    with fpath.open('r', encoding='utf-8-sig', newline='') as fobj:
        rows = csv.DictReader(fobj)
        targets = {row['pop_name']: float(row['target_rate']) for row in rows}

    missing = [pop_name for pop_name in THAL_POPS if pop_name not in targets]
    if missing:
        raise KeyError(f'Missing target rates for {missing}')
    return targets


def format_error(value):
    """Format a two-decimal error without negative zero."""
    value = 0 if round(value, 2) == 0 else value
    return f'{value:.2f}'


def main():
    """Create the summary CSV with mean-minus-target rate errors."""
    header, rows = parse_markdown_table(FPATH_INFO)
    target_rates = load_target_rates(FPATH_TARGET)
    output_rows = []

    # Subtract each population target from its across-seed mean rate
    for row in rows:
        dirpath_exp = resolve_experiment_dir(row[0])
        fpath_collected = DIR_COLLECTED / f'{dirpath_exp.name}.nc'
        result_xr = load_xr(fpath_collected, data_type='dataset', load=True)
        errors = [
            format_error(get_mean_rate(result_xr, pop_name) - target_rates[pop_name])
            for pop_name in THAL_POPS
        ]
        result_xr.close()
        output_rows.append(row + errors)

    # Write the experiment table plus population-error columns
    with FPATH_OUT.open('w', encoding='utf-8', newline='') as fobj:
        writer = csv.writer(fobj)
        writer.writerow(header + THAL_POPS)
        writer.writerows(output_rows)

    print(f'Created {FPATH_OUT}')


if __name__ == '__main__':
    main()
