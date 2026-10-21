import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile


SOURCE_ROOT = 'dev_scratch/hpc/helper_src'
INSTALLER = f'{SOURCE_ROOT}/promotion/promote_completion_recovery.py'
MANIFEST = f'{SOURCE_ROOT}/promotion/completion_recovery_hashes.json'
RUN_ID = 'thal-irem-fade-pilot-20261020b'
ACTIVE_COMMIT = 'a1d5bb23de7c6e934b44b3948193e4f7737556db'
REMOTE_ROOT = Path('/ddn/niknovikov19/hpc_codex')


def git(repo, *arguments):
    """Read reviewed sources without changing the active checkout. """
    return subprocess.check_output(['git', '-c', f'safe.directory={repo}', '-C', str(repo), *arguments])


def targets(site):
    """Return only fixed module and helper destinations for this repair. """
    if site == 'local':
        root = Path('/opt/a1-hpc/bin')
        return [(name, root / name, 0o444) for name in ('hpc_job_lifecycle.py', 'hpc_archive.py')]
    result = []
    for host in ('lethe', 'grid'):
        root = REMOTE_ROOT / 'helpers' / host
        result += [(name, root / name, 0o444) for name in ('hpc_job_lifecycle.py', 'hpc_job_control.py')]
    root = REMOTE_ROOT / 'helpers/lethe'
    result.append(('hpc_archive.py', root / 'hpc_archive.py', 0o444))
    result.append((f'{SOURCE_ROOT}/remote_lethe/hpc-lethe-job', root / 'hpc-lethe-job', 0o555))
    return result


def read_regular(fpath):
    """Read an existing regular file while rejecting symlinks. """
    if not stat.S_ISREG(fpath.lstat().st_mode):
        raise ValueError(f'Not a regular file: {fpath}')
    return fpath.read_bytes()


def validate_target(fpath, hashes):
    """Accept only the pinned predecessor or the reviewed replacement. """
    payload = read_regular(fpath)
    if hashlib.sha256(payload).hexdigest() not in (hashes['old'], hashes['new']):
        raise ValueError(f'Unexpected installed predecessor: {fpath}')
    return payload


def install_file(fpath, payload, mode, group_id):
    """Replace one protected file atomically while its parent is writable. """
    descriptor, temporary = tempfile.mkstemp(prefix='.completion-recovery-', dir=fpath.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), -1, group_id)
        os.replace(temporary, fpath)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check_active_run():
    """Verify that this exact pilot has ended before installing while locked. """
    state = REMOTE_ROOT / 'state/A1_OUinp'
    active = json.loads(read_regular(state / 'active-run.json'))
    if active['run_id'] != RUN_ID or active['git_commit'] != ACTIVE_COMMIT:
        raise ValueError('The active run differs from the reviewed recovery')
    completed = subprocess.run(
        [str(REMOTE_ROOT / 'helpers/lethe/hpc-lethe-job'), 'status', RUN_ID],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, check=True,
    )
    if len(completed.stdout) > 1048576:
        raise ValueError('Installed status response is too large')
    status_value = json.loads(completed.stdout)
    jobs = [status_value['scheduler']] + [child['scheduler'] for child in status_value['children']]
    job_ids = [job['job_id'] for job in jobs]
    if status_value['status'] != 'ok' or status_value['run_id'] != RUN_ID:
        raise ValueError('Installed status returned another run')
    if job_ids != [118799, 118800, 118801, 118802, 118803]:
        raise ValueError('Installed status returned other jobs')
    for job in jobs:
        if job['raw_state'] != 'COMPLETED' or job['exit_code'] != '0:0' or job['accounting_gap']:
            raise ValueError('The pilot has not settled successfully')
    return {fpath: read_regular(fpath) for fpath in (
        state / 'active-run.json', state / 'runs' / f'{RUN_ID}.json',
        state / 'finals' / f'{RUN_ID}.json',
    )}


def main():
    """Install this reviewed repair without moving the locked HPC checkout. """
    parser = argparse.ArgumentParser()
    parser.add_argument('site', choices=('local', 'lethe'))
    parser.add_argument('commit')
    args = parser.parse_args()
    if re.fullmatch(r'[0-9a-f]{40}', args.commit) is None:
        raise ValueError('Expected a full lowercase commit hash')
    local = args.site == 'local'
    if local and os.geteuid() != 0:
        raise ValueError('Local installation requires sudo')
    if not local and pwd.getpwuid(os.geteuid()).pw_name != 'niknovikov19':
        raise ValueError('Lethe installation requires niknovikov19')
    repo = Path('/home/nnovikov/repo/A1-OUinp' if local else '/ddn/niknovikov19/repo/A1_OUinp_codex')
    if git(repo, 'branch', '--show-current').decode().strip() != 'codex-hpc':
        raise ValueError('Unexpected automation branch')
    reference = 'HEAD' if local else 'refs/remotes/origin/codex-hpc'
    if git(repo, 'rev-parse', reference).decode().strip() != args.commit:
        raise ValueError('Reviewed commit differs from the fetched branch')
    if not local and git(repo, 'rev-parse', 'HEAD').decode().strip() != ACTIVE_COMMIT:
        raise ValueError('Active checkout moved before recovery')
    if git(repo, 'show', f'{args.commit}:{INSTALLER}') != Path(__file__).read_bytes():
        raise ValueError('Installer differs from the reviewed commit')

    # Verify all sources and installed predecessors before opening any directory
    manifest = json.loads(git(repo, 'show', f'{args.commit}:{MANIFEST}'))
    mappings = targets(args.site)
    sources = {}
    originals = {}
    for name, fpath, mode in mappings:
        payload = git(repo, 'show', f'{args.commit}:{name}')
        if hashlib.sha256(payload).hexdigest() != manifest[name]['new']:
            raise ValueError(f'Reviewed source hash differs: {name}')
        compile(payload, name, 'exec')
        sources[fpath] = payload
        originals[fpath] = (validate_target(fpath, manifest[name]), fpath.stat())
    parents = {fpath.parent for _, fpath, _ in mappings}
    for parent in parents:
        if not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o555:
            raise ValueError(f'Unexpected protected directory: {parent}')

    # Hold the existing locks and preserve active records throughout installation
    with ExitStack() as stack:
        unchanged = {}
        if not local:
            for name in ('code-update.lock', 'job.lock'):
                stream = stack.enter_context(open(REMOTE_ROOT / 'state/A1_OUinp' / name, 'r+'))
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            unchanged = check_active_run()
        try:
            for parent in parents:
                parent.chmod(0o755)
            for _, fpath, mode in mappings:
                install_file(fpath, sources[fpath], mode, originals[fpath][1].st_gid)
            for fpath, payload in sources.items():
                if read_regular(fpath) != payload:
                    raise ValueError(f'Installed file differs: {fpath}')
            for fpath, payload in unchanged.items():
                if read_regular(fpath) != payload:
                    raise ValueError(f'Active record changed: {fpath}')
        except Exception:
            for fpath, (payload, info) in originals.items():
                install_file(fpath, payload, stat.S_IMODE(info.st_mode), info.st_gid)
            raise
        finally:
            for parent in parents:
                parent.chmod(0o555)

    for _, fpath, mode in mappings:
        print(f'{hashlib.sha256(read_regular(fpath)).hexdigest()}  {fpath}  mode={mode:o}')
    print(f'COMPLETION_RECOVERY_INSTALL=PASS site={args.site} commit={args.commit}')


if __name__ == '__main__':
    main()
