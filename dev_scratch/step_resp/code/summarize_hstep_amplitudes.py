import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


DIR_DATA = Path(__file__).resolve().parents[1] / 'data/l2_hstep_pilot2'
METRICS = {
    'drift_adjusted_hz': 'Step-run before/after change minus control before/after change',
    'matched_post_hz': 'Post-step rate minus control rate over the same time',
}


def plot_amplitudes(observed, predictions, pops, metric, output_file):
    """Compare individual-seed signed responses with the fixed linear predictor. """
    groups = sorted(observed.step_group.unique())
    seeds = sorted(observed.seed_main.unique())
    fig = plt.figure(figsize=(10, 11.5), constrained_layout=True)
    layout = fig.add_gridspec(len(pops) + 1, len(groups), height_ratios=[2] * len(pops) + [0.65])
    axes = np.empty((len(pops), len(groups)), dtype=object)
    for row in range(len(pops)):
        for col in range(len(groups)):
            axes[row, col] = fig.add_subplot(layout[row, col])
    for col, group in enumerate(groups):
        for row, pop in enumerate(pops):
            axis = axes[row, col]
            data = observed[(observed.step_group == group) & (observed['pop'] == pop)]
            predicted = predictions[(predictions.step_group == group) & (predictions['pop'] == pop)]
            predicted = predicted.sort_values('amp')
            axis.plot(predicted.amp, predicted.predicted_hz, color='0.2', linestyle='--')
            for index, seed in enumerate(seeds):
                selected = data[data.seed_main == seed].sort_values('amp')
                axis.scatter(selected.amp, selected[metric], color=f'C{index}', alpha=0.7, s=30)
            axis.axhline(0, color='0.8', linewidth=0.8)
            axis.axvline(0, color='0.8', linewidth=0.8)
            axis.set_ylabel(f'{pop}\nRate change (Hz)')
            axis.grid(False)
            axis.margins(x=0.12, y=0.15)
            if row == 0:
                axis.set_title(f'Current into {group}')
            if row == len(pops) - 1:
                axis.set_xlabel('Current amplitude (nA)')

    # Identify actual measurements separately from the predicted straight line
    handles = [Line2D([], [], color=f'C{index}', marker='o', linestyle='none', label=f'Seed {seed}')
               for index, seed in enumerate(seeds)]
    handles.append(Line2D([], [], color='0.2', linestyle='--', label='J–Q prediction'))
    legend_axis = fig.add_subplot(layout[-1, :])
    legend_axis.set_axis_off()
    legend_axis.legend(handles=handles, fontsize=9, loc='center', ncol=3, frameon=False)
    fig.suptitle(METRICS[metric], fontsize=11)
    fig.savefig(output_file, dpi=150)
    plt.close(fig)


def half_amplitude_checks(observed):
    """Compare each measured half-amplitude response with half its full-amplitude response. """
    rows = []
    for (seed, group, pop), frame in observed.groupby(['seed_main', 'step_group', 'pop']):
        values = frame.set_index('amp')
        for amp in sorted(values.index):
            if 2 * amp not in values.index:
                continue
            for metric in METRICS:
                small, large = float(values.loc[amp, metric]), float(values.loc[2 * amp, metric])
                rows.append({'seed_main': seed, 'step_group': group, 'pop': pop,
                             'response_definition': metric, 'small_amp_nA': amp, 'large_amp_nA': 2 * amp,
                             'small_change_hz': small, 'large_change_hz': large,
                             'half_full_change_hz': large / 2, 'half_minus_half_full_hz': small - large / 2})
    return pd.DataFrame(rows)


def main():
    """Summarize existing signed responses without fitting or new simulations. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=DIR_DATA)
    args = parser.parse_args()
    analysis_dir = args.data_dir / 'analysis'
    output_dir = analysis_dir / 'jq/amplitude_summary'
    output_dir.mkdir(parents=True, exist_ok=True)
    observed = pd.read_csv(analysis_dir / 'response_estimates.csv')
    observed = observed[~observed.zero_input]
    manifest = json.loads((analysis_dir / 'jq/manifest.json').read_text())
    predictions = pd.read_csv(analysis_dir / 'jq/conditional_predictions.csv')
    predictions = predictions[predictions.model == manifest['primary']]
    if predictions.duplicated(['step_group', 'amp', 'pop']).any():
        raise ValueError('Duplicate primary predictions')
    pops = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']

    # Retain both response definitions and report means and descriptive seed SD
    rows, symmetry = [], []
    for metric in METRICS:
        summary = observed.groupby(['step_group', 'amp', 'pop'])[metric].agg(['mean', 'std', 'count']).reset_index()
        summary = summary.merge(predictions[['step_group', 'amp', 'pop', 'predicted_hz']],
                                on=['step_group', 'amp', 'pop'], validate='one_to_one')
        summary['response_definition'] = metric
        rows.append(summary)
        for (seed, group, pop), data in observed.groupby(['seed_main', 'step_group', 'pop']):
            values = data.set_index('amp')[metric]
            for amp in sorted(value for value in values.index if value > 0):
                negative, positive = float(values.loc[-amp]), float(values.loc[amp])
                symmetry.append({'seed_main': seed, 'step_group': group, 'pop': pop,
                                 'response_definition': metric, 'amp_abs_nA': amp,
                                 'symmetric_change_hz': (positive - negative) / 2,
                                 'central_slope_hz_per_nA': (positive - negative) / (2 * amp),
                                 'sign_asymmetry_hz': (positive + negative) / 2})
        plot_amplitudes(observed, predictions, pops, metric, output_dir / f'{metric}.png')
    pd.concat(rows, ignore_index=True).to_csv(output_dir / 'response_summary.csv', index=False)
    pd.DataFrame(symmetry).to_csv(output_dir / 'signed_response_components.csv', index=False)
    scaling = half_amplitude_checks(observed)
    if not scaling.empty:
        scaling.to_csv(output_dir / 'half_amplitude_checks.csv', index=False)
        keys = ['step_group', 'pop', 'response_definition', 'small_amp_nA', 'large_amp_nA']
        summary = scaling.groupby(keys)['half_minus_half_full_hz'].agg(['mean', 'std', 'count'])
        summary.to_csv(output_dir / 'half_amplitude_summary.csv')
    if len(observed) != len(predictions) * observed.seed_main.nunique():
        raise ValueError('Incomplete measured/predicted condition grid')
    if not np.all(np.isfinite(pd.concat(rows).predicted_hz)):
        raise ValueError('Non-finite primary prediction')
    print(output_dir)


if __name__ == '__main__':
    main()
