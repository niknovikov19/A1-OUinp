import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


def verify_copy(input_dir, source_dir, hpc_root):
    """Verify copied artifacts against exact source files and record provenance. """
    files = []
    for path in sorted(input_dir.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(input_dir)
        source_relative = Path('jobs/index.jsonl') if relative.name == 'jobs_index.jsonl' else relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_digest = hashlib.sha256((source_dir / source_relative).read_bytes()).hexdigest()
        if digest != source_digest:
            raise ValueError(f'Copy checksum mismatch: {relative}')
        files.append({
            'local_file': relative.as_posix(),
            'hpc_file': f'{hpc_root.rstrip("/")}/{source_relative.as_posix()}',
            'bytes': path.stat().st_size,
            'sha256': digest,
        })
    return {'hpc_result_root': hpc_root, 'files': files}


def load_trials(input_dir):
    """Load compact sim_data_analyzer rate traces and saved window counts. """
    trials = []
    for path in sorted((input_dir / 'results').glob('result_*.json')):
        result = json.loads(path.read_text())
        suffix = path.stem.removeprefix('result_')
        rates = xr.load_dataarray(input_dir / 'rvec_xr' / f'rvec_{suffix}.nc')
        current = xr.load_dataarray(input_dir / 'hvec_xr' / f'hvec_{suffix}.nc')
        cfg = json.loads((input_dir / 'cfg' / f'cfg_{suffix}.json').read_text())['simConfig']
        trials.append({'id': suffix, 'result': result, 'rates': rates, 'h': current, 'cfg': cfg})
    if not trials:
        raise ValueError('No connected-step result files found')
    return trials


def validate_trial(trial):
    """Check current delivery metadata, raw traces, clamps, and count arithmetic. """
    result, rates, current, cfg = (trial[key] for key in ('result', 'rates', 'h', 'cfg'))
    pops = list(rates['pop'].values)
    times = rates.time.values
    if rates.dims != ('pop', 'time') or rates.attrs['tau_smooth_s'] != 0:
        raise ValueError('Expected unsmoothed population-rate traces')
    if rates.attrs['units'] != 'Hz' or current.attrs['units'] != 'nA':
        raise ValueError('Unexpected rate or current units')
    np.testing.assert_array_equal(current['pop'], rates['pop'])
    np.testing.assert_array_equal(current.time, rates.time)
    np.testing.assert_allclose(np.diff(times), rates.attrs['dt_bin_s'], rtol=0, atol=1e-12)
    if not np.all(np.isfinite(rates)) or not np.all(np.isfinite(current)):
        raise ValueError('Non-finite trace values')

    # Check the group expansion and the declared half-open step waveform
    pars = result['parameters']
    multipliers = cfg['step_groups'][pars['step_group']]
    active = (times >= cfg['h_step_t0'] / 1000) & (times < cfg['duration'] / 1000)
    for pop in pops:
        amp = pars['amp'] * multipliers.get(pop, 0)
        np.testing.assert_allclose(result['h_step_nA'][pop], amp, rtol=0, atol=1e-12)
        np.testing.assert_allclose(current.sel(pop=pop), amp * active, rtol=0, atol=1e-12)
        n_cells = result['window_stats']['baseline'][pop]['n_cells']
        if result['h_clamp_count_by_pop'][pop] != n_cells:
            raise ValueError(f'Incorrect clamp count: {pop}')

    # Cross-check saved spike-count means against the unsmoothed rate bins
    for window, (start, stop) in result['rate_windows_s'].items():
        mask = (times >= start) & (times < stop)
        means = rates.values[:, mask].mean(axis=1)
        for index, pop in enumerate(pops):
            stats = result['window_stats'][window][pop]
            rate = stats['n_spikes'] / (stats['n_cells'] * (stop - start))
            np.testing.assert_allclose(stats['rate_hz'], rate, rtol=0, atol=1e-10)
            np.testing.assert_allclose(means[index], rate, rtol=0, atol=1e-10)
    for pop in pops:
        stats = result['window_stats']
        split_count = stats['response_early'][pop]['n_spikes'] + stats['response_late'][pop]['n_spikes']
        if split_count != stats['response'][pop]['n_spikes']:
            raise ValueError(f'Response-window count mismatch: {pop}')


def is_zero_input(trial):
    """Identify baseline trials by their current vector, not their group name. """
    return all(value == 0 for value in trial['result']['h_step_nA'].values())


def compare_pair(trial, control):
    """Measure raw-trace reproducibility before onset and across the whole run. """
    rates = trial['rates']
    np.testing.assert_array_equal(rates['pop'], control['rates']['pop'])
    np.testing.assert_array_equal(rates.time, control['rates'].time)
    onset = rates.attrs['h_step_t0_ms'] / 1000
    diff = rates.values - control['rates'].values
    pre_diff = diff[:, rates.time.values < onset]
    return {
        'trial': trial['id'],
        'control': control['id'],
        'pre_step_identical': bool(np.all(pre_diff == 0)),
        'whole_trace_identical': bool(np.all(diff == 0)),
        'pre_step_changed_bins': int(np.sum(np.any(pre_diff != 0, axis=0))),
        'pre_step_max_abs_hz': float(np.max(np.abs(pre_diff))),
    }


def analyze_trials(trials):
    """Summarize validation, zero-input repeats, and seed/amplitude contrasts. """
    window_rows, contrasts, pair_checks, zero_checks = [], [], [], []
    baseline_by_seed = {}
    for trial in trials:
        validate_trial(trial)
        result, cfg = trial['result'], trial['cfg']
        seed = result['parameters']['seed_main']
        baseline = {key: cfg[key] for key in ('seeds', 'IClamp', 'bkg_spike_inputs', 'subnet_params', 'mech_changes')}
        if seed in baseline_by_seed and baseline != baseline_by_seed[seed]:
            raise ValueError(f'Baseline configuration differs within seed {seed}')
        baseline_by_seed[seed] = baseline
        for window, stats_by_pop in result['window_stats'].items():
            for pop, stats in stats_by_pop.items():
                window_rows.append({'trial': trial['id'], **result['parameters'],
                                    'zero_input': is_zero_input(trial),
                                    'pop': pop, 'window': window, **stats})

    # Compare every physically zero-input repetition within each seed
    zeros = [trial for trial in trials if is_zero_input(trial)]
    seeds = sorted(baseline_by_seed)
    for seed in seeds:
        seed_zeros = [trial for trial in zeros if trial['result']['parameters']['seed_main'] == seed]
        for left, right in combinations(seed_zeros, 2):
            zero_checks.append(compare_pair(left, right))

    # Match treatment controls by seed and scalar amplitude without pooling noise
    for trial in trials:
        if is_zero_input(trial):
            continue
        pars = trial['result']['parameters']
        controls = [control for control in zeros
                    if control['result']['parameters']['seed_main'] == pars['seed_main']
                    and control['result']['parameters']['amp'] == pars['amp']]
        if not controls:
            raise ValueError(f'Missing matched zero-input trial: {trial["id"]}')
        for control in controls:
            check = compare_pair(trial, control)
            pair_checks.append(check)
            for window in trial['result']['window_stats']:
                for pop, stats in trial['result']['window_stats'][window].items():
                    baseline_rate = control['result']['window_stats'][window][pop]['rate_hz']
                    contrasts.append({
                        'trial': trial['id'], 'control': control['id'], **pars,
                        'window': window, 'pop': pop,
                        'delta_rate_hz': stats['rate_hz'] - baseline_rate,
                        'pre_step_identical': check['pre_step_identical'],
                    })

    # Report matching failures without treating them as numerical predictions
    matching_ok = all(check['pre_step_identical'] for check in pair_checks)
    repeats_ok = all(check['whole_trace_identical'] for check in zero_checks)
    summary = {
        'n_trials': len(trials), 'n_zero_input_trials': len(zeros), 'seeds': seeds,
        'protocol_checks_passed': True,
        'matched_pre_step_identical': matching_ok,
        'zero_input_repeats_identical': repeats_ok,
        'matched_response_comparison_ready': matching_ok and repeats_ok,
        'matched_pairs': pair_checks, 'zero_input_repeat_pairs': zero_checks,
        'simulation_total_seconds': [trial['result']['timing']['totalTime'] for trial in trials],
        'prediction_computed': False,
    }
    return summary, pd.DataFrame(window_rows), pd.DataFrame(contrasts)


def summarize_responses(windows, contrasts):
    """Compute descriptive post-rate and drift-adjusted contrasts per seed. """
    keys = ['trial', 'seed_main', 'step_group', 'amp', 'pop', 'zero_input']
    wide = windows.pivot(index=keys, columns='window', values='rate_hz').reset_index()
    wide.columns.name = None
    wide['pre_post_hz'] = wide.response - wide.baseline
    wide['late_early_hz'] = wide.response_late - wide.response_early

    # Pool physical zero-input repetitions within each seed before using them
    controls = wide[wide.zero_input]
    control_columns = ['baseline', 'response', 'pre_post_hz', 'late_early_hz']
    seed_controls = controls.groupby(['seed_main', 'pop'])[control_columns].mean().reset_index()
    seed_controls = seed_controls.rename(columns={
        'baseline': 'control_baseline_hz', 'response': 'control_response_hz',
        'pre_post_hz': 'control_drift_hz', 'late_early_hz': 'control_late_early_hz',
    })

    # Keep the original by-amplitude comparison alongside pooled controls
    responses = wide[~wide.zero_input].merge(seed_controls, on=['seed_main', 'pop'], validate='many_to_one')
    matched = contrasts[contrasts.window == 'response']
    matched = matched.groupby(['trial', 'pop'])['delta_rate_hz'].mean().reset_index()
    matched = matched.rename(columns={'delta_rate_hz': 'matched_post_hz'})
    responses = responses.merge(matched, on=['trial', 'pop'], validate='one_to_one')
    responses['pooled_post_hz'] = responses.response - responses.control_response_hz
    responses['pre_offset_hz'] = responses.baseline - responses.control_baseline_hz
    responses['drift_adjusted_hz'] = responses.pre_post_hz - responses.control_drift_hz

    # Report variation across seed-level estimates, not smoothed time samples
    metrics = ['matched_post_hz', 'pooled_post_hz', 'drift_adjusted_hz',
               'pre_offset_hz', 'pre_post_hz', 'late_early_hz']
    summary = responses.groupby(['step_group', 'amp', 'pop'])[metrics].agg(['mean', 'std', 'count'])
    summary.columns = [f'{metric}_{stat}' for metric, stat in summary.columns]
    return wide, seed_controls, responses, summary.reset_index()


def central_slopes(responses):
    """Calculate exploratory symmetric plus/minus slopes without fitting a gain. """
    rows = []
    metrics = ['matched_post_hz', 'pooled_post_hz', 'drift_adjusted_hz']
    for (seed, group, pop), frame in responses.groupby(['seed_main', 'step_group', 'pop']):
        amps = set(frame.amp)
        for amp in sorted(value for value in amps if value > 0 and -value in amps):
            plus = frame[frame.amp == amp].iloc[0]
            minus = frame[frame.amp == -amp].iloc[0]
            row = {'seed_main': seed, 'step_group': group, 'pop': pop, 'amp_abs_nA': amp}
            for metric in metrics:
                row[f'{metric}_slope_hz_per_nA'] = (plus[metric] - minus[metric]) / (2 * amp)
            rows.append(row)
    return pd.DataFrame(rows)


def add_q_reference(responses, trials, qpath):
    """Add the declared open-loop Qh reference without substituting it for feedback. """
    qmat = xr.load_dataarray(qpath)
    pops = list(trials[0]['rates']['pop'].values)
    qmat = qmat.sel(pop_h=pops, pop_post=pops)
    if qmat.attrs['units'] != 'Hz/nA' or not np.all(np.isfinite(qmat)):
        raise ValueError('Expected a finite Q matrix in Hz/nA')
    predictions = {}
    for trial in trials:
        current = np.asarray([trial['result']['h_step_nA'][pop] for pop in pops])
        delta = qmat.values.T @ current
        predictions[trial['id']] = dict(zip(pops, delta))
    responses = responses.copy()
    responses['q_direct_hz'] = [predictions[row.trial][row.pop] for row in responses.itertuples()]
    provenance = {
        'q_path': str(qpath), 'q_sha256': hashlib.sha256(qpath.read_bytes()).hexdigest(),
        'population_order': pops, 'formula': 'Q_saved.T @ h',
        'interpretation': 'Open-loop reference only; not the connected J-Q prediction',
        'feedback_prediction_computed': False,
    }
    return responses, provenance


def audit_j_inputs(paths, pops):
    """Record finite-entry checks without selecting or repairing a J candidate. """
    records = []
    for path in paths:
        matrix = xr.load_dataarray(path).sel(pop_pre=pops, pop_post=pops)
        missing = [{'pre': pops[i], 'post': pops[j]}
                   for i, j in np.argwhere(~np.isfinite(matrix.values))]
        records.append({
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'missing_entries': missing, 'finite_l2_matrix': not missing,
            'selected_for_prediction': False,
        })
    return records


def plot_responses(responses, pops, output_file):
    """Show all seed estimates and seed SD for three descriptive response contrasts. """
    groups = list(responses.step_group.unique())
    metrics = [('matched_post_hz', 'By-amplitude control'),
               ('pooled_post_hz', 'Seed-pooled controls'),
               ('drift_adjusted_hz', 'Drift-adjusted pre/post')]
    fig, axes = plt.subplots(len(groups), len(metrics), figsize=(15, 4 * len(groups)),
                             sharey='row', squeeze=False)
    positions = np.arange(len(pops))
    for row, group in enumerate(groups):
        data = responses[responses.step_group == group]
        amps = sorted(data.amp.unique())
        for col, (metric, title) in enumerate(metrics):
            axis = axes[row, col]
            for index, amp in enumerate(amps):
                selected = data[data.amp == amp]
                summary = selected.groupby('pop')[metric].agg(['mean', 'std']).reindex(pops)
                offset = (index - (len(amps) - 1) / 2) * 0.25
                color = f'C{index}'
                axis.errorbar(positions + offset, summary['mean'], yerr=summary['std'],
                              fmt='o', capsize=3, color=color, label=f'h = {amp:g} nA')
                for seed in sorted(selected.seed_main.unique()):
                    values = selected[selected.seed_main == seed].set_index('pop').reindex(pops)
                    axis.scatter(positions + offset, values[metric], color=color, alpha=0.5, s=15)
                if 'q_direct_hz' in selected:
                    reference = selected.groupby('pop').q_direct_hz.mean().reindex(pops)
                    axis.scatter(positions + offset, reference, marker='x', color='0.4', s=40,
                                 label='Qh, no feedback' if index == 0 else None)
            axis.axhline(0, color='0.7', linewidth=1)
            axis.set_xticks(positions, pops)
            axis.set_title(f'{group} input: {title}')
            axis.grid(False)
        axes[row, 0].set_ylabel('Rate change (Hz)')
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Descriptive pilot contrasts: means ± seed SD; dots are individual seeds')
    fig.tight_layout()
    fig.savefig(output_file, dpi=150)
    plt.close(fig)


def plot_trial_overview(trials, output_file):
    """Plot all saved rate traces with display-only smoothing and timing markers. """
    pops = list(trials[0]['rates']['pop'].values)
    conditions = sorted({(trial['result']['parameters']['step_group'], trial['result']['parameters']['amp'])
                         for trial in trials if not is_zero_input(trial)})
    conditions = [None] + conditions
    seeds = sorted({trial['result']['parameters']['seed_main'] for trial in trials})
    fig, axes = plt.subplots(len(pops), len(conditions), figsize=(4 * len(conditions), 2.2 * len(pops)),
                             sharex=True, sharey='row', squeeze=False)
    for col, condition in enumerate(conditions):
        for trial in trials:
            pars = trial['result']['parameters']
            if condition is None and not is_zero_input(trial):
                continue
            if condition is not None and (pars['step_group'], pars['amp']) != condition:
                continue
            n_smooth = max(1, round(0.5 / trial['rates'].attrs['dt_bin_s']))
            smoothed = trial['rates'].rolling(time=n_smooth, center=True, min_periods=1).mean()
            smoothed = smoothed.sel(time=slice(10, None))
            color = f'C{seeds.index(pars["seed_main"])}'
            for row, pop in enumerate(pops):
                axis = axes[row, col]
                axis.plot(smoothed.time, smoothed.sel(pop=pop), color=color, alpha=0.7,
                          label=f"Seed {pars['seed_main']}")
        for row in range(len(pops)):
            axis = axes[row, col]
            axis.axvline(trials[0]['cfg']['h_step_t0'] / 1000, color='0.4', linestyle='--')
            start, stop = trials[0]['result']['rate_windows_s']['response']
            axis.axvspan(start, stop, color='0.5', alpha=0.08)
            axis.grid(False)
        axes[0, col].set_title('Zero input: all repetitions' if condition is None
                               else f'{condition[0]}, {condition[1]:g} nA')
        axes[-1, col].set_xlabel('Time (s)')
    for row, pop in enumerate(pops):
        axes[row, 0].set_ylabel(f'{pop} rate (Hz)')
    axes[0, min(1, len(conditions) - 1)].legend(fontsize=8)
    fig.suptitle('Connected L2 pilot: 0.5-s display smoothing; shaded response window')
    fig.tight_layout()
    fig.savefig(output_file, dpi=150)
    plt.close(fig)


def plot_zero_inputs(trials, output_file):
    """Plot smoothed zero-input repetitions to expose failed seed matching. """
    zeros = [trial for trial in trials if is_zero_input(trial)]
    seeds = sorted({trial['result']['parameters']['seed_main'] for trial in zeros})
    pops = list(trials[0]['rates']['pop'].values)
    start = trials[0]['result']['rate_windows_s']['baseline'][0]
    fig, axes = plt.subplots(len(pops), len(seeds), figsize=(6 * len(seeds), 2 * len(pops)),
                             sharex=True, sharey='row', squeeze=False)
    for col, seed in enumerate(seeds):
        for trial in zeros:
            pars = trial['result']['parameters']
            if pars['seed_main'] != seed:
                continue
            n_smooth = max(1, round(0.5 / trial['rates'].attrs['dt_bin_s']))
            smoothed = trial['rates'].rolling(time=n_smooth, center=True, min_periods=1).mean()
            smoothed = smoothed.sel(time=slice(start, None))
            for row, pop in enumerate(pops):
                label = f"{pars['step_group']}, amp coordinate {pars['amp']:g}"
                axes[row, col].plot(smoothed.time, smoothed.sel(pop=pop), label=label)
                axes[row, col].grid(False)
        axes[0, col].set_title(f'Seed {seed}: applied h = 0')
        axes[-1, col].set_xlabel('Time (s)')
    for row, pop in enumerate(pops):
        axes[row, 0].set_ylabel(f'{pop} rate (Hz)')
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Zero-input reproducibility check; 0.5-s smoothing for display only')
    fig.tight_layout()
    fig.savefig(output_file, dpi=150)
    plt.close(fig)


def main():
    """Write local validation and descriptive analysis without modifying simulations. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--verify-source', type=Path)
    parser.add_argument('--hpc-root')
    parser.add_argument('--qmat', type=Path)
    parser.add_argument('--audit-jmat', action='append', type=Path, default=[])
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Check the copy once; later runs need only the local input directory
    if args.verify_source is not None:
        if not args.hpc_root:
            parser.error('--hpc-root is required with --verify-source')
        manifest = verify_copy(args.input_dir, args.verify_source, args.hpc_root)
        (args.output_dir / 'input_manifest.json').write_text(json.dumps(manifest, indent=2))

    # Save diagnostics and descriptive contrasts, even when matching fails
    trials = load_trials(args.input_dir)
    summary, windows, contrasts = analyze_trials(trials)
    (args.output_dir / 'validation.json').write_text(json.dumps(summary, indent=2))
    windows.to_csv(args.output_dir / 'window_rates.csv', index=False)
    contrasts.to_csv(args.output_dir / 'matched_contrasts.csv', index=False)

    # Retain multiple descriptive estimands while exact seed matching is deferred
    wide, controls, responses, response_summary = summarize_responses(windows, contrasts)
    if args.qmat is not None:
        responses, provenance = add_q_reference(responses, trials, args.qmat)
        (args.output_dir / 'q_reference.json').write_text(json.dumps(provenance, indent=2))
    wide.to_csv(args.output_dir / 'trial_window_summary.csv', index=False)
    controls.to_csv(args.output_dir / 'seed_control_summary.csv', index=False)
    responses.to_csv(args.output_dir / 'response_estimates.csv', index=False)
    response_summary.to_csv(args.output_dir / 'response_summary.csv', index=False)
    central_slopes(responses).to_csv(args.output_dir / 'central_slopes.csv', index=False)

    # Audit J without selecting a candidate or filling missing entries
    pops = list(trials[0]['rates']['pop'].values)
    if args.audit_jmat:
        audit = audit_j_inputs(args.audit_jmat, pops)
        (args.output_dir / 'j_audit.json').write_text(json.dumps(audit, indent=2))

    # Smooth only the diagnostic figures and leave the axes grids disabled
    plot_responses(responses, pops, args.output_dir / 'static_response_contrasts.png')
    plot_trial_overview(trials, args.output_dir / 'rate_overview.png')
    plot_zero_inputs(trials, args.output_dir / 'zero_input_repeats.png')
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in ('matched_pairs', 'zero_input_repeat_pairs', 'simulation_total_seconds')}, indent=2))


if __name__ == '__main__':
    main()
