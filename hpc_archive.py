import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile

from hpc_job import canonical_json, validate_repo_path
from hpc_result import HpcResultError, _open_known_file


MAX_ARCHIVE_BYTES = 1024 ** 3
MAX_ARCHIVE_FILES = 4096
MAX_MANIFEST_BYTES = 4 * 1024 ** 2
MANIFEST_NAME = 'archive_manifest.json'


def compact_path(value):
    """Accept only the fixed compact-result profile beneath a run's result root. """
    try:
        path = PurePosixPath(validate_repo_path(value, 'compact result path'))
    except ValueError as exc:
        raise HpcResultError(str(exc)) from exc
    if str(path) == 'jobs/index.jsonl':
        return str(path)
    if len(path.parts) != 2:
        raise HpcResultError('Compact artifact must be directly beneath an allowed directory')
    suffixes = {'cfg': '.json', 'results': '.json', 'rvec_xr': '.nc', 'hvec_xr': '.nc'}
    if path.parts[0] not in suffixes or path.suffix != suffixes[path.parts[0]]:
        raise HpcResultError('Artifact is outside the compact-result profile')
    return str(path)


def hash_path(path):
    """Hash one regular local file in bounded chunks without following a symlink. """
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise HpcResultError('Archive must be a regular file')
    digest = hashlib.sha256()
    with os.fdopen(descriptor, 'rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


class HashingReader:
    """Hash bytes as the archive consumes an already-open source file. """

    def __init__(self, stream):
        """Keep one source stream and its running digest. """
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size):
        """Read and hash the next archive payload chunk. """
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def file_fingerprint(info):
    """Return identity, size, and timestamps used to detect changing source files. """
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def build_archive(repo_root, prepared, final, destination):
    """Archive only finalized compact outputs, hashing each source during packing. """
    if final['status'] != 'complete':
        raise HpcResultError('Only complete runs can be archived')
    selected = []
    required = final.get('completion_files_required', prepared['completion_files'])
    for relative in required:
        try:
            selected.append(compact_path(relative))
        except HpcResultError:
            continue
    if not selected or len(selected) > MAX_ARCHIVE_FILES or len(set(selected)) != len(selected):
        raise HpcResultError('Invalid compact archive file count')
    if not set(selected) <= set(final['completion_files_verified']):
        raise HpcResultError('Archive source lacks finalization evidence')
    result_root = PurePosixPath(prepared['expected_result_path'])
    manifest = {key: prepared[key] for key in ('run_id', 'git_commit', 'expected_result_path')}
    manifest.update({'schema_version': 1, 'files': [], 'total_bytes': 0})

    # Read exact declared files once without scanning or archiving large raw results
    try:
        with tarfile.open(destination, 'w:gz') as archive:
            for relative in selected:
                source = str(result_root / relative)
                descriptor, before = _open_known_file(repo_root, source)
                if manifest['total_bytes'] + before.st_size > MAX_ARCHIVE_BYTES:
                    os.close(descriptor)
                    raise HpcResultError('Compact source bytes exceed the archive limit')
                with os.fdopen(descriptor, 'rb') as stream:
                    reader = HashingReader(stream)
                    member = tarfile.TarInfo(relative)
                    member.size = before.st_size
                    member.mode = 0o600
                    archive.addfile(member, reader)
                    after = os.fstat(stream.fileno())
                if file_fingerprint(before) != file_fingerprint(after):
                    raise HpcResultError('Archive source changed during packing')
                manifest['files'].append({'path': relative, 'hpc_path': str(Path(repo_root) / source),
                                          'size_bytes': before.st_size, 'sha256': reader.digest.hexdigest()})
                manifest['total_bytes'] += before.st_size
            payload = canonical_json(manifest).encode()
            if len(payload) > MAX_MANIFEST_BYTES:
                raise HpcResultError('Archive manifest is too large')
            member = tarfile.TarInfo(MANIFEST_NAME)
            member.size = len(payload)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(payload))
    except (OSError, tarfile.TarError) as exc:
        raise HpcResultError(f'Cannot build compact archive: {exc}') from exc
    size = Path(destination).stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise HpcResultError('Compressed archive exceeds transfer limit')
    return {**{key: manifest[key] for key in ('run_id', 'git_commit', 'expected_result_path', 'total_bytes')},
            'size_bytes': size, 'sha256': hash_path(destination), 'file_count': len(selected),
            'manifest_sha256': hashlib.sha256(payload).hexdigest()}


def read_archive(path, metadata, destination=None):
    """Verify archive checksums and optionally unpack regular compact files safely. """
    if not 0 < metadata['size_bytes'] <= MAX_ARCHIVE_BYTES:
        raise HpcResultError('Invalid archive size')
    if Path(path).stat().st_size != metadata['size_bytes'] or hash_path(path) != metadata['sha256']:
        raise HpcResultError('Archive size or checksum differs')
    collected, manifest, total = {}, None, 0
    try:
        with tarfile.open(path, 'r|gz') as archive:
            for member in archive:
                if not member.isreg() or member.name in collected:
                    raise HpcResultError('Archive has duplicate or non-regular members')
                if member.name == MANIFEST_NAME:
                    if manifest is not None or not 0 <= member.size <= MAX_MANIFEST_BYTES:
                        raise HpcResultError('Invalid archive manifest')
                    payload = archive.extractfile(member).read(MAX_MANIFEST_BYTES + 1)
                    if hashlib.sha256(payload).hexdigest() != metadata['manifest_sha256']:
                        raise HpcResultError('Archive manifest checksum differs')
                    manifest = json.loads(payload.decode())
                    continue
                relative = compact_path(member.name)
                total += member.size
                if member.size < 0 or total > MAX_ARCHIVE_BYTES or len(collected) >= MAX_ARCHIVE_FILES:
                    raise HpcResultError('Archive contents exceed limits')
                digest = hashlib.sha256()
                target = None
                if destination is not None:
                    fpath = Path(destination) / relative
                    fpath.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    target = open(fpath, 'xb')
                try:
                    stream = archive.extractfile(member)
                    for chunk in iter(lambda: stream.read(65536), b''):
                        digest.update(chunk)
                        if target is not None:
                            target.write(chunk)
                finally:
                    if target is not None:
                        target.close()
                collected[relative] = (member.size, digest.hexdigest())
    except (OSError, ValueError, tarfile.TarError) as exc:
        raise HpcResultError(f'Cannot read compact archive: {exc}') from exc
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise HpcResultError('Missing or invalid archive manifest')
    for key in ('run_id', 'git_commit', 'expected_result_path', 'total_bytes'):
        if manifest.get(key) != metadata[key]:
            raise HpcResultError('Archive manifest binding differs')
    entries = manifest.get('files')
    if not isinstance(entries, list) or len(entries) != metadata['file_count'] or total != metadata['total_bytes']:
        raise HpcResultError('Archive manifest counts differ')
    if any(not isinstance(item, dict) or not {'path', 'size_bytes', 'sha256', 'hpc_path'} <= set(item)
           for item in entries):
        raise HpcResultError('Invalid archive manifest file entries')
    expected = {item['path']: (item['size_bytes'], item['sha256']) for item in entries}
    if len(expected) != len(entries) or collected != expected:
        raise HpcResultError('Archived file checksums differ from manifest')
    if destination is not None:
        (Path(destination) / MANIFEST_NAME).write_text(canonical_json(manifest) + '\n')
    return manifest


def unpack_archive(path, metadata, destination):
    """Unpack verified data into a fresh directory without replacing existing files. """
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise HpcResultError('Unpack destination already exists; existing data were preserved')
    with tempfile.TemporaryDirectory(prefix='.compact-', dir=destination.parent) as temporary:
        read_archive(path, metadata, temporary)
        if destination.exists() or destination.is_symlink():
            raise HpcResultError('Unpack destination appeared during verification')
        os.rename(temporary, destination)
    return destination


def verify_unpacked(destination, manifest):
    """Check an existing unpacked cache without replacing user-modified files. """
    for item in manifest['files']:
        relative = compact_path(item['path'])
        descriptor, info = _open_known_file(destination, relative)
        with os.fdopen(descriptor, 'rb') as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(65536), b''):
                digest.update(chunk)
        if info.st_size != item['size_bytes'] or digest.hexdigest() != item['sha256']:
            raise HpcResultError('Existing unpacked cache differs; files were preserved')
