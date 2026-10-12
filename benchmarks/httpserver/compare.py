#!/usr/bin/env python3
"""Finite 548-query cache-front identity/LRU/HoL comparison, fixed 1.5x p50+p99 gate.

Full acceptance is the default (three paired rounds). --verify-only runs one
correctness round and explicitly does NOT qualify performance.
"""
import argparse
from collections import OrderedDict
from contextlib import contextmanager
import csv
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import math
from pathlib import Path
import queue
import statistics
import subprocess
import threading
import time
import urllib.parse

HERE = Path(__file__).resolve().parent
CORPUS_SHA = '74f31164ecbcb19c8911870510fd7fb56f58d79930d39fc0c3aebd9c1e1fb6f6'
REPLAY_SHA = '6233b7f0e13c9c5563d65d892d750d1ab6357ddddc5d39cc91dd530d35d660bb'
COHORTS = ('miss', 'hit', 'stats', 'hol_miss', 'hol_hit')
THRESHOLD = 1.5


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def corpus(queries, recording):
    assert digest(queries) == CORPUS_SHA, '548-query corpus bytes changed'
    assert digest(recording) == REPLAY_SHA, 'recorded body input bytes changed'
    with Path(queries).open(newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    queries = [row['query'] for row in rows]
    assert len(queries) == len(set(queries)) == 548
    with gzip.open(recording, 'rt', encoding='utf-8', errors='surrogateescape') as stream:
        bodies = [json.loads(line).encode('utf-8', 'surrogateescape') for line in stream]
    assert len(bodies) == 548
    # Reproduce query-specific engine compute latency from its recorded total_us,
    # without changing any response bytes. Both fronts see precisely this trace.
    delays = [json.loads(body)['total_us'] / 1_000_000 for body in bodies]
    assert all(isinstance(delay, (int, float)) and 0 <= delay < 5 for delay in delays)
    return queries, bodies, delays


def target(query, k='10'):
    return '/api/search?q=' + urllib.parse.quote(query, safe='') + '&k=' + k


class Replay(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    def __init__(self, queries, bodies, delays):
        self.table = dict(zip(queries, zip(bodies, delays)))
        self.lock = threading.Lock()
        self.calls = []
        self.started = threading.Event()
        self.block_query = None
        self.release = threading.Event()
        super().__init__(('127.0.0.1', 0), ReplayHandler)
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()


class ReplayHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_GET(self):
        parts = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)
        query = parts.get('q', [''])[0]
        body, delay = self.server.table.get(query, (b'unknown query', 0))
        with self.server.lock:
            self.server.calls.append(self.path)
        self.server.started.set()
        if query == self.server.block_query:
            self.server.release.wait(timeout=4)
        time.sleep(delay)
        status = 200 if query in self.server.table else 404
        self.send_response_only(status)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(body)))
        self.send_header('connection', 'close')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True
    def log_message(self, *args):
        pass


@contextmanager
def replay(queries, bodies, delays):
    server = Replay(queries, bodies, delays)
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        server.thread.join(timeout=2)


@contextmanager
def front(binary, upstream, log, entries=100000, byte_limit=268435456):
    command = [str(Path(binary).resolve()), '0', '127.0.0.1', str(upstream), str(entries), str(byte_limit)]
    with Path(log).open('w+') as diagnostics:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=diagnostics, text=True)
        try:
            ready = queue.Queue()
            threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
            line = ready.get(timeout=10)
            assert line.strip().isdigit(), ('front startup failed', command, line)
            yield int(line), command
            assert process.poll() is None, ('front died', process.returncode)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
            process.stdout.close()
            diagnostics.seek(0)
            text = diagnostics.read()
            assert not text, (command, text)


def fetch(port, path, expected=None, state=None, deadline=None):
    timeout = 6
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
        assert timeout > 0, 'finite run deadline exceeded'
    start = time.perf_counter_ns()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        connection.request('GET', path, headers={'Connection': 'close'})
        response = connection.getresponse()
        body = response.read()
        elapsed = (time.perf_counter_ns() - start) / 1000
        assert response.status == 200, (path, response.status, body[:100])
        assert int(response.getheader('content-length')) == len(body)
        observed = response.getheader('x-cache')
        if state is not None:
            assert observed == state, (path, state, observed)
        if expected is not None:
            assert body == expected, ('raw byte identity failed', path)
        return elapsed, body, observed
    finally:
        connection.close()


def stats(port):
    return json.loads(fetch(port, '/stats', state='none')[1])


def raw_key(path):
    query = path.split('?', 1)[1]
    def first(name):
        for part in query.split('&'):
            key, sep, value = part.partition('=')
            if sep and key == name:
                return value
        return ''
    return (first('k') + '\0' + first('q')).encode()


def verify_lru(binary, upstream, queries, bodies, output):
    # Independent OrderedDict oracle checks both entry and key+body byte bounds,
    # raw encoding/duplicate parameter distinctions and deterministic eviction.
    paths = [target(q) for q in queries[:4]]
    first = target(queries[0])
    raw_variant = first.replace('%20', '+') if '%20' in first else first + '&k=ignored'
    cases = [(3, 268435456, [0, 1, 2, 0, 3, 0, 2, 3, 1, 0]),
             (3, max(len(b) + len(raw_key(p)) for p, b in zip(paths, bodies)) * 2, [0, 1, 0, 2, 3, 0]),
             (3, 1, [0, 0])]
    for case, (entries, byte_limit, sequence) in enumerate(cases):
        model = OrderedDict()
        hits = misses = evictions = used = 0
        with front(binary, upstream, output / f'lru-{case}.log', entries, byte_limit) as (port, _):
            accesses = [(paths[i], bodies[i]) for i in sequence]
            if case == 0:
                accesses += [(raw_variant, bodies[0]), (paths[0] + '&q=ignored', bodies[0]),
                             (target(queries[0], '11'), bodies[0])]
            for path, body in accesses:
                key = raw_key(path)
                hit = key in model
                fetch(port, path, body, 'hit' if hit else 'miss')
                if hit:
                    hits += 1; model.move_to_end(key)
                else:
                    misses += 1
                    size = len(key) + len(body)
                    if size <= byte_limit:
                        while len(model) >= entries or used + size > byte_limit:
                            old_key, old_body = model.popitem(last=False)
                            used -= len(old_key) + len(old_body); evictions += 1
                        model[key] = body; used += size
                observed = stats(port)
                expected = dict(hits=hits, misses=misses, entries=len(model), bytes=used,
                                evictions=evictions, upstream_connects=misses)
                assert observed == expected, (case, path, observed, expected)


def rows(port, paths, bodies, state, deadline):
    result = []
    for index, (path, body) in enumerate(zip(paths, bodies)):
        elapsed, observed, cache = fetch(port, path, body, state, deadline)
        result.append(dict(index=index, latency_us=elapsed, body_sha256=hashlib.sha256(observed).hexdigest(),
                           status=200, cache=cache))
    return result


def verify_hol(binary, upstream, queries, bodies, output):
    # Causal correctness check: hold an upstream miss until a cached hit finishes.
    with front(binary, upstream.server_port, output/'hol-control.log') as (port, _):
        fetch(port, target(queries[0]), bodies[0], 'miss')
        upstream.started.clear(); upstream.release.clear(); upstream.block_query = queries[1]
        done = queue.Queue()
        def miss():
            try:
                done.put(fetch(port, target(queries[1]), bodies[1], 'miss'))
            except BaseException as error:
                done.put(error)
        worker = threading.Thread(target=miss, daemon=True); worker.start()
        try:
            assert upstream.started.wait(timeout=2), 'upstream miss never started'
            assert done.empty(), 'miss finished before HoL control'
            fetch(port, target(queries[0]), bodies[0], 'hit')
            assert done.empty(), 'cached hit waited for held upstream miss'
        finally:
            upstream.release.set(); upstream.block_query = None
            worker.join(timeout=6)
        assert not worker.is_alive()
        result = done.get(timeout=1)
        if isinstance(result, BaseException):
            raise result
        assert stats(port)['hits'] == 1 and stats(port)['misses'] == 2


def run_round(binary, upstream, queries, bodies, output, deadline):
    paths = [target(query) for query in queries]
    result = {}
    with front(binary, upstream.server_port, output/'sequential.log') as (port, command):
        # Warm accept/stats code without populating the search cache.
        for _ in range(16):
            stats(port)
        result['miss'] = rows(port, paths, bodies, 'miss', deadline)
        assert stats(port) == dict(hits=0, misses=548, entries=548,
            bytes=sum(len(raw_key(p)) + len(b) for p, b in zip(paths, bodies)), evictions=0, upstream_connects=548)
        result['hit'] = rows(port, paths, bodies, 'hit', deadline)
        snapshot = stats(port)
        assert snapshot['hits'] == snapshot['misses'] == 548
        result['stats'] = rows(port, ['/stats'] * 548, [json.dumps(snapshot, separators=(',', ':')).encode()] * 548,
                               'none', deadline)
    with front(binary, upstream.server_port, output/'concurrent.log') as (port, _):
        fetch(port, paths[0], bodies[0], 'miss', deadline)
        upstream.started.clear()
        done = queue.Queue()
        def misses():
            try:
                done.put(rows(port, paths[1:], bodies[1:], 'miss', deadline))
            except BaseException as error:
                done.put(error)
        worker = threading.Thread(target=misses, daemon=True); worker.start()
        assert upstream.started.wait(timeout=2), 'concurrent misses did not start'
        try:
            result['hol_hit'] = rows(port, [paths[0]] * 548, [bodies[0]] * 548, 'hit', deadline)
            assert worker.is_alive(), 'HoL cohort did not overlap misses'
        finally:
            worker.join(timeout=max(0.01, min(60, deadline - time.monotonic())))
        assert not worker.is_alive(), 'finite miss worker did not finish'
        missed = done.get(timeout=1)
        if isinstance(missed, BaseException):
            raise missed
        result['hol_miss'] = missed
        assert stats(port)['hits'] == stats(port)['misses'] == 548
    return result, command


def percentile(samples, p):
    return sorted(samples)[max(0, math.ceil(len(samples) * p / 100) - 1)]


def gate(results):
    assert set(results) == {'minyar', 'axum'}
    assert all(len(results[name]) == 3 for name in results), 'acceptance requires exactly three paired rounds'
    ratios = {}
    for cohort in COHORTS:
        ratios[cohort] = {}
        expected_count = 547 if cohort == 'hol_miss' else 548
        for rounds in results.values():
            assert all(set(run) == set(COHORTS) and len(run[cohort]) == expected_count for run in rounds)
            assert all(row['status'] == 200 and math.isfinite(row['latency_us']) and row['latency_us'] > 0
                       for run in rounds for row in run[cohort])
        for p in (50, 99):
            # Gate the median of three complete per-round nearest-rank percentiles.
            measured = {name: statistics.median(percentile([row['latency_us'] for row in run[cohort]], p)
                         for run in rounds) for name, rounds in results.items()}
            ratio = measured['minyar'] / measured['axum']
            ratios[cohort][f'p{p}'] = dict(minyar_us=measured['minyar'], axum_us=measured['axum'], ratio=ratio,
                                         passed=ratio <= THRESHOLD)
    return ratios, all(cell['passed'] for cohort in ratios.values() for cell in cohort.values())


def controls():
    def dataset(latency):
        return [{cohort: [dict(status=200, latency_us=latency)] * (547 if cohort == 'hol_miss' else 548)
                 for cohort in COHORTS} for _ in range(3)]
    assert gate(dict(minyar=dataset(150), axum=dataset(100)))[1]
    assert not gate(dict(minyar=dataset(150.001), axum=dataset(100)))[1]
    tail = dataset(100)
    for run in tail:
        for cohort in COHORTS:
            run[cohort] = [dict(row) for row in run[cohort]]
            for row in run[cohort][-6:]:
                row['latency_us'] = 200
    ratios, passed = gate(dict(minyar=tail, axum=dataset(100)))
    assert not passed and all(cell['p50']['passed'] and not cell['p99']['passed'] for cell in ratios.values())
    missing = dict(minyar=dataset(100), axum=dataset(100)); missing['minyar'][0]['hit'].pop()
    try:
        gate(missing)
    except AssertionError:
        pass
    else:
        raise AssertionError('gate accepted missing samples')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minyar', type=Path)
    parser.add_argument('--axum', type=Path)
    parser.add_argument('--queries', type=Path)
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    controls()
    if args.self_test:
        print('Fixed 1.5x p50/p99 gate rejects regression and missing samples'); return
    for name in ('minyar', 'axum', 'queries', 'replay', 'output'):
        if getattr(args, name) is None:
            parser.error('--' + name + ' is required')
    args.output.mkdir(parents=True, exist_ok=True)
    assert not any(args.output.iterdir()), 'output must be empty'
    queries, bodies, delays = corpus(args.queries, args.replay)
    manifest = dict(schema_version=1, threshold=THRESHOLD, mode='verify-only' if args.verify_only else 'acceptance',
        status='running', corpus_sha256=digest(args.queries), replay_sha256=digest(args.replay),
        binaries={name: dict(path=str(path.resolve()), sha256=digest(path))
                  for name, path in [('minyar', args.minyar), ('axum', args.axum)]}, commands=[], results={})
    rounds = 1 if args.verify_only else 3
    results = dict(minyar=[], axum=[])
    deadline = time.monotonic() + (180 if args.verify_only else 600)
    try:
        with replay(queries, bodies, delays) as upstream:
            for name, binary in [('minyar', args.minyar), ('axum', args.axum)]:
                output = args.output/name; output.mkdir()
                verify_lru(binary, upstream.server_port, queries, bodies, output)
                verify_hol(binary, upstream, queries, bodies, output)
            for round in range(rounds):
                # Alternate process order; fronts never run together while timing cohorts.
                names = ['minyar', 'axum'] if round % 2 == 0 else ['axum', 'minyar']
                for name in names:
                    output = args.output/name/f'round-{round}'; output.mkdir()
                    result, command = run_round(getattr(args, name), upstream, queries, bodies, output, deadline)
                    results[name].append(result); manifest['commands'].append(command)
                    (output/'samples.json').write_text(json.dumps(result, indent=2)+'\n')
            with upstream.lock:
                (args.output/'upstream-targets.json').write_text(json.dumps(upstream.calls, indent=2)+'\n')
        if args.verify_only:
            manifest['status'] = 'correctness_passed'; manifest['performance'] = 'not_qualified'
        else:
            ratios, passed = gate(results)
            manifest['results'] = ratios
            manifest['status'] = 'passed' if passed else 'failed'
            assert passed, 'fixed <=1.5x p50 AND p99 gate failed; inspect results.json'
    except BaseException as error:
        manifest['status'] = 'failed'; manifest['error'] = repr(error)
        raise
    finally:
        (args.output/'results.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('548-query raw identity, exact LRU and async HoL verified; ' +
          ('performance not qualified' if args.verify_only else 'all fixed p50/p99 gates passed'))


if __name__ == '__main__':
    main()
