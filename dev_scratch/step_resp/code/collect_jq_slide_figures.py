import argparse
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import xarray as xr

from analyze_h_io import collect_h_rate_data, smooth_rates
from analyze_hstep import load_trials, validate_trial


DIR_STEP = Path(__file__).resolve().parents[1]
DIR_DATA = DIR_STEP / 'data'
DIR_Q = DIR_DATA / 'l2_current_sweep_5seeds_pm100pa_t40s'
DIR_J = DIR_DATA / 'l2_rate_sweep_j_5seeds'
DIR_STEPS = DIR_DATA / 'l2_connected_steps_5seeds_15_30pa_100s'
POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']


def seed_handles(seeds):
    """Build a shared seed-color legend for five-seed overlays. """
    return [Line2D([], [], color=f'C{index}', label=f'Seed {seed}')
            for index, seed in enumerate(seeds)]


def plot_sweep(rates, stimulus, onset, title, input_label, output):
    """Plot the actual sweep input and population outputs with display-only smoothing. """
    seeds = [int(seed) for seed in rates.seed.values]
    fig = plt.figure(figsize=(14, 9), constrained_layout=True)
    layout = fig.add_gridspec(7, 1, height_ratios=[0.8] + [1] * 5 + [0.3])
    input_axis = fig.add_subplot(layout[0])
    axes = [fig.add_subplot(layout[index + 1], sharex=input_axis) for index in range(5)]

    # Display each seed without averaging across trials or changing the data cache
    for index, seed in enumerate(seeds):
        input_axis.plot(stimulus.time, stimulus.sel(seed=seed), color=f'C{index}', alpha=0.6)
        for axis, pop in zip(axes, POPS):
            trace = rates.sel(seed=seed, pop=pop)
            axis.plot(trace.time, trace, color=f'C{index}', alpha=0.6, linewidth=1)
    input_axis.set_ylabel(input_label)
    for axis, pop in zip(axes, POPS):
        axis.set_ylabel(f'{pop}\nRate (Hz)')
    for axis in [input_axis] + axes:
        axis.axvline(onset, color='0.4', linestyle=':', linewidth=1)
        axis.grid(False)
        axis.set_xlim(float(rates.time.min()), float(rates.time.max()))
        axis.tick_params(labelbottom=False)
        axis.margins(y=0.08)
    axes[-1].tick_params(labelbottom=True)
    axes[-1].set_xlabel('Time (s)')
    legend_axis = fig.add_subplot(layout[-1])
    legend_axis.set_axis_off()
    legend_axis.legend(handles=seed_handles(seeds), loc='center', ncol=5, frameon=False)
    fig.suptitle(title)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_step_prediction(output):
    """Show PV2 rates and fixed static endpoints for all four IT2 current steps. """
    jq_dir = DIR_STEPS / 'analysis/jq'
    manifest = json.loads((jq_dir / 'manifest.json').read_text())
    predictions = pd.read_csv(jq_dir / 'conditional_predictions.csv')
    selected = predictions[(predictions.model == manifest['primary'])
                           & (predictions.step_group == 'IT2') & (predictions['pop'] == 'PV2')]
    if len(selected) != 4 or selected.amp.duplicated().any():
        raise ValueError('Expected four primary IT2-to-PV2 predictions')
    predictions = selected.set_index('amp')
    trials = [trial for trial in load_trials(DIR_STEPS / 'input')
              if trial['result']['parameters']['step_group'] == 'IT2']
    seeds = sorted({trial['result']['parameters']['seed_main'] for trial in trials})
    amps = sorted(predictions.index)
    if seeds != list(range(1000, 1005)) or amps != [-0.03, -0.015, 0.015, 0.03]:
        raise ValueError('Unexpected seed/amplitude grid')

    # Reserve an aligned current strip for every condition and a shared legend
    fig = plt.figure(figsize=(15, 9), constrained_layout=True)
    layout = fig.add_gridspec(5, 2, height_ratios=[0.35, 2, 0.35, 2, 0.35])
    levels = []
    for index, amp in enumerate(amps):
        row, column = 2 * (index // 2), index % 2
        input_axis = fig.add_subplot(layout[row, column])
        axis = fig.add_subplot(layout[row + 1, column], sharex=input_axis)
        condition = [trial for trial in trials if trial['result']['parameters']['amp'] == amp]
        actual_seeds = sorted(trial['result']['parameters']['seed_main'] for trial in condition)
        if actual_seeds != seeds:
            raise ValueError(f'Missing or repeated seeds for {amp:g} nA')
        first = condition[0]
        onset, stop = first['cfg']['h_step_t0'] / 1000, first['cfg']['duration'] / 1000
        current = first['h'].sel(pop='IT2', time=slice(10, None))
        input_axis.step(current.time, current, color='0.2', where='mid')
        input_axis.set_title(f'IT2 input: {amp:+g} nA')
        input_axis.set_ylabel('h (nA)')
        input_axis.tick_params(labelbottom=False)

        # Place each static endpoint at its own raw pre-step baseline plus pooled prediction
        delta = float(predictions.loc[amp, 'predicted_hz'])
        for trial in condition:
            validate_trial(trial)
            np.testing.assert_allclose(trial['h'], first['h'], rtol=0, atol=1e-12)
            seed = trial['result']['parameters']['seed_main']
            smoothed, _ = smooth_rates(trial['rates'].sel(pop='PV2'), 0.5)
            smoothed = smoothed.sel(time=slice(10, None))
            baseline = trial['result']['window_stats']['baseline']['PV2']['rate_hz']
            color = f'C{seeds.index(seed)}'
            axis.plot(smoothed.time, smoothed, color=color, alpha=0.6, linewidth=1)
            axis.hlines(baseline + delta, onset, stop, color=color, linestyle='--', linewidth=1.7)
            levels.append({'trial': trial['id'], 'seed_main': seed, 'amp_nA': amp,
                           'baseline_hz': baseline, 'predicted_change_hz': delta,
                           'predicted_rate_hz': baseline + delta})
        for panel in [input_axis, axis]:
            panel.axvline(onset, color='0.4', linestyle=':', linewidth=1)
            panel.set_xlim(10, stop)
            panel.grid(False)
            panel.margins(y=0.08)
        axis.set_ylabel('PV2 rate (Hz)')
        axis.set_xlabel('Time (s)')
    handles = seed_handles(seeds)
    handles += [Line2D([], [], color='0.3', alpha=0.6, label='Simulated rate'),
                Line2D([], [], color='0.3', linestyle='--', label='Baseline + J–Q prediction')]
    legend_axis = fig.add_subplot(layout[-1, :])
    legend_axis.set_axis_off()
    legend_axis.legend(handles=handles, loc='center', ncol=4, frameon=False)
    fig.suptitle('Connected L2: IT2 current steps → PV2; 0.5-s display smoothing')
    fig.savefig(output, dpi=200)
    plt.close(fig)
    return pd.DataFrame(levels)


def main():
    """Collect five slide figures from local selected datasets without any refitting. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=DIR_DATA / 'slide_assets/jq_prediction')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Plot current-identification traces using the existing validated local pair loader
    current = collect_h_rate_data(DIR_Q)
    rates, _ = smooth_rates(current.rate, 0.2)
    reference = current.h.sel(seed=1000, pop='IT2')
    for seed in current.seed.values:
        for pop in POPS:
            np.testing.assert_allclose(current.h.sel(seed=seed, pop=pop), reference, rtol=0, atol=1e-12)
    plot_sweep(rates, current.h.sel(pop='IT2'), 5,
               'Open-loop current identification: ±0.1 nA, T = 40 s; 0.2-s display smoothing',
               'h (nA)', args.output_dir / '01_h_to_l2_triangle_timecourse.png')

    # Select only the IT2 presynaptic-sweep condition from the existing sim_data_analyzer cache
    rates = xr.load_dataarray(DIR_J / 'input/rates.nc').sel(pop_pre='IT2', time=slice(2, None))
    rates, _ = smooth_rates(rates, 0.2)
    plot_sweep(rates.sel(pop=POPS), rates.sel(pop='IT2frz'), 5,
               'Open-loop IT2-rate identification → L2; 0.2-s additional display smoothing',
               'IT2 input\nrate (Hz)', args.output_dir / '02_it2_to_l2_triangle_timecourse.png')

    # Copy the selected saved fit figures unchanged rather than rerunning either fitter
    copies = {
        '03_h_to_pv2_curve_fit.png': DIR_Q / 'processed/tau_0.2/fits/PV2.png',
        '04_it2_to_pv2_curve_fit.png': DIR_J / 'processed/tau_0.2_bins_64/fits/IT2_PV2.png',
    }
    for name, source in copies.items():
        destination = args.output_dir / name
        shutil.copyfile(source, destination)
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(destination.read_bytes()).digest()
    levels = plot_step_prediction(args.output_dir / '05_it2_to_pv2_step_prediction.png')
    levels.to_csv(args.output_dir / 'step_prediction_levels.csv', index=False)
    print(args.output_dir)
    print(f'Five figures; {len(levels)} seed-specific step prediction levels; no fits changed')


if __name__ == '__main__':
    main()
