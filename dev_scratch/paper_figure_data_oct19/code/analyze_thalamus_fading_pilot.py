"""Validate short thalamic fading runs and plot their compact rate exports. """

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_REPO = DIR_TASK.parents[1]
sys.path.insert(0, str(DIR_REPO / 'external'))
from sim_data_analyzer.xr_io import load_xr


POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']
TARGETS = {'TC': 8, 'HTC': 8, 'TI': 15, 'IRE': 15, 'TCM': 2, 'TIM': 10, 'IREM': 10}
DIR_SNAPSHOTS = DIR_TASK / 'data/snapshots/pilot_thalamus_fading'


def main():
    """Read four bounded local summaries and preserve their validation evidence. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    args = parser.parse_args()
    cache = DIR_REPO / 'exp_results_local/hpc_codex' / args.run_id
    paths = sorted(cache.glob('*/result_*.json'))
    if len(paths) != 4:
        raise ValueError(f'Expected four local result summaries, found {len(paths)}')
    DIR_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    runs = []
    phase_rows = []
    evidence = []

    # Verify population identity, protocol, coefficients, and terminal rank states
    for path in paths:
        data = json.loads(path.read_text())
        pilot = data['pilot']
        pair = pilot['fade_pair']
        seed = pilot['seed_main']
        if pair not in [['IREM', 'TI'], ['IREM', 'IRE']] or seed not in [1000, 1001]:
            raise ValueError(f'Unexpected condition or seed: {path}')
        assert pilot['duration_ms'] == 6000 and data['t_limits_r'] == [5, 6]
        assert pilot['fader_pts_ms'] == [[0, 0], [3000, 0], [5000, 1], [6000, 1]]
        assert pilot['target_rates_hz'] == TARGETS
        subnet = pilot['subnet_params']
        assert subnet['pops_active'] == POPS and subnet['conns_frozen'] == []
        assert subnet['conns_split'] == {f'{pair[0]}, {pair[1]}': 0.5}
        assert min(pilot['contact_counts'].values()) > 0
        assert len(pilot['rank_endpoints']) == 8
        for rank in pilot['rank_endpoints']:
            for name, expected in [('ee_pos', 1), ('ee_neg', 0)]:
                assert rank[name]['use_pmod'] == 1
                for key in ['shared_coefficient', 'synaptic_coefficient', 'effective_coefficient']:
                    assert abs(rank[name][key] - expected) < 1e-10
        coefficients = pilot['coefficients']
        pos = np.asarray(coefficients['ee_pos'])
        neg = np.asarray(coefficients['ee_neg'])
        assert pos.shape == neg.shape and len(pos) >= 300
        coefficient_times = np.arange(len(pos)) * pilot['coefficient_record_dt_ms']
        expected = np.interp(coefficient_times, [0, 3000, 5000, 6000], [0, 0, 1, 1])
        mask = coefficient_times > 0
        max_error = float(np.max(np.abs(pos[mask] - expected[mask])))
        max_complement_error = float(np.max(np.abs(pos[mask] + neg[mask] - 1)))
        assert max_error < 0.0002 and max_complement_error < 1e-10

        # Preserve unrounded phase rates and a checksummed local snapshot
        phase_mae = {}
        for phase, rates in pilot['phase_rates_hz'].items():
            errors = []
            for pop in POPS:
                rate = float(rates[pop])
                assert np.isfinite(rate) and rate >= 0
                if phase == 'after_fade':
                    assert rate == data['rates'][pop]
                error = rate - TARGETS[pop]
                errors.append(abs(error))
                phase_rows.append({'fade_projection': '→'.join(pair), 'seed': seed,
                                   'phase': phase, 'population': pop,
                                   't0_s': pilot['phase_windows_s'][phase][0],
                                   't1_s': pilot['phase_windows_s'][phase][1],
                                   'target_hz': TARGETS[pop], 'rate_hz': rate,
                                   'error_hz': error})
            phase_mae[phase] = float(np.mean(errors))
        dynamics = pilot['rate_dynamics']
        assert np.asarray(dynamics['rate_hz']).shape == (7, 300)
        assert np.isfinite(dynamics['rate_hz']).all()
        snapshot = DIR_SNAPSHOTS / f'{pair[0].lower()}_to_{pair[1].lower()}_seed_{seed}.json'
        payload = path.read_bytes()
        snapshot.write_bytes(payload)
        evidence.append({'source_cache': str(path.relative_to(DIR_REPO)),
                         'snapshot': str(snapshot.relative_to(DIR_TASK)),
                         'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
                         'fade_projection': '→'.join(pair), 'seed': seed,
                         'max_coefficient_error': max_error,
                         'max_complement_error': max_complement_error,
                         'initial_sample_coefficients': [float(pos[0]), float(neg[0])],
                         'contact_counts': pilot['contact_counts'],
                         'rank_endpoint_checks': 'passed on all eight ranks',
                         'phase_mean_absolute_errors_hz': phase_mae})
        runs.append(pilot)
    observed = {(run['fade_pair'][1], run['seed_main']) for run in runs}
    assert observed == {(post, seed) for post in ['TI', 'IRE'] for seed in [1000, 1001]}

    # Read only local historical caches through sim_data_analyzer for context
    historical = {}
    reference_sources = {}
    for label in ['irem_ti_0', 'irem_ire_0', 'thal_ee_1', 'thal_all_fade']:
        name = f'exp_{label}_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5.nc'
        path = DIR_REPO / 'dev_scratch/thal_frz/analysis/collected' / name
        with load_xr(path, data_type='dataset', engine='h5netcdf', load=True) as dataset:
            historical[label] = {pop: float(dataset['rate'].sel(pop=pop).mean()) for pop in POPS}
        reference_sources[label] = {'path': str(path.relative_to(DIR_REPO)),
                                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    # Plot both seeds, all modeled populations, targets, and the fade interval
    figure, axes = plt.subplots(7, 2, figsize=(12, 15), sharex=True)
    for column, post in enumerate(['TI', 'IRE']):
        for row, pop in enumerate(POPS):
            axis = axes[row, column]
            for run in sorted(runs, key=lambda item: item['seed_main']):
                if run['fade_pair'][1] != post:
                    continue
                rates = run['rate_dynamics']
                index = rates['pops'].index(pop)
                axis.plot(rates['time_s'], rates['rate_hz'][index],
                          label=f"Seed {run['seed_main']}", linewidth=1)
            axis.axhline(TARGETS[pop], color='black', linestyle='--', linewidth=0.8, label='Target')
            axis.axvspan(3, 5, color='orange', alpha=0.15)
            axis.set_ylabel(f'{pop} rate (Hz)')
            if row == 0:
                axis.set_title(f'IREM→{post} restoration; 6 s pilot')
                axis.legend(fontsize=8)
            if row == 6:
                axis.set_xlabel('Time (s); shaded interval: fading')
    figure.tight_layout()
    plots = DIR_TASK / 'plots'
    plots.mkdir(exist_ok=True)
    figure.savefig(plots / 'thalamus_fading_pilot_rates.png', dpi=150)

    # Save a second view so the initial discharge does not compress later dynamics
    for column, post in enumerate(['TI', 'IRE']):
        for row, pop in enumerate(POPS):
            axis = axes[row, column]
            values = [TARGETS[pop]]
            for run in runs:
                if run['fade_pair'][1] != post:
                    continue
                rates = run['rate_dynamics']
                index = rates['pops'].index(pop)
                values.extend(rate for time, rate in zip(rates['time_s'], rates['rate_hz'][index])
                              if time >= 1)
            margin = max((max(values) - min(values)) * 0.1, 0.5)
            axis.set_xlim(1, 6)
            axis.set_ylim(max(0, min(values) - margin), max(values) + margin)
    figure.savefig(plots / 'thalamus_fading_pilot_rates_after_1s.png', dpi=150)
    plt.close(figure)

    # Write machine-readable results separately from the incomplete production table
    path = DIR_TASK / 'data/tables/thalamus_fading_pilot_phase_rates.csv'
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(phase_rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(phase_rows)
    report = {'run_id': args.run_id, 'validation': 'saved_protocol_and_coefficients_passed',
              'scientific_convergence': 'not_established', 'runs': evidence,
              'historical_15_seed_mean_rates_hz': historical,
              'historical_sources': reference_sources,
              'historical_window_s': [7, 10], 'pilot_endpoint_window_s': [5, 6],
              'initial_coefficient_sample_note': 't=0 excluded from schedule/complement checks; shared-variable initialization transient',
              'production_table_updated': False}
    path = DIR_TASK / 'data/inventories/thalamus_fading_pilot_analysis.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
