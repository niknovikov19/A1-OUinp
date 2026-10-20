"""Snapshot explicitly inventoried small summaries and representative saved configurations. """

import csv
import hashlib
import json
from pathlib import Path
import shutil


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_REPO = DIR_TASK.parents[1]
DIR_DATA = DIR_TASK / 'data'
DIR_INVENTORIES = DIR_DATA / 'inventories'
DIR_TABLES = DIR_DATA / 'tables'
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024


def main():
    """Read only manifest-listed JSON files, with per-file and total byte limits. """
    manifest = json.loads((DIR_INVENTORIES / 'experiment_manifest.json').read_text())
    source_log = []
    rate_rows = []
    cfg_summary = {}
    total_bytes = 0

    # Snapshot local inputs independently of the mounted result folders
    dir_inputs = DIR_DATA / 'inputs'
    dir_inputs.mkdir(exist_ok=True)
    for batch in ['net_newsec_ee_fade_var_seed', 'net_newsec_var_seed',
                  'net_newsec_ctrl_var_seed']:
        source_dir = DIR_REPO / 'exp_configs/batch_rxbkg_state1_mech1' / batch
        names = ['target_state_1.csv', 'rx_bkg_mid_sm_ctx21_thal41.csv',
                 'ibkg_mech1_verest_-70_thal_spkthr.json', 'ibkg_ctrl_1.json',
                 'mech_changes_1.json', 'target_sec_1.json']
        for name in names:
            source = source_dir / name
            if source.is_file():
                shutil.copyfile(source, dir_inputs / f'{batch}__{name}')

    # Limit remote reads to the exact small JSON files already inventoried
    for label, info in manifest.items():
        if not info['exists']:
            continue
        root = DIR_REPO / info['path']
        dir_snapshot = DIR_DATA / 'snapshots' / label
        dir_snapshot.mkdir(parents=True, exist_ok=True)
        files = [('cfg', info['files']['cfg'][0])]
        files += [('results', name) for name in info['files']['results']]
        cfg = None
        for kind, name in files:
            source = root / kind / name
            cached = dir_snapshot / name
            read_path = cached if cached.is_file() else source
            size = read_path.stat().st_size
            if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
                raise RuntimeError(f'Read budget exceeded: {source}, {size} bytes')
            content = read_path.read_bytes()
            total_bytes += len(content)
            if read_path == source:
                cached.write_bytes(content)
            source_log.append({
                'label': label,
                'path': str(source.relative_to(DIR_REPO)),
                'bytes': len(content),
                'sha256': hashlib.sha256(content).hexdigest(),
            })
            data = json.loads(content)
            if kind == 'cfg':
                cfg = data.get('simConfig', data)
                fields = ['duration', 't0_calc', 'seed_main', 'seeds', 'wmult',
                          'EEGain', 'subnet_params', 'runtime_params', 'IClamp',
                          'target_rates', 'ee_fader_on', 'conns_split',
                          'ou_ctrl_params']
                cfg_summary[label] = {key: cfg[key] for key in fields if key in cfg}
                continue
            seed = int(name.removesuffix('.json').split('_seed_')[-1])
            for pop, target in cfg['target_rates'].items():
                if pop not in data['rates']:
                    continue
                rate = data['rates'][pop]
                rate_rows.append({
                    'experiment': label,
                    'seed': seed,
                    'pop': pop,
                    'rate_hz': rate,
                    'target_hz': target,
                    'error_hz': rate - target,
                    't0_s': data['t_limits_r'][0],
                    't1_s': data['t_limits_r'][1],
                    'source_file': str(source.relative_to(DIR_REPO)),
                })

    # Save a compact audit trail and an offline population-rate table
    (DIR_INVENTORIES / 'remote_read_audit.json').write_text(
        json.dumps({'total_bytes': total_bytes, 'files': source_log}, indent=2) + '\n')
    (DIR_INVENTORIES / 'saved_cfg_summary.json').write_text(
        json.dumps(cfg_summary, indent=2) + '\n')
    with (DIR_TABLES / 'population_rates.csv').open('w') as fid:
        writer = csv.DictWriter(fid, fieldnames=list(rate_rows[0]))
        writer.writeheader()
        writer.writerows(rate_rows)
    print(f'Snapshotted {len(source_log)} remote JSON files, {total_bytes} bytes')
    print(f'Saved {len(rate_rows)} population-rate rows')


if __name__ == '__main__':
    main()
