"""One-time cfg_base.json normalization for the standalone model_nn_1 setup."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


DIRPATH_MODEL = Path(__file__).resolve().parents[1]
FPATH_CFG = DIRPATH_MODEL / 'cfg_base.json'
GUARD_KEY = 'model_nn_1_cfg_base_normalization'


def _parse_pair(pair):
    if not isinstance(pair, str) or ',' not in pair:
        raise ValueError(f'Unsupported split pair key: {pair!r}')
    return [part.strip() for part in pair.split(',', 1)]


def main():
    """Normalize cfg_base.json once and leave a backup plus guard metadata."""
    with open(FPATH_CFG, 'r') as fid:
        data = json.load(fid)

    cfg = data['simConfig']
    if cfg.get(GUARD_KEY, {}).get('split_wmat_precompensated_for_subnet_tuner'):
        raise RuntimeError(
            f'{FPATH_CFG} already has split-weight normalization metadata; '
            'refusing to run twice.'
        )

    split_cfg = cfg['subnet_params']['conns_split']
    bad_splits = {
        pair: value for pair, value in split_cfg.items()
        if not isinstance(value, (int, float)) or abs(value - 0.5) > 1e-12
    }
    if bad_splits:
        raise ValueError(
            'This one-time normalizer only supports conns_split values of 0.5: '
            f'{bad_splits}'
        )

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    fpath_backup = FPATH_CFG.with_name(f'{FPATH_CFG.name}.bak_{timestamp}')
    shutil.copy2(FPATH_CFG, fpath_backup)

    changed_pairs = []
    skipped_pairs = []
    wmat = cfg['wmat']
    for pair in split_cfg:
        pre, post = _parse_pair(pair)
        if pre in wmat and post in wmat[pre]:
            wmat[pre][post] *= 2.0
            changed_pairs.append(pair)
        else:
            skipped_pairs.append(pair)

    original_wmult = cfg.pop('wmult', None)
    original_add_pulses = cfg.get('add_pulses', None)
    cfg['add_pulses'] = 0
    cfg[GUARD_KEY] = {
        'normalized_at_utc': timestamp,
        'script': str(Path(__file__).relative_to(DIRPATH_MODEL)),
        'backup_file': fpath_backup.name,
        'removed_wmult': original_wmult,
        'original_add_pulses': original_add_pulses,
        'new_add_pulses': cfg['add_pulses'],
        'wmat_contains_original_global_wmult': True,
        'split_wmat_precompensated_for_subnet_tuner': True,
        'split_value_required': 0.5,
        'split_wmat_multiplier': 2.0,
        'changed_split_pairs': changed_pairs,
        'skipped_split_pairs': skipped_pairs,
    }

    with open(FPATH_CFG, 'w') as fid:
        json.dump(data, fid, indent=4)
        fid.write('\n')

    print(f'Backup: {fpath_backup}')
    print(f'Changed split pairs: {len(changed_pairs)}')
    print(f'Skipped split pairs: {len(skipped_pairs)}')
    if skipped_pairs:
        print('Skipped pairs missing from wmat:')
        for pair in skipped_pairs:
            print(f'  {pair}')


if __name__ == '__main__':
    main()
