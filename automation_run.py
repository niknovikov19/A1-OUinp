import hashlib
import json
from pathlib import Path, PurePosixPath
import re


RUN_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
SAFE_NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
EXPERIMENT_SEGMENT_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
COMMIT_RE = re.compile(r'[0-9a-f]{40}')
TOKEN_NAME_RE = re.compile(r'[A-Z][A-Z0-9_]*')
TOKEN_RE = re.compile(r'@@([A-Z][A-Z0-9_]*)@@')
RENDER_VALUE_RE = re.compile(r'[A-Za-z0-9_./,:=+-]+')

RESOURCE_KEYS = {
    'partition',
    'nodes',
    'cores',
    'memory_gb',
    'wall_time_min',
}
REQUEST_KEYS = {
    'schema_version',
    'request_id',
    'run_type',
    'experiment',
    'expected_commit',
    'launcher_path',
    'controller_resources',
    'child_resources',
    'parameter_axes',
    'max_concurrent_jobs',
}


class AutomationValidationError(ValueError):
    """Represent an invalid automation request or launcher value."""


def canonical_json(value):
    """Serialize one JSON-compatible value deterministically."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            sort_keys=True,
            separators=(',', ':'),
        )
    except (TypeError, ValueError) as exc:
        raise AutomationValidationError('Value is not finite JSON data') from exc


def hash_data(value):
    """Return the SHA256 digest of one normalized JSON value."""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_run_id(value):
    """Validate and return one unique automation run ID."""
    if not isinstance(value, str) or RUN_ID_RE.fullmatch(value) is None:
        raise AutomationValidationError(f'Invalid run ID: {value!r}')
    return value


def validate_safe_name(value, label):
    """Validate and return one short shell-inert name."""
    if not isinstance(value, str) or SAFE_NAME_RE.fullmatch(value) is None:
        raise AutomationValidationError(f'Invalid {label}: {value!r}')
    return value


def validate_experiment_id(value):
    """Validate and return one repository-relative experiment ID."""
    if not isinstance(value, str) or len(value) > 255 or '\\' in value:
        raise AutomationValidationError(f'Invalid experiment ID: {value!r}')
    segments = value.split('/')
    valid = all(
        segment not in {'.', '..'} and
        EXPERIMENT_SEGMENT_RE.fullmatch(segment) is not None
        for segment in segments
    )
    if not valid:
        raise AutomationValidationError(f'Invalid experiment ID: {value!r}')
    return value


def validate_git_commit(value):
    """Validate and return one full lowercase Git commit."""
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise AutomationValidationError(f'Invalid Git commit: {value!r}')
    return value


def validate_repo_path(value, label='repository path'):
    """Validate and return one normalized repository-relative path."""
    if not isinstance(value, str) or not value or len(value) > 512:
        raise AutomationValidationError(f'Invalid {label}: {value!r}')
    fpath = PurePosixPath(value)
    valid = (
        not fpath.is_absolute() and
        value == fpath.as_posix() and
        all(
            segment not in {'', '.', '..'} and
            EXPERIMENT_SEGMENT_RE.fullmatch(segment) is not None
            for segment in fpath.parts
        )
    )
    if not valid:
        raise AutomationValidationError(f'Invalid {label}: {value!r}')
    return value


def validate_resources(value, label):
    """Validate and normalize one controller or child resource mapping."""
    if not isinstance(value, dict) or set(value) != RESOURCE_KEYS:
        raise AutomationValidationError(f'Invalid {label} keys')
    partition = validate_safe_name(value['partition'], f'{label} partition')
    normalized = {'partition': partition}
    for key in ('nodes', 'cores', 'memory_gb', 'wall_time_min'):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise AutomationValidationError(f'Invalid {label} {key}')
        normalized[key] = number
    return normalized


def calculate_child_jobs(run_type, parameter_axes, maximum=None):
    """Validate parameter axes and return the expanded child-job count."""
    if run_type not in {'single', 'batch'}:
        raise AutomationValidationError(f'Invalid run type: {run_type!r}')
    if not isinstance(parameter_axes, dict):
        raise AutomationValidationError('Parameter axes must be an object')
    if run_type == 'single':
        if parameter_axes:
            raise AutomationValidationError('Single runs cannot define axes')
        return 1
    if not parameter_axes:
        raise AutomationValidationError('Batch runs require parameter axes')

    # Validate every axis before multiplying its size
    count = 1
    for name, values in parameter_axes.items():
        validate_safe_name(name, 'parameter name')
        if not isinstance(values, list) or not values:
            raise AutomationValidationError(f'Invalid parameter axis: {name!r}')
        normalized = [canonical_json(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise AutomationValidationError(f'Duplicate axis values: {name!r}')
        count *= len(values)
        if maximum is not None and count > maximum:
            raise AutomationValidationError(
                f'Calculated child jobs exceed {maximum}'
            )
    return count


def get_run_layout(repo_root, experiment, run_id):
    """Return the fixed automation paths for one validated run."""
    repo_root = Path(repo_root)
    if not repo_root.is_absolute():
        raise AutomationValidationError('Repository root must be absolute')
    experiment = validate_experiment_id(experiment)
    run_id = validate_run_id(run_id)
    result_root = repo_root / 'exp_results' / 'automation'
    run_dir = result_root.joinpath(*experiment.split('/'), run_id)
    return {
        'result_root': result_root,
        'run_dir': run_dir,
        'request': run_dir / 'request.json',
        'run': run_dir / 'run.json',
        'submission': run_dir / 'submission.json',
        'status': run_dir / 'status.json',
        'controller_dir': run_dir / 'controller',
        'submit_script': run_dir / 'controller' / 'submit.sh',
        'jobs_dir': run_dir / 'jobs',
        'job_index': run_dir / 'jobs' / 'index.jsonl',
        'sim_results_dir': run_dir / 'sim_results',
        'meta_dir': run_dir / 'meta',
    }


def build_run_context(request, run_id, repo_root, max_child_jobs):
    """Validate one request and build its canonical immutable run context."""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise AutomationValidationError('Invalid automation request keys')
    if request['schema_version'] != 2:
        raise AutomationValidationError('Unsupported automation schema version')
    request_id = validate_safe_name(request['request_id'], 'request ID')
    run_id = validate_run_id(run_id)
    run_type = request['run_type']
    experiment = validate_experiment_id(request['experiment'])
    commit = validate_git_commit(request['expected_commit'])
    launcher = validate_repo_path(request['launcher_path'], 'launcher path')
    controller = validate_resources(
        request['controller_resources'],
        'controller resources',
    )
    child = request['child_resources']
    if run_type == 'single' and child is not None:
        raise AutomationValidationError('Single runs cannot define child resources')
    if run_type == 'batch' and child is None:
        raise AutomationValidationError('Batch runs require child resources')
    if child is not None:
        child = validate_resources(child, 'child resources')

    # Resolve and bound the requested child-job topology
    if isinstance(max_child_jobs, bool) or not isinstance(max_child_jobs, int):
        raise AutomationValidationError('Invalid child-job limit')
    if max_child_jobs < 1:
        raise AutomationValidationError('Invalid child-job limit')
    child_jobs = calculate_child_jobs(
        run_type,
        request['parameter_axes'],
        maximum=max_child_jobs,
    )
    concurrent = request['max_concurrent_jobs']
    if isinstance(concurrent, bool) or not isinstance(concurrent, int):
        raise AutomationValidationError('Invalid concurrent-job limit')
    if concurrent < 1 or concurrent > child_jobs:
        raise AutomationValidationError('Invalid concurrent-job limit')

    layout = get_run_layout(repo_root, experiment, run_id)
    return {
        'schema_version': 2,
        'request_id': request_id,
        'request_sha256': hash_data(request),
        'run_id': run_id,
        'run_type': run_type,
        'experiment': experiment,
        'git_commit': commit,
        'launcher_path': launcher,
        'controller_resources': controller,
        'child_resources': child,
        'parameter_axes': request['parameter_axes'],
        'calculated_child_jobs': child_jobs,
        'max_concurrent_jobs': concurrent,
        'result_dir': layout['run_dir'].as_posix(),
        'controller_dir': layout['controller_dir'].as_posix(),
        'submit_script': layout['submit_script'].as_posix(),
        'jobs_dir': layout['jobs_dir'].as_posix(),
        'sim_results_dir': layout['sim_results_dir'].as_posix(),
    }


def render_launcher(template_text, values, required_tokens):
    """Render one launcher through an exact fixed token set."""
    if not isinstance(template_text, str) or '\x00' in template_text:
        raise AutomationValidationError('Launcher template must be text')
    if not isinstance(values, dict) or not isinstance(required_tokens, set):
        raise AutomationValidationError('Invalid launcher render inputs')
    if set(values) != required_tokens:
        raise AutomationValidationError('Launcher values do not match tokens')
    if any(TOKEN_NAME_RE.fullmatch(name) is None for name in required_tokens):
        raise AutomationValidationError('Invalid launcher token name')

    # Require every known token exactly once and reject unknown placeholders
    found = TOKEN_RE.findall(template_text)
    if set(found) != required_tokens:
        raise AutomationValidationError('Launcher template tokens do not match')
    duplicates = sorted(
        name for name in required_tokens if found.count(name) != 1
    )
    if duplicates:
        raise AutomationValidationError(
            f'Launcher tokens must occur once: {duplicates}'
        )

    rendered = template_text
    for name in sorted(required_tokens):
        value = values[name]
        if not isinstance(value, str) or RENDER_VALUE_RE.fullmatch(value) is None:
            raise AutomationValidationError(f'Invalid launcher value: {name}')
        rendered = rendered.replace(f'@@{name}@@', value)
    if TOKEN_RE.search(rendered) is not None:
        raise AutomationValidationError('Unresolved launcher token')
    return rendered
