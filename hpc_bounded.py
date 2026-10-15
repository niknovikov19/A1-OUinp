import os
import selectors
import signal
import subprocess
import time


def run_bounded(command, timeout, max_stdout, max_stderr=65536, output=None, env=None):
    """Drain a subprocess within time and byte bounds, optionally streaming stdout. """
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, start_new_session=True)
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    counts = {'stdout': 0, 'stderr': 0}
    limits = {'stdout': max_stdout, 'stderr': max_stderr}
    complete = False
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
            selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                for key, _ in selector.select(remaining):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    name = key.data
                    counts[name] += len(data)
                    if counts[name] > limits[name]:
                        raise ValueError(f'{name} exceeded {limits[name]} bytes')
                    if name == 'stdout' and output is not None:
                        output.write(data)
                    else:
                        buffers[name].extend(data)
        process.wait(timeout=max(0.001, deadline - time.monotonic()))
        complete = True
    finally:
        if not complete or process.poll() is None:
            # Stop descendants that might still hold the captured pipes open
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        process.stdout.close()
        process.stderr.close()
    return subprocess.CompletedProcess(command, process.returncode,
                                       bytes(buffers['stdout']), bytes(buffers['stderr']))
