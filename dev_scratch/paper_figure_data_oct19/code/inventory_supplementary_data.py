"""Inventory selected supplementary sources with bounded JSON reads and local caches. """

import csv
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_REPO = DIR_TASK.parents[1]
sys.path.insert(0, str(DIR_REPO / 'external'))
from sim_data_analyzer.xr_io import load_xr


DIR_OUT = DIR_TASK / 'data/inventories'
DIR_SNAPSHOTS = DIR_TASK / 'data/snapshots/supplementary'
DIR_RESULTS = DIR_REPO / 'exp_results/batch_rxbkg_state1_mech1'
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
A1_EXPERIMENTS = {
    'a1_no_fade_no_corr': 'exp_a1_ee_full_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5',
    'a1_no_fade_corr': 'exp_a1_full_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5',
    'a1_fade_no_corr': 'exp_a1_ee_fade_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5',
    'a1_fade_corr': 'exp_a1_ee_fade_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5',
    'a1_ee_surr_no_corr': 'exp_a1_ee_0_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5',
    'a1_ee_surr_corr': 'exp_a1_ee_0_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5',
}
THAL_POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']


def list_names(folder):
    """List one directory without recursively visiting children. """
    if not folder.is_dir():
        return []
    with os.scandir(folder) as entries:
        return sorted(entry.name for entry in entries)


def probe_outputs(root):
    """Inventory compact output folders and stat only the illustrative raw file. """
    output = {name: list_names(root / name)
              for name in ['wmod_figs', 'rvec_figs', 'rvec_xr']}
    sample = root / 'pkl/data_00000_seed_1000.pkl'
    output['sample_pickle'] = str(sample.relative_to(DIR_REPO))
    output['sample_pickle_bytes'] = sample.stat().st_size if sample.is_file() else None
    return output


def main():
    """Save source evidence without loading remote pickles or running simulations. """
    inventory = {'a1_controls': {}, 'thal_local': {}, 'main_outputs': {}}
    audit = []
    total_bytes = 0
    population_rows = []

    # Read only the explicitly selected small remote JSON files, reusing snapshots
    for label, experiment in A1_EXPERIMENTS.items():
        root = DIR_RESULTS / 'net_newsec_ctrl_var_seed' / experiment
        entry = {'path': str(root.relative_to(DIR_REPO)), 'exists': root.is_dir()}
        inventory['a1_controls'][label] = entry
        if not entry['exists']:
            continue
        results = [name for name in list_names(root / 'results') if name.endswith('.json')]
        cfgs = [name for name in list_names(root / 'cfg') if name.endswith('.json')]
        entry.update(result_files=results, cfg_files=cfgs, outputs=probe_outputs(root))
        if not cfgs:
            continue
        destination = DIR_SNAPSHOTS / label
        destination.mkdir(parents=True, exist_ok=True)
        cfg = None
        windows = set()
        seeds = []
        for folder, name in [('cfg', cfgs[0])] + [('results', name) for name in results]:
            source = root / folder / name
            cached = destination / name
            read_path = cached if cached.is_file() else source
            size = read_path.stat().st_size
            if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
                raise RuntimeError(f'JSON read budget exceeded: {source}')
            content = read_path.read_bytes()
            total_bytes += len(content)
            if read_path == source:
                cached.write_bytes(content)
            audit.append({'path': str(source.relative_to(DIR_REPO)),
                          'snapshot': str(cached.relative_to(DIR_TASK)),
                          'bytes': len(content),
                          'sha256': hashlib.sha256(content).hexdigest()})
            data = json.loads(content)
            if folder == 'cfg':
                cfg = data['simConfig']
                subnet = cfg['subnet_params']
                frozen = subnet['conns_frozen']
                entry['cfg'] = {
                    'duration_s': cfg['duration'] / 1000,
                    't0_calc_s': cfg['t0_calc'] / 1000,
                    'pops_active': subnet['pops_active'],
                    'conns_frozen': frozen,
                    'conns_split': subnet.get('conns_split', {}),
                    'IClamp': cfg.get('IClamp'),
                    'wmult': cfg['wmult'], 'EEGain': cfg['EEGain'],
                    'cache_efficient': cfg.get('cache_efficient'),
                    'runtime_params': cfg.get('runtime_params'),
                    'ou_ctrl_params': cfg.get('ou_ctrl_params'),
                }
                compared = {key: cfg.get(key) for key in
                            ['target_rates', 'bkg_spike_inputs', 'mech_changes',
                             'wmult', 'EEGain', 'connRandomSecFromList',
                             'connWeightSecByLength', 'seeds']}
                compared['subnet_global_seed'] = subnet['global_seed']
                signature = json.dumps(compared, sort_keys=True).encode()
                entry['selected_settings_sha256'] = hashlib.sha256(signature).hexdigest()
                continue
            seed = int(name.removesuffix('.json').split('_seed_')[-1])
            seeds.append(seed)
            windows.add(tuple(data['t_limits_r']))
            for pop, target in cfg['target_rates'].items():
                if pop not in data['rates']:
                    continue
                rate = data['rates'][pop]
                population_rows.append({'experiment': label, 'seed': seed, 'pop': pop,
                                        'target_hz': target, 'rate_hz': rate,
                                        'error_hz': rate - target})
        entry['summary_windows_s'] = sorted(windows)
        entry['seeds'] = sorted(seeds)

    # Read existing local thalamic summaries through sim_data_analyzer
    targets = json.loads((DIR_TASK / 'data/inventories/saved_cfg_summary.json').read_text())
    target_rates = targets['thal_surr']['target_rates']
    collected = DIR_REPO / 'dev_scratch/thal_frz/analysis/collected'
    for path in sorted(collected.glob('*.nc')):
        cfg_path = DIR_REPO / 'dev_scratch/thal_frz/cfg' / (path.stem + '__cfg_00000_seed_1000.json')
        cfg = json.loads(cfg_path.read_text())['simConfig']
        subnet = cfg['subnet_params']
        pops = subnet['pops_active']
        with load_xr(path, data_type='dataset', engine='h5netcdf', load=True) as dataset:
            rates = dataset['rate'].sel(pop=pops)
            errors = rates - np.array([target_rates[pop] for pop in pops])
            entry = {
                'cache': str(path.relative_to(DIR_REPO)),
                'cfg': str(cfg_path.relative_to(DIR_REPO)),
                'bytes': path.stat().st_size,
                'seeds': dataset.seed_main.values.tolist(),
                'pops_active': pops, 'duration_s': cfg['duration'] / 1000,
                'window_s': [cfg['t0_calc'] / 1000, cfg['duration'] / 1000],
                'conns_frozen': subnet['conns_frozen'],
                'conns_split': subnet.get('conns_split', {}),
                'mean_absolute_bias_hz': float(abs(errors.mean('seed_main')).mean()),
                'mean_rates_hz': {pop: float(rates.sel(pop=pop).mean()) for pop in pops},
            }
        selected = ['thal_all_fade', 'thal_tc_ti_fade', 'thal_ti_tc_fade',
                    'thal_ee_1', 'thal_ti_tc_0', 'thal_tc_ti_0', 'thal_unconn']
        if any(path.stem.startswith(f'exp_{label}_nseed_15_') for label in selected):
            raw_root = DIR_RESULTS / 'net_newsec_ee_fade_var_seed' / path.stem
            entry['raw_source'] = str(raw_root.relative_to(DIR_REPO))
            entry['outputs'] = probe_outputs(raw_root)
        inventory['thal_local'][path.stem] = entry

    # Preserve one small saved conductance image to inspect the historical fade timing
    experiment = 'exp_thal_all_fade_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5'
    source = DIR_RESULTS / 'net_newsec_ee_fade_var_seed' / experiment / 'wmod_figs/wmod_00000_seed_1000.png'
    cached = DIR_TASK / 'evidence/simulation/supplementary_thal_all_fade_seed1000.png'
    read_path = cached if cached.is_file() else source
    size = read_path.stat().st_size
    if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
        raise RuntimeError('Conductance image read budget exceeded')
    content = read_path.read_bytes()
    if read_path == source:
        cached.write_bytes(content)
    total_bytes += len(content)
    audit.append({'path': str(source.relative_to(DIR_REPO)),
                  'snapshot': str(cached.relative_to(DIR_TASK)),
                  'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})

    # Check output availability only for the already documented main-figure sources
    main_manifest = json.loads((DIR_OUT / 'experiment_manifest.json').read_text())
    for label in ['ctx_full', 'ctx_ee_fade', 'thal_orig', 'a1_errors', 'a1_example']:
        root = DIR_REPO / main_manifest[label]['path']
        inventory['main_outputs'][label] = probe_outputs(root)

    # Persist compact evidence and the bounded remote-read audit
    (DIR_OUT / 'supplementary_data_readiness.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (DIR_OUT / 'supplementary_read_audit.json').write_text(
        json.dumps({'total_bytes': total_bytes, 'files': audit}, indent=2) + '\n')
    with (DIR_TASK / 'data/tables/supplementary_a1_control_rates.csv').open('w', newline='') as fid:
        writer = csv.DictWriter(fid, fieldnames=list(population_rows[0]))
        writer.writeheader()
        writer.writerows(population_rows)
    n_thal = len(inventory['thal_local'])
    print(f'Inventoried {len(A1_EXPERIMENTS)} A1 controls and {n_thal} local thalamic caches')
    print(f'Remote artifact payload: {total_bytes} bytes across {len(audit)} files; no pickle contents read')


if __name__ == '__main__':
    main()
