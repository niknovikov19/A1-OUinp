import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import grp
import stat
import subprocess
import tempfile


SOURCE_ROOT = 'dev_scratch/hpc/helper_src'
SHARED = ['hpc_archive.py', 'hpc_bounded.py', 'hpc_job.py', 'hpc_job_lifecycle.py', 'hpc_result.py']


def git(repo, *arguments):
    """Read a fixed repository's exact committed promotion sources. """
    command = ['git', '-c', f'safe.directory={repo}', '-C', str(repo), *arguments]
    return subprocess.check_output(command)


def plans(site):
    """Return the fixed destination mapping for one protected helper installation. """
    if site == 'local':
        root = Path('/opt/a1-hpc')
        mappings = [(f'{SOURCE_ROOT}/local/{name}', root / 'bin' / name, 0o555)
                    for name in ('hpc-job', 'hpc-result', 'hpc-status')]
        mappings.append((f'{SOURCE_ROOT}/local/hpc_common.py', root / 'bin/hpc_common.py', 0o444))
        mappings += [(name, root / 'bin' / name, 0o444) for name in SHARED]
        return root, mappings, [root / 'bin']
    root = Path('/ddn/niknovikov19/hpc_codex')
    mappings = []
    for host, names in (('lethe', ('hpc-lethe-job', 'hpc-lethe-result', 'hpc-lethe-status')),
                        ('grid', ('hpc-grid-job', 'hpc-grid-status'))):
        mappings += [(f'{SOURCE_ROOT}/remote_{host}/{name}', root / 'helpers' / host / name, 0o555)
                     for name in names]
        modules = SHARED if host == 'lethe' else ['hpc_bounded.py', 'hpc_job.py', 'hpc_job_lifecycle.py']
        mappings += [(name, root / 'helpers' / host / name, 0o444) for name in modules]
    mappings.append((f'{SOURCE_ROOT}/config_examples/remote-hpc-status.json.example',
                     root / 'config/A1_OUinp-status.json', 0o444))
    return root, mappings, [root / 'helpers/lethe', root / 'helpers/grid', root / 'config']


def regular(path):
    """Require an existing non-symlink regular installation artifact. """
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'Not a regular file: {path}')


def main():
    """Install only hash-pinned committed sources during the user's Gate-B promotion. """
    parser = argparse.ArgumentParser()
    parser.add_argument('site', choices=['local', 'lethe'])
    parser.add_argument('commit')
    args = parser.parse_args()
    import re
    if re.fullmatch(r'[0-9a-f]{40}', args.commit) is None:
        raise ValueError('Expected a full lowercase commit hash')
    repo = Path('/home/nnovikov/repo/A1-OUinp' if args.site == 'local'
                else '/ddn/niknovikov19/repo/A1_OUinp_codex')
    if args.site == 'local' and os.geteuid() != 0:
        raise ValueError('The local promotion requires sudo')
    if args.site == 'lethe' and pwd.getpwuid(os.geteuid()).pw_name != 'niknovikov19':
        raise ValueError('The remote promotion requires niknovikov19')
    if git(repo, 'rev-parse', 'HEAD').decode().strip() != args.commit:
        raise ValueError('Checkout HEAD differs from the reviewed commit')
    if git(repo, 'branch', '--show-current').decode().strip() != 'codex-hpc':
        raise ValueError('Unexpected automation branch')
    if args.site == 'lethe' and git(repo, 'status', '--porcelain=v1').strip():
        raise ValueError('Remote checkout must be clean')
    installer = f'{SOURCE_ROOT}/promotion/promote_monitor_archive.py'
    if git(repo, 'show', f'{args.commit}:{installer}') != Path(__file__).read_bytes():
        raise ValueError('Promotion installer differs from committed source')

    # Verify every source and installed predecessor before opening protected directories
    manifest_path = f'{SOURCE_ROOT}/promotion/monitor_archive_hashes.json'
    manifest = json.loads(git(repo, 'show', f'{args.commit}:{manifest_path}'))
    root, mappings, directories = plans(args.site)
    if args.site == 'lethe' and (root / 'state/A1_OUinp/active-run.json').exists():
        raise ValueError('Promote shared lifecycle code only while no run is active')
    sources = {}
    for source, target, mode in mappings:
        data = git(repo, 'show', f'{args.commit}:{source}')
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest['sources'][source]['new']:
            raise ValueError(f'Source hash differs: {source}')
        if target.exists() or target.is_symlink():
            regular(target)
            current = hashlib.sha256(target.read_bytes()).hexdigest()
            allowed = [digest] + manifest['sources'][source].get('previous', [])
            if current not in allowed:
                raise ValueError(f'Unexpected installed predecessor: {target} ({current})')
        sources[source] = data
        print(f'{digest}  {target}', flush=True)
    for directory in directories:
        if not stat.S_ISDIR(directory.lstat().st_mode):
            raise ValueError(f'Invalid installation directory: {directory}')

    # Restore immutable directory modes even after a failed installation
    try:
        for directory in directories:
            directory.chmod(0o755)
        for source, target, mode in mappings:
            descriptor, staging = tempfile.mkstemp(prefix='.monitor-archive-', dir=target.parent)
            temporary = Path(staging)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(sources[source])
                    stream.flush()
                    os.fsync(stream.fileno())
                if args.site == 'lethe':
                    os.chown(temporary, -1, grp.getgrnam('salvadord').gr_gid)
                temporary.chmod(mode)
                os.replace(temporary, target)
                if hashlib.sha256(target.read_bytes()).hexdigest() != manifest['sources'][source]['new']:
                    raise ValueError(f'Installed hash differs: {target}')
            finally:
                temporary.unlink(missing_ok=True)
    finally:
        for directory in directories:
            directory.chmod(0o555)
    if args.site == 'lethe':
        archive_dir = root / 'state/A1_OUinp/result-archives'
        if archive_dir.is_symlink():
            raise ValueError('Archive directory must not be a symlink')
        archive_dir.mkdir(mode=0o700, exist_ok=True)
        archive_dir.chmod(0o700)
        subprocess.run([str(root / 'helpers/lethe/hpc-lethe-job'), 'version'], check=True)
        subprocess.run([str(root / 'helpers/lethe/hpc-lethe-result'), 'version'], check=True)
        command = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                   '--', 'lattice', str(root / 'helpers/grid/hpc-grid-status'), 'self-test']
        subprocess.run(command, check=True, timeout=60)
    else:
        subprocess.run([str(root / 'bin/hpc-helper-info'), 'info'], check=True)
        subprocess.run([str(root / 'bin/hpc-job'), 'logs', '--help'], check=True)
        subprocess.run([str(root / 'bin/hpc-result'), 'archive', '--help'], check=True)


if __name__ == '__main__':
    main()
