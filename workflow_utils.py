import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import time


def normalize_json(value):
    """Convert common Python values to stable JSON-compatible values."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): normalize_json(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json(val) for val in value]
    if hasattr(value, 'item'):
        return normalize_json(value.item())
    return value


def canonical_json(value):
    """Serialize a value in a stable form suitable for hashing."""
    return json.dumps(
        normalize_json(value),
        sort_keys=True,
        separators=(',', ':'),
    )


def hash_data(value):
    """Return the SHA256 hash of normalized JSON data."""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def read_json(fpath):
    """Read a JSON file."""
    with open(fpath, 'r') as fid:
        return json.load(fid)


def write_json_atomic(fpath, value):
    """Write JSON by atomically replacing the destination file."""
    fpath = Path(fpath)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath_tmp = fpath.with_suffix(f'{fpath.suffix}.tmp')
    with open(fpath_tmp, 'w') as fid:
        json.dump(normalize_json(value), fid, indent=2, sort_keys=True)
    os.replace(fpath_tmp, fpath)


def merge_batch_params(default_params, overrides):
    """Patch existing batch axes while retaining omitted defaults."""
    unknown = sorted(set(overrides) - set(default_params))
    if unknown:
        raise KeyError(f'Unknown batch parameter overrides: {unknown}')

    # Copy all axes so workflow code cannot mutate experiment constants
    params = {
        name: list(values)
        for name, values in default_params.items()
    }
    for name, values in overrides.items():
        values = list(values)
        if not values:
            raise ValueError(f'Batch parameter {name!r} cannot be empty')
        params[name] = values
    return params


def expand_param_grid(params):
    """Expand a parameter grid into ordered Cartesian combinations."""
    names = list(params)
    values = [params[name] for name in names]
    return [
        dict(zip(names, combination))
        for combination in itertools.product(*values)
    ]


def param_key(params, names):
    """Build a stable key for one parameter combination."""
    return tuple(canonical_json(params[name]) for name in names)


def make_job_record(context, sim_label, job_id, batch_params, outputs):
    """Build one compact workflow job completion record."""
    return {
        'status': 'complete',
        'workflow_name': context['workflow_name'],
        'run_id': context['run_id'],
        'iteration': context['iteration'],
        'stage': context['stage'],
        'stage_spec_hash': context['stage_spec_hash'],
        'sim_label': sim_label,
        'job_id': int(job_id),
        'batch_params': normalize_json(batch_params),
        'outputs': [Path(output).as_posix() for output in outputs],
    }


def load_job_records(stage_dir):
    """Load all compact job records from a stage."""
    dirpath_meta = Path(stage_dir) / 'job_meta'
    return [
        read_json(fpath)
        for fpath in sorted(dirpath_meta.glob('*.json'))
    ]


def validate_job_records(stage_dir, expected, param_names, stage_hash):
    """Validate complete records and their declared result files."""
    stage_dir = Path(stage_dir)
    expected_by_key = {
        param_key(params, param_names): params
        for params in expected
    }
    complete = {}

    # Accept only records from this exact stage specification
    for record in load_job_records(stage_dir):
        if record.get('status') != 'complete':
            continue
        if record.get('stage_spec_hash') != stage_hash:
            continue
        params = record.get('batch_params', {})
        if set(params) != set(param_names):
            continue
        key = param_key(params, param_names)
        if key not in expected_by_key:
            continue

        # A completion record is valid only while every declared output exists
        outputs = record.get('outputs', [])
        if not outputs:
            continue
        if not all((stage_dir / relpath).is_file() for relpath in outputs):
            continue
        complete[key] = record

    missing = [
        params
        for key, params in expected_by_key.items()
        if key not in complete
    ]
    return complete, missing


def poll_job_records(stage_dir, expected, param_names, stage_hash,
                     refresh_sec, timeout_sec=None, sleep_fn=time.sleep,
                     clock_fn=time.monotonic, print_fn=print):
    """Poll compact completion records until the full batch is valid."""
    start = clock_fn()
    seen = set()

    while True:
        complete, missing = validate_job_records(
            stage_dir,
            expected,
            param_names,
            stage_hash,
        )
        complete_ids = {
            record['job_id']
            for record in complete.values()
        }
        new_ids = sorted(complete_ids - seen)
        missing_text = ', '.join(canonical_json(params) for params in missing)
        print_fn(
            f'Completed {len(complete)}/{len(expected)}; '
            f'new jobs: {new_ids}; missing: {missing_text or "none"}'
        )
        if not missing:
            return list(complete.values())
        seen = complete_ids

        # Enforce the optional wait limit after reporting current progress
        if timeout_sec is not None and clock_fn() - start >= timeout_sec:
            raise TimeoutError(
                f'Timed out waiting for {len(missing)} batch jobs'
            )
        sleep_fn(refresh_sec)


def build_job_index(records, param_grid):
    """Build an xarray job-id grid from compact job records."""
    import numpy as np
    import xarray as xr

    names = list(param_grid)
    shape = tuple(len(param_grid[name]) for name in names)
    job_ids = np.full(shape, np.nan)
    coord_indices = {
        name: {
            canonical_json(value): index
            for index, value in enumerate(param_grid[name])
        }
        for name in names
    }

    # Place each job ID at its resolved parameter coordinates
    for record in records:
        params = record['batch_params']
        index = tuple(
            coord_indices[name][canonical_json(params[name])]
            for name in names
        )
        job_ids[index] = int(record['job_id'])

    if np.isnan(job_ids).any():
        raise ValueError('Job records do not cover the full parameter grid')
    return xr.DataArray(
        job_ids.astype(int),
        coords={name: param_grid[name] for name in names},
        dims=names,
        name='job_id',
    )


def file_fingerprint(fpath):
    """Return a content fingerprint or None when a file is absent."""
    fpath = Path(fpath)
    if not fpath.is_file():
        return None
    return {
        'size': fpath.stat().st_size,
        'sha256': hashlib.sha256(fpath.read_bytes()).hexdigest(),
    }


def _get_next_attempt(stage_dir):
    """Return the next BatchTools artifact attempt number."""
    attempts = []
    dirpath_batchtools = Path(stage_dir) / 'batchtools'
    for fpath in dirpath_batchtools.glob('**/attempt_*'):
        prefix = fpath.name.split('_', 2)[:2]
        if len(prefix) != 2 or prefix[0] != 'attempt':
            continue
        try:
            attempts.append(int(prefix[1]))
        except ValueError:
            continue
    return max(attempts, default=-1) + 1


def _archive_artifact(fpath, dirpath_out, attempt):
    """Move one artifact to an attempt-specific destination."""
    fpath = Path(fpath)
    dirpath_out = Path(dirpath_out)
    dirpath_out.mkdir(parents=True, exist_ok=True)
    fpath_out = dirpath_out / f'attempt_{attempt:03d}_{fpath.name}'
    collision = 1
    while fpath_out.exists():
        fpath_out = dirpath_out / (
            f'attempt_{attempt:03d}_{collision:02d}_{fpath.name}'
        )
        collision += 1
    shutil.move(fpath, fpath_out)
    return fpath_out


def collect_batchtools_artifacts(stage_dir, root_summary=None,
                                 root_summary_before=None, print_fn=print):
    """Archive one attempt's BatchTools files without overwriting."""
    stage_dir = Path(stage_dir)
    dirpath_batchtools = stage_dir / 'batchtools'
    categories = {
        '.sh': 'scripts',
        '.run': 'logs',
        '.err': 'logs',
        '.out': 'logs',
        '.sgl': 'comm',
    }
    for dirname in set(categories.values()) | {'comm', 'summaries'}:
        (dirpath_batchtools / dirname).mkdir(parents=True, exist_ok=True)
    attempt = _get_next_attempt(stage_dir)
    collected = []
    summaries = []

    # Preserve names and group every loose stage file by artifact type
    for fpath in list(stage_dir.iterdir()):
        if not fpath.is_file():
            continue
        if fpath.suffix == '.csv':
            fpath_out = _archive_artifact(
                fpath,
                dirpath_batchtools / 'summaries',
                attempt,
            )
            summaries.append(fpath_out.relative_to(stage_dir).as_posix())
            continue
        dirname = categories.get(fpath.suffix, 'comm')
        fpath_out = _archive_artifact(
            fpath,
            dirpath_batchtools / dirname,
            attempt,
        )
        collected.append(fpath_out.relative_to(stage_dir).as_posix())

    # Claim the repo-root summary only when this search created or changed it
    if root_summary is not None:
        root_summary = Path(root_summary)
        root_summary_after = file_fingerprint(root_summary)
        changed = (
            root_summary_after is not None and
            root_summary_after != root_summary_before
        )
        if changed:
            fpath_out = _archive_artifact(
                root_summary,
                dirpath_batchtools / 'summaries',
                attempt,
            )
            summaries.append(fpath_out.relative_to(stage_dir).as_posix())
        elif root_summary_after is not None:
            print_fn(
                f'Leaving unchanged BatchTools summary in repo root: '
                f'{root_summary}'
            )

    return {
        'attempt': attempt,
        'files': collected,
        'summaries': summaries,
    }


def compare_resolved_params(saved, current):
    """Return concise top-level differences between resolved parameters."""
    differences = []
    keys = sorted(set(saved) | set(current))
    for key in keys:
        if saved.get(key) == current.get(key):
            continue
        differences.append({
            'key': key,
            'saved': saved.get(key),
            'current': current.get(key),
        })
    return differences
