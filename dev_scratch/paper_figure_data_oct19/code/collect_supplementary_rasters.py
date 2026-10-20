"""Copy one saved raster per selected supplementary condition with provenance. """

import csv
import hashlib
import json
from pathlib import Path
import struct


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_REPO = DIR_TASK.parents[1]
DIR_OUT = DIR_TASK / 'evidence/rasters'
FILE_RASTER = 'raster_00000_seed_1000.png'
FILE_CFG = 'cfg_00000_seed_1000.json'
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024

# Keep names readable while separating different protocol durations
CONDITIONS = [
    ('ctx_surr', 'cortex_all_surrogate', 'S1', 'All cortical connections replaced by surrogates'),
    ('ctx_full', 'cortex_no_fading', 'S1', 'Naive recurrent cortex'),
    ('ctx_ee_surr', 'cortex_ee_surrogate', 'S1', 'Cortical E-E connections replaced by surrogates'),
    ('ctx_ee_fade', 'cortex_ee_faded', 'S1;S6', 'Cortical E-E connections faded to recurrence'),
    ('thal_orig', 'thalamus_uncorrected_220s', 'S2', 'Long recurrent reference without second-stage correction'),
    ('thal_own', 'thalamus_own_correction_220s', 'S2', 'Long run with realization-specific feedback correction'),
    ('thal_med', 'thalamus_median_correction_220s', 'S2', 'Long run with fixed median correction'),
    ('thal_surr', 'thalamus_all_surrogate_10s', 'S2;S3', 'All thalamic connections replaced by surrogates'),
    ('thal_ee_1', 'thalamus_recurrent_10s', 'S3', 'Short uncorrected recurrent reference'),
    ('thal_all_fade', 'thalamus_all_faded_10s', 'S3;S6', 'All 49 requested thalamic population pairs faded to recurrence'),
    ('thal_ti_tc_0', 'thalamus_i_to_e_frozen_10s', 'S3', 'TI/TIM to TC/HTC/TCM inputs replaced by surrogates'),
    ('thal_ti_tc_fade', 'thalamus_i_to_e_faded_10s', 'S3', 'TI/TIM to TC/HTC/TCM inputs faded to recurrence'),
    ('thal_tc_ti_0', 'thalamus_e_to_i_frozen_10s', 'S3', 'TC/HTC/TCM to TI/TIM inputs replaced by surrogates'),
    ('thal_tc_ti_fade', 'thalamus_e_to_i_faded_10s', 'S3', 'TC/HTC/TCM to TI/TIM inputs faded to recurrence'),
    ('a1_no_fade_no_corr', 'a1_no_fading_no_correction_15s', 'S4', 'Historical A1: no fading, no median correction'),
    ('a1_no_fade_corr', 'a1_no_fading_with_correction_15s', 'S4', 'Historical A1: no fading, with median correction'),
    ('a1_fade_no_corr', 'a1_fading_no_correction_15s', 'S4', 'Historical A1: E-E fading, no median correction'),
    ('a1_fade_corr', 'a1_fading_with_correction_15s', 'S4;S6', 'Historical A1: E-E fading, with median correction'),
    ('a1_ee_surr_no_corr', 'a1_ee_surrogate_no_correction_15s', 'S4', 'Historical A1: static E-E surrogate, no median correction'),
    ('a1_ee_surr_corr', 'a1_ee_surrogate_with_correction_15s', 'S4', 'Historical A1: static E-E surrogate, with median correction'),
    ('a1_example', 'a1_paper_example_20s', 'S5;S6', 'Exact three-seed illustrative FIG_A1 cohort, E-E fading and median correction'),
]


def save_manifest(rows):
    """Preserve the source mapping after each copied image. """
    with (DIR_OUT / 'manifest.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Collect selected PNGs without opening any raw simulation data. """
    inventories = DIR_TASK / 'data/inventories'
    main_sources = json.loads((inventories / 'experiment_manifest.json').read_text())
    extra = json.loads((inventories / 'supplementary_data_readiness.json').read_text())
    sources = {key: item['path'] for key, item in main_sources.items()}
    cfgs = {key: DIR_TASK / 'data/snapshots' / key / FILE_CFG for key in sources}

    # Reuse local metadata for historical controls and short thalamic protocols
    for key, item in extra['a1_controls'].items():
        sources[key] = item['path']
        cfgs[key] = DIR_TASK / 'data/snapshots/supplementary' / key / FILE_CFG
    for name, item in extra['thal_local'].items():
        if 'raw_source' in item:
            key = name.split('_nseed')[0].removeprefix('exp_')
            sources[key] = item['raw_source']
            cfgs[key] = DIR_REPO / item['cfg']

    # Trust a cached image only when its recorded source and checksum match
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    previous = {}
    manifest = DIR_OUT / 'manifest.csv'
    if manifest.exists():
        with manifest.open() as stream:
            previous = {row['filename']: row for row in csv.DictReader(stream)}
    rows = []
    bytes_read = 0
    for alias, name, items, condition in CONDITIONS:
        source = Path(sources[alias]) / 'rasters' / FILE_RASTER
        filename = name + '.png'
        destination = DIR_OUT / filename
        cfg = json.loads(cfgs[alias].read_text())['simConfig']
        raster = cfg['analysis']['plotRaster']
        row = {
            'filename': filename, 'alias': alias, 'supplementary_items': items,
            'condition': condition, 'seed': 1000,
            'duration_s': cfg['duration'] / 1000,
            'summary_start_s': cfg['t0_calc'] / 1000,
            'summary_end_s': cfg['duration'] / 1000,
            'configured_raster_time_range_ms': json.dumps(raster.get('timeRange')),
            'source_path': str(source),
            'local_cfg_path': str(cfgs[alias].relative_to(DIR_REPO)),
            'status': 'missing', 'bytes': '', 'sha256': '', 'width_px': '', 'height_px': '',
        }
        if not (DIR_REPO / source).is_file():
            rows.append(row)
            save_manifest(rows)
            continue

        # Read at most one bounded PNG from each remote experiment
        size = (DIR_REPO / source).stat().st_size
        cached = previous.get(filename, {})
        if destination.exists():
            data = destination.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            if cached.get('sha256') != checksum or cached.get('source_path') != str(source):
                raise RuntimeError(f'Unverified local image: {destination}')
            if len(data) != size:
                raise RuntimeError(f'Source size changed: {source}')
        else:
            if size > MAX_FILE_BYTES or bytes_read + size > MAX_TOTAL_BYTES:
                raise RuntimeError(f'Raster read budget exceeded: {source}')
            data = (DIR_REPO / source).read_bytes()
            bytes_read += len(data)
            checksum = hashlib.sha256(data).hexdigest()
            if len(data) != size or data[:8] != b'\x89PNG\r\n\x1a\n':
                raise RuntimeError(f'Invalid or changed PNG: {source}')
            destination.write_bytes(data)
        width, height = struct.unpack('>II', data[16:24])
        row.update(status='copied', bytes=len(data), sha256=checksum,
                   width_px=width, height_px=height)
        rows.append(row)
        save_manifest(rows)
        print(f'{filename}: {len(data):,} bytes', flush=True)

    # Record this run separately from the earlier supplementary JSON read audit
    audit = {
        'remote_png_bytes_read_this_run': bytes_read,
        'copied_images': sum(row['status'] == 'copied' for row in rows),
        'missing_images': [row['filename'] for row in rows if row['status'] == 'missing'],
        'total_local_png_bytes': sum(row['bytes'] or 0 for row in rows),
        'seed': 1000,
        'limits': {'max_file_bytes': MAX_FILE_BYTES, 'max_total_bytes': MAX_TOTAL_BYTES},
        'note': 'Checksums describe copied bytes; cached reruns check source presence/size only.',
    }
    (DIR_OUT / 'copy_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
