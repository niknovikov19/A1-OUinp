import hashlib
import json
from pathlib import Path, PurePosixPath
import re


RUN_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
SAFE_NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
PATH_SEGMENT_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,239}')
COMMIT_RE = re.compile(r'[0-9a-f]{40}')
TOKEN_NAME_RE = re.compile(r'[A-Z][A-Z0-9_]*')
TOKEN_RE = re.compile(r'@@([A-Z][A-Z0-9_]*)@@')
RENDER_VALUE_RE = re.compile(r'[A-Za-z0-9_./,:=+%-]+')

RESOURCE_KEYS = {
    'partition',
    'nodes',
    'cores',
    'memory_gb',
    'wall_time_min',
}
COMMON_REQUEST_KEYS = {
    'schema_version',
    'request_id',
    'job_kind',
    'target',
    'template_path',
    'expected_result_path',
    'completion_files',
    'top_level_resources',
}
BATCH_REQUEST_KEYS = {
    'simulation_job_resources',
    'max_concurrent_simulation_jobs',
    'max_simulation_jobs',
}
WORKFLOW_REQUEST_KEYS = {
    'stage_jobs',
    'max_simulation_jobs',
}
STAGE_JOB_KEYS = {
    'resources',
    'max_concurrent_simulation_jobs',
}
TEMPLATE_TOKENS = {
    'single': {
        'CHECKOUT', 'CORES', 'JOB_NAME', 'MEMORY', 'NODES', 'PARTITION',
        'REQUEST_PATH', 'STDERR', 'STDOUT', 'TASKS', 'WALL_TIME',
    },
    'batch': {
        'CHECKOUT', 'CORES', 'JOB_NAME', 'MEMORY', 'NODES', 'PARTITION',
        'REQUEST_PATH', 'STDERR', 'STDOUT', 'WALL_TIME',
    },
    'workflow': {
        'CHECKOUT', 'CORES', 'JOB_NAME', 'MEMORY', 'NODES', 'PARTITION',
        'REQUEST_PATH', 'STDERR', 'STDOUT', 'WALL_TIME',
    },
}


class HpcJobValidationError(ValueError):
    """Represent an invalid HPC job request or prepared value."""


def normalize_json(value):
    """Convert common scientific scalar values to stable JSON data."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): normalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json(item) for item in value]
    if hasattr(value, 'item'):
        return normalize_json(value.item())
    return value


def canonical_json(value):
    """Serialize one JSON-compatible value deterministically."""
    try:
        return json.dumps(
            normalize_json(value),
            allow_nan=False,
            sort_keys=True,
            separators=(',', ':'),
        )
    except (TypeError, ValueError) as exc:
        raise HpcJobValidationError('Value is not finite JSON data') from exc


def hash_data(value):
    """Return the SHA256 digest of one normalized JSON value."""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_run_id(value):
    """Validate and return one unique HPC job-run ID."""
    if not isinstance(value, str) or RUN_ID_RE.fullmatch(value) is None:
        raise HpcJobValidationError(f'Invalid run ID: {value!r}')
    return value


def validate_safe_name(value, label):
    """Validate and return one short shell-inert name."""
    if not isinstance(value, str) or SAFE_NAME_RE.fullmatch(value) is None:
        raise HpcJobValidationError(f'Invalid {label}: {value!r}')
    return value


def validate_target(value):
    """Validate and return one repository experiment or workflow ID."""
    if not isinstance(value, str) or len(value) > 255 or '\\' in value:
        raise HpcJobValidationError(f'Invalid target: {value!r}')
    segments = value.split('/')
    valid = all(
        segment not in {'.', '..'} and
        PATH_SEGMENT_RE.fullmatch(segment) is not None
        for segment in segments
    )
    if not valid:
        raise HpcJobValidationError(f'Invalid target: {value!r}')
    return value


def validate_git_commit(value):
    """Validate and return one full lowercase Git commit."""
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise HpcJobValidationError(f'Invalid Git commit: {value!r}')
    return value


def validate_repo_path(value, label='repository path'):
    """Validate and return one normalized repository-relative path."""
    if not isinstance(value, str) or not value or len(value) > 512:
        raise HpcJobValidationError(f'Invalid {label}: {value!r}')
    fpath = PurePosixPath(value)
    valid = (
        not fpath.is_absolute() and
        value == fpath.as_posix() and
        all(
            segment not in {'', '.', '..'} and
            PATH_SEGMENT_RE.fullmatch(segment) is not None
            for segment in fpath.parts
        )
    )
    if not valid:
        raise HpcJobValidationError(f'Invalid {label}: {value!r}')
    return value


def validate_resources(value, label):
    """Validate and normalize one Slurm resource mapping."""
    if not isinstance(value, dict) or set(value) != RESOURCE_KEYS:
        raise HpcJobValidationError(f'Invalid {label} keys')
    partition = validate_safe_name(value['partition'], f'{label} partition')
    normalized = {'partition': partition}
    for key in ('nodes', 'cores', 'memory_gb', 'wall_time_min'):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise HpcJobValidationError(f'Invalid {label} {key}')
        normalized[key] = number
    return normalized


def validate_positive_int(value, label):
    """Validate one positive integer while rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HpcJobValidationError(f'Invalid {label}')
    return value


def format_slurm_time(wall_time_min):
    """Format integer minutes as one Slurm day-hour-minute time value."""
    wall_time_min = validate_positive_int(wall_time_min, 'wall time')
    days, minute_of_day = divmod(wall_time_min, 24 * 60)
    hours, minutes = divmod(minute_of_day, 60)
    if days:
        return f'{days}-{hours:02d}:{minutes:02d}:00'
    return f'{hours:02d}:{minutes:02d}:00'


def get_batchtools_resource_config(resources):
    """Convert validated resources to existing BatchTools Slurm fields."""
    resources = validate_resources(resources, 'simulation-job resources')
    return {
        'partition': resources['partition'],
        'realtime': format_slurm_time(resources['wall_time_min']),
        'nodes': resources['nodes'],
        'coresPerNode': resources['cores'],
        'mem': f'{resources["memory_gb"]}G',
    }


def calculate_parameter_grid_size(parameter_axes, maximum=None):
    """Validate parameter axes and return their Cartesian-product size."""
    if not isinstance(parameter_axes, dict) or not parameter_axes:
        raise HpcJobValidationError('Parameter axes must be a non-empty object')
    if maximum is not None:
        validate_positive_int(maximum, 'parameter-grid limit')

    # Validate every repository-derived axis before multiplying its size
    count = 1
    for name, values in parameter_axes.items():
        validate_safe_name(name, 'parameter name')
        if not isinstance(values, list) or not values:
            raise HpcJobValidationError(f'Invalid parameter axis: {name!r}')
        normalized = [canonical_json(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise HpcJobValidationError(f'Duplicate axis values: {name!r}')
        count *= len(values)
        if maximum is not None and count > maximum:
            raise HpcJobValidationError(
                f'Calculated simulation jobs exceed {maximum}'
            )
    return count


def _validate_expected_result_path(value, job_kind, target):
    """Validate one expected result path against existing repo conventions."""
    value = validate_repo_path(value, 'expected result path')
    parts = PurePosixPath(value).parts
    target_parts = PurePosixPath(target).parts
    if job_kind in {'single', 'batch'}:
        prefix = ('exp_results', *target_parts)
    else:
        prefix = ('exp_results', 'workflows', *target_parts)
    if parts[:len(prefix)] != prefix or len(parts) != len(prefix) + 1:
        raise HpcJobValidationError(
            'Expected result path does not match the target layout'
        )
    return value


def _validate_completion_files(value):
    """Validate bounded files relative to one scientific result directory."""
    if not isinstance(value, list) or not value or len(value) > 32:
        raise HpcJobValidationError('Invalid completion files')
    files = [
        validate_repo_path(item, 'completion file')
        for item in value
    ]
    if len(files) != len(set(files)):
        raise HpcJobValidationError('Duplicate completion files')
    return files


def _validate_stage_jobs(value):
    """Validate per-stage workflow simulation-job settings."""
    if not isinstance(value, dict) or not value:
        raise HpcJobValidationError('Workflow stage jobs must be non-empty')
    normalized = {}
    for stage, settings in value.items():
        stage = validate_safe_name(stage, 'workflow stage')
        if not isinstance(settings, dict) or set(settings) != STAGE_JOB_KEYS:
            raise HpcJobValidationError(f'Invalid stage-job settings: {stage}')
        normalized[stage] = {
            'resources': validate_resources(
                settings['resources'],
                f'{stage} simulation-job resources',
            ),
            'max_concurrent_simulation_jobs': validate_positive_int(
                settings['max_concurrent_simulation_jobs'],
                f'{stage} concurrent simulation-job limit',
            ),
        }
    return normalized


def validate_request(request):
    """Validate and normalize one tracked HPC job request."""
    if not isinstance(request, dict):
        raise HpcJobValidationError('HPC job request must be an object')
    if request.get('schema_version') != 1:
        raise HpcJobValidationError('Unsupported HPC job schema version')
    job_kind = request.get('job_kind')
    if job_kind not in {'single', 'batch', 'workflow'}:
        raise HpcJobValidationError(f'Invalid job kind: {job_kind!r}')

    expected_keys = set(COMMON_REQUEST_KEYS)
    if job_kind == 'batch':
        expected_keys |= BATCH_REQUEST_KEYS
    elif job_kind == 'workflow':
        expected_keys |= WORKFLOW_REQUEST_KEYS
    if set(request) != expected_keys:
        raise HpcJobValidationError('Invalid HPC job request keys')

    target = validate_target(request['target'])
    template_path = validate_repo_path(
        request['template_path'],
        'template path',
    )
    template = PurePosixPath(template_path)
    if template.parts[:2] != ('hpc_jobs', 'templates') or template.suffix != '.sh':
        raise HpcJobValidationError('Template must be below hpc_jobs/templates')

    normalized = {
        'schema_version': 1,
        'request_id': validate_safe_name(request['request_id'], 'request ID'),
        'job_kind': job_kind,
        'target': target,
        'template_path': template_path,
        'expected_result_path': _validate_expected_result_path(
            request['expected_result_path'],
            job_kind,
            target,
        ),
        'completion_files': _validate_completion_files(
            request['completion_files']
        ),
        'top_level_resources': validate_resources(
            request['top_level_resources'],
            'top-level resources',
        ),
    }

    # Add only the settings meaningful to this concrete job shape
    if job_kind == 'batch':
        normalized['simulation_job_resources'] = validate_resources(
            request['simulation_job_resources'],
            'simulation-job resources',
        )
        normalized['max_concurrent_simulation_jobs'] = validate_positive_int(
            request['max_concurrent_simulation_jobs'],
            'concurrent simulation-job limit',
        )
        normalized['max_simulation_jobs'] = validate_positive_int(
            request['max_simulation_jobs'],
            'simulation-job limit',
        )
    elif job_kind == 'workflow':
        normalized['stage_jobs'] = _validate_stage_jobs(request['stage_jobs'])
        normalized['max_simulation_jobs'] = validate_positive_int(
            request['max_simulation_jobs'],
            'simulation-job limit',
        )
    return normalized


def get_job_run_layout(repo_root, run_id):
    """Return the fixed repository paths for one prepared top-level job."""
    repo_root = Path(repo_root)
    if not repo_root.is_absolute():
        raise HpcJobValidationError('Repository root must be absolute')
    run_id = validate_run_id(run_id)
    run_root = repo_root / 'hpc_jobs' / 'runs'
    run_dir = run_root / run_id
    return {
        'run_root': run_root,
        'run_dir': run_dir,
        'request': run_dir / 'request.json',
        'run': run_dir / 'run.json',
        'submission': run_dir / 'submission.json',
        'status': run_dir / 'status.json',
        'submit_script': run_dir / 'submit.sh',
        'stdout': run_dir / 'slurm-%j.out',
        'stderr': run_dir / 'slurm-%j.err',
    }


def validate_result_destination(repo_root, result_path):
    """Require an absent or empty result directory inside exp_results."""
    repo_root = Path(repo_root)
    if not repo_root.is_absolute():
        raise HpcJobValidationError('Repository root must be absolute')
    relpath = validate_repo_path(result_path, 'result path')
    fpath = repo_root / relpath
    result_root = repo_root / 'exp_results'
    if PurePosixPath(relpath).parts[0] != 'exp_results':
        raise HpcJobValidationError('Result path must be below exp_results')

    # Reject an existing symlink component before inspecting destination data
    current = result_root
    for part in PurePosixPath(relpath).parts[1:]:
        if current.is_symlink():
            raise HpcJobValidationError('Result path contains a symlink')
        current /= part
    if current.is_symlink():
        raise HpcJobValidationError('Result path contains a symlink')
    if fpath.exists() and not fpath.is_dir():
        raise HpcJobValidationError('Result destination is not a directory')
    if fpath.is_dir() and next(fpath.iterdir(), None) is not None:
        raise HpcJobValidationError('Result destination is not empty')
    return fpath


def build_prepared_job_context(request, run_id, repo_root, git_commit):
    """Build one immutable context without executing repository Python."""
    request = validate_request(request)
    run_id = validate_run_id(run_id)
    git_commit = validate_git_commit(git_commit)
    validate_result_destination(repo_root, request['expected_result_path'])
    layout = get_job_run_layout(repo_root, run_id)
    simulation_job_limit = 1
    if request['job_kind'] != 'single':
        simulation_job_limit = request['max_simulation_jobs']
    return {
        'schema_version': 1,
        'request_id': request['request_id'],
        'request_sha256': hash_data(request),
        'run_id': run_id,
        'job_kind': request['job_kind'],
        'target': request['target'],
        'git_commit': git_commit,
        'template_path': request['template_path'],
        'top_level_resources': request['top_level_resources'],
        'simulation_job_limit': simulation_job_limit,
        'expected_result_path': request['expected_result_path'],
        'completion_files': request['completion_files'],
        'job_run_dir': layout['run_dir'].as_posix(),
        'submit_script': layout['submit_script'].as_posix(),
        'stdout_path': layout['stdout'].as_posix(),
        'stderr_path': layout['stderr'].as_posix(),
    }


def build_template_values(context, checkout_root):
    """Build the fixed token values for one prepared top-level job script."""
    if not isinstance(context, dict) or context.get('job_kind') not in TEMPLATE_TOKENS:
        raise HpcJobValidationError('Invalid prepared job context')
    checkout_root = Path(checkout_root)
    if not checkout_root.is_absolute():
        raise HpcJobValidationError('Checkout root must be absolute')
    checkout = checkout_root.as_posix()
    if RENDER_VALUE_RE.fullmatch(checkout) is None:
        raise HpcJobValidationError('Invalid checkout root')
    resources = validate_resources(
        context.get('top_level_resources'),
        'top-level resources',
    )
    run_id = validate_run_id(context.get('run_id'))
    request_id = validate_safe_name(context.get('request_id'), 'request ID')
    job_name = f'a1-{run_id}'
    if len(job_name) > 64:
        suffix = hashlib.sha256(job_name.encode()).hexdigest()[:8]
        job_name = f'{job_name[:55]}-{suffix}'
    values = {
        'CHECKOUT': checkout,
        'CORES': str(resources['cores']),
        'JOB_NAME': job_name,
        'MEMORY': f'{resources["memory_gb"]}G',
        'NODES': str(resources['nodes']),
        'PARTITION': resources['partition'],
        'REQUEST_PATH': f'hpc_jobs/requests/{request_id}.json',
        'STDERR': context['stderr_path'],
        'STDOUT': context['stdout_path'],
        'WALL_TIME': format_slurm_time(resources['wall_time_min']),
    }
    if context['job_kind'] == 'single':
        values['TASKS'] = str(resources['nodes'] * resources['cores'])
    if set(values) != TEMPLATE_TOKENS[context['job_kind']]:
        raise HpcJobValidationError('Prepared values do not match job template')
    return values


def render_template(template_text, values, required_tokens):
    """Render one shell template through an exact fixed token set."""
    if not isinstance(template_text, str) or '\x00' in template_text:
        raise HpcJobValidationError('Shell template must be text')
    if not isinstance(values, dict) or not isinstance(required_tokens, set):
        raise HpcJobValidationError('Invalid shell-template inputs')
    if set(values) != required_tokens:
        raise HpcJobValidationError('Template values do not match tokens')
    if any(TOKEN_NAME_RE.fullmatch(name) is None for name in required_tokens):
        raise HpcJobValidationError('Invalid template token name')

    # Require every known token exactly once and reject unknown placeholders
    found = TOKEN_RE.findall(template_text)
    if set(found) != required_tokens:
        raise HpcJobValidationError('Shell-template tokens do not match')
    duplicates = sorted(
        name for name in required_tokens if found.count(name) != 1
    )
    if duplicates:
        raise HpcJobValidationError(
            f'Shell-template tokens must occur once: {duplicates}'
        )

    rendered = template_text
    for name in sorted(required_tokens):
        value = values[name]
        if not isinstance(value, str) or RENDER_VALUE_RE.fullmatch(value) is None:
            raise HpcJobValidationError(f'Invalid shell-template value: {name}')
        rendered = rendered.replace(f'@@{name}@@', value)
    if TOKEN_RE.search(rendered) is not None:
        raise HpcJobValidationError('Unresolved shell-template token')
    return rendered
