"""Export workflow weight multipliers and Ibkg corrections per iteration."""

import csv
import json
from pathlib import Path


DIR_REPO = Path(__file__).resolve().parents[2]

WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_list_1d'
RUN_ID = (
    'ibkg_adj__fullsim__var_wmult_list_1d_L2_wmult_list_ee_efb_1_5_10_'
    'nseeds_3_ibkg_-1_0.2_10_tdw_5.0_15.0_tfull_5.0_15.0'
)
WORKFLOW_DIR = DIR_REPO / 'exp_results' / 'workflows' / WORKFLOW_NAME / RUN_ID
DIR_OUT = (
    DIR_REPO / 'exp_results_local' / 'workflows' /
    WORKFLOW_NAME / RUN_ID / 'wmult_ibkg'
)

OVERWRITE = 1


def _read_json(path):
    """Read one JSON file."""
    with Path(path).open('r', encoding='utf-8') as fid:
        return json.load(fid)


def _write_json(path, payload):
    """Write one pretty JSON file."""
    path = Path(path)
    if path.exists() and not OVERWRITE:
        raise FileExistsError(f'Output already exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fid:
        json.dump(payload, fid, indent=2)
        fid.write('\n')


def _write_csv(path, rows, fieldnames):
    """Write one CSV table."""
    path = Path(path)
    if path.exists() and not OVERWRITE:
        raise FileExistsError(f'Output already exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as fid:
        writer = csv.DictWriter(fid, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _iter_iteration_jsons(workflow_dir):
    """Yield iteration metadata paths in numeric order."""
    iter_root = Path(workflow_dir) / 'iterations'
    paths = sorted(iter_root.glob('iter_*/meta/iteration.json'))
    if not paths:
        raise FileNotFoundError(f'No iteration.json files found in {iter_root}')
    return paths


def _get_wmult_label(iter_meta):
    """Return the workflow multiplier label for one iteration."""
    result = iter_meta.get('result', {})
    context = iter_meta.get('context', {})
    return result.get('wmult_variant', context.get('wmult_variant'))


def _safe_label(label):
    """Return one filesystem-safe label."""
    return str(label).replace('/', '_')


def _make_iter_payload(iter_meta):
    """Build one compact iteration export payload."""
    result = iter_meta.get('result', {})
    context = iter_meta.get('context', {})
    wmat_multipliers = result.get(
        'wmat_multipliers',
        context.get('wmat_multipliers', []),
    )
    ibkg_corrections = result.get('ibkg_corrections')
    return {
        'wmult_label': _get_wmult_label(iter_meta),
        'wmat_multipliers': [
            {
                'pre': item['pre'],
                'post': item['post'],
                'mult': item['mult'],
            }
            for item in wmat_multipliers
        ],
        'ibkg_corrections': ibkg_corrections,
    }


def _round_corr(value):
    """Round one correction value for CSV output."""
    return round(float(value), 4)


def _make_csv_rows(iter_meta, payload):
    """Build CSV rows for one iteration."""
    iteration = int(iter_meta['iteration'])
    wmult_label = payload['wmult_label']
    corrections = payload['ibkg_corrections'] or {}
    corr_cols = {
        f'ibkg_corr_{pop}': _round_corr(value)
        for pop, value in corrections.items()
    }

    # Repeat iteration-level Ibkg corrections for every multiplier row
    rows = []
    for item in payload['wmat_multipliers']:
        row = {
            'iter': iteration,
            'wmult_label': wmult_label,
            'pre': item['pre'],
            'post': item['post'],
            'wmult': item['mult'],
        }
        row.update(corr_cols)
        rows.append(row)
    return rows


def export_iteration(path_meta, dir_out):
    """Export one iteration metadata file."""
    iter_meta = _read_json(path_meta)
    payload = _make_iter_payload(iter_meta)
    iteration = int(iter_meta['iteration'])
    label = _safe_label(payload['wmult_label'])
    fpath_out = Path(dir_out) / f'{iteration}__{label}.json'
    _write_json(fpath_out, payload)
    return payload, iter_meta, fpath_out


def _get_csv_fieldnames(rows):
    """Return stable CSV column order."""
    corr_cols = sorted({
        key
        for row in rows
        for key in row
        if key.startswith('ibkg_corr_')
    })
    return ['iter', 'wmult_label', 'pre', 'post', 'wmult'] + corr_cols


def main():
    """Export configured workflow multiplier/current records."""
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    csv_rows = []

    # Store one compact JSON per iteration
    for path_meta in _iter_iteration_jsons(WORKFLOW_DIR):
        payload, iter_meta, fpath_out = export_iteration(path_meta, DIR_OUT)
        csv_rows.extend(_make_csv_rows(iter_meta, payload))
        print(f'Saved: {fpath_out}')

    # Store one joint table across all iterations
    fpath_csv = DIR_OUT / 'wmult_ibkg.csv'
    _write_csv(fpath_csv, csv_rows, _get_csv_fieldnames(csv_rows))
    print(f'Saved: {fpath_csv}')


if __name__ == '__main__':
    main()
