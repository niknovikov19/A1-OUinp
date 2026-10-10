import os
from pathlib import Path
import re
import stat

from hpc_job import validate_repo_path
from hpc_job_lifecycle import (
    HpcJobLifecycleError,
    SLURM_TERMINAL_STATES,
    validate_prepared_record,
)


IDENTITY_RE = re.compile(r'[0-9]+:[0-9]+')
SBATCH_RESULT_RE = re.compile(r'([1-9][0-9]*)(?:;[A-Za-z0-9_.-]+)?')


def validate_cursor(cursor, label):
    """Validate one optional incremental-log cursor."""
    if cursor is None:
        return None
    required = {'identity', 'offset'}
    if not isinstance(cursor, dict) or set(cursor) != required:
        raise HpcJobLifecycleError(f'Invalid {label} cursor')
    identity = cursor['identity']
    offset = cursor['offset']
    valid_offset = isinstance(offset, int) and not isinstance(offset, bool)
    if not isinstance(identity, str) or IDENTITY_RE.fullmatch(identity) is None:
        raise HpcJobLifecycleError(f'Invalid {label} cursor identity')
    if not valid_offset or offset < 0:
        raise HpcJobLifecycleError(f'Invalid {label} cursor offset')
    return cursor


def parse_sbatch_result(value):
    """Parse one bounded `sbatch --parsable` result."""
    if not isinstance(value, str):
        raise HpcJobLifecycleError('Invalid sbatch result')
    value = value.strip()
    match = SBATCH_RESULT_RE.fullmatch(value)
    if match is None:
        raise HpcJobLifecycleError('Invalid sbatch result')
    return int(match.group(1))


def validate_scheduler_job(value, expected_job_id):
    """Validate one normalized A5 scheduler result for a known job."""
    required = {
        'accounting_gap',
        'exit_code',
        'job_id',
        'normalized_state',
        'raw_state',
        'reason',
        'retry_after_sec',
        'source',
    }
    if not isinstance(value, dict) or set(value) != required:
        raise HpcJobLifecycleError('Invalid scheduler result')
    if value['job_id'] != expected_job_id:
        raise HpcJobLifecycleError('Scheduler result has another job ID')
    if value['source'] not in {'squeue', 'sacct', 'missing'}:
        raise HpcJobLifecycleError('Invalid scheduler result source')
    for key in ('raw_state', 'normalized_state', 'reason', 'exit_code'):
        if not isinstance(value[key], str):
            raise HpcJobLifecycleError(f'Invalid scheduler {key}')
    if not isinstance(value['accounting_gap'], bool):
        raise HpcJobLifecycleError('Invalid scheduler accounting gap')
    retry = value['retry_after_sec']
    valid_retry = retry is None or (
        isinstance(retry, int) and not isinstance(retry, bool) and retry > 0
    )
    if not valid_retry:
        raise HpcJobLifecycleError('Invalid scheduler retry interval')
    return value


def get_terminal_scheduler_state(job):
    """Return a supported terminal Slurm token or reject nonterminal state."""
    job = validate_scheduler_job(job, job.get('job_id'))
    token = job['raw_state'].strip().split(maxsplit=1)[0].rstrip('+').upper()
    if token not in SLURM_TERMINAL_STATES:
        raise HpcJobLifecycleError('Scheduler state is not terminal')
    return token


def missing_stream():
    """Return one empty result for a log file not created yet."""
    return {
        'status': 'missing',
        'identity': None,
        'size': 0,
        'mtime_ns': None,
        'start_offset': 0,
        'end_offset': 0,
        'byte_count': 0,
        'content': '',
        'line_count': 0,
        'more_available': False,
        'limit_reason': None,
        'reset_reason': None,
    }


def _start_offset(cursor, identity, size):
    """Choose one safe starting offset for a current log file."""
    if cursor is None:
        return 0, 'initial'
    if cursor['identity'] != identity:
        return 0, 'replaced'
    if cursor['offset'] > size:
        return 0, 'truncated'
    return cursor['offset'], None


def _limit_lines(data, start, size, max_lines):
    """Apply the line cap after the byte cap."""
    line_count = 0
    cut = None
    for index, value in enumerate(data):
        if value != 10:
            continue
        line_count += 1
        if line_count == max_lines:
            cut = index + 1
            break
    limit_reason = None
    if cut is not None and cut < len(data):
        data = data[:cut]
        limit_reason = 'lines'
    end = start + len(data)
    more_available = end < size
    if more_available and limit_reason is None:
        limit_reason = 'bytes'
    return data, end, more_available, limit_reason


def read_log_stream(fpath, cursor, max_bytes, max_lines):
    """Read one bounded incremental chunk from an exact recorded log path."""
    cursor = validate_cursor(cursor, 'log')
    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    try:
        file_id = os.open(fpath, flags)
    except FileNotFoundError:
        return missing_stream()
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot open job log: {exc}') from exc
    try:
        file_stat = os.fstat(file_id)
        if not stat.S_ISREG(file_stat.st_mode):
            raise HpcJobLifecycleError('Job log must be a regular file')
        identity = f'{file_stat.st_dev}:{file_stat.st_ino}'
        start, reset_reason = _start_offset(
            cursor,
            identity,
            file_stat.st_size,
        )
        data = os.pread(file_id, max_bytes, start)
        file_stat = os.fstat(file_id)
        if file_stat.st_size < start:
            start = 0
            reset_reason = 'truncated'
            data = os.pread(file_id, max_bytes, start)
            file_stat = os.fstat(file_id)
    except OSError as exc:
        raise HpcJobLifecycleError(f'Cannot read job log: {exc}') from exc
    finally:
        os.close(file_id)
    data, end, more_available, limit_reason = _limit_lines(
        data,
        start,
        file_stat.st_size,
        max_lines,
    )
    content = data.decode('utf-8', errors='replace')
    line_count = data.count(b'\n')
    if data and not data.endswith(b'\n'):
        line_count += 1
    return {
        'status': 'ok',
        'identity': identity,
        'size': file_stat.st_size,
        'mtime_ns': file_stat.st_mtime_ns,
        'start_offset': start,
        'end_offset': end,
        'byte_count': len(data),
        'content': content,
        'line_count': line_count,
        'more_available': more_available,
        'limit_reason': limit_reason,
        'reset_reason': reset_reason,
    }


def find_completion_files(repo_root, prepared):
    """Return declared completion files that exist below the expected result."""
    prepared = validate_prepared_record(prepared)
    repo_root = Path(repo_root)
    result_relpath = validate_repo_path(
        prepared['expected_result_path'],
        'expected result path',
    )
    result_root = repo_root / result_relpath
    if result_root.is_symlink():
        raise HpcJobLifecycleError('Result directory cannot be a symlink')
    if not result_root.exists():
        return []
    if not result_root.is_dir():
        raise HpcJobLifecycleError('Result destination is not a directory')

    # Reject symlinks from exp_results through the result directory
    current = repo_root / 'exp_results'
    for part in Path(result_relpath).parts[1:]:
        if current.is_symlink():
            raise HpcJobLifecycleError('Result path contains a symlink')
        current /= part
    present = []
    for relpath in prepared['completion_files']:
        fpath = result_root / relpath
        current = result_root
        for part in Path(relpath).parts:
            if current.is_symlink():
                raise HpcJobLifecycleError('Completion path contains a symlink')
            current /= part
        try:
            file_stat = fpath.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HpcJobLifecycleError(
                f'Cannot inspect completion file: {exc}'
            ) from exc
        if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
            raise HpcJobLifecycleError('Completion file must be regular')
        present.append(relpath)
    return present
