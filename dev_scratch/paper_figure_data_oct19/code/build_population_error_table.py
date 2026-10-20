"""Export population error table panels from the cached per-seed summaries. """

import csv
from collections import defaultdict
import math
from pathlib import Path
from statistics import fmean, stdev


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_TABLES = DIR_TASK / 'data/tables'
SEEDS = set(range(1000, 1015))
PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'CT5A',
            'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']
THAL_POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']
PANELS = {
    'cortex': {
        'pops': PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS,
        'setups': {
            'All-surrogate': 'ctx_surr',
            'Fully recurrent': 'ctx_full',
            'E-E surrogate': 'ctx_ee_surr',
            'Faded': 'ctx_ee_fade',
            'Full thalamocortical circuit': 'a1_errors',
        },
    },
    'thalamus': {
        'pops': THAL_POPS,
        'setups': {
            'All-surrogate': 'thal_surr',
            'Fully recurrent': 'thal_orig',
            'Own correction': 'thal_own',
            'Median correction': 'thal_med',
            'Full thalamocortical circuit': 'a1_errors',
        },
    },
}


def main():
    """Validate trial selection and write two setup-column CSV panels. """
    with (DIR_TABLES / 'population_rates.csv').open(newline='') as fid:
        rates = list(csv.DictReader(fid))
    grouped = defaultdict(list)
    for row in rates:
        grouped[row['experiment'], row['pop']].append(row)
    with (DIR_TABLES / 'rate_error_statistics.csv').open(newline='') as fid:
        stats = {(r['experiment'], r['pop']): r for r in csv.DictReader(fid)}

    # Validate all 15 realizations and summarize each population within each setup
    for panel_name, panel in PANELS.items():
        output = []
        for pop in panel['pops']:
            targets = set()
            result = {'Population': pop}
            for label, experiment in panel['setups'].items():
                rows = grouped[experiment, pop]
                seeds = {int(r['seed']) for r in rows}
                if len(rows) != 15 or seeds != SEEDS:
                    raise ValueError(f'Incomplete or duplicate trials: {experiment}, {pop}')
                t_limits = (15, 20) if experiment == 'a1_errors' else (7, 10)
                if experiment in ['thal_orig', 'thal_own', 'thal_med']:
                    t_limits = (200, 220)
                for row in rows:
                    targets.add(float(row['target_hz']))
                    window = (float(row['t0_s']), float(row['t1_s']))
                    if window != t_limits:
                        raise ValueError(f'Unexpected averaging window: {experiment}, {pop}')
                    expected = float(row['rate_hz']) - float(row['target_hz'])
                    assert math.isclose(float(row['error_hz']), expected, abs_tol=1e-12)
                errors = [float(r['error_hz']) for r in rows]
                mean = fmean(errors)
                sd = stdev(errors)
                reference = stats[experiment, pop]
                assert math.isclose(mean, float(reference['mean']), abs_tol=1e-12)
                assert math.isclose(sd, float(reference['std']), abs_tol=1e-12)
                mean = round(mean, 3)
                if mean == 0:
                    mean = 0
                result[label] = f'{mean:.3f} ± {sd:.3f}'
            if len(targets) != 1:
                raise ValueError(f'Targets differ between setups: {pop}')
            result['Target rate (Hz)'] = f'{targets.pop():g}'
            output.append(result)

        # Write spreadsheet-friendly UTF-8 CSVs with one column per setup
        columns = ['Population', 'Target rate (Hz)'] + list(panel['setups'])
        path = DIR_TABLES / f'population_error_table_{panel_name}.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as fid:
            writer = csv.DictWriter(fid, fieldnames=columns)
            writer.writeheader()
            writer.writerows(output)
        n_setups = len(panel['setups'])
        print(f'{path.name}: {len(output)} populations, {n_setups} setups')
    print('All selections and unrounded statistics match the cached summaries')


if __name__ == '__main__':
    main()
