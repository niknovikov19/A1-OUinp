"""Check parameter-only thalamic pilots using compact local HPC archives. """

import argparse
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
from sim_data_analyzer.batch_xr import load_job_json
from sim_data_analyzer.xr_io import load_xr


POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']
SEEDS = [1000, 1001]


def main():
    """Validate saved configurations and compare endpoint rates with local references. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('post', choices=['TI', 'IRE'])
    args = parser.parse_args()
    cache = DIR_REPO / 'exp_results_local/hpc_codex' / args.run_id / 'compact'
    manifest = json.loads((cache / 'archive_manifest.json').read_text())
    assert manifest['run_id'] == args.run_id
    assert len(manifest['files']) == 5
    entries = {item['path']: item for item in manifest['files']}

    # Check every compact payload against the helper's verified archive manifest
    for name, entry in entries.items():
        payload = (cache / name).read_bytes()
        assert len(payload) == entry['size_bytes']
        assert hashlib.sha256(payload).hexdigest() == entry['sha256']
    children = [json.loads(line) for line in (cache / 'jobs/index.jsonl').read_text().splitlines()]
    assert len(children) == 2
    assert sorted(child['parameters']['seed_main'] for child in children) == SEEDS
    assert all(set(child['parameters']) == {'seed_main'} for child in children)

    # Load archived reference rates through sim_data_analyzer without remote reads
    sources = json.loads((DIR_TASK / 'data/inventories/thalamus_fading_table_sources.json').read_text())
    labels = [f'IREM→{args.post} frozen', 'Fully recurrent', 'Faded from all-surrogate']
    historical = {}
    historical_seeds = {}
    historical_setup = {}
    for label in labels:
        source = sources['conditions'][label]
        path = DIR_REPO / source['local_rate_cache']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['cache_sha256']
        with load_xr(path, data_type='dataset', engine='h5netcdf', load=True) as dataset:
            historical[label] = {pop: float(dataset['rate'].sel(pop=pop).mean()) for pop in POPS}
            historical_seeds[label] = {
                seed: {pop: float(dataset['rate'].sel(seed_main=seed, pop=pop)) for pop in POPS}
                for seed in SEEDS
            }
        reference_cfg = json.loads((DIR_REPO / source['local_cfg']).read_text())['simConfig']
        historical_setup[label] = {
            'population_order': reference_cfg['subnet_params']['pops_active'],
            'matches_pilot_population_order': reference_cfg['subnet_params']['pops_active'] == POPS,
            'exc_background_seeds_at_seed_1000': {
                pop: reference_cfg['bkg_spike_inputs'][pop]['exc']['seed'] for pop in POPS
            },
        }
    source = sources['conditions'][labels[0]]
    reference = json.loads((DIR_REPO / source['local_cfg']).read_text())['simConfig']
    targets = sources['target_rates_hz']
    rates_by_seed = {}
    evidence = []
    snapshot = DIR_TASK / 'data/snapshots/parameter_only_pilot' / f'irem_to_{args.post.lower()}'
    snapshot.mkdir(parents=True, exist_ok=True)

    # Check the saved scientific settings and preserve the existing compact outputs
    for index, seed in enumerate(SEEDS):
        postfix = f'{index:05d}_seed_{seed}'
        cfg_name = f'cfg/cfg_{postfix}.json'
        result_name = f'results/result_{postfix}.json'
        cfg = json.loads((cache / cfg_name).read_text())['simConfig']
        result = load_job_json({'job_id': index}, cache / 'results')
        assert cfg['seed_main'] == seed
        assert cfg['duration'] == 10000 and cfg['t0_calc'] == 7000
        expected_seeds = dict(reference['seeds'], stim=seed, conn=seed * 2)
        assert cfg['seeds'] == expected_seeds
        subnet = cfg['subnet_params']
        assert subnet['pops_active'] == POPS and subnet['conns_frozen'] == []
        assert subnet['conns_split'] == {f'IREM, {args.post}': 0.5}
        assert subnet['global_seed'] == seed * 3
        for key in ['IClamp', 'mech_changes', 'wmult', 'EEGain', 'EIGain', 'IEGain', 'IIGain',
                    'connRandomSecFromList', 'connWeightSecByLength', 'addSubConn']:
            assert cfg[key] == reference[key], key
        for pop in POPS:
            assert cfg['target_rates'][pop] == targets[pop]
            for kind in ['exc', 'inh']:
                background = dict(cfg['bkg_spike_inputs'][pop][kind])
                background['seed'] -= seed - 1000
                assert background == reference['bkg_spike_inputs'][pop][kind]
        assert result['t_limits_r'] == [7, 10]
        assert 'pilot' not in result
        rates = {pop: float(result['rates'][pop]) for pop in POPS}
        assert all(math.isfinite(rate) and rate >= 0 for rate in rates.values())
        rates_by_seed[seed] = rates
        for name in [cfg_name, result_name]:
            destination = snapshot / Path(name).name
            destination.write_bytes((cache / name).read_bytes())
        evidence.append({'seed': seed, 'rates_hz': rates,
                         'mean_absolute_error_hz': fmean(abs(rates[pop] - targets[pop]) for pop in POPS),
                         'timing': result['timing'],
                         'cfg_sha256': entries[cfg_name]['sha256'],
                         'result_sha256': entries[result_name]['sha256']})

    # Keep two-seed pilot statistics separate from the production paper table
    rows = []
    for pop in POPS:
        values = [rates_by_seed[seed][pop] for seed in SEEDS]
        row = {'Population': pop, 'Target (Hz)': f'{targets[pop]:.2f}',
               'Seed 1000 (Hz)': f'{values[0]:.2f}', 'Seed 1001 (Hz)': f'{values[1]:.2f}',
               'Pilot mean (Hz)': f'{fmean(values):.2f}', 'Pilot SD (Hz)': f'{stdev(values):.2f}'}
        row.update({f'{label}, 15-seed mean (Hz)': f'{historical[label][pop]:.2f}' for label in labels})
        rows.append(row)
    table = DIR_TASK / f'data/tables/thalamus_param_pilot_{args.post.lower()}_rates.csv'
    with table.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    report = {'run_id': args.run_id, 'git_commit': manifest['git_commit'],
              'projection': ['IREM', args.post], 'saved_cfg_checks': 'passed',
              'window_s': [7, 10], 'seeds': SEEDS, 'runs': evidence,
              'historical_15_seed_mean_rates_hz': historical,
              'historical_same_numbered_seed_rates_hz': historical_seeds,
              'historical_setup': historical_setup,
              'reference_seed_note': 'The same numeric seed does not ensure identical realized networks across static and split construction.',
              'archive_manifest': manifest, 'production_table_updated': False,
              'coefficient_time_course_verified': False,
              'limitation': 'Unchanged experiment saves endpoint rates; no numerical coefficient trace or population-rate time course is exported.'}
    path = DIR_TASK / f'data/inventories/thalamus_param_pilot_{args.post.lower()}_analysis.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(table.read_text(encoding='utf-8-sig'))
    print(f'Validated two saved cfgs and results; report: {path.relative_to(DIR_REPO)}')


if __name__ == '__main__':
    main()
