import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from analyze_hstep import is_zero_input, load_trials, validate_trial


DIR_DATA = Path(__file__).resolve().parents[1] / 'data/l2_hstep_pilot2'


def plot_condition(trials, predictions, colors, output_file, smooth_win, start):
    """Overlay seed traces and their baseline-shifted static predictions. """
    first = trials[0]
    pars = first['result']['parameters']
    pops = first['cfg']['subnet_params']['pops_active']
    onset = first['cfg']['h_step_t0'] / 1000
    stop = first['cfg']['duration'] / 1000
    if not start < onset < stop:
        raise ValueError('Display interval must include time before and after the step')

    # Reserve compact rows for the actual input waveform and shared legend
    fig = plt.figure(figsize=(11, 12), constrained_layout=True)
    layout = fig.add_gridspec(len(pops) + 2, 1, height_ratios=[0.55] + [2] * len(pops) + [0.45])
    input_axis = fig.add_subplot(layout[0])
    axes = [fig.add_subplot(layout[index + 1], sharex=input_axis) for index in range(len(pops))]
    current = first['h'].sel(time=slice(start, None))
    for pop in first['result']['step_pops']:
        input_axis.step(current.time, current.sel(pop=pop), where='mid', label=pop)
    input_axis.set_ylabel('Input (nA)')
    input_axis.margins(y=0.25)
    input_axis.legend(loc='upper right', fontsize=8, frameon=False)

    # Keep raw window means for baselines and smooth only the displayed traces
    levels = []
    for trial in trials:
        result = trial['result']
        seed = result['parameters']['seed_main']
        np.testing.assert_array_equal(trial['rates']['pop'], first['rates']['pop'])
        np.testing.assert_allclose(trial['h'], first['h'], rtol=0, atol=1e-12)
        if trial['cfg']['h_step_t0'] / 1000 != onset or trial['cfg']['duration'] / 1000 != stop:
            raise ValueError('Step timing differs between seeds')
        n_smooth = max(1, round(smooth_win / trial['rates'].attrs['dt_bin_s']))
        smoothed = trial['rates'].rolling(time=n_smooth, center=True, min_periods=1).mean()
        smoothed = smoothed.sel(time=slice(start, None))
        for axis, pop in zip(axes, pops):
            baseline = result['window_stats']['baseline'][pop]['rate_hz']
            delta = float(predictions.loc[pop, 'predicted_hz'])
            predicted = baseline + delta
            if not np.isfinite(predicted):
                raise ValueError(f'Non-finite prediction for {pop}')
            axis.plot(smoothed.time, smoothed.sel(pop=pop), color=colors[seed], alpha=0.6)
            axis.hlines(predicted, onset, stop, color=colors[seed], linestyle='--', linewidth=1.7)
            axis.set_ylabel(f'{pop}\nRate (Hz)')
            axis.margins(y=0.08)
            levels.append({'trial': trial['id'], 'seed_main': seed, 'step_group': pars['step_group'],
                           'amp': pars['amp'], 'pop': pop, 'baseline_hz': baseline,
                           'predicted_change_hz': delta, 'predicted_rate_hz': predicted})

    # Align the onset marker across the input and independently scaled rate panels
    for axis in [input_axis] + axes:
        axis.axvline(onset, color='0.4', linestyle=':', linewidth=1)
        axis.set_xlim(start, stop)
        axis.grid(False)
        axis.tick_params(labelbottom=False)
    axes[-1].tick_params(labelbottom=True)
    axes[-1].set_xlabel('Time (s)')
    handles = [Line2D([], [], color=color, label=f'Seed {seed}') for seed, color in colors.items()]
    handles += [Line2D([], [], color='0.3', alpha=0.6, label='Simulated rate'),
                Line2D([], [], color='0.3', linestyle='--', label='Predicted steady rate')]
    legend_axis = fig.add_subplot(layout[-1])
    legend_axis.set_axis_off()
    legend_axis.legend(handles=handles, loc='center', ncol=len(handles), frameon=False, fontsize=9)
    fig.suptitle(f"Current into {pars['step_group']}: {pars['amp']:g} nA; {smooth_win:g} s rate smoothing")
    fig.savefig(output_file, dpi=150)
    plt.close(fig)
    return levels


def main():
    """Plot saved connected-step rates against the existing pooled J–Q predictions. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=DIR_DATA)
    parser.add_argument('--smooth-win', type=float, default=0.5)
    parser.add_argument('--start', type=float, default=10)
    args = parser.parse_args()
    if args.smooth_win <= 0:
        raise ValueError('Smoothing window must be positive')

    # Select the same primary predictions used in the static comparison figure
    jq_dir = args.data_dir / 'analysis/jq'
    manifest = json.loads((jq_dir / 'manifest.json').read_text())
    predictions = pd.read_csv(jq_dir / 'conditional_predictions.csv')
    predictions = predictions[predictions.model == manifest['primary']]
    if predictions.empty or predictions.duplicated(['step_group', 'amp', 'pop']).any():
        raise ValueError('Missing or duplicate primary predictions')
    trials = [trial for trial in load_trials(args.data_dir / 'input') if not is_zero_input(trial)]
    seeds = sorted({trial['result']['parameters']['seed_main'] for trial in trials})
    colors = {seed: f'C{index % 10}' for index, seed in enumerate(seeds)}
    conditions = {}
    for trial in trials:
        validate_trial(trial)
        pars = trial['result']['parameters']
        conditions.setdefault((pars['step_group'], pars['amp']), []).append(trial)

    # Save the exact baseline and predicted height for every displayed seed and population
    output_dir = jq_dir / 'rate_dynamics'
    output_dir.mkdir(parents=True, exist_ok=True)
    levels = []
    for (group, amp), selected in sorted(conditions.items()):
        selected_seeds = [trial['result']['parameters']['seed_main'] for trial in selected]
        if sorted(selected_seeds) != seeds:
            raise ValueError(f'Missing or repeated seeds for {group}, {amp:g}')
        predicted = predictions[(predictions.step_group == group) & (predictions.amp == amp)].set_index('pop')
        output_file = output_dir / f'group_{group}_amp_{amp:g}.png'
        levels.extend(plot_condition(selected, predicted, colors, output_file, args.smooth_win, args.start))
        print(output_file)
    pd.DataFrame(levels).to_csv(output_dir / 'prediction_levels.csv', index=False)


if __name__ == '__main__':
    main()
