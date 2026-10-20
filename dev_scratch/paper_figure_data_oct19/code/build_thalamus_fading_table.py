"""Export the uncorrected thalamic rate table from local per-seed caches. """

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean, stdev
import sys


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_REPO = DIR_TASK.parents[1]
sys.path.insert(0, str(DIR_REPO / 'external'))
from sim_data_analyzer.xr_io import load_xr


DIR_TABLES = DIR_TASK / 'data/tables'
DIR_INVENTORIES = DIR_TASK / 'data/inventories'
POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']
SEEDS = list(range(1000, 1015))
CONDITIONS = {
    'All-surrogate': 'thal_unconn',
    'IREM→TI frozen': 'irem_ti_0',
    'IREM→IRE frozen': 'irem_ire_0',
    'Fully recurrent': 'thal_ee_1',
    'Faded from all-surrogate': 'thal_all_fade',
    'Faded IREM→TI': None,
    'Faded IREM→IRE': None,
}


def write_csv(path, columns, rows):
    """Write spreadsheet-friendly CSV with explicit empty missing values. """
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Validate local sources and export rates, provenance, and formatted cells. """
    inventory = json.loads((DIR_INVENTORIES / 'supplementary_data_readiness.json').read_text())
    cfg_summary = json.loads((DIR_INVENTORIES / 'saved_cfg_summary.json').read_text())
    targets = {pop: cfg_summary['thal_surr']['target_rates'][pop] for pop in POPS}
    summaries = {}
    per_seed = []
    provenance = {
        'quantity': 'Modeled population firing rate in Hz, not signed rate error or surrogate-source rate',
        'summary': 'Mean ± sample SD (ddof=1), two decimal places',
        'populations': POPS, 'seeds': SEEDS, 'duration_s': 10, 'window_s': [7, 10],
        'target_rates_hz': targets, 'second_stage_corrections': False,
        'missing_cell_encoding': 'Empty CSV field', 'conditions': {},
        'remote_reads': 0,
    }

    # Validate the exact population set, protocol, and intervention in each local cfg
    for column, label in CONDITIONS.items():
        if label is None:
            provenance['conditions'][column] = {'status': 'missing', 'experiment': None}
            continue
        name = f'exp_{label}_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5'
        entry = inventory['thal_local'][name]
        cache = DIR_REPO / entry['cache']
        cfg_path = DIR_REPO / entry['cfg']
        cfg = json.loads(cfg_path.read_text())['simConfig']
        subnet = cfg['subnet_params']
        if set(subnet['pops_active']) != set(POPS):
            raise ValueError(f'Unexpected populations: {name}')
        if cfg['duration'] != 10000 or cfg['t0_calc'] != 7000:
            raise ValueError(f'Unexpected averaging window: {name}')
        if any(cfg['target_rates'][pop] != targets[pop] for pop in POPS):
            raise ValueError(f'Target mismatch: {name}')
        expected_frozen = {'thal_unconn': 'all', 'irem_ti_0': [['IREM', 'TI']],
                           'irem_ire_0': [['IREM', 'IRE']]}.get(label, [])
        if subnet['conns_frozen'] != expected_frozen:
            raise ValueError(f'Unexpected frozen connections: {name}')
        split = subnet.get('conns_split', {})
        if label == 'thal_all_fade':
            expected_pairs = {f'{pre}, {post}' for pre in POPS for post in POPS}
            if set(split) != expected_pairs or any(value != 0.5 for value in split.values()):
                raise ValueError(f'Unexpected faded connections: {name}')
        elif split:
            raise ValueError(f'Unexpected split connections: {name}')

        # Select modeled populations explicitly and exclude the surrogate frz coordinates
        with load_xr(cache, data_type='dataset', engine='h5netcdf', load=True) as dataset:
            if sorted(dataset.seed_main.values.tolist()) != SEEDS:
                raise ValueError(f'Incomplete or duplicate seed set: {name}')
            rates = dataset['rate'].sel(seed_main=SEEDS, pop=POPS)
            rates = rates.transpose('seed_main', 'pop')
            values = rates.values.tolist()
        summaries[column] = {}
        for index, pop in enumerate(POPS):
            trials = [float(row[index]) for row in values]
            if not all(math.isfinite(value) and value >= 0 for value in trials):
                raise ValueError(f'Invalid modeled rates: {name}, {pop}')
            mean = fmean(trials)
            sd = stdev(trials)
            if not math.isclose(mean, entry['mean_rates_hz'][pop], abs_tol=1e-12):
                raise ValueError(f'Inventory mean mismatch: {name}, {pop}')
            summaries[column][pop] = {'mean_hz': mean, 'sample_sd_hz': sd, 'n': len(trials)}
            for seed, rate in zip(SEEDS, trials):
                per_seed.append({'condition': column, 'experiment': name, 'population': pop,
                                 'seed': seed, 'target_hz': targets[pop], 'rate_hz': rate,
                                 't0_s': 7, 't1_s': 10})

        provenance['conditions'][column] = {
            'status': 'available', 'experiment': name,
            'remote_experiment': 'exp_results/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/' + name,
            'local_rate_cache': entry['cache'], 'local_cfg': entry['cfg'],
            'cache_sha256': hashlib.sha256(cache.read_bytes()).hexdigest(),
            'cfg_sha256': hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
            'statistics': summaries[column],
        }

    # Keep both unavailable fading columns empty for every population
    rows = []
    for pop in POPS:
        row = {'Population': pop, 'Target rate (Hz)': f'{targets[pop]:g}'}
        for column, label in CONDITIONS.items():
            if label is None:
                row[column] = ''
                continue
            stats = summaries[column][pop]
            row[column] = f"{stats['mean_hz']:.2f} ± {stats['sample_sd_hz']:.2f}"
        rows.append(row)

    # Preserve unrounded per-seed rates and exact source hashes alongside the paper table
    path = DIR_TABLES / 'population_rate_table_thalamus_fading.csv'
    columns = ['Population', 'Target rate (Hz)'] + list(CONDITIONS)
    write_csv(path, columns, rows)
    write_csv(DIR_TABLES / 'thalamus_fading_rates_per_seed.csv', list(per_seed[0]), per_seed)
    audit = DIR_INVENTORIES / 'thalamus_fading_table_sources.json'
    audit.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + '\n')
    print(f'{path.name}: {len(rows)} populations, 5 available and 2 blank condition columns')
    print(f'Validated {len(per_seed)} local per-seed rates; no mounted results read')


if __name__ == '__main__':
    main()
