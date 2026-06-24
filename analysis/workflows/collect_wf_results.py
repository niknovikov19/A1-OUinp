"""Collect workflow-stage xarray outputs across iterations."""

import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr


DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import _write_batch_netcdf, iter_batch_jobs
from sim_data_analyzer.xr_io import load_xr


WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_list_1d'
RUN_ID = (
    'ibkg_adj__fullsim__var_wmult_list_1d_L2_wmult_list_ee_efb_2_'
    'wvars_base_ee2_efb2_ee2_efb2_nseeds_1_ibkg_-0.5_0.1_10_'
    'tdw_5.0_15.0_tfull_5.0_15.0'
)
WORKFLOW_DIR = DIR_REPO / 'exp_results' / 'workflows' / WORKFLOW_NAME / RUN_ID
DIR_OUT_ROOT = DIR_REPO / 'exp_results_local'

STAGE_NAME = 'fullsim'
TARGETS = ('rates', 'lfp')

LAZY = 1
OVERWRITE = 1
SKIP_MISSING = 0
LOAD_OUTPUT = 0
SOURCE_OPEN_KWARGS = {
    'engine': 'scipy',
}

TARGET_CONFIGS = {
    'rates': {
        'data_subdir': 'rvec_xr',
        'fname_templ': 'rvec_{job:05d}_*.nc',
        'out_name': 'rvec_xr.nc',
    },
    'lfp': {
        'data_subdir': 'lfp_xr',
        'fname_templ': 'lfp_{job:05d}_*.nc',
        'out_name': 'lfp_xr.nc',
    },
}

CHUNKS = {
    'iteration': 1,
    'seed_main': 1,
}


def _read_json(path):
    """Read one JSON file."""
    with Path(path).open('r', encoding='utf-8') as fid:
        return json.load(fid)


def _get_run_info(workflow_dir):
    """Read stable workflow identifiers."""
    params = _read_json(Path(workflow_dir) / 'meta' / 'resolved_params.json')
    return {
        'workflow_name': params['workflow_name'],
        'run_id': Path(workflow_dir).name,
    }


def _iter_iteration_dirs(workflow_dir):
    """Yield existing iteration folders in numeric order."""
    iter_root = Path(workflow_dir) / 'iterations'
    iter_dirs = sorted(iter_root.glob('iter_*'))
    return [path for path in iter_dirs if path.is_dir()]


def _load_iteration_meta(iter_dir):
    """Load one iteration metadata file."""
    meta = _read_json(iter_dir / 'meta' / 'iteration.json')
    context = meta.get('context', {})
    stage_hashes = meta.get('stage_spec_hashes', {})
    return {
        'iteration': int(meta['iteration']),
        'wmult_id': context.get('wmult_id', np.nan),
        'wmult_variant': context.get('wmult_variant', ''),
        'stage_spec_hash': stage_hashes.get(STAGE_NAME, ''),
    }


def _load_stage_spec(iter_dir, stage_name):
    """Load one stage spec."""
    return _read_json(iter_dir / stage_name / 'meta' / 'stage_spec.json')


def _load_stage_jobs(iter_dir, stage_name):
    """Load completed job metadata records for one stage."""
    job_dir = iter_dir / stage_name / 'job_meta'
    records = []
    for path in sorted(job_dir.glob('*.json')):
        record = _read_json(path)
        if record.get('status') == 'complete':
            records.append(record)
    return records


def _get_batch_dims(stage_spec, job_records):
    """Return batch dimensions in stage-spec order."""
    dims = list(stage_spec.get('batch_params', {}))
    if dims:
        return dims

    # Fall back to first job metadata when the stage spec is sparse
    if not job_records:
        return []
    return list(job_records[0].get('batch_params', {}))


def _coord_values_from_jobs(job_records, batch_dims):
    """Collect sorted coordinate values for all batch dimensions."""
    coord_values = {}
    for dim in batch_dims:
        values = sorted({record['batch_params'][dim] for record in job_records})
        coord_values[dim] = values
    return coord_values


def _coord_index(values):
    """Map coordinate values to integer positions."""
    return {value: idx for idx, value in enumerate(values)}


def _build_job_idx_xr(workflow_dir, stage_name):
    """Build nested workflow and batch job index."""
    workflow_dir = Path(workflow_dir)
    iter_dirs = _iter_iteration_dirs(workflow_dir)
    if not iter_dirs:
        raise FileNotFoundError(f'No iter_* folders found in {workflow_dir}')

    iter_meta = [_load_iteration_meta(path) for path in iter_dirs]
    stage_specs = [_load_stage_spec(path, stage_name) for path in iter_dirs]
    job_sets = [_load_stage_jobs(path, stage_name) for path in iter_dirs]
    if not any(job_sets):
        raise FileNotFoundError(f'No completed {stage_name!r} jobs found')

    batch_dims = _get_batch_dims(stage_specs[0], job_sets[0])
    all_jobs = [record for records in job_sets for record in records]
    coord_values = _coord_values_from_jobs(all_jobs, batch_dims)

    # Allocate one workflow layer outside the stage batch dimensions
    dims = ['iteration'] + batch_dims
    coords = {
        'iteration': [meta['iteration'] for meta in iter_meta],
    }
    coords.update(coord_values)
    shape = tuple(len(coords[dim]) for dim in dims)
    job_idx = np.full(shape, np.nan, dtype=float)

    iter_index = _coord_index(coords['iteration'])
    coord_indexes = {
        dim: _coord_index(values)
        for dim, values in coord_values.items()
    }

    # Fill the nested grid with stage-local job ids
    for iter_dir, meta, records in zip(iter_dirs, iter_meta, job_sets):
        iter_pos = iter_index[meta['iteration']]
        for record in records:
            idx = [iter_pos]
            for dim in batch_dims:
                value = record['batch_params'][dim]
                idx.append(coord_indexes[dim][value])
            job_idx[tuple(idx)] = int(record['job_id'])

    X = xr.DataArray(job_idx, dims=dims, coords=coords, name='job_id')
    X = X.assign_coords({
        'iter_dir': ('iteration', [path.name for path in iter_dirs]),
        'wmult_id': ('iteration', [meta['wmult_id'] for meta in iter_meta]),
        'wmult_variant': (
            'iteration',
            [str(meta['wmult_variant']) for meta in iter_meta],
        ),
        'stage_spec_hash': (
            'iteration',
            [str(meta['stage_spec_hash']) for meta in iter_meta],
        ),
    })
    return X


def _get_output_dir(workflow_dir, out_root):
    """Return the local combined-output directory."""
    run_info = _get_run_info(workflow_dir)
    return (
        Path(out_root) / 'workflows' / run_info['workflow_name'] /
        run_info['run_id'] / 'combined'
    )


def _get_source_file(workflow_dir, stage_name, target_cfg, job):
    """Resolve one per-job xarray source file."""
    iter_dir = f"iter_{int(job['sel']['iteration']):03d}"
    data_dir = (
        Path(workflow_dir) / 'iterations' / iter_dir / stage_name /
        'sim_results' / target_cfg['data_subdir']
    )
    pattern = target_cfg['fname_templ'].format(job=int(job['job_id']))
    files = sorted(data_dir.glob(pattern))
    if len(files) != 1:
        raise FileNotFoundError(
            f'Expected one {pattern!r} match in {data_dir}, found {len(files)}'
        )
    return files[0]


def _make_reader(workflow_dir, stage_name, target_cfg):
    """Return a job reader for nested workflow-stage outputs."""
    def read_job_xr(job):
        fpath = _get_source_file(workflow_dir, stage_name, target_cfg, job)
        return load_xr(
            fpath,
            data_type='dataarray',
            load=False,
            **SOURCE_OPEN_KWARGS,
        )

    return read_job_xr


def _get_output_attrs(workflow_dir, stage_name, target, target_cfg):
    """Build lightweight attrs for combined outputs."""
    run_info = _get_run_info(workflow_dir)
    return {
        'source_workflow_dir': str(Path(workflow_dir)),
        'stage': stage_name,
        'target': target,
        'workflow_name': run_info['workflow_name'],
        'run_id': run_info['run_id'],
        'lazy': int(bool(LAZY)),
        'skip_missing': int(bool(SKIP_MISSING)),
        'source_file_template': target_cfg['fname_templ'],
    }


def collect_target(workflow_dir, stage_name, target, out_dir):
    """Collect one target into one combined NetCDF."""
    if target not in TARGET_CONFIGS:
        raise ValueError(f'Unknown target: {target}')
    target_cfg = TARGET_CONFIGS[target]
    job_idx_xr = _build_job_idx_xr(workflow_dir, stage_name)
    out_path = Path(out_dir) / target_cfg['out_name']
    attrs = _get_output_attrs(workflow_dir, stage_name, target, target_cfg)
    reader = _make_reader(workflow_dir, stage_name, target_cfg)

    # Write directly to NetCDF unless LAZY is disabled for debugging
    if LAZY:
        out = _write_batch_netcdf(
            out_path,
            job_idx_xr,
            reader,
            chunks=CHUNKS,
            attrs=attrs,
            skip_missing=bool(SKIP_MISSING),
            load=bool(LOAD_OUTPUT),
            overwrite=bool(OVERWRITE),
        )
    else:
        records = []
        for job in iter_batch_jobs(job_idx_xr):
            record = reader(job).expand_dims(job['sel'])
            records.append(record)
        out = xr.combine_by_coords(records)
        out.attrs.update(attrs)
        out.to_netcdf(out_path)

    print(f'{target}: {out_path}')
    print(f'Shape: {dict(out.sizes)}')
    out.close()
    return out_path


def main():
    """Collect configured workflow-stage xarray outputs."""
    out_dir = _get_output_dir(WORKFLOW_DIR, DIR_OUT_ROOT)
    out_dir.mkdir(parents=True, exist_ok=True)

    for target in TARGETS:
        collect_target(
            WORKFLOW_DIR,
            STAGE_NAME,
            target,
            out_dir,
        )


if __name__ == '__main__':
    main()
