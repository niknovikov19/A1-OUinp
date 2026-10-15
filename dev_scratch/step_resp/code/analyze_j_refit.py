import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from refit_rate_io import DIR_DATA, PARAM_NAMES, richards_derivative


DIR_STEP = Path(__file__).resolve().parents[1]


def audit_history(input_dir, pops, targets):
    """Separate absent fits from unstable historical derivative evaluation. """
    rows = []
    for label, tau in (('l2', '0.3'), ('ctx', '0.2')):
        root = input_dir / 'historical' / label
        matrix = xr.load_dataarray(root / f'wmat_tau_{tau}.nc')
        coeffs = json.loads((root / f'richards_coeffs_tau_{tau}.json').read_text())
        for pre in pops:
            for post in pops:
                old = float(matrix.sel(pop_pre=pre, pop_post=post))
                entry = coeffs.get(pre, {}).get(post)
                stable = None
                if entry is not None and entry['nu'] > 0:
                    params = [entry[key] for key in PARAM_NAMES]
                    stable = float(richards_derivative(targets[pre], *params))
                reason = 'finite_stored_entry' if np.isfinite(old) else 'coefficient_absent'
                if not np.isfinite(old) and entry is not None:
                    reason = 'derivative_numerics' if stable is not None and np.isfinite(stable) else 'invalid_coefficients'
                rows.append({'candidate': label, 'pop_pre': pre, 'pop_post': post,
                             'stored_gain': old, 'coefficient_present': entry is not None,
                             'stable_old_gain': stable, 'classification': reason})
    return pd.DataFrame(rows)


def solve_response(jmat, qmat, h):
    """Align input-first matrices by labels and solve the static feedback equation. """
    pops = list(h)
    j = jmat.sel(pop_pre=pops, pop_post=pops).transpose('pop_post', 'pop_pre').values
    q = qmat.sel(pop_h=pops, pop_post=pops).transpose('pop_post', 'pop_h').values
    if not np.all(np.isfinite(j)) or not np.all(np.isfinite(q)):
        raise ValueError('Prediction requires finite labelled J and Q; no filling allowed')
    system = np.eye(len(pops)) - j
    direct = q @ np.asarray([h[pop] for pop in pops])
    predicted = np.linalg.solve(system, direct)
    if not np.all(np.isfinite(predicted)):
        raise ValueError('Non-finite feedback prediction')
    return dict(zip(pops, predicted)), dict(zip(pops, direct)), float(np.linalg.cond(system))


def zero_missing_gains(jmat):
    """Make an explicit provisional zero-filled copy without changing finite gains. """
    matrix = jmat.transpose('pop_pre', 'pop_post').copy(deep=True)
    missing = ~np.isfinite(matrix.values)
    entries = [{'pop_pre': str(matrix.pop_pre.values[i]), 'pop_post': str(matrix.pop_post.values[k])}
               for i, k in np.argwhere(missing)]
    matrix.values[missing] = 0
    matrix.attrs['missing_gain_policy'] = 'User-requested provisional zeros, not measured structural zeros'
    matrix.attrs['zero_filled_entries'] = json.dumps(entries)
    return matrix, entries


def collect_conditions(hstep_dir):
    """Read actual step vectors without fitting to any connected response. """
    conditions = {}
    for path in sorted((hstep_dir / 'input' / 'results').glob('result_*.json')):
        result = json.loads(path.read_text())
        if all(value == 0 for value in result['h_step_nA'].values()):
            continue
        pars = result['parameters']
        key = (pars['step_group'], pars['amp'])
        if key in conditions and conditions[key] != result['h_step_nA']:
            raise ValueError('Step vectors differ across seeds of the same condition')
        conditions[key] = result['h_step_nA']
    return conditions


def build_predictions(paths, qpath, conditions):
    """Compute predictions from finite matrices supplied explicitly by the caller. """
    qmat = xr.load_dataarray(qpath)
    rows, audit = [], []
    for path in paths:
        matrix = xr.load_dataarray(path)
        label = f'{path.parent.name}/{path.stem}'
        finite = bool(np.all(np.isfinite(matrix)))
        audit.append({'label': label, 'path': str(path), 'finite': finite,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        if not finite:
            continue
        for (group, amp), h in conditions.items():
            predicted, direct, condition = solve_response(matrix, qmat, h)
            for pop in h:
                rows.append({'model': label, 'step_group': group, 'amp': amp, 'pop': pop,
                             'predicted_hz': predicted[pop], 'q_direct_hz': direct[pop],
                             'condition_number': condition})
    return pd.DataFrame(rows), audit


def plot_prediction_comparison(predictions, observed, primary, pops, path):
    """Separate rates measured in simulations from predictions using saved J and Q. """
    groups = list(observed.step_group.unique())
    amps = sorted(observed.amp.unique())
    # Keep panels, legend, and caption in adjacent rows with explicit heights
    fig = plt.figure(figsize=(max(12, 4.5 * len(amps)), 4 * len(groups) + 1.1), constrained_layout=True)
    heights = [4] * len(groups) + [0.65, 0.18]
    layout = fig.add_gridspec(len(heights), len(amps), height_ratios=heights)
    axes = np.empty((len(groups), len(amps)), dtype=object)
    for row in range(len(groups)):
        for col in range(len(amps)):
            axes[row, col] = fig.add_subplot(layout[row, col])
    positions = np.arange(len(pops))
    measurement_labels = {
        'matched_post_hz': 'MEASURED: rates after step\n(step run minus control run)',
        'drift_adjusted_hz': 'MEASURED: before/after rate changes\n(step run minus controls)',
    }
    prediction_labels = {
        'jq': 'PREDICTED: J + Q\n(includes circuit feedback)',
        'q': 'PREDICTED: Q only\n(ignores circuit feedback)',
    }
    for row, group in enumerate(groups):
        for col, amp in enumerate(amps):
            axis = axes[row, col]
            data = observed[(observed.step_group == group) & (observed.amp == amp)]
            for index, metric in enumerate(('matched_post_hz', 'drift_adjusted_hz')):
                summary = data.groupby('pop')[metric].agg(['mean', 'std']).reindex(pops)
                axis.errorbar(positions - 0.24 + index * 0.16, summary['mean'], yerr=summary['std'],
                              fmt='o', capsize=3, label=measurement_labels[metric])
            variants = predictions[(predictions.step_group == group) & (predictions.amp == amp)]
            selected = variants[variants.model == primary].set_index('pop').reindex(pops)
            axis.scatter(positions + 0.08, selected.predicted_hz, marker='*', color='C2', s=90,
                         label=prediction_labels['jq'])
            axis.scatter(positions + 0.24, selected.q_direct_hz, marker='x', color='0.3',
                         label=prediction_labels['q'])
            axis.axhline(0, color='0.7', linewidth=1)
            axis.set_xticks(positions, pops)
            axis.set_title(f'Current into {group}: {amp:g} nA')
            axis.set_ylabel('Rate change (Hz)')
            axis.grid(False)
    # Put the complete symbol guide below the panels without covering measurements
    handles, labels = axes[0, 0].get_legend_handles_labels()
    legend_items = dict(zip(labels, handles))
    legend_order = list(measurement_labels.values()) + list(prediction_labels.values())
    handles = [legend_items[label] for label in legend_order]
    legend_axis = fig.add_subplot(layout[-2, :])
    legend_axis.set_axis_off()
    legend_axis.legend(handles, legend_order, loc='center', ncol=2, fontsize=9,
                       frameon=False, labelspacing=0.45, borderaxespad=0)
    fig.suptitle('Measured rate changes versus predictions')
    caption_axis = fig.add_subplot(layout[-1, :])
    caption_axis.set_axis_off()
    n_seeds = observed.seed_main.nunique()
    caption = f'Circles: average across {n_seeds} seeds; bars show seed-to-seed spread (SD), not confidence intervals.'
    caption_axis.text(0.5, 0.5, caption,
                      ha='center', va='center', fontsize=9)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    """Audit the refit and illustrate prediction sensitivity without declaring J final. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=DIR_DATA)
    parser.add_argument('--hstep-dir', type=Path, default=DIR_STEP / 'data' / 'l2_hstep_pilot1')
    parser.add_argument('--output-dir', type=Path,
                        help='Keep comparisons for a new pilot separate from historical outputs')
    parser.add_argument('--qmat', type=Path, default=DIR_STEP / 'data' / 'l2_sym_slow_pilot/processed/tau_0.2/qmat.nc')
    parser.add_argument('--zero-missing', action='store_true',
                        help='Explicitly replace missing primary J gains with provisional zeros in a separate file')
    args = parser.parse_args()
    output = args.output_dir if args.output_dir is not None else args.data_dir / 'analysis'
    output.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((args.data_dir / 'input/cfg.json').read_text())['simConfig']
    pops = list(cfg['subnet_params']['pops_active'])
    history = audit_history(args.data_dir / 'input', pops, cfg['target_rates'])
    history.to_csv(output / 'historical_audit.csv', index=False)

    # Report weak curves and bound dependence separately from numerical completeness
    primary_dir = args.data_dir / 'processed/tau_0.2_bins_64'
    primary = f'{primary_dir.name}/jmat_pooled'
    diagnostics = pd.read_csv(primary_dir / 'fit_diagnostics.csv')
    diagnostics['low_explained_variance'] = diagnostics.r_squared < 0.1
    diagnostics.to_csv(output / 'primary_diagnostics.csv', index=False)
    paths = sorted((args.data_dir / 'processed').glob('tau_*_bins_64/jmat_*.nc'))
    zero_filled_entries = []
    if args.zero_missing:
        source = primary_dir / 'jmat_pooled.nc'
        matrix, zero_filled_entries = zero_missing_gains(xr.load_dataarray(source))
        matrix.attrs['source_path'] = str(source)
        matrix.attrs['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        filled_path = output / 'jmat_pooled_zero_filled.nc'
        matrix.to_netcdf(filled_path)
        paths.append(filled_path)
        primary = f'{filled_path.parent.name}/{filled_path.stem}'

    # Use the existing pilot inputs and Q without any additional fitting
    conditions = collect_conditions(args.hstep_dir)
    predictions, audit = build_predictions(paths, args.qmat, conditions)
    predictions.to_csv(output / 'conditional_predictions.csv', index=False)
    sensitivity = predictions.groupby(['step_group', 'amp', 'pop']).predicted_hz.agg(['min', 'max']).reset_index()
    sensitivity.to_csv(output / 'prediction_sensitivity.csv', index=False)

    # Compare conditionally to existing measurements without optimizing any fit choice
    observed = pd.read_csv(args.hstep_dir / 'analysis/response_estimates.csv')
    selected = predictions[predictions.model == primary]
    if selected.empty:
        raise ValueError('Primary refit is incomplete; no primary prediction was manufactured')
    selected_for_merge = selected.rename(columns={'q_direct_hz': 'q_only_prediction_hz'})
    comparison = observed.merge(selected_for_merge, on=['step_group', 'amp', 'pop'], validate='many_to_one')
    comparison['error_specified_hz'] = comparison.matched_post_hz - comparison.predicted_hz
    comparison['error_adjusted_hz'] = comparison.drift_adjusted_hz - comparison.predicted_hz
    comparison.to_csv(output / 'pilot_comparison.csv', index=False)
    error_rows = []
    for (seed, group, amp), frame in comparison.groupby(['seed_main', 'step_group', 'amp']):
        for metric in ('matched_post_hz', 'drift_adjusted_hz'):
            for model, column in (('JQ', 'predicted_hz'), ('Q_only', 'q_only_prediction_hz')):
                error = frame[metric] - frame[column]
                error_rows.append({'seed_main': seed, 'step_group': group, 'amp': amp,
                                   'response_definition': metric, 'model': model,
                                   'vector_rmse_hz': float(np.sqrt(np.mean(error ** 2)))})
    pd.DataFrame(error_rows).to_csv(output / 'comparison_errors.csv', index=False)
    plot_prediction_comparison(predictions, observed, primary, pops, output / 'prediction_vs_pilot.png')

    # Record that finite family-conditioned predictions are not a validated J estimate
    manifest = {
        'primary': primary, 'status': 'Provisional family-conditioned sensitivity analysis; not a final identified J',
        'prediction_computed': True,
        'missing_gain_policy': 'Explicit provisional zeros' if args.zero_missing else 'Reject missing gains',
        'zero_filled_entries': zero_filled_entries,
        'hstep_dir': str(args.hstep_dir),
        'observed_sha256': hashlib.sha256((args.hstep_dir / 'analysis/response_estimates.csv').read_bytes()).hexdigest(),
        'j_inputs': audit, 'q_path': str(args.qmat),
        'q_sha256': hashlib.sha256(args.qmat.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'historical_missing': history[~np.isfinite(history.stored_gain)].astype(object).where(pd.notna(history), None).to_dict('records'),
        'low_explained_variance_pairs': diagnostics[diagnostics.low_explained_variance][['pop_pre', 'pop_post']].to_dict('records'),
        'sensitivity_range_is_confidence_interval': False,
        'simulation_baseline_changed': False,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(selected[['step_group', 'amp', 'pop', 'predicted_hz', 'q_direct_hz']].round(6).to_string(index=False))


if __name__ == '__main__':
    main()
