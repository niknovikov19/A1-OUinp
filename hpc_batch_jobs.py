import ast
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path

from hpc_job import (
    canonical_json,
    normalize_json,
    validate_repo_path,
    validate_run_id,
    validate_safe_name,
)
from hpc_job_control import parse_sbatch_result


MAX_INDEX_BYTES = 65536
MAX_INDEX_LINE_BYTES = 4096


class HpcBatchJobError(ValueError):
    """Represent invalid BatchTools submission evidence. """


def decode_batch_parameters(environment, parameter_names):
    """Recover selected BatchTools coordinates from its encoded environment. """
    selected = set(parameter_names)
    parameters = {}
    for env_name, assignment in environment.items():
        if 'RUNTK' not in env_name or '*=' not in assignment:
            continue
        name, value = assignment.split('*=', 1)
        if name not in selected:
            continue
        value_type = env_name.split('RUNTK', 1)[0]
        if value_type == 'STR':
            decoded = value
        else:
            try:
                decoded = ast.literal_eval(value)
            except (SyntaxError, ValueError) as exc:
                raise HpcBatchJobError(
                    f'Cannot decode BatchTools parameter: {name}'
                ) from exc
        parameters[name] = normalize_json(decoded)
    if set(parameters) != selected:
        missing = sorted(selected - set(parameters))
        raise HpcBatchJobError(f'Missing BatchTools parameters: {missing}')
    canonical_json(parameters)
    return parameters


def parse_child_sbatch_result(completed):
    """Return one child Slurm ID from a successful bounded sbatch result. """
    if completed.returncode != 0:
        details = completed.stderr.replace('\r', ' ').replace('\n', ' ').strip()
        raise HpcBatchJobError(
            f'Child sbatch exited {completed.returncode}: {details[:500]}'
        )
    if len(completed.stdout.encode()) > 65536:
        raise HpcBatchJobError('Child sbatch output is too large')
    try:
        return parse_sbatch_result(completed.stdout)
    except ValueError as exc:
        raise HpcBatchJobError(str(exc)) from exc


def build_child_record(run_id, child_key, slurm_job_id, parameters,
                       job_dir, expected_outputs):
    """Build one durable child-job submission record. """
    run_id = validate_run_id(run_id)
    child_key = validate_safe_name(child_key, 'child key')
    valid_id = isinstance(slurm_job_id, int) and not isinstance(slurm_job_id, bool)
    if not valid_id or slurm_job_id < 1:
        raise HpcBatchJobError('Invalid child Slurm job ID')
    if not isinstance(parameters, dict) or not parameters:
        raise HpcBatchJobError('Invalid child parameters')
    job_dir = validate_repo_path(job_dir, 'child job directory')
    expected_outputs = [
        validate_repo_path(path, 'child expected output')
        for path in expected_outputs
    ]
    if not expected_outputs or len(expected_outputs) != len(set(expected_outputs)):
        raise HpcBatchJobError('Invalid child expected outputs')
    record = {
        'schema_version': 1,
        'run_id': run_id,
        'child_key': child_key,
        'slurm_job_id': slurm_job_id,
        'parameters': normalize_json(parameters),
        'stdout_path': f'{job_dir}/{child_key}.run',
        'stderr_path': f'{job_dir}/{child_key}.err',
        'expected_outputs': expected_outputs,
        'submitted_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    data = canonical_json(record).encode()
    if len(data) > MAX_INDEX_LINE_BYTES:
        raise HpcBatchJobError('Child-job record is too large')
    return record


def append_child_record(fpath, record):
    """Append one unique child record while holding an exclusive file lock. """
    fpath = Path(fpath)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT
    flags |= getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    file_id = os.open(fpath, flags, 0o600)
    try:
        fcntl.flock(file_id, fcntl.LOCK_EX)
        os.fchmod(file_id, 0o600)
        file_stat = os.fstat(file_id)
        if file_stat.st_size > MAX_INDEX_BYTES:
            raise HpcBatchJobError('Child-job index is too large')
        os.lseek(file_id, 0, os.SEEK_SET)
        payload = os.read(file_id, MAX_INDEX_BYTES + 1)

        # Reject duplicate identities before one locked append
        for line in payload.splitlines():
            try:
                existing = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HpcBatchJobError('Child-job index is invalid') from exc
            duplicate = (
                existing.get('child_key') == record['child_key'] or
                existing.get('slurm_job_id') == record['slurm_job_id']
            )
            if duplicate:
                raise HpcBatchJobError('Duplicate child-job identity')
        data = canonical_json(record).encode() + b'\n'
        if len(payload) + len(data) > MAX_INDEX_BYTES:
            raise HpcBatchJobError('Child-job index would exceed its limit')
        written = os.write(file_id, data)
        if written != len(data):
            raise HpcBatchJobError('Child-job record append was incomplete')
        os.fsync(file_id)
    finally:
        os.close(file_id)
