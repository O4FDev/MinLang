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
    """Yield independently timed samples and framed output; kill on any failure."""
    if timeout <= 0 or period <= 0: raise ValueError('positive observation times required')
    started = time.monotonic()
    next_sample = started
    pending = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
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
        selector.close()
        stop(process)
        process.stdout.close()
        if process.stderr is not None: process.stderr.close()

def memory_summary(samples, warmup=60):
    warm = [s for s in samples if s.get('elapsed_seconds', 0) >= warmup and 'rss_kib' in s]
    if not warm:
        return {'warm_rss_min_kib': None, 'warm_rss_max_kib': None, 'rss_slope_kib_per_second': None}
    mean_time = sum(s['elapsed_seconds'] for s in warm) / len(warm)
    mean_rss = sum(s['rss_kib'] for s in warm) / len(warm)
    numerator = sum((s['elapsed_seconds'] - mean_time) * (s['rss_kib'] - mean_rss) for s in warm)
    denominator = sum((s['elapsed_seconds'] - mean_time) ** 2 for s in warm)
    return {'warm_rss_min_kib': min(s['rss_kib'] for s in warm),
            'warm_rss_max_kib': max(s['rss_kib'] for s in warm),
            'rss_slope_kib_per_second': numerator / denominator if denominator else 0}

def require_remote_lab():
    if not sys.platform.startswith('linux') or os.environ.get('MINYAR_REMOTE_LAB') != '1':
        raise SystemExit('Run sustained tests on the remote Linux lab with MINYAR_REMOTE_LAB=1')
