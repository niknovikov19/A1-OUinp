import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from hpc_job import (
    validate_repo_path,
    validate_run_id,
    validate_safe_name,
)
from hpc_job_lifecycle import (
    validate_final_record,
    validate_prepared_record,
)


SHA256_LENGTH = 64


class HpcResultError(ValueError):
    """Represent invalid result inventory or retrieval data. """


def validate_artifact_types(value):
    """Validate the configured artifact-type suffix mapping. """
    if not isinstance(value, dict) or not value:
        raise HpcResultError('Artifact types must be a non-empty object')
    normalized = {}
    for artifact_type, suffixes in value.items():
        try:
            artifact_type = validate_safe_name(artifact_type, 'artifact type')
        except ValueError as exc:
            raise HpcResultError(str(exc)) from exc
        valid = (
            isinstance(suffixes, list) and suffixes and
            all(isinstance(item, str) and item.startswith('.') for item in suffixes)
        )
        if not valid:
            raise HpcResultError(f'Invalid suffixes for {artifact_type}')
        suffixes = [item.lower() for item in suffixes]
        if len(suffixes) != len(set(suffixes)):
            raise HpcResultError(f'Duplicate suffix for {artifact_type}')
        normalized[artifact_type] = suffixes
    all_suffixes = [item for suffixes in normalized.values() for item in suffixes]
    if len(all_suffixes) != len(set(all_suffixes)):
        raise HpcResultError('Artifact suffixes overlap')
    return normalized


def classify_artifact(relpath, artifact_types):
    """Return the configured type for one known output path. """
    suffix = PurePosixPath(relpath).suffix.lower()
    matches = [
        name for name, suffixes in artifact_types.items()
        if suffix in suffixes
    ]
    if len(matches) > 1:
        raise HpcResultError('Artifact type is ambiguous')
    return matches[0] if matches else None


def _open_known_file(repo_root, relpath):
    """Open one regular file beneath the repository without following links. """
    relpath = validate_repo_path(relpath, 'artifact path')
    repo_root = Path(repo_root)
    current = repo_root
    for part in PurePosixPath(relpath).parts[:-1]:
        current /= part
        try:
            current_stat = current.lstat()
        except OSError as exc:
            raise HpcResultError(f'Cannot inspect artifact parent: {exc}') from exc
        if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(current_stat.st_mode):
            raise HpcResultError('Artifact path contains a non-directory or symlink')
    fpath = repo_root / relpath
    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    try:
        file_id = os.open(fpath, flags)
    except OSError as exc:
        raise HpcResultError(f'Cannot open artifact: {exc}') from exc
    file_stat = os.fstat(file_id)
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(file_id)
        raise HpcResultError('Artifact must be a regular file')
    return file_id, file_stat


def _hash_file(file_id, size):
    """Hash one already-open bounded artifact. """
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        data = os.pread(file_id, min(65536, size - offset), offset)
        if not data:
            raise HpcResultError('Artifact changed while hashing')
        digest.update(data)
        offset += len(data)
    return digest.hexdigest()


def _known_outputs(prepared, child_records):
    """Return labels, parameters, and only previously declared outputs. """
    result_root = PurePosixPath(prepared['expected_result_path'])
    if prepared['job_kind'] == 'batch':
        return [
            (record['child_key'], record['parameters'], record['expected_outputs'])
            for record in child_records
        ]
    outputs = [
        (result_root / relpath).as_posix()
        for relpath in prepared['completion_files']
    ]
    return [('main', {}, outputs)]


def build_result_inventory(repo_root, prepared, final, child_records,
                           artifact_types, limits, generated_at_utc):
    """Build one bounded inventory from finalized declared outputs. """
    prepared = validate_prepared_record(prepared)
    final = validate_final_record(final, prepared)
    if final['status'] != 'complete':
        raise HpcResultError('Only a complete run can be inventoried')
    artifact_types = validate_artifact_types(artifact_types)
    max_artifacts = limits['max_artifacts']
    checksum_max_bytes = limits['checksum_max_bytes']
    result_root = PurePosixPath(prepared['expected_result_path'])
    verified = {
        (result_root / relpath).as_posix()
        for relpath in final['completion_files_verified']
    }

    # Inspect only output paths recorded by the completed run
    artifacts = []
    known_output_count = 0
    for child_key, parameters, outputs in _known_outputs(prepared, child_records):
        child_key = validate_safe_name(child_key, 'child key')
        for relpath in outputs:
            relpath = validate_repo_path(relpath, 'artifact path')
            if relpath not in verified:
                raise HpcResultError('Child output lacks finalization evidence')
            known_output_count += 1
            artifact_type = classify_artifact(relpath, artifact_types)
            if artifact_type is None:
                continue
            if len(artifacts) >= max_artifacts:
                raise HpcResultError('Artifact count exceeds configured limit')
            file_id, file_stat = _open_known_file(repo_root, relpath)
            try:
                checksum = None
                if file_stat.st_size <= checksum_max_bytes:
                    checksum = _hash_file(file_id, file_stat.st_size)
            finally:
                os.close(file_id)
            artifacts.append({
                'child_key': child_key,
                'parameters': parameters,
                'artifact_type': artifact_type,
                'relative_path': relpath,
                'size_bytes': file_stat.st_size,
                'mtime_ns': file_stat.st_mtime_ns,
                'sha256': checksum,
            })

    # Require unambiguous selection by the public three-part key
    keys = [
        (item['child_key'], item['artifact_type'])
        for item in artifacts
    ]
    if len(keys) != len(set(keys)):
        raise HpcResultError('Child has multiple artifacts of one type')
    return {
        'schema_version': 1,
        'run_id': prepared['run_id'],
        'git_commit': prepared['git_commit'],
        'expected_result_path': prepared['expected_result_path'],
        'generated_at_utc': generated_at_utc,
        'known_output_count': known_output_count,
        'artifact_count': len(artifacts),
        'artifacts': artifacts,
    }


def validate_result_inventory(value, prepared):
    """Validate one persisted inventory against its prepared run. """
    required = {
        'schema_version', 'run_id', 'git_commit', 'expected_result_path',
        'generated_at_utc', 'known_output_count', 'artifact_count', 'artifacts',
    }
    if not isinstance(value, dict) or set(value) != required:
        raise HpcResultError('Invalid inventory keys')
    if value['schema_version'] != 1:
        raise HpcResultError('Invalid inventory schema version')
    binding = {
        'run_id': prepared['run_id'],
        'git_commit': prepared['git_commit'],
        'expected_result_path': prepared['expected_result_path'],
    }
    if any(value[key] != expected for key, expected in binding.items()):
        raise HpcResultError('Inventory binding differs from prepared run')
    counts = (value['known_output_count'], value['artifact_count'])
    valid_counts = all(
        isinstance(item, int) and not isinstance(item, bool) and item >= 0
        for item in counts
    )
    if not valid_counts or not isinstance(value['artifacts'], list):
        raise HpcResultError('Invalid inventory counts')
    if value['artifact_count'] != len(value['artifacts']):
        raise HpcResultError('Inventory artifact count differs')
    if value['known_output_count'] < value['artifact_count']:
        raise HpcResultError('Inventory output count differs')
    result_root = PurePosixPath(prepared['expected_result_path']).parts
    keys = []
    for item in value['artifacts']:
        item_required = {
            'child_key', 'parameters', 'artifact_type', 'relative_path',
            'size_bytes', 'mtime_ns', 'sha256',
        }
        if not isinstance(item, dict) or set(item) != item_required:
            raise HpcResultError('Invalid inventory artifact')
        validate_safe_name(item['child_key'], 'child key')
        validate_safe_name(item['artifact_type'], 'artifact type')
        validate_repo_path(item['relative_path'], 'artifact path')
        if not isinstance(item['parameters'], dict):
            raise HpcResultError('Invalid artifact parameters')
        if PurePosixPath(item['relative_path']).parts[:len(result_root)] != result_root:
            raise HpcResultError('Inventory artifact left expected results')
        for key in ('size_bytes', 'mtime_ns'):
            if isinstance(item[key], bool) or not isinstance(item[key], int):
                raise HpcResultError(f'Invalid artifact {key}')
            if item[key] < 0:
                raise HpcResultError(f'Invalid artifact {key}')
        checksum = item['sha256']
        valid_checksum = checksum is None or (
            isinstance(checksum, str) and len(checksum) == SHA256_LENGTH and
            all(char in '0123456789abcdef' for char in checksum)
        )
        if not valid_checksum:
            raise HpcResultError('Invalid artifact checksum')
        keys.append((item['child_key'], item['artifact_type']))
    if len(keys) != len(set(keys)):
        raise HpcResultError('Duplicate inventory selection key')
    return value


def select_artifact(inventory, child_key, artifact_type):
    """Select exactly one artifact without accepting a path. """
    try:
        child_key = validate_safe_name(child_key, 'child key')
        artifact_type = validate_safe_name(artifact_type, 'artifact type')
    except ValueError as exc:
        raise HpcResultError(str(exc)) from exc
    selected = [
        item for item in inventory['artifacts']
        if item['child_key'] == child_key and item['artifact_type'] == artifact_type
    ]
    if len(selected) != 1:
        raise HpcResultError('Unknown child key or artifact type')
    return selected[0]


def read_inventory_artifact(repo_root, artifact, max_bytes):
    """Read one selected artifact if its recorded fingerprint still matches. """
    if artifact['size_bytes'] > max_bytes:
        raise HpcResultError('Artifact exceeds the transfer limit')
    if artifact['sha256'] is None:
        raise HpcResultError('Artifact has no bounded-transfer checksum')
    file_id, file_stat = _open_known_file(repo_root, artifact['relative_path'])
    try:
        if file_stat.st_size != artifact['size_bytes']:
            raise HpcResultError('Artifact size changed after inventory')
        if file_stat.st_mtime_ns != artifact['mtime_ns']:
            raise HpcResultError('Artifact modification time changed after inventory')
        data = os.pread(file_id, file_stat.st_size + 1, 0)
    finally:
        os.close(file_id)
    if len(data) != file_stat.st_size:
        raise HpcResultError('Artifact changed while reading')
    if hashlib.sha256(data).hexdigest() != artifact['sha256']:
        raise HpcResultError('Artifact checksum changed after inventory')
    return data
