"""Independent bounded-output process observer; never trusts peer progress."""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

def process_sample(pid):
    try:
        if sys.platform.startswith('linux'):
            # comm may contain spaces and ')' characters; fields follow its last ')'.
            fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
            return {'cpu_seconds': (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
                    'rss_kib': int(fields[21]) * os.sysconf('SC_PAGE_SIZE') // 1024}
        rss = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
        return {'rss_kib': int(rss.stdout.strip())} if rss.stdout.strip() else {}
    except (OSError, ValueError, IndexError):
        return {}

def stop(process):
    # A parent can exit while a descendant keeps stdout open. Kill the owned
    # session even then, otherwise the timeout would leak the descendant.
    try: os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    process.wait(timeout=5)

def observe(process, timeout, period=1):
    """Yield samples in the main thread; reap on failure or interruption.

    Signal cleanup begins on first iteration, after the caller launches its
    child. Termination before entering this observer is outside its scope.
    """
    if timeout <= 0 or period <= 0: raise ValueError('positive observation times required')
    started = time.monotonic()
    next_sample = started
    pending = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    previous_handlers = {}
    closed = False
    def cleanup():
        nonlocal closed
        if closed: return
        closed = True
        try:
            selector.close()
            stop(process)
            process.stdout.close()
            if process.stderr is not None: process.stderr.close()
        finally:
            for value, handler in previous_handlers.items():
                signal.signal(value, handler)
    def interrupt(signum, frame):
        cleanup()
        raise KeyboardInterrupt(f'soak observation interrupted by signal {signum}')
    try:
        # The native target owns another session, so driver termination alone
        # cannot reap it. Unwind through the existing cleanup on TERM and INT.
        for value in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[value] = signal.getsignal(value)
            signal.signal(value, interrupt)
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            if now - started >= timeout:
                raise TimeoutError('process exceeded the independent soak deadline')
            if now >= next_sample:
                yield {'elapsed_seconds': now - started, **process_sample(process.pid)}
                next_sample = now + period
            for key, _ in selector.select(min(period, timeout - (now - started))):
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    selector.unregister(key.fileobj)
                    if pending: yield {'line': pending.decode('utf-8'), 'elapsed_seconds': time.monotonic() - started}
                    pending.clear()
                    continue
                pending.extend(data)
                while b'\n' in pending:
                    line, _, rest = pending.partition(b'\n')
                    if len(line) > 65536: raise ValueError('soak output line exceeded 64 KiB')
                    pending = bytearray(rest)
                    yield {'line': line.decode('utf-8'), 'elapsed_seconds': time.monotonic() - started}
                if len(pending) > 65536: raise ValueError('soak output line exceeded 64 KiB')
    finally:
        cleanup()

def memory_summary(samples, warmup=60):
    # Online centered moments consume iterators without retaining sample rows.
    count = 0
    mean_time = mean_rss = covariance = variance = 0.0
    low = high = None
    for sample in samples:
        if not (sample.get('elapsed_seconds', 0) >= warmup and 'rss_kib' in sample):
            continue
        elapsed, rss = sample['elapsed_seconds'], sample['rss_kib']
        count += 1
        delta_time, delta_rss = elapsed - mean_time, rss - mean_rss
        mean_time += delta_time / count
        mean_rss += delta_rss / count
        covariance += delta_time * (rss - mean_rss)
        variance += delta_time * (elapsed - mean_time)
        low = rss if low is None else min(low, rss)
        high = rss if high is None else max(high, rss)
    return {'warm_rss_min_kib': low, 'warm_rss_max_kib': high,
            'rss_slope_kib_per_second': None if not count else covariance / variance if variance else 0}


def require_remote_lab():
    if not sys.platform.startswith('linux') or os.environ.get('MINYAR_REMOTE_LAB') != '1':
        raise SystemExit('Run sustained tests on the remote Linux lab with MINYAR_REMOTE_LAB=1')
