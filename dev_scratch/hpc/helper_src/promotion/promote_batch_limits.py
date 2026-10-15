import argparse
from copy import deepcopy
import grp
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
POLICIES = {
    'local': {
        'repo': '/home/nnovikov/repo/A1-OUinp',
        'source': f'{SOURCE_ROOT}/config_examples/hpc-helper.json.example',
        'target': '/opt/a1-hpc/config/hpc-helper.json',
        'old': '3a85f7f69ae0a59052ea4c40fa8fc985206809fe2bc2a2b4588ec821d689b545',
        'new': '546fae687acbd5269f94e6d946f24e665259fbc54eab39340a20c3d3ef8ac61b',
    },
    'lethe': {
        'repo': '/ddn/niknovikov19/repo/A1_OUinp_codex',
        'source': f'{SOURCE_ROOT}/config_examples/remote-hpc-prepare.json.example',
        'target': '/ddn/niknovikov19/hpc_codex/config/A1_OUinp-prepare.json',
        'old': 'bc7195e554103d76de6bcf8858259e7897249de7834bf7b147efeb0e376ee881',
        'new': 'b44abec6b2ba18ed7e0e1b3a594d80a2016614fe6182dc2401cf9bddb7fedb84',
    },
}


def validate_transition(current, proposed):
    """Permit only the requested two limits to change, retaining all resource policy. """
    expected = deepcopy(current)
    expected['scheduler']['limits']['max_child_jobs'] = 60
    expected['scheduler']['limits']['max_concurrent_jobs'] = 10
    if expected != proposed:
        raise ValueError('Policy changes values beyond the requested 60-child/10-concurrent limits')


def git(repo, *arguments):
    """Read an exact reviewed commit from the fixed automation branch. """
    return subprocess.check_output(['git', '-c', f'safe.directory={repo}', '-C', str(repo), *arguments])


def main():
    """Promote one pinned submission policy during the user's manual Gate-B step. """
    parser = argparse.ArgumentParser()
    parser.add_argument('site', choices=sorted(POLICIES))
    parser.add_argument('commit')
    args = parser.parse_args()
    if re.fullmatch(r'[0-9a-f]{40}', args.commit) is None:
        raise ValueError('Expected a full lowercase commit hash')
    if args.site == 'local' and os.geteuid() != 0:
        raise ValueError('Local policy promotion requires sudo')
    if args.site == 'lethe' and pwd.getpwuid(os.geteuid()).pw_name != 'niknovikov19':
        raise ValueError('Remote policy promotion requires niknovikov19')
    policy = POLICIES[args.site]
    repo = Path(policy['repo'])
    if git(repo, 'rev-parse', 'HEAD').decode().strip() != args.commit:
        raise ValueError('Checkout HEAD differs from the reviewed commit')
    if git(repo, 'branch', '--show-current').decode().strip() != 'codex-hpc':
        raise ValueError('Unexpected automation branch')
    if args.site == 'lethe':
        if git(repo, 'status', '--porcelain=v1').strip():
            raise ValueError('Remote checkout must be clean')
        active = Path('/ddn/niknovikov19/hpc_codex/state/A1_OUinp/active-run.json')
        if active.exists() or active.is_symlink():
            raise ValueError('Promote submission policy only while no run is active')
    installer = f'{SOURCE_ROOT}/promotion/promote_batch_limits.py'
    if git(repo, 'show', f'{args.commit}:{installer}') != Path(__file__).read_bytes():
        raise ValueError('Installer differs from the committed source')

    # Verify the exact source and predecessor before opening the protected config directory
    payload = git(repo, 'show', f"{args.commit}:{policy['source']}")
    if hashlib.sha256(payload).hexdigest() != policy['new']:
        raise ValueError('Reviewed policy hash differs')
    target = Path(policy['target'])
    if not stat.S_ISREG(target.lstat().st_mode) or not stat.S_ISDIR(target.parent.lstat().st_mode):
        raise ValueError('Policy path must contain a real directory and regular file')
    previous = target.read_bytes()
    if hashlib.sha256(previous).hexdigest() not in (policy['old'], policy['new']):
        raise ValueError('Unexpected installed policy hash')
    proposed = json.loads(payload)
    validate_transition(json.loads(previous), proposed)
    print(f"Installing {policy['new']}  {target}", flush=True)

    # Publish the policy atomically and restore the immutable parent directory
    temporary = None
    try:
        target.parent.chmod(0o755)
        descriptor, temporary = tempfile.mkstemp(prefix='.batch-limits-', dir=target.parent)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if args.site == 'lethe':
            os.chown(temporary, -1, grp.getgrnam('salvadord').gr_gid)
        Path(temporary).chmod(0o444)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        target.parent.chmod(0o555)
    installed = target.read_bytes()
    if hashlib.sha256(installed).hexdigest() != policy['new']:
        raise ValueError('Installed policy hash differs')
    print(json.dumps(json.loads(installed)['scheduler']['limits'], sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
