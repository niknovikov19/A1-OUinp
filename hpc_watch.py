import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from hpc_job import validate_git_commit, validate_run_id, validate_safe_name
from hpc_job_control import validate_scheduler_job
from hpc_job_lifecycle import SLURM_TERMINAL_STATES


HELPER = '/opt/a1-hpc/bin/hpc-job'
HELPER_TIMEOUT_SEC = 245
MAX_STDOUT = 2 * 1048576
MAX_STDERR = 65536
MAX_STATE_BYTES = 262144
MAX_REPORT_BYTES = 8192
SEGMENT_BYTES = 16 * 1048576
STORAGE_BYTES = 256 * 1048576
ACTIVE_STATES = {
    'PENDING', 'RUNNING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED',
    'RESIZING', 'REQUEUED', 'REQUEUE_FED', 'REQUEUE_HOLD', 'SIGNALING',
    'STAGE_OUT', 'STOPPED', 'SPECIAL_EXIT',
}
EXIT_CODES = {
    'checkpoint': 0, 'scheduler-terminal': 0, 'attention': 2,
    'monitoring-unavailable': 3, 'local-error': 4, 'local-storage-limit': 4,
    'deadline': 5, 'interrupted': 130,
}


def utc_string(timestamp):
    """Format one UTC wall-clock time. """
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def utc_seconds(value):
    """Read a UTC timestamp without assuming the machine's timezone. """
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('Invalid UTC timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('Timestamp must specify UTC')
    return parsed.timestamp()


def encode(value):
    """Serialize a compact deterministic JSON record. """
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    """Identify one compact record without retaining another full copy. """
    return hashlib.sha256(encode(value).encode()).hexdigest()


class WatchError(ValueError):
    """Represent an invalid response or local watcher state. """


class StorageLimit(WatchError):
    """Stop before exceeding the local observation budget. """


class SystemClock:
    """Supply real time while tests use an injected clock. """

    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)
    time = staticmethod(time.time)


@dataclass
class WatchOptions:
    codex_check_sec: int | None = None
    until: str | None = None
    extend_until: str | None = None
    logs: bool = True
    startup_poll_sec: int = 60
    poll_sec: int = 120
    pending_poll_sec: int = 300
    log_sec: int = 300
    unavailable_limit: int = 3
    unavailable_sec: int = 600

    def __post_init__(self):
        """Reject invalid timings before starting a process or touching state. """
        for key, value in vars(self).items():
            if key.endswith('_sec') or key == 'unavailable_limit':
                if value is None and key == 'codex_check_sec':
                    continue
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 86400:
                    raise WatchError(f'{key} must be an integer from 1 to 86400')
        if self.until and self.extend_until:
            raise WatchError('Choose --until or --extend-until')
        for value in (self.until, self.extend_until):
            if value is not None:
                utc_seconds(value)


class HelperRunner:
    def __call__(self, run_id, operation, child_key, timeout):
        """Read one installed helper response within time and stream limits. """
        validate_run_id(run_id)
        if operation not in {'status', 'log'} or operation == 'status' and child_key:
            raise WatchError('Watcher permits status and selected log reads only')
        command = [HELPER, '--json', operation, run_id]
        if child_key:
            validate_safe_name(child_key, 'child key')
            command += ['--child', child_key]
        result = {'returncode': None, 'stdout': '', 'stderr': '', 'error': None,
                  'interrupted': False, 'local_error': False}
        buffers = {'stdout': bytearray(), 'stderr': bytearray()}
        process = None
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
            )
            deadline = time.monotonic() + timeout
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
                selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Local helper read timed out')
                    for key, _ in selector.select(remaining):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        name = key.data
                        limit = MAX_STDOUT if name == 'stdout' else MAX_STDERR
                        room = limit - len(buffers[name])
                        buffers[name].extend(data[:room])
                        if len(data) > room:
                            raise WatchError(f'Helper {name} exceeded {limit} bytes')
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except KeyboardInterrupt:
            result.update(error='Local helper read interrupted', interrupted=True)
        except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
            result['error'] = str(exc)[:500]
            result['local_error'] = isinstance(exc, (OSError, WatchError)) and not isinstance(exc, TimeoutError)
        finally:
            if process is not None:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()
                result['returncode'] = process.returncode
                process.stdout.close()
                process.stderr.close()
            for name, data in buffers.items():
                result[name] = data.decode('utf-8', errors='replace')
        return result


def read_json(fpath, maximum):
    """Read bounded local JSON without following a file symlink. """
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(fpath, flags)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise WatchError(f'Invalid local state file: {fpath}')
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise WatchError(f'Local state is too large: {fpath}')
    return json.loads(data)


class WatchStore:
    def __init__(self, directory, storage_bytes=STORAGE_BYTES, segment_bytes=SEGMENT_BYTES):
        """Keep one run's local state and bounded append-only observations. """
        self.directory = Path(directory).absolute()
        self.storage_bytes = storage_bytes
        self.segment_bytes = segment_bytes
        self.lock = None
        self.sequence = 0
        self.segment = 1
        self.used = 0
        self.torn_observation = False

    def __enter__(self):
        """Lock this local watcher without locking or modifying the HPC run. """
        for path in (self.directory, *self.directory.parents):
            if path.is_symlink():
                raise WatchError('Watcher directory contains a symlink')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDWR | os.O_CREAT | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(self.directory / 'watch.lock', flags, 0o600)
        self.lock = os.fdopen(descriptor, 'r+')
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise WatchError('Watcher lock must be a regular file')
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            files = list(self.directory.iterdir())
            segments = sorted(path for path in files if re.fullmatch(r'observations-[0-9]{4}.jsonl', path.name))
            if len(segments) > 256:
                raise StorageLimit('Too many local observation segments')
            for path in files:
                if path.suffix == '.jsonl':
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        raise WatchError('Observation files must be regular files')
                    self.used += info.st_size
            if segments:
                self.segment = int(segments[-1].stem.split('-')[1])
                if segments[-1].stat().st_size > self.segment_bytes:
                    raise StorageLimit('Observation segment exceeds its limit')
                data = segments[-1].read_bytes()
                complete = data.splitlines()
                if data and not data.endswith(b'\n'):
                    self.torn_observation = True
                    self.segment += 1
                    complete = complete[:-1]
                for segment in reversed(segments):
                    if segment.stat().st_size > self.segment_bytes:
                        raise StorageLimit('Observation segment exceeds its limit')
                    fragment = segment.read_bytes()
                    lines = fragment.splitlines()
                    if fragment and not fragment.endswith(b'\n'):
                        lines = lines[:-1]
                    if lines:
                        self.sequence = json.loads(lines[-1])['sequence']
                        break
        except BaseException:
            self.lock.close()
            self.lock = None
            raise
        return self

    def __exit__(self, *_):
        """Release the local lock when a session stops or is interrupted. """
        self.lock.close()

    def atomic_json(self, name, value, maximum=MAX_STATE_BYTES):
        """Replace a small state file while preserving the preceding valid copy. """
        data = (encode(value) + '\n').encode()
        if len(data) > maximum:
            raise WatchError(f'{name} exceeds its byte limit')
        target = self.directory / name
        if target.is_symlink():
            raise WatchError(f'{name} cannot be a symlink')
        descriptor, temporary = tempfile.mkstemp(prefix=f'.{name}-', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def append(self, name, value):
        """Append bounded evidence without deleting earlier observations. """
        data = (encode(value) + '\n').encode()
        if self.used + len(data) > self.storage_bytes:
            raise StorageLimit('Local observation storage limit reached')
        descriptor = os.open(
            self.directory / name,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0), 0o600,
        )
        with os.fdopen(descriptor, 'ab') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise WatchError('Observation destination must be a regular file')
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.used += len(data)

    def observation(self, value):
        """Save the full bounded reply before deriving a report from it. """
        self.sequence += 1
        value = {**value, 'sequence': self.sequence}
        size = len((encode(value) + '\n').encode())
        if size > self.segment_bytes:
            raise StorageLimit('One observation exceeds the segment limit')
        name = f'observations-{self.segment:04d}.jsonl'
        path = self.directory / name
        if path.exists() and path.stat().st_size + size > self.segment_bytes:
            self.segment += 1
            name = f'observations-{self.segment:04d}.jsonl'
        if self.segment > 256:
            raise StorageLimit('Too many local observation segments')
        self.append(name, value)
        return self.sequence


def classify_job(job, job_id):
    """Distinguish active, terminal, failed, and unknown scheduler observations. """
    validate_scheduler_job(job, job_id)
    if type(job['job_id']) is not int:
        raise WatchError('Invalid observed Slurm ID')
    tokens = job['raw_state'].split()
    token = tokens[0].rstrip('+').upper() if tokens else ''
    known = not job['accounting_gap'] and job['source'] != 'missing'
    if not known or token not in ACTIVE_STATES | SLURM_TERMINAL_STATES:
        return {'state': 'unknown', 'terminal': False, 'abnormal': False}
    terminal = token in SLURM_TERMINAL_STATES
    if token == 'COMPLETED' and re.fullmatch(r'[0-9]+:[0-9]+', job['exit_code']) is None:
        return {'state': 'unknown', 'terminal': False, 'abnormal': False}
    abnormal = terminal and (token != 'COMPLETED' or job['exit_code'] != '0:0')
    return {'state': token, 'terminal': terminal, 'abnormal': abnormal}


def summarize_status(payload, run_id):
    """Validate a run-bound status without treating observed children as a full plan. """
    if payload.get('operation') != 'job-status' or payload.get('run_id') != run_id:
        raise WatchError('Status response has another operation or run ID')
    validate_git_commit(payload.get('git_commit'))
    main_id = payload.get('slurm_job_id')
    if isinstance(main_id, bool) or not isinstance(main_id, int) or main_id <= 0:
        raise WatchError('Invalid batch-main Slurm ID')
    utc_seconds(payload.get('observed_at_utc'))
    children = payload.get('children')
    if not isinstance(children, list) or len(children) > 99:
        raise WatchError('Invalid recorded child list')
    main = classify_job(payload['scheduler'], main_id)
    jobs = {'main': {**main, 'job_id': main_id, 'exit_code': payload['scheduler']['exit_code']}}
    bindings = {}
    ids = {main_id}
    for child in children:
        key = validate_safe_name(child['child_key'], 'child key')
        job_id = child['slurm_job_id']
        if key == 'main' or key in bindings or isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0 or job_id in ids:
            raise WatchError('Duplicate or invalid simulation identity')
        binding = {name: child[name] for name in ('parameters', 'expected_outputs', 'stdout_path', 'stderr_path')}
        bindings[key] = {'job_id': job_id, 'details_sha256': digest(binding)}
        jobs[key] = {**classify_job(child['scheduler'], job_id), 'job_id': job_id,
                     'exit_code': child['scheduler']['exit_code']}
        ids.add(job_id)
    hints = [payload['scheduler']['retry_after_sec']]
    hints += [child['scheduler']['retry_after_sec'] for child in children]
    return {'git_commit': payload['git_commit'], 'main_id': main_id, 'jobs': jobs,
            'bindings': bindings, 'observed_at_utc': payload['observed_at_utc'],
            'retry_after_sec': min(300, max((value or 0) for value in hints))}


class Watcher:
    def __init__(self, run_id, store, options=None, runner=None, clock=None):
        """Observe one run through a fixed read-only helper and local state. """
        self.run_id = validate_run_id(run_id)
        self.store = store
        self.options = options or WatchOptions()
        self.runner = runner or HelperRunner()
        self.clock = clock or SystemClock()
        self.state = None
        self.attention = []
        self.log_diagnostics = []

    def save(self, operation):
        """Expose the process state before and after each potentially slow operation. """
        self.state.update(updated_at_utc=utc_string(self.clock.time()), current_operation=operation,
                          sequence=self.store.sequence)
        self.store.atomic_json('state.json', self.state)

    def initialize(self, resume):
        """Load one resumable history without silently extending its deadline. """
        path = self.store.directory / 'state.json'
        if resume:
            saved = read_json(path, MAX_STATE_BYTES)
            required = {'schema_version', 'run_id', 'started_at_utc', 'codex_check_sec', 'until',
                        'identity', 'bindings', 'last_status', 'last_good_at_utc', 'unavailable_since',
                        'failures', 'acknowledged', 'pending_attention', 'changes', 'last_signature',
                        'stable_since', 'last_log_at', 'uncertainty'}
            if not isinstance(saved, dict) or not required <= set(saved):
                raise WatchError('Invalid saved watcher state')
            if saved['schema_version'] != 1 or saved['run_id'] != self.run_id:
                raise WatchError('Saved watcher state belongs to another run or version')
            utc_seconds(saved['started_at_utc'])
            if not isinstance(saved['bindings'], dict) or not isinstance(saved['acknowledged'], list):
                raise WatchError('Invalid saved watcher identities')
            if len(saved['acknowledged']) > 256 or len(saved['bindings']) > 99:
                raise WatchError('Saved watcher state exceeds identity limits')
            if not isinstance(saved['changes'], dict) or type(saved['failures']) is not int or saved['failures'] < 0:
                raise WatchError('Invalid saved watcher counters')
            for key in ('stable_since', 'last_log_at', 'unavailable_since'):
                value = saved[key]
                if value is not None and (type(value) not in {int, float} or not math.isfinite(value)):
                    raise WatchError('Invalid saved watcher time')
            for key in ('until', 'last_good_at_utc'):
                if saved[key] is not None:
                    utc_seconds(saved[key])
            for key in ('acknowledged', 'pending_attention'):
                values = saved[key]
                if not isinstance(values, list) or len(values) > 256:
                    raise WatchError('Invalid saved attention history')
                if any(not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None for value in values):
                    raise WatchError('Invalid saved attention identity')
            if not isinstance(saved['uncertainty'], dict) or any(not isinstance(value, list) for value in saved['uncertainty'].values()):
                raise WatchError('Invalid saved watcher uncertainty')
            previous = saved['last_status']
            if previous is not None:
                if not isinstance(previous, dict) or not isinstance(previous.get('jobs'), dict):
                    raise WatchError('Invalid saved scheduler summary')
                if not isinstance(previous.get('bindings'), dict):
                    raise WatchError('Invalid saved simulation summary')
                for job in previous['jobs'].values():
                    if not isinstance(job, dict) or not {'job_id', 'state', 'terminal', 'abnormal', 'exit_code'} <= set(job):
                        raise WatchError('Invalid saved scheduler job')
                    if type(job['job_id']) is not int or not isinstance(job['state'], str) or job['state'] not in ACTIVE_STATES | SLURM_TERMINAL_STATES | {'unknown'}:
                        raise WatchError('Invalid saved scheduler identity or state')
                    if type(job['terminal']) is not bool or type(job['abnormal']) is not bool or not isinstance(job['exit_code'], str):
                        raise WatchError('Invalid saved scheduler flags')
                utc_seconds(previous['observed_at_utc'])
                if saved['identity'] is None:
                    raise WatchError('Saved scheduler summary has no bound run identity')
            if saved['identity'] is not None:
                validate_git_commit(saved['identity']['git_commit'])
                if type(saved['identity']['main_id']) is not int or saved['identity']['main_id'] <= 0:
                    raise WatchError('Invalid saved batch-main identity')
            for key, binding in saved['bindings'].items():
                validate_safe_name(key, 'saved child key')
                if type(binding['job_id']) is not int or binding['job_id'] <= 0:
                    raise WatchError('Invalid saved simulation identity')
                if re.fullmatch(r'[0-9a-f]{64}', binding['details_sha256']) is None:
                    raise WatchError('Invalid saved simulation details')
            if self.options.until and self.options.until != saved['until']:
                raise WatchError('Resume cannot change --until; use explicit --extend-until')
            self.state = saved
            self.state['acknowledged'] = list(dict.fromkeys(saved['acknowledged'] + saved['pending_attention']))[-256:]
            self.state['pending_attention'] = []
        else:
            if path.exists():
                raise WatchError('Watcher state already exists; use --resume')
            if self.options.extend_until:
                raise WatchError('--extend-until requires --resume')
            self.state = {
                'schema_version': 1, 'run_id': self.run_id,
                'started_at_utc': utc_string(self.clock.time()), 'codex_check_sec': 1800,
                'until': self.options.until, 'identity': None, 'bindings': {},
                'last_status': None, 'last_good_at_utc': None, 'unavailable_since': None,
                'failures': 0, 'acknowledged': [], 'pending_attention': [], 'changes': {}, 'last_signature': None,
                'stable_since': self.clock.time(), 'last_log_at': None, 'uncertainty': {},
            }
        if self.options.extend_until:
            old = self.state['until']
            if old is None or utc_seconds(self.options.extend_until) <= utc_seconds(old):
                raise WatchError('--extend-until must extend an existing deadline')
            self.store.append('events.jsonl', {'type': 'deadline-extended', 'old': old, 'new': self.options.extend_until})
            self.state['until'] = self.options.extend_until
        if self.options.codex_check_sec is not None:
            self.state['codex_check_sec'] = self.options.codex_check_sec
        interval = self.state['codex_check_sec']
        if isinstance(interval, bool) or not isinstance(interval, int) or not 1 <= interval <= 86400:
            raise WatchError('Invalid saved Codex check interval')
        self.wall_start = self.clock.time()
        self.mono_start = self.clock.monotonic()
        self.wall_checkpoint = self.wall_start + interval
        self.mono_checkpoint = self.mono_start + interval
        if self.state['until'] is not None:
            utc_seconds(self.state['until'])
        self.state.update(pid=os.getpid(), session_status='running',
                          next_checkpoint_at_utc=utc_string(self.wall_checkpoint))
        if self.store.torn_observation:
            self.store.append('events.jsonl', {'type': 'interrupted-observation', 'message': 'Retained torn segment; started a new segment'})
        self.save('starting')

    def remaining(self):
        """Respect both clock types so host sleep cannot silently extend a session. """
        remaining = min(self.mono_checkpoint - self.clock.monotonic(), self.wall_checkpoint - self.clock.time())
        if self.state['until']:
            remaining = min(remaining, utc_seconds(self.state['until']) - self.clock.time())
        return max(0, remaining)

    def call(self, operation, child_key=None):
        """Save one helper response before interpreting its contents. """
        if self.remaining() <= 0:
            return None
        self.save(f'{operation}:{child_key or "main"}')
        if self.remaining() <= 0:
            return None
        started = self.clock.time()
        mono = self.clock.monotonic()
        result = self.runner(self.run_id, operation, child_key, min(HELPER_TIMEOUT_SEC, self.remaining()))
        payload = None
        parse_error = None
        if result['stdout']:
            try:
                payload = json.loads(result['stdout'])
                if not isinstance(payload, dict):
                    raise ValueError('Helper JSON is not an object')
            except ValueError as exc:
                parse_error = str(exc)[:300]
        self.store.observation({**result, 'operation': operation, 'child_key': child_key,
                                'started_at_utc': utc_string(started), 'ended_at_utc': utc_string(self.clock.time()),
                                'elapsed_sec': self.clock.monotonic() - mono,
                                'payload': payload, 'parse_error': parse_error})
        self.save('interpreting')
        if result.get('interrupted'):
            raise KeyboardInterrupt
        if result.get('local_error'):
            raise WatchError(result['error'])
        if payload and payload.get('status') == 'ok':
            if payload.get('operation') != f'job-{operation}' or payload.get('run_id') != self.run_id:
                raise WatchError('Helper reply has another operation or run ID')
            if operation == 'log' and payload.get('child_key') != child_key:
                raise WatchError('Log reply has another simulation identity')
            if operation == 'log' and self.state['last_status']:
                expected = self.state['last_status']['jobs'].get(child_key or 'main')
                if expected and payload.get('slurm_job_id') != expected['job_id']:
                    raise WatchError('Log reply has another Slurm job ID')
        return {**result, 'payload': payload, 'parse_error': parse_error}

    def apply_status(self, snapshot):
        """Detect changes while preserving previously observed simulation identities. """
        identity = {'git_commit': snapshot['git_commit'], 'main_id': snapshot['main_id']}
        if self.state['identity'] is not None and identity != self.state['identity']:
            raise WatchError('Run commit or batch-main identity changed')
        for key, binding in self.state['bindings'].items():
            if key in snapshot['bindings'] and snapshot['bindings'][key] != binding:
                raise WatchError('Simulation parameters, paths, or Slurm ID changed')
        missing = set(self.state['bindings']) - set(snapshot['bindings'])
        self.state['identity'] = identity
        self.state['bindings'].update(snapshot['bindings'])
        previous = (self.state['last_status'] or {}).get('jobs', {})
        for key, job in snapshot['jobs'].items():
            if previous.get(key) != job:
                event_type = 'discovered' if key not in previous else 'transition'
                self.store.append('events.jsonl', {'type': event_type, 'key': key, 'job': job,
                                                 'at_utc': utc_string(self.clock.time())})
                changes = self.state['changes']
                changes[event_type] = changes.get(event_type, 0) + 1
            if job['abnormal']:
                alert = {'key': key, 'job_id': job['job_id'], 'state': job['state'], 'exit_code': job['exit_code']}
                signature = digest(alert)
                if signature not in self.state['acknowledged']:
                    self.store.append('events.jsonl', {'type': 'attention', 'alert': alert})
                    self.attention.append(alert)
        active = [job for job in snapshot['jobs'].values() if not job['terminal'] and job['state'] != 'unknown']
        if snapshot['jobs']['main']['terminal'] and active:
            alert = {'key': 'main', 'state': 'main-ended-with-active-simulations',
                     'active_job_ids': sorted(job['job_id'] for job in active)}
            if digest(alert) not in self.state['acknowledged']:
                self.store.append('events.jsonl', {'type': 'attention', 'alert': alert})
                self.attention.append(alert)
        signature = digest(snapshot['jobs'])
        if signature != self.state['last_signature']:
            self.state['last_signature'] = signature
            self.state['stable_since'] = self.clock.time()
        self.state['last_status'] = snapshot
        unknown = missing or any(job['state'] == 'unknown' for job in snapshot['jobs'].values())
        self.state['uncertainty'] = {
            'missing_children': sorted(missing),
            'unknown_job_ids': [job['job_id'] for job in snapshot['jobs'].values() if job['state'] == 'unknown'],
        }
        if not unknown:
            self.state['last_good_at_utc'] = snapshot['observed_at_utc']
        return not unknown

    def read_logs(self, force=False):
        """Read at most the main log and two affected simulations per cycle. """
        if not self.options.logs or self.remaining() <= 0:
            return
        last = self.state['last_log_at']
        if not force and last is not None and self.clock.time() - last < self.options.log_sec:
            return
        keys = [None]
        keys += [alert['key'] for alert in self.attention if alert['key'] != 'main'][:2]
        for key in keys:
            result = self.call('log', key)
            if result is None:
                break
            payload = result['payload'] or {}
            streams = payload.get('streams', {})
            if result['error'] or payload.get('status') != 'ok':
                self.log_diagnostics.append({'child_key': key, 'state': 'unavailable'})
            elif not isinstance(streams, dict) or any(not isinstance(stream, dict) for stream in streams.values()):
                self.log_diagnostics.append({'child_key': key, 'state': 'invalid-log-response'})
            elif any(stream.get('more_available') for stream in streams.values()):
                self.log_diagnostics.append({'child_key': key, 'state': 'backlog'})
        self.state['last_log_at'] = self.clock.time()

    def report(self, reason, detail=None):
        """Persist a short handoff without certifying scientific completion. """
        now = self.clock.time()
        snapshot = self.state.get('last_status') if self.state else None
        jobs = snapshot['jobs'] if snapshot else {}
        last_good = self.state.get('last_good_at_utc') if self.state else None
        report = {
            'schema_version': 1, 'run_id': self.run_id, 'reason': reason,
            'detail': detail[:500] if detail else None, 'reported_at_utc': utc_string(now),
            'identity': self.state.get('identity') if self.state else None,
            'main_state': jobs.get('main', {}).get('state'),
            'child_state_counts': dict(Counter(job['state'] for key, job in jobs.items() if key != 'main')),
            'observed_children': len(jobs) - 1 if jobs else 0,
            'previously_observed_children': len(self.state.get('bindings', {})) if self.state else 0,
            'last_good_at_utc': last_good,
            'last_status_at_utc': snapshot.get('observed_at_utc') if snapshot else None,
            'status_unavailable': bool(self.state.get('failures', 0)) if self.state else True,
            'observation_age_sec': max(0, now - utc_seconds(last_good)) if last_good else None,
            'session_elapsed_sec': max(0, self.clock.monotonic() - getattr(self, 'mono_start', self.clock.monotonic())),
            'codex_check_sec': self.state.get('codex_check_sec') if self.state else None,
            'until': self.state.get('until') if self.state else None,
            'changes': self.state.get('changes', {}) if self.state else {},
            'attention': self.attention[:3], 'attention_omitted': max(0, len(self.attention) - 3),
            'log_diagnostics': self.log_diagnostics[:3],
            'uncertainty': {key: value[:3] for key, value in self.state.get('uncertainty', {}).items()} if self.state else {},
            'expected_child_coverage_verified': False, 'output_files_verified': False,
            'evidence_directory': str(self.store.directory), 'sequence': self.store.sequence,
        }
        if len((encode(report) + '\n').encode()) > MAX_REPORT_BYTES:
            raise WatchError('Report exceeds its byte limit')
        self.store.atomic_json('report.json', report, MAX_REPORT_BYTES)
        if self.state is not None:
            self.state['pending_attention'] = [digest(alert) for alert in self.attention]
            self.state.update(session_status='exited', last_report_reason=reason, changes={})
            self.save('finished')
        return report

    def run(self, resume=False):
        """Poll without involving Codex until a checkpoint or meaningful handoff. """
        try:
            self.initialize(resume)
            while self.remaining() > 0:
                result = self.call('status')
                if result is None:
                    break
                payload = result['payload'] or {}
                if result['returncode'] in {2, 4} or payload.get('status') in {'rejected', 'failed'}:
                    return self.report('attention', 'Installed helper rejected or failed the status operation')
                if result['parse_error']:
                    return self.report('local-error', 'Installed helper returned malformed JSON')
                if result['returncode'] not in {0, 3, None} and not result['error']:
                    return self.report('local-error', 'Installed helper exited without a valid response')
                usable = False
                if not result['error'] and result['returncode'] == 0 and payload.get('status') == 'ok':
                    usable = self.apply_status(summarize_status(payload, self.run_id))
                now = self.clock.time()
                if usable:
                    self.state.update(failures=0, unavailable_since=None)
                else:
                    self.state['failures'] += 1
                    if self.state['unavailable_since'] is None:
                        self.state['unavailable_since'] = now
                jobs = (self.state['last_status'] or {}).get('jobs', {})
                terminal = usable and jobs and all(job['terminal'] for job in jobs.values())
                self.read_logs(force=bool(self.attention) or bool(terminal))
                if self.attention:
                    return self.report('attention')
                if terminal:
                    return self.report('scheduler-terminal')
                failures = self.state['failures']
                if failures and (failures >= self.options.unavailable_limit or now - self.state['unavailable_since'] >= self.options.unavailable_sec):
                    return self.report('monitoring-unavailable', 'Status is unavailable, incomplete, or contains unknown jobs')
                elapsed = now - utc_seconds(self.state['started_at_utc'])
                interval = self.options.startup_poll_sec if elapsed < 300 else self.options.poll_sec
                if jobs and all(job['state'] == 'PENDING' for job in jobs.values()) and now - self.state['stable_since'] >= 600:
                    interval = self.options.pending_poll_sec
                if failures:
                    interval = min(300, 60 * 2 ** min(failures - 1, 3))
                    interval = max(interval, (self.state['last_status'] or {}).get('retry_after_sec', 0))
                self.save('sleeping')
                self.clock.sleep(min(interval, self.remaining()))
            reason = 'deadline' if self.state['until'] and self.clock.time() >= utc_seconds(self.state['until']) else 'checkpoint'
            return self.report(reason)
        except KeyboardInterrupt:
            return self.report('interrupted', 'Stopped local monitoring; HPC jobs were not cancelled')
        except StorageLimit as exc:
            return self.report('local-storage-limit', str(exc))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            return self.report('local-error', str(exc))


def watcher_status(directory):
    """Read local process and freshness information without querying HPC. """
    directory = Path(directory)
    state = read_json(directory / 'state.json', MAX_STATE_BYTES)
    descriptor = os.open(directory / 'watch.lock', os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'r+') as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            running = False
        except BlockingIOError:
            running = True
    return {key: state.get(key) for key in (
        'run_id', 'pid', 'session_status', 'updated_at_utc', 'current_operation',
        'last_good_at_utc', 'next_checkpoint_at_utc', 'last_report_reason',
    )} | {'watcher_running': running, 'status_checks_hpc': False}


def main(argv=None):
    """Run one bounded session or inspect its saved local status. """
    parser = argparse.ArgumentParser(description='Watch one submitted HPC run through installed read-only helpers.')
    parser.add_argument('run_id')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--resume', action='store_true')
    mode.add_argument('--status', action='store_true')
    parser.add_argument('--codex-check-sec', type=int)
    parser.add_argument('--until', help='Overall UTC deadline, preserved on resume.')
    parser.add_argument('--extend-until', help='Explicitly extend the saved deadline on resume.')
    parser.add_argument('--no-logs', action='store_true')
    parser.add_argument('--state-root', type=Path, default=Path('exp_results_local/hpc_codex'))
    args = parser.parse_args(argv)
    old_handler = signal.getsignal(signal.SIGTERM)

    # Stop the local reader gracefully without sending any HPC cancellation command
    def stop_local(_signum, _frame):
        """Use the same persistence path for SIGTERM and keyboard interruption. """
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_local)
    try:
        validate_run_id(args.run_id)
        directory = args.state_root / args.run_id / 'watch'
        if args.status:
            status_value = watcher_status(directory)
            if status_value['run_id'] != args.run_id:
                raise WatchError('Saved status belongs to another run')
            print(encode(status_value))
            return 0
        options = WatchOptions(codex_check_sec=args.codex_check_sec, until=args.until,
                               extend_until=args.extend_until, logs=not args.no_logs)
        with WatchStore(directory) as store:
            report = Watcher(args.run_id, store, options).run(resume=args.resume)
        print(encode(report))
        return EXIT_CODES[report['reason']]
    except (ValueError, OSError, KeyboardInterrupt, KeyError, TypeError) as exc:
        reason = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'local-error'
        if isinstance(exc, StorageLimit):
            reason = 'local-storage-limit'
        report = {'schema_version': 1, 'run_id': args.run_id, 'reason': reason,
                  'detail': str(exc)[:500], 'state_saved': False}
        print(encode(report))
        return EXIT_CODES[reason]
    finally:
        signal.signal(signal.SIGTERM, old_handler)


if __name__ == '__main__':
    raise SystemExit(main())
