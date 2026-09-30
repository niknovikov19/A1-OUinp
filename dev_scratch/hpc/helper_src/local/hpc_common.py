import hashlib
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone


BUNDLE_VERSION = '0.1.0-a0'
CONFIG_SCHEMA_VERSION = 1

EXIT_SUCCESS = 0
EXIT_REJECTED = 2
EXIT_UNKNOWN = 3
EXIT_FAILED = 4

RUNTIME_SOURCE_NAMES = (
    'hpc-helper-info',
    'hpc_common.py',
)

RUN_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
GIT_COMMIT_RE = re.compile(r'[0-9a-f]{40}')
EXPERIMENT_SEGMENT_RE = re.compile(
    r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}'
)
JOB_LABEL_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
SAFE_NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
SAFE_BRANCH_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}')

SENSITIVE_KEY_PARTS = (
    'identity_file',
    'password',
    'private_key',
    'secret',
    'token',
)

PUBLIC_AUDIT_ARGS = {
    '--help',
    '--json',
    'audit-tail',
    'experiment-id',
    'git-commit',
    'info',
    'job-label',
    'run-id',
    'validate',
    'version',
}


class RejectedInput(ValueError):
    """Represent input rejected before any remote action."""


class HelperFailure(RuntimeError):
    """Represent a known local helper failure."""


def get_install_root():
    """Return the protected installation root derived from this module."""
    return Path(__file__).resolve().parent.parent


def get_config_path():
    """Return the one fixed protected configuration path."""
    return get_install_root() / 'config' / 'hpc-helper.json'


def get_audit_path():
    """Return the one fixed protected audit-log path."""
    return get_install_root() / 'state' / 'actions.jsonl'


def _require_string(value, label):
    """Return a non-empty string or reject it."""
    if not isinstance(value, str) or not value:
        raise RejectedInput(f'{label} must be a non-empty string')
    if '\x00' in value:
        raise RejectedInput(f'{label} contains a null byte')
    return value


def validate_run_id(value):
    """Validate one path-safe run ID."""
    value = _require_string(value, 'run ID')
    if value in {'.', '..'} or RUN_ID_RE.fullmatch(value) is None:
        raise RejectedInput(f'Invalid run ID: {value!r}')
    return value


def validate_git_commit(value):
    """Validate one lowercase full Git commit hash."""
    value = _require_string(value, 'Git commit')
    if GIT_COMMIT_RE.fullmatch(value) is None:
        raise RejectedInput(
            'Git commit must contain exactly 40 lowercase hex characters'
        )
    return value


def validate_experiment_id(value):
    """Validate one repository-relative experiment identifier."""
    value = _require_string(value, 'experiment ID')
    if len(value) > 255 or '\\' in value:
        raise RejectedInput(f'Invalid experiment ID: {value!r}')
    segments = value.split('/')
    valid = all(
        segment not in {'.', '..'} and
        EXPERIMENT_SEGMENT_RE.fullmatch(segment) is not None
        for segment in segments
    )
    if not valid:
        raise RejectedInput(f'Invalid experiment ID: {value!r}')
    return value


def validate_job_label(value):
    """Validate one path-safe BatchTools job label."""
    value = _require_string(value, 'job label')
    if value in {'.', '..'} or JOB_LABEL_RE.fullmatch(value) is None:
        raise RejectedInput(f'Invalid job label: {value!r}')
    return value


def validate_identifier(kind, value):
    """Validate an identifier selected from the public allowlist."""
    validators = {
        'experiment-id': validate_experiment_id,
        'git-commit': validate_git_commit,
        'job-label': validate_job_label,
        'run-id': validate_run_id,
    }
    if kind not in validators:
        raise RejectedInput(f'Unsupported identifier kind: {kind!r}')
    return validators[kind](value)


def _require_mapping(value, label):
    """Return a mapping or reject it."""
    if not isinstance(value, dict):
        raise RejectedInput(f'{label} must be an object')
    return value


def _require_exact_keys(value, required, label):
    """Reject missing or unknown mapping keys."""
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(required))
    if missing:
        raise RejectedInput(f'{label} is missing keys: {missing}')
    if unknown:
        raise RejectedInput(f'{label} has unknown keys: {unknown}')


def _require_regular_file(fpath, label, allow_missing=False):
    """Require a non-symlink regular file at a fixed path."""
    try:
        file_stat = fpath.lstat()
    except FileNotFoundError:
        if allow_missing:
            return False
        raise HelperFailure(f'{label} is missing: {fpath}')
    if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
        raise HelperFailure(f'{label} must be a real regular file: {fpath}')
    return True


def _validate_safe_name(value, label, allow_empty=False):
    """Validate one shell-inert configuration name."""
    if allow_empty and value == '':
        return value
    value = _require_string(value, label)
    if SAFE_NAME_RE.fullmatch(value) is None:
        raise RejectedInput(f'Invalid {label}: {value!r}')
    return value


def _validate_branch(value):
    """Validate the one configured Git branch name."""
    value = _require_string(value, 'Git branch')
    invalid = (
        SAFE_BRANCH_RE.fullmatch(value) is None or
        value.startswith('/') or
        value.endswith('/') or
        '..' in value or
        '//' in value
    )
    if invalid:
        raise RejectedInput(f'Invalid Git branch: {value!r}')
    return value


def _validate_absolute_path(value, label):
    """Validate one normalized absolute POSIX path."""
    value = _require_string(value, label)
    fpath = Path(value)
    if not fpath.is_absolute() or '..' in fpath.parts:
        raise RejectedInput(f'{label} must be an absolute normalized path')
    if value != fpath.as_posix():
        raise RejectedInput(f'{label} must use normalized POSIX syntax')
    return value


def _validate_positive_int(value, label, minimum=1, maximum=None):
    """Validate one bounded integer configuration value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RejectedInput(f'{label} must be an integer')
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f'>= {minimum}'
        if maximum is not None:
            bounds += f' and <= {maximum}'
        raise RejectedInput(f'{label} must be {bounds}')
    return value


def _validate_ssh_config(config):
    """Validate the fixed SSH-alias configuration block."""
    config = _require_mapping(config, 'ssh')
    required = {
        'connect_timeout_sec',
        'grid_access_mode',
        'grid_host_alias',
        'lethe_host_alias',
    }
    _require_exact_keys(config, required, 'ssh')
    _validate_safe_name(config['lethe_host_alias'], 'lethe host alias')
    _validate_safe_name(config['grid_host_alias'], 'grid host alias')
    _validate_positive_int(
        config['connect_timeout_sec'],
        'SSH connection timeout',
        maximum=120,
    )
    if config['grid_access_mode'] != 'through-lethe-helper':
        raise RejectedInput(
            'grid_access_mode must be through-lethe-helper for the prototype'
        )


def _validate_git_config(config):
    """Validate the fixed Git deployment configuration block."""
    config = _require_mapping(config, 'git')
    required = {
        'automation_checkout',
        'branch',
        'manual_checkout',
        'remote_name',
    }
    _require_exact_keys(config, required, 'git')
    _validate_safe_name(config['remote_name'], 'Git remote name')
    _validate_branch(config['branch'])
    automation = _validate_absolute_path(
        config['automation_checkout'],
        'automation checkout',
    )
    manual = _validate_absolute_path(
        config['manual_checkout'],
        'manual checkout',
    )
    if automation == manual:
        raise RejectedInput(
            'Automation and manual checkouts must be different paths'
        )


def _validate_remote_helpers(config):
    """Validate protected remote-helper directories."""
    config = _require_mapping(config, 'remote_helpers')
    required = {'grid_dir', 'lethe_dir'}
    _require_exact_keys(config, required, 'remote_helpers')
    _validate_absolute_path(config['lethe_dir'], 'lethe helper directory')
    _validate_absolute_path(config['grid_dir'], 'grid helper directory')


def _validate_runs_config(config):
    """Validate the remote run-record root."""
    config = _require_mapping(config, 'runs')
    _require_exact_keys(config, {'root'}, 'runs')
    _validate_absolute_path(config['root'], 'automation run root')


def _validate_scheduler_config(config):
    """Validate scheduler identity, partitions, and resource ceilings."""
    config = _require_mapping(config, 'scheduler')
    required = {'account', 'allowed_partitions', 'limits', 'user'}
    _require_exact_keys(config, required, 'scheduler')
    _validate_safe_name(config['user'], 'scheduler user')
    _validate_safe_name(
        config['account'],
        'scheduler account',
        allow_empty=True,
    )
    partitions = config['allowed_partitions']
    if not isinstance(partitions, list) or not partitions:
        raise RejectedInput('allowed_partitions must be a non-empty list')
    if len(partitions) != len(set(partitions)):
        raise RejectedInput('allowed_partitions contains duplicates')
    for partition in partitions:
        _validate_safe_name(partition, 'Slurm partition')

    limits = _require_mapping(config['limits'], 'scheduler limits')
    required_limits = {
        'max_child_jobs',
        'max_concurrent_jobs',
        'max_cores_per_job',
        'max_memory_gb_per_job',
        'max_nodes_per_job',
        'max_wall_time_min',
    }
    _require_exact_keys(limits, required_limits, 'scheduler limits')
    for name in sorted(required_limits):
        _validate_positive_int(limits[name], name)
    if limits['max_concurrent_jobs'] > limits['max_child_jobs']:
        raise RejectedInput(
            'max_concurrent_jobs cannot exceed max_child_jobs'
        )


def validate_config(config):
    """Validate the complete protected helper configuration."""
    config = _require_mapping(config, 'configuration')
    required = {
        'deployment_id',
        'git',
        'remote_helpers',
        'runs',
        'scheduler',
        'schema_version',
        'ssh',
    }
    _require_exact_keys(config, required, 'configuration')
    if config['schema_version'] != CONFIG_SCHEMA_VERSION:
        raise RejectedInput(
            f'Unsupported schema_version: {config["schema_version"]!r}'
        )
    _validate_safe_name(config['deployment_id'], 'deployment ID')
    _validate_ssh_config(config['ssh'])
    _validate_git_config(config['git'])
    _validate_remote_helpers(config['remote_helpers'])
    _validate_runs_config(config['runs'])
    _validate_scheduler_config(config['scheduler'])
    return config


def load_config():
    """Load and validate the one fixed protected JSON configuration."""
    fpath = get_config_path()
    _require_regular_file(fpath, 'Protected configuration')
    try:
        with open(fpath, 'r') as fid:
            config = json.load(fid)
    except (OSError, json.JSONDecodeError) as exc:
        raise HelperFailure(
            f'Cannot read protected configuration {fpath}: {exc}'
        ) from exc
    try:
        return validate_config(config)
    except RejectedInput as exc:
        raise HelperFailure(f'Invalid protected configuration: {exc}') from exc


def canonical_json(value):
    """Serialize JSON data deterministically for hashing."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def hash_bytes(value):
    """Return a SHA256 hex digest for bytes."""
    return hashlib.sha256(value).hexdigest()


def hash_file(fpath):
    """Return a SHA256 hex digest for one file."""
    return hash_bytes(Path(fpath).read_bytes())


def get_bundle_identity():
    """Return hashes for the installed runtime source bundle."""
    dirpath_bin = Path(__file__).resolve().parent
    source_hashes = {}
    bundle_hash = hashlib.sha256()

    # Bind each digest to its fixed runtime filename
    for name in RUNTIME_SOURCE_NAMES:
        fpath = dirpath_bin / name
        _require_regular_file(fpath, 'Installed runtime source')
        digest = hash_file(fpath)
        source_hashes[name] = digest
        bundle_hash.update(name.encode())
        bundle_hash.update(b'\x00')
        bundle_hash.update(bytes.fromhex(digest))

    return {
        'bundle_version': BUNDLE_VERSION,
        'bundle_sha256': bundle_hash.hexdigest(),
        'source_sha256': source_hashes,
    }


def get_config_identity(config):
    """Return the protected configuration digest."""
    return hash_bytes(canonical_json(config).encode())


def redact_config(value, key=''):
    """Redact values whose configuration keys look sensitive."""
    key_lower = key.lower()
    if any(part in key_lower for part in SENSITIVE_KEY_PARTS):
        return '<redacted>'
    if isinstance(value, dict):
        return {
            item_key: redact_config(item, item_key)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_config(item, key) for item in value]
    return value


def _validate_audit_parent(dirpath):
    """Validate the pre-created protected audit directory."""
    try:
        file_stat = dirpath.lstat()
    except FileNotFoundError as exc:
        raise HelperFailure(
            f'Protected audit directory is missing: {dirpath}'
        ) from exc
    if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISDIR(file_stat.st_mode):
        raise HelperFailure(
            f'Protected audit parent must be a real directory: {dirpath}'
        )


def sanitize_audit_args(args):
    """Retain only public command words in audit arguments."""
    values = []
    for value in list(args)[:20]:
        value = str(value)
        values.append(value if value in PUBLIC_AUDIT_ARGS else '<value>')
    return values


def read_recent_audit_events(limit=20, max_bytes=65536):
    """Read a fixed number of recent events from the protected audit log."""
    fpath = get_audit_path()
    if not _require_regular_file(
        fpath,
        'Protected audit log',
        allow_missing=True,
    ):
        return []
    try:
        with open(fpath, 'rb') as fid:
            fid.seek(0, os.SEEK_END)
            size = fid.tell()
            offset = max(0, size - max_bytes)
            fid.seek(offset)
            data = fid.read(max_bytes)
    except OSError as exc:
        raise HelperFailure(f'Cannot read protected audit log: {exc}') from exc

    # Discard a partial first line when reading from the middle of the file
    lines = data.splitlines()
    if offset and lines:
        lines = lines[1:]
    events = []
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HelperFailure(
                f'Protected audit log contains invalid JSON: {exc}'
            ) from exc
        events.append(event)
    return events


def append_audit_event(action, status, exit_code, args, details=None):
    """Append one bounded JSON event to the protected audit log."""
    fpath = get_audit_path()
    _validate_audit_parent(fpath.parent)
    _require_regular_file(
        fpath,
        'Protected audit log',
        allow_missing=True,
    )
    event = {
        'schema_version': 1,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'helper': 'hpc-helper-info',
        'helper_version': BUNDLE_VERSION,
        'action': action,
        'status': status,
        'exit_code': exit_code,
        'args': sanitize_audit_args(args),
    }
    if details:
        event['details'] = str(details)[:500]
    line = (canonical_json(event) + '\n').encode()
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    flags |= getattr(os, 'O_CLOEXEC', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)

    # Append under a lock so concurrent helper calls cannot interleave records
    try:
        import fcntl

        file_id = os.open(fpath, flags, 0o600)
        try:
            fcntl.flock(file_id, fcntl.LOCK_EX)
            os.write(file_id, line)
            os.fsync(file_id)
        finally:
            os.close(file_id)
    except OSError as exc:
        raise HelperFailure(f'Cannot append protected audit log: {exc}') from exc
    return event
