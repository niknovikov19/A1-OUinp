import hashlib
import json
from datetime import datetime, timedelta
import os
from pathlib import Path, PurePosixPath
import re
import stat

from hpc_job import (
    HpcJobValidationError,
    canonical_json,
    validate_git_commit,
    validate_repo_path,
    validate_run_id,
    validate_safe_name,
)


SHA256_RE = re.compile(r'[0-9a-f]{64}')
SLURM_TERMINAL_STATES = {
    'BOOT_FAIL',
    'CANCELLED',
    'COMPLETED',
    'DEADLINE',
    'FAILED',
    'NODE_FAIL',
    'OUT_OF_MEMORY',
    'PREEMPTED',
    'REVOKED',
    'TIMEOUT',
}
MAX_RECORD_BYTES = 65536
MAX_CHILD_LINE_BYTES = 4096


class HpcJobLifecycleError(ValueError):
    """Represent an invalid top-level job lifecycle record or transition."""


def _require_mapping(value, label):
    """Return a mapping or reject it."""
    if not isinstance(value, dict):
        raise HpcJobLifecycleError(f'{label} must be an object')
    return value


def _require_exact_keys(value, required, label):
    """Reject missing or unknown mapping keys."""
    if set(value) != set(required):
        raise HpcJobLifecycleError(f'Invalid {label} keys')


def _validate_sha256(value, label):
    """Validate one lowercase SHA256 digest."""
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise HpcJobLifecycleError(f'Invalid {label}')
    return value


def _validate_positive_int(value, label):
    """Validate one positive integer while rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HpcJobLifecycleError(f'Invalid {label}')
    return value


def _validate_absolute_path(value, label):
    """Validate one normalized absolute path."""
    if not isinstance(value, str) or not value:
        raise HpcJobLifecycleError(f'Invalid {label}')
    fpath = Path(value)
    valid = fpath.is_absolute() and '..' not in fpath.parts
    if not valid or value != fpath.as_posix():
        raise HpcJobLifecycleError(f'Invalid {label}')
    return fpath


def _validate_timestamp(value, label):
    """Validate one bounded non-empty UTC timestamp string."""
    valid = isinstance(value, str) and 1 <= len(value) <= 64
    if not valid or not (value.endswith('Z') or value.endswith('+00:00')):
        raise HpcJobLifecycleError(f'Invalid {label}')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise HpcJobLifecycleError(f'Invalid {label}') from exc
    if parsed.utcoffset() != timedelta(0):
        raise HpcJobLifecycleError(f'Invalid {label}')
    return value


def _validate_prepared_paths(record):
    """Validate fixed paths derived from one prepared run directory."""
    run_dir = _validate_absolute_path(record['job_run_dir'], 'job-run path')
    run_id = validate_run_id(record['run_id'])
    expected_tail = ('hpc_jobs', 'runs', run_id)
    if run_dir.parts[-3:] != expected_tail:
        raise HpcJobLifecycleError('Job-run path does not match run ID')
    expected = {
        'submit_script': run_dir / 'submit.sh',
        'stdout_path': run_dir / 'slurm-%j.out',
        'stderr_path': run_dir / 'slurm-%j.err',
    }
    for key, fpath in expected.items():
        actual = _validate_absolute_path(record[key], key.replace('_', ' '))
        if actual != fpath:
            raise HpcJobLifecycleError(f'{key} does not match job-run path')
    return run_dir


def validate_prepared_record(record):
    """Validate the lifecycle-relevant fields of one prepared job record."""
    record = _require_mapping(record, 'prepared record')
    required = {
        'schema_version',
        'request_id',
        'request_sha256',
        'run_id',
        'job_kind',
        'git_commit',
        'simulation_job_limit',
        'expected_result_path',
        'completion_files',
        'job_run_dir',
        'submit_script',
        'stdout_path',
        'stderr_path',
        'status',
        'rendered_script_sha256',
    }
    missing = required - set(record)
    if missing:
        raise HpcJobLifecycleError(f'Prepared record is missing: {sorted(missing)}')
    if record['schema_version'] != 1 or record['status'] != 'prepared':
        raise HpcJobLifecycleError('Invalid prepared record state')
    try:
        validate_safe_name(record['request_id'], 'request ID')
        validate_run_id(record['run_id'])
        validate_git_commit(record['git_commit'])
        validate_repo_path(record['expected_result_path'], 'expected result path')
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    _validate_sha256(record['request_sha256'], 'request SHA256')
    _validate_sha256(record['rendered_script_sha256'], 'script SHA256')
    _validate_positive_int(record['simulation_job_limit'], 'simulation-job limit')
    if record['job_kind'] not in {'single', 'batch', 'workflow'}:
        raise HpcJobLifecycleError('Invalid prepared job kind')
    completion_files = record['completion_files']
    if not isinstance(completion_files, list) or not completion_files:
        raise HpcJobLifecycleError('Invalid completion files')
    try:
        validated = [
            validate_repo_path(item, 'completion file')
            for item in completion_files
        ]
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    if len(validated) != len(set(validated)):
        raise HpcJobLifecycleError('Duplicate completion files')
    _validate_prepared_paths(record)
    return record


def require_exact_checkout(prepared, actual_commit, clean):
    """Require the checkout to remain clean at the prepared commit."""
    prepared = validate_prepared_record(prepared)
    try:
        actual_commit = validate_git_commit(actual_commit)
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    if actual_commit != prepared['git_commit']:
        raise HpcJobLifecycleError('Checkout commit differs from prepared commit')
    if clean is not True:
        raise HpcJobLifecycleError('Checkout is not clean')
    return actual_commit


def get_submission_binding(prepared):
    """Return immutable fields shared by intent and receipt records."""
    prepared = validate_prepared_record(prepared)
    return {
        'schema_version': 1,
        'run_id': prepared['run_id'],
        'request_id': prepared['request_id'],
        'request_sha256': prepared['request_sha256'],
        'git_commit': prepared['git_commit'],
        'rendered_script_sha256': prepared['rendered_script_sha256'],
        'submit_script': prepared['submit_script'],
    }


def build_submission_intent(prepared, timestamp):
    """Build the durable record written before one scheduler call."""
    return {
        **get_submission_binding(prepared),
        'status': 'pending',
        'intent_at_utc': _validate_timestamp(timestamp, 'intent timestamp'),
    }


def validate_submission_record(record, prepared):
    """Validate one submission record against immutable prepared inputs."""
    record = _require_mapping(record, 'submission record')
    status_value = record.get('status')
    common = set(get_submission_binding(prepared)) | {'status', 'intent_at_utc'}
    status_keys = {
        'pending': common,
        'submitted': common | {'slurm_job_id', 'submitted_at_utc'},
        'unknown': common | {'reason', 'unknown_at_utc'},
    }
    if status_value not in status_keys:
        raise HpcJobLifecycleError('Invalid submission status')
    _require_exact_keys(record, status_keys[status_value], 'submission record')
    binding = get_submission_binding(prepared)
    if any(record[key] != value for key, value in binding.items()):
        raise HpcJobLifecycleError('Submission record binding differs')
    _validate_timestamp(record['intent_at_utc'], 'intent timestamp')
    if status_value == 'submitted':
        _validate_positive_int(record['slurm_job_id'], 'Slurm job ID')
        _validate_timestamp(record['submitted_at_utc'], 'submission timestamp')
    if status_value == 'unknown':
        reason = record['reason']
        if not isinstance(reason, str) or not reason or len(reason) > 500:
            raise HpcJobLifecycleError('Invalid unknown-submission reason')
        _validate_timestamp(record['unknown_at_utc'], 'unknown timestamp')
    return record


def decide_submission(current, prepared, timestamp):
    """Create one intent or return an existing receipt without resubmission."""
    if current is None:
        return build_submission_intent(prepared, timestamp), 'intent'
    current = validate_submission_record(current, prepared)
    if current['status'] == 'submitted':
        return current, 'existing'
    raise HpcJobLifecycleError(
        f'Submission is {current["status"]}; automatic retry is unsafe'
    )


def build_submission_receipt(intent, prepared, slurm_job_id, timestamp):
    """Replace one pending intent with its single successful receipt."""
    intent = validate_submission_record(intent, prepared)
    if intent['status'] != 'pending':
        raise HpcJobLifecycleError('Only a pending intent accepts a receipt')
    return {
        **intent,
        'status': 'submitted',
        'slurm_job_id': _validate_positive_int(slurm_job_id, 'Slurm job ID'),
        'submitted_at_utc': _validate_timestamp(timestamp, 'submission timestamp'),
    }


def build_unknown_submission(intent, prepared, reason, timestamp):
    """Mark an intent unsafe to retry when scheduler outcome is unknown."""
    intent = validate_submission_record(intent, prepared)
    if intent['status'] != 'pending':
        raise HpcJobLifecycleError('Only a pending intent can become unknown')
    if not isinstance(reason, str) or not reason or len(reason) > 500:
        raise HpcJobLifecycleError('Invalid unknown-submission reason')
    return {
        **intent,
        'status': 'unknown',
        'reason': reason,
        'unknown_at_utc': _validate_timestamp(timestamp, 'unknown timestamp'),
    }


def resolve_top_level_log_path(prepared, submission, stream):
    """Resolve one fixed top-level log path from its recorded Slurm ID."""
    prepared = validate_prepared_record(prepared)
    submission = validate_submission_record(submission, prepared)
    if submission['status'] != 'submitted':
        raise HpcJobLifecycleError('Logs require a submitted receipt')
    if stream not in {'stdout', 'stderr'}:
        raise HpcJobLifecycleError('Invalid top-level log stream')
    pattern = prepared[f'{stream}_path']
    if pattern.count('%j') != 1:
        raise HpcJobLifecycleError('Invalid top-level log pattern')
    resolved = Path(pattern.replace('%j', str(submission['slurm_job_id'])))
    run_dir = Path(prepared['job_run_dir'])
    if resolved.parent != run_dir:
        raise HpcJobLifecycleError('Resolved log path left the job-run directory')
    return resolved


def _validate_child_record(record, prepared):
    """Validate one repository-produced child-job record."""
    record = _require_mapping(record, 'child-job record')
    required = {
        'schema_version',
        'run_id',
        'child_key',
        'slurm_job_id',
        'stdout_path',
        'stderr_path',
    }
    _require_exact_keys(record, required, 'child-job record')
    if record['schema_version'] != 1 or record['run_id'] != prepared['run_id']:
        raise HpcJobLifecycleError('Child-job record belongs to another run')
    try:
        validate_safe_name(record['child_key'], 'child key')
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    _validate_positive_int(record['slurm_job_id'], 'child Slurm job ID')
    result_root = PurePosixPath(prepared['expected_result_path'])
    for key in ('stdout_path', 'stderr_path'):
        try:
            relpath = validate_repo_path(record[key], f'child {key}')
        except HpcJobValidationError as exc:
            raise HpcJobLifecycleError(str(exc)) from exc
        parts = PurePosixPath(relpath).parts
        prefix = result_root.parts
        if parts[:len(prefix)] != prefix or len(parts) <= len(prefix):
            raise HpcJobLifecycleError('Child log path left expected results')
    return record


def parse_child_records(payload, prepared):
    """Parse bounded JSONL child-job records under the prepared job limit."""
    prepared = validate_prepared_record(prepared)
    if not isinstance(payload, bytes) or len(payload) > MAX_RECORD_BYTES:
        raise HpcJobLifecycleError('Invalid child-record payload size')
    try:
        text = payload.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise HpcJobLifecycleError('Child records are not UTF-8') from exc
    lines = text.splitlines()
    if any(len(line.encode()) > MAX_CHILD_LINE_BYTES for line in lines):
        raise HpcJobLifecycleError('Child-job record line is too large')
    if prepared['job_kind'] == 'single' and lines:
        raise HpcJobLifecycleError('Single jobs cannot report child jobs')
    if len(lines) > prepared['simulation_job_limit']:
        raise HpcJobLifecycleError('Child-job count exceeds prepared limit')

    # Validate each JSONL entry and require stable unique identities
    records = []
    for line in lines:
        if not line:
            raise HpcJobLifecycleError('Child-job record line is empty')
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HpcJobLifecycleError('Invalid child-job JSON') from exc
        records.append(_validate_child_record(record, prepared))
    child_keys = [record['child_key'] for record in records]
    job_ids = [record['slurm_job_id'] for record in records]
    if len(child_keys) != len(set(child_keys)) or len(job_ids) != len(set(job_ids)):
        raise HpcJobLifecycleError('Duplicate child-job identity')
    return records


def resolve_child_log_path(prepared, child_records, child_key, stream):
    """Resolve one selected child log only from validated ingested records."""
    if stream not in {'stdout', 'stderr'}:
        raise HpcJobLifecycleError('Invalid child log stream')
    try:
        child_key = validate_safe_name(child_key, 'child key')
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    records = parse_child_records(
        b'\n'.join(canonical_json(record).encode() for record in child_records),
        prepared,
    )
    selected = [record for record in records if record['child_key'] == child_key]
    if len(selected) != 1:
        raise HpcJobLifecycleError('Unknown child key')
    run_dir = Path(prepared['job_run_dir'])
    repo_root = run_dir.parents[2]
    return repo_root / selected[0][f'{stream}_path']


def build_active_run_marker(prepared, timestamp):
    """Build the exact-commit marker that blocks checkout updates."""
    binding = get_submission_binding(prepared)
    return {
        'schema_version': 1,
        'status': 'active',
        'run_id': binding['run_id'],
        'request_sha256': binding['request_sha256'],
        'git_commit': binding['git_commit'],
        'rendered_script_sha256': binding['rendered_script_sha256'],
        'active_at_utc': _validate_timestamp(timestamp, 'active timestamp'),
    }


def validate_final_record(record, prepared):
    """Validate one terminal record against its prepared job."""
    record = _require_mapping(record, 'final record')
    required = set(get_submission_binding(prepared)) | {
        'status',
        'slurm_job_id',
        'scheduler_state',
        'completion_files_verified',
        'child_job_ids',
        'finalized_at_utc',
    }
    _require_exact_keys(record, required, 'final record')
    binding = get_submission_binding(prepared)
    if any(record[key] != value for key, value in binding.items()):
        raise HpcJobLifecycleError('Final record binding differs')
    state = record['scheduler_state']
    if state not in SLURM_TERMINAL_STATES:
        raise HpcJobLifecycleError('Final record is not terminal')
    expected_status = 'complete' if state == 'COMPLETED' else 'failed'
    if record['status'] != expected_status:
        raise HpcJobLifecycleError('Final status differs from scheduler state')
    _validate_positive_int(record['slurm_job_id'], 'Slurm job ID')
    _validate_timestamp(record['finalized_at_utc'], 'final timestamp')

    completion_files = record['completion_files_verified']
    if not isinstance(completion_files, list):
        raise HpcJobLifecycleError('Invalid verified completion files')
    expected = set(prepared['completion_files'])
    try:
        verified = {
            validate_repo_path(item, 'verified completion file')
            for item in completion_files
        }
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    if not verified <= expected:
        raise HpcJobLifecycleError('Unexpected verified completion file')
    if state == 'COMPLETED' and verified != expected:
        raise HpcJobLifecycleError('Complete run lacks declared result files')

    child_job_ids = record['child_job_ids']
    valid_ids = isinstance(child_job_ids, list) and all(
        isinstance(job_id, int) and not isinstance(job_id, bool) and job_id > 0
        for job_id in child_job_ids
    )
    if not valid_ids or len(child_job_ids) != len(set(child_job_ids)):
        raise HpcJobLifecycleError('Invalid final child-job IDs')
    if len(child_job_ids) > prepared['simulation_job_limit']:
        raise HpcJobLifecycleError('Final child-job count exceeds prepared limit')
    if prepared['job_kind'] == 'single' and child_job_ids:
        raise HpcJobLifecycleError('Single job has child-job IDs')
    return record


def build_final_record(
    prepared,
    submission,
    scheduler_state,
    present_completion_files,
    child_records,
    timestamp,
):
    """Build a terminal record from scheduler and declared-file evidence."""
    prepared = validate_prepared_record(prepared)
    submission = validate_submission_record(submission, prepared)
    if submission['status'] != 'submitted':
        raise HpcJobLifecycleError('Finalization requires a submitted receipt')
    if scheduler_state not in SLURM_TERMINAL_STATES:
        raise HpcJobLifecycleError('Scheduler state is not terminal')
    if not isinstance(present_completion_files, list):
        raise HpcJobLifecycleError('Invalid completion evidence')
    try:
        present = {
            validate_repo_path(item, 'completion evidence')
            for item in present_completion_files
        }
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    expected = set(prepared['completion_files'])
    missing = sorted(expected - present)
    if scheduler_state == 'COMPLETED' and missing:
        raise HpcJobLifecycleError('Completed job lacks declared result files')
    records = parse_child_records(
        b'\n'.join(canonical_json(record).encode() for record in child_records),
        prepared,
    )
    status_value = 'complete' if scheduler_state == 'COMPLETED' else 'failed'
    return {
        **get_submission_binding(prepared),
        'status': status_value,
        'slurm_job_id': submission['slurm_job_id'],
        'scheduler_state': scheduler_state,
        'completion_files_verified': sorted(expected & present),
        'child_job_ids': [record['slurm_job_id'] for record in records],
        'finalized_at_utc': _validate_timestamp(timestamp, 'final timestamp'),
    }


def release_active_run(active_marker, final_record, prepared, timestamp):
    """Validate one terminal run before explicitly releasing its commit lock."""
    prepared = validate_prepared_record(prepared)
    final_record = validate_final_record(final_record, prepared)
    active_marker = _require_mapping(active_marker, 'active-run marker')
    required = {
        'schema_version',
        'status',
        'run_id',
        'request_sha256',
        'git_commit',
        'rendered_script_sha256',
        'active_at_utc',
    }
    _require_exact_keys(active_marker, required, 'active-run marker')
    if active_marker['schema_version'] != 1 or active_marker['status'] != 'active':
        raise HpcJobLifecycleError('Invalid active-run marker state')
    try:
        validate_run_id(active_marker['run_id'])
        validate_git_commit(active_marker['git_commit'])
    except HpcJobValidationError as exc:
        raise HpcJobLifecycleError(str(exc)) from exc
    _validate_sha256(active_marker['request_sha256'], 'active request SHA256')
    _validate_sha256(
        active_marker['rendered_script_sha256'],
        'active script SHA256',
    )
    _validate_timestamp(active_marker['active_at_utc'], 'active timestamp')
    binding_keys = {
        'run_id',
        'request_sha256',
        'git_commit',
        'rendered_script_sha256',
    }
    if any(active_marker[key] != final_record.get(key) for key in binding_keys):
        raise HpcJobLifecycleError('Final record differs from active run')
    return {
        'schema_version': 1,
        'status': 'released',
        'run_id': active_marker['run_id'],
        'git_commit': active_marker['git_commit'],
        'released_at_utc': _validate_timestamp(timestamp, 'release timestamp'),
    }


def record_sha256(record):
    """Return one lifecycle record's canonical SHA256 digest."""
    return hashlib.sha256(canonical_json(record).encode()).hexdigest()


def read_state_record(fpath, label):
    """Read one bounded regular JSON state record without following symlinks."""
    fpath = Path(fpath)
    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    try:
        file_id = os.open(fpath, flags)
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot open {label}: {exc}') from exc
    try:
        file_stat = os.fstat(file_id)
        if not stat.S_ISREG(file_stat.st_mode):
            raise HpcJobLifecycleError(f'{label} must be a regular file')
        if file_stat.st_size > MAX_RECORD_BYTES:
            raise HpcJobLifecycleError(f'{label} is too large')
        chunks = []
        remaining = MAX_RECORD_BYTES + 1
        while remaining:
            chunk = os.read(file_id, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b''.join(chunks)
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot read {label}: {exc}') from exc
    finally:
        os.close(file_id)
    if len(payload) > MAX_RECORD_BYTES:
        raise HpcJobLifecycleError(f'{label} is too large')
    try:
        value = json.loads(payload.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HpcJobLifecycleError(f'Cannot read {label}: {exc}') from exc
    return _require_mapping(value, label)


def _require_state_parent(fpath):
    """Require an existing non-symlink state directory."""
    try:
        parent_stat = fpath.parent.lstat()
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot inspect state directory: {exc}') from exc
    valid = stat.S_ISDIR(parent_stat.st_mode) and not stat.S_ISLNK(parent_stat.st_mode)
    if not valid:
        raise HpcJobLifecycleError('State parent must be a real directory')


def create_state_record(fpath, record):
    """Create one mode-0600 state record without replacing existing evidence."""
    fpath = Path(fpath)
    _require_state_parent(fpath)
    payload = (canonical_json(record) + '\n').encode()
    if len(payload) > MAX_RECORD_BYTES:
        raise HpcJobLifecycleError('State record is too large')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        file_id = os.open(fpath, flags, 0o600)
    except FileExistsError as exc:
        raise HpcJobLifecycleError('State record already exists') from exc
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot create state record: {exc}') from exc
    try:
        os.fchmod(file_id, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(file_id, payload[offset:])
            if written < 1:
                raise OSError('State-record write made no progress')
            offset += written
        os.fsync(file_id)
    except OSError as exc:
        try:
            fpath.unlink()
        except OSError:
            pass
        raise HpcJobLifecycleError(f'Cannot write state record: {exc}') from exc
    finally:
        os.close(file_id)
    return record_sha256(record)


def replace_state_record(fpath, expected, replacement):
    """Atomically replace one state record only from its expected contents."""
    fpath = Path(fpath)
    current = read_state_record(fpath, 'state record')
    if canonical_json(current) != canonical_json(expected):
        raise HpcJobLifecycleError('State record changed before replacement')
    temp = fpath.with_name(f'.{fpath.name}.tmp-{os.getpid()}')
    try:
        create_state_record(temp, replacement)
        os.replace(temp, fpath)
    except Exception:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise
    return record_sha256(replacement)


def remove_state_record(fpath, expected):
    """Remove one state record only when its contents still match."""
    fpath = Path(fpath)
    current = read_state_record(fpath, 'state record')
    if canonical_json(current) != canonical_json(expected):
        raise HpcJobLifecycleError('State record changed before removal')
    try:
        fpath.unlink()
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot remove state record: {exc}') from exc
