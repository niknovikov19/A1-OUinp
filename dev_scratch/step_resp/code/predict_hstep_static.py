import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from analyze_j_refit import build_predictions, collect_conditions, plot_prediction_comparison


DIR_STEP = Path(__file__).resolve().parents[1]
DIR_REPO = Path(__file__).resolve().parents[3]


def checked_matrix_copy(source, destination, checksum):
    """Copy a frozen matrix only if its bytes match the prior prediction manifest. """
    source = Path(source)
    if not source.is_absolute():
        source = DIR_REPO / source
    if hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
        raise ValueError(f'Frozen matrix differs from the reference manifest: {source}')
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != checksum:
            raise ValueError(f'Existing matrix differs; preserved without replacement: {destination}')
    else:
        shutil.copyfile(source, destination)
    return source


def predict_dataset(data_dir, reference_dir):
    """Evaluate the unchanged prior predictor on new conditions without any refitting. """
    output = data_dir / 'analysis/jq'
    output.mkdir(parents=True, exist_ok=True)
    reference = json.loads((reference_dir / 'manifest.json').read_text())
    candidates = [item for item in reference['j_inputs'] if item['label'] == reference['primary']]
    if len(candidates) != 1:
        raise ValueError('Reference manifest does not identify one primary J')

    # Preserve byte-identical copies of the already selected J and Q
    jpath, qpath = output / 'jmat_fixed.nc', output / 'qmat_fixed.nc'
    j_source = checked_matrix_copy(candidates[0]['path'], jpath, candidates[0]['sha256'])
    q_source = checked_matrix_copy(reference['q_path'], qpath, reference['q_sha256'])
    conditions = collect_conditions(data_dir)
    predictions, audit = build_predictions([jpath], qpath, conditions)
    if predictions.empty or len(audit) != 1 or not audit[0]['finite']:
        raise ValueError('Fixed predictor must be finite and cover nonzero conditions')
    primary = audit[0]['label']
    predictions.to_csv(output / 'conditional_predictions.csv', index=False)

    # Keep observations and predictions separate until the labelled comparison
    observations_path = data_dir / 'analysis/response_estimates.csv'
    observed = pd.read_csv(observations_path)
    renamed = predictions.rename(columns={'q_direct_hz': 'q_only_prediction_hz'})
    comparison = observed.merge(renamed, on=['step_group', 'amp', 'pop'], validate='many_to_one')
    if len(comparison) != len(observed):
        raise ValueError('Some observed conditions lack predictions')
    comparison['error_specified_hz'] = comparison.matched_post_hz - comparison.predicted_hz
    comparison['error_adjusted_hz'] = comparison.drift_adjusted_hz - comparison.predicted_hz
    comparison.to_csv(output / 'pilot_comparison.csv', index=False)
    rows = []
    for (seed, group, amp), frame in comparison.groupby(['seed_main', 'step_group', 'amp']):
        for metric in ('matched_post_hz', 'drift_adjusted_hz'):
            for model, column in (('JQ', 'predicted_hz'), ('Q_only', 'q_only_prediction_hz')):
                error = frame[metric] - frame[column]
                rows.append({'seed_main': seed, 'step_group': group, 'amp': amp,
                             'response_definition': metric, 'model': model,
                             'vector_rmse_hz': float(np.sqrt(np.mean(error ** 2)))})
    pd.DataFrame(rows).to_csv(output / 'comparison_errors.csv', index=False)

    # Record the frozen reference and draw the new measured-versus-predicted comparison
    manifest = {
        'primary': primary, 'status': 'Fixed prior J-Q prediction; no fitting to new observations',
        'prediction_computed': True, 'reference_manifest': str(reference_dir / 'manifest.json'),
        'j_inputs': audit, 'q_path': str(qpath), 'q_sha256': reference['q_sha256'],
        'j_source': str(j_source), 'q_source': str(q_source),
        'zero_filled_entries': reference['zero_filled_entries'],
        'missing_gain_policy': reference['missing_gain_policy'],
        'observed_sha256': hashlib.sha256(observations_path.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'simulation_baseline_changed': False,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    cfg_path = next((data_dir / 'input/cfg').glob('cfg_*.json'))
    cfg = json.loads(cfg_path.read_text())['simConfig']
    pops = cfg['subnet_params']['pops_active']
    plot_prediction_comparison(predictions, observed, primary, pops, output / 'prediction_vs_pilot.png')
    return manifest


def main():
    """Run the local fixed-matrix static predictor for one completed step dataset. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--reference-dir', type=Path, default=DIR_STEP / 'data/l2_hstep_pilot2/analysis/jq')
    args = parser.parse_args()
    print(json.dumps(predict_dataset(args.data_dir, args.reference_dir), indent=2))


if __name__ == '__main__':
    main()
