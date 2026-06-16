import json
from pathlib import Path
import re
import sys


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[2]
if str(DIR_REPO) not in sys.path:
    sys.path.insert(0, str(DIR_REPO))

from workflow_utils import (
    expand_param_grid,
    make_job_record,
    param_key,
    read_json,
    write_json_atomic,
)


CFG_JOB_RE = re.compile(r'^cfg_(\d+)(?:_|\.json$)')


def _resolve_source_dir(source_dir):
    """Resolve one configured fixture source directory."""
    dirpath = Path(source_dir)
    if not dirpath.is_absolute():
        dirpath = DIR_REPO / dirpath
    return dirpath.resolve()


def _file_info(fpath, dirpath_source):
    """Describe one source file without reading its large payload."""
    stat = fpath.stat()
    return {
        'path': fpath.relative_to(dirpath_source).as_posix(),
        'name': fpath.name,
        'size': stat.st_size,
        'mtime_ns': stat.st_mtime_ns,
    }


def _load_cfg(fpath):
    """Load the simConfig dictionary from one source cfg file."""
    with open(fpath, 'r') as fid:
        payload = json.load(fid)
    if 'simConfig' not in payload:
        raise ValueError(f'Missing simConfig in fixture cfg: {fpath}')
    return payload['simConfig']


def _get_job_id(fpath):
    """Extract the integer job ID from a source cfg filename."""
    match = CFG_JOB_RE.match(fpath.name)
    if match is None:
        raise ValueError(f'Invalid fixture cfg filename: {fpath.name}')
    return int(match.group(1))


def _inspect_source(stage_spec, source_dir, linked_dirs, output_dir,
                    output_pattern):
    """Validate a fixture source and build its compact manifest."""
    dirpath_source = _resolve_source_dir(source_dir)
    dirpath_cfg = dirpath_source / linked_dirs['cfg']
    dirpath_output = dirpath_source / linked_dirs[output_dir]
    if not dirpath_cfg.is_dir() or not dirpath_output.is_dir():
        raise FileNotFoundError(
            f'Fixture source directories are unavailable: {dirpath_source}'
        )

    # Index the exact expected Cartesian grid
    param_names = list(stage_spec['batch_params'])
    expected = expand_param_grid(stage_spec['batch_params'])
    expected_by_key = {
        param_key(params, param_names): params
        for params in expected
    }
    seen_params = {}
    seen_job_ids = set()
    jobs = []

    # Require one cfg and one processor input for every source job
    cfg_paths = sorted(dirpath_cfg.glob('cfg_*.json'))
    if not cfg_paths:
        raise FileNotFoundError(f'No fixture cfg files found: {dirpath_cfg}')
    for fpath_cfg in cfg_paths:
        job_id = _get_job_id(fpath_cfg)
        if job_id in seen_job_ids:
            raise ValueError(f'Duplicate fixture job ID: {job_id}')
        seen_job_ids.add(job_id)

        cfg = _load_cfg(fpath_cfg)
        params = {
            name: cfg[name]
            for name in param_names
        }
        key = param_key(params, param_names)
        if key not in expected_by_key:
            raise ValueError(f'Unexpected fixture parameters: {params}')
        if key in seen_params:
            raise ValueError(f'Duplicate fixture parameters: {params}')
        seen_params[key] = params

        output_paths = sorted(
            dirpath_output.glob(output_pattern.format(job=job_id))
        )
        if len(output_paths) != 1:
            raise ValueError(
                f'Expected one fixture output for job {job_id}, '
                f'found {len(output_paths)}'
            )
        jobs.append({
            'job_id': job_id,
            'sim_label': cfg['simLabel'],
            'batch_params': params,
            'cfg': _file_info(fpath_cfg, dirpath_source),
            'output': _file_info(output_paths[0], dirpath_source),
        })

    # Reject incomplete fixture grids before publishing any records
    missing = [
        params
        for key, params in expected_by_key.items()
        if key not in seen_params
    ]
    if missing:
        raise ValueError(f'Missing fixture parameter combinations: {missing}')
    if len(jobs) != len(expected):
        raise ValueError(
            f'Fixture has {len(jobs)} jobs, expected {len(expected)}'
        )

    manifest = {
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'source_dir': dirpath_source.as_posix(),
        'linked_dirs': {
            name: (dirpath_source / relpath).as_posix()
            for name, relpath in linked_dirs.items()
        },
        'jobs': sorted(jobs, key=lambda item: item['job_id']),
    }
    return dirpath_source, manifest


def _check_saved_manifest(stage_dir, manifest):
    """Refuse reuse when the mounted fixture source has changed."""
    fpath_manifest = Path(stage_dir) / 'meta' / 'source_manifest.json'
    if not fpath_manifest.exists():
        return False
    saved = read_json(fpath_manifest)
    if saved != manifest:
        raise ValueError(
            f'Fixture source changed since the stage was created: '
            f'{manifest["source_dir"]}'
        )
    return True


def _link_directory(fpath_link, dirpath_source):
    """Create or repair one local directory symlink."""
    fpath_link = Path(fpath_link)
    dirpath_source = Path(dirpath_source)
    if fpath_link.is_symlink():
        if fpath_link.resolve(strict=False) == dirpath_source:
            return
        fpath_link.unlink()
    elif fpath_link.exists():
        raise FileExistsError(
            f'Fixture link path is not a symlink: {fpath_link}'
        )
    fpath_link.symlink_to(dirpath_source, target_is_directory=True)


def _links_are_valid(stage_dir, manifest):
    """Check that every local fixture link targets its saved source."""
    dirpath_results = Path(stage_dir) / 'sim_results'
    for name, source_path in manifest['linked_dirs'].items():
        fpath_link = dirpath_results / name
        if not fpath_link.is_symlink():
            return False
        if fpath_link.resolve(strict=False) != Path(source_path):
            return False
    return True


def _write_job_records(stage_dir, stage_spec, manifest, output_dir):
    """Write normal compact job records for linked processor inputs."""
    context = {
        'workflow_name': stage_spec['workflow_name'],
        'run_id': stage_spec['run_id'],
        'iteration': stage_spec['iteration'],
        'stage': stage_spec['stage'],
        'stage_spec_hash': stage_spec['stage_spec_hash'],
    }
    for job in manifest['jobs']:
        output_name = job['output']['name']
        outputs = [
            f'sim_results/{output_dir}/{output_name}',
        ]
        record = make_job_record(
            context,
            job['sim_label'],
            job['job_id'],
            job['batch_params'],
            outputs,
        )
        write_json_atomic(
            Path(stage_dir) / 'job_meta' / f'{job["sim_label"]}.json',
            record,
        )


def run_stage(stage_dir, stage_spec, source_dir, linked_dirs, output_dir,
              output_pattern):
    """Link one existing fixture batch into a workflow stage."""
    # Keep direct executor use consistent with generic runner preparation
    for relpath in ('meta', 'job_meta', 'sim_results'):
        (Path(stage_dir) / relpath).mkdir(parents=True, exist_ok=True)

    dirpath_source, manifest = _inspect_source(
        stage_spec,
        source_dir,
        linked_dirs,
        output_dir,
        output_pattern,
    )
    manifest_exists = _check_saved_manifest(stage_dir, manifest)

    # Publish only the configured source directories into local results
    dirpath_results = Path(stage_dir) / 'sim_results'
    for name, relpath in linked_dirs.items():
        _link_directory(
            dirpath_results / name,
            dirpath_source / relpath,
        )

    # Publish compact records after every required link is available
    _write_job_records(
        stage_dir,
        stage_spec,
        manifest,
        output_dir,
    )
    if not manifest_exists:
        write_json_atomic(
            Path(stage_dir) / 'meta' / 'source_manifest.json',
            manifest,
        )


def validate_stage(stage_dir, stage_spec, source_dir, linked_dirs,
                   output_dir, output_pattern):
    """Validate saved source fingerprints and local fixture links."""
    _, manifest = _inspect_source(
        stage_spec,
        source_dir,
        linked_dirs,
        output_dir,
        output_pattern,
    )
    if not _check_saved_manifest(stage_dir, manifest):
        return False
    return _links_are_valid(stage_dir, manifest)
