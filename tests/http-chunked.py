#!/usr/bin/env python3
"""Portable HTTP framing proof; independent socket peers, exact bodies, raw logs.

Run through make check-http-chunked / check-http-chunked-sanitize. Linux TLS
controls use a private fixture CA via OpenSSL's ordinary SSL_CERT_FILE path;
the production TLS implementation and its certificate checks are unchanged.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback


HEAD = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nX-Original: keep\r\n\r\n'
PAYLOAD = bytes([0, 255, 13, 10]) + b'hello world'
WIRE = HEAD + b'4 ; opaque="a\\\"b"\r\n' + PAYLOAD[:4] + b'\r\nB\r\n' + PAYLOAD[4:] + b'\r\n0\r\nSet-Cookie: trailer=ignored\r\n\r\n'
SAN = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(command, env, directory, name, timeout=180):
    started = time.monotonic()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, start_new_session=True)
    timed_out = False
    try:
        out, err = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(child.pid, signal.SIGKILL)
        out, err = child.communicate()
    (directory / (name + '.stdout')).write_bytes(out)
    (directory / (name + '.stderr')).write_bytes(err)
    row = {'command': command, 'returncode': child.returncode, 'timeout': timed_out,
           'elapsed_seconds': time.monotonic() - started,
           'stdout': out.decode('utf-8', errors='replace'), 'stderr': err.decode('utf-8', errors='replace')}
    (directory / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
    return row


@contextlib.contextmanager
def peer(parts, *, tls=None, hold=False):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(5)
    stop = threading.Event()
    record = {'request': None, 'error': None}

    def serve():
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                if tls:
                    connection = tls.wrap_socket(connection, server_side=True)
                with connection:
                    request = bytearray()
                    while b'\r\n\r\n' not in request:
                        block = connection.recv(4096)
                        if not block or len(request) + len(block) > 32768:
                            raise ValueError('incomplete or oversized request')
                        request.extend(block)
                    record['request'] = request.decode('ascii')
                    for delay, data in parts:
                        if stop.wait(delay):
                            break
                        connection.sendall(data)
                    if hold:
                        stop.wait(5)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as error:
            record['peer_closed'] = str(error)
        except Exception as error:
            record['error'] = repr(error)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield listener.getsockname()[1], record
    finally:
        stop.set()
        listener.close()
        worker.join(6)
        assert not worker.is_alive(), 'socket fixture did not finish'


def certificates(directory, env):
    key, cert = directory / 'root.key', directory / 'root.pem'
    commands = [
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
         '-subj', '/CN=Minyar chunk fixture root', '-keyout', str(key), '-out', str(cert),
         '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign'],
        ['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
         '-keyout', str(directory / 'leaf.key'), '-out', str(directory / 'leaf.csr')],
        ['openssl', 'x509', '-req', '-in', str(directory / 'leaf.csr'), '-CA', str(cert),
         '-CAkey', str(key), '-CAcreateserial', '-days', '1', '-out', str(directory / 'leaf.pem'),
         '-extfile', str(directory / 'leaf.ext')],
    ]
    (directory / 'leaf.ext').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
    for index, command in enumerate(commands):
        row = run(command, env, directory, 'certificate-' + str(index))
        assert row['returncode'] == 0 and not row['timeout'], row
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_3
    server.maximum_version = ssl.TLSVersion.TLSv1_3
    server.load_cert_chain(directory / 'leaf.pem', directory / 'leaf.key')
    return cert, server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, default=Path('build/http-chunked'))
    parser.add_argument('--profiles', nargs='+', choices=['debug', 'optimized', 'sanitize'], default=['debug', 'optimized'])
    args = parser.parse_args()
    root = Path.cwd()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='run-', dir=args.artifacts.resolve()))
    report = {'format': 'minyar-http-chunked-proof-v0', 'profiles': [], 'root': str(root),
              'source_sha256': {p: sha(root / p) for p in ('library/http.min', 'tests/http-chunked-client.min', 'tests/http-chunked.py', 'runtime/native/tlsverify.c')},
              'scope': 'public portable client against independent local plain/TLS peers; private parser tests at every selected profile'}
    failures = []
    try:
        env = dict(os.environ)
        env.update(LIMITED='', SANITIZER_LIMITED='')
        # The optional driver artifact collector copies the whole Clang ELF,
        # which exceeds the test file-size cap. Hash the installed tool instead.
        env.pop('MINYAR_LINK_ARTIFACTS', None)
        tls = ca = None
        if sys.platform.startswith('linux'):
            ca, tls = certificates(output, env)
        for profile in args.profiles:
            directory = output / profile
            directory.mkdir()
            flags = SAN if profile == 'sanitize' else ('-O0' if profile == 'debug' else '-O2') + ' -Wno-override-module'
            current = dict(env)
            current.update(MINYAR_CLANG_FLAGS=flags, MINYAR_NATIVE_FLAGS=flags, MINYAR_RUNTIME_FLAGS=flags,
                           ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            row = {'profile': profile, 'flags': flags, 'cases': [], 'tls': 'private CA via SSL_CERT_FILE' if tls else 'not run: this fixture requires Linux OpenSSL system-root provider'}
            report['profiles'].append(row)
            for source, name, test_mode in [('library/http.min', 'parser', True), ('tests/http-chunked-client.min', 'client', False)]:
                command = [str(root / 'minyar'), '--library', str(root / 'library')]
                if test_mode:
                    command.append('--test-mode')
                command += ['--debug' if profile == 'debug' else '--release', source, '-o', str(directory / name)]
                result = run(command, current, directory, 'build-' + name, 600)
                assert result['returncode'] == 0 and not result['timeout'], result
                row[name + '_sha256'] = sha(directory / name)
            parsed = run([str(directory / 'parser')], current, directory, 'private-parser', 120)
            assert parsed['returncode'] == 0 and not parsed['stderr'] and not parsed['timeout'], parsed
            row['private_parser_test_blocks'] = 7

            def case(name, wire=None, *, parts=None, body=b'', status=0, limit=64, timeout=500, method='GET', secure=False, trusted=True, hold=False):
                data = parts if parts is not None else [(0, wire)]
                result = {'name': name, 'expected_status': status, 'expected_body_hex': body.hex()}
                row['cases'].append(result)
                try:
                    body_path = directory / (name + '.body')
                    settings = dict(current)
                    if secure and trusted:
                        settings['SSL_CERT_FILE'] = str(ca)
                        settings['SSL_CERT_DIR'] = str(output / 'no-system-ca-directory')
                    with peer(data, tls=tls if secure else None, hold=hold) as (port, request):
                        url = ('https' if secure else 'http') + '://127.0.0.1:' + str(port) + '/chunked'
                        command = [str(directory / 'client'), method, url, str(limit), str(timeout), str(body_path)]
                        actual = run(command, settings, directory, name, 10)
                    result.update(process=actual, peer=request)
                    assert not request['error'], request
                    assert actual['returncode'] == 0 and not actual['stderr'] and not actual['timeout'], actual
                    lines = actual['stdout'].splitlines()
                    assert len(lines) >= 2 and int(lines[0]) == status, actual
                    assert bool(lines[1]) == (status == 0), actual
                    assert body_path.read_bytes() == body, (body_path.read_bytes(), body)
                    result['body_sha256'] = sha(body_path)
                    if status:
                        assert request['request'].startswith(method + ' /chunked HTTP/1.1\r\n'), request
                        assert 'Connection: close\r\n' in request['request'], request
                        assert all(not h.lower().startswith('set-cookie:') for h in lines[2:]), lines
                    result['passed'] = True
                except Exception as error:
                    result.update(passed=False, error=repr(error), traceback=traceback.format_exc())
                    failures.append(profile + ':' + name)
                print(profile, 'PASS' if result['passed'] else 'FAIL', name, flush=True)

            case('binary-extensions-trailers', WIRE, body=PAYLOAD, status=200, limit=len(PAYLOAD))
            case('split-every-byte', parts=[(0, bytes([b])) for b in WIRE], body=PAYLOAD, status=200, limit=len(PAYLOAD))
            case('complete-without-eof', WIRE, body=PAYLOAD, status=200, hold=True)
            case('empty', HEAD + b'0\r\n\r\n', status=200)
            case('informational', b'HTTP/1.1 103 Early Hints\r\nLink: </x>\r\n\r\n' + WIRE, body=PAYLOAD, status=200)
            case('decoded-body-cap', WIRE, limit=len(PAYLOAD) - 1)
            case('overflow', HEAD + b'8000000000000000\r\n')
            case('huge-announced-chunk', HEAD + b'7fffffffffffffff\r\n')
            case('incomplete-data', HEAD + b'4\r\nabc')
            case('incomplete-trailer', HEAD + b'0\r\nX: y\r\n')
            case('wrong-data-ending', HEAD + b'1\r\naX\r\n0\r\n\r\n')
            case('trailer-control', HEAD + b'0\r\nX: a\x00b\r\n\r\n')
            case('ambiguous-length', b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 0\r\n\r\n0\r\n\r\n')
            case('duplicate-coding', b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n')
            case('unsupported-coding', b'HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip, chunked\r\n\r\n0\r\n\r\n')
            case('framing-cap', HEAD + b'0\r\nX: ' + b'x' * 32768 + b'\r\n\r\n')
            case('read-deadline', parts=[(0, HEAD + b'1\r\na\r\n'), (0.3, b'0\r\n\r\n')], timeout=60)
            case('absolute-deadline', parts=[(0, HEAD), (0.04, b'1\r\na\r\n'), (0.04, b'1\r\nb\r\n'), (0.04, b'0\r\n\r\n')], timeout=90)
            case('head', HEAD, status=200, limit=1, method='HEAD', hold=True)
            case('reset-empty', b'HTTP/1.1 205 Reset\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n', status=205)
            case('reset-nonempty', b'HTTP/1.1 205 Reset\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\n\r\n')
            if tls:
                case('tls-binary', WIRE, body=PAYLOAD, status=200, secure=True)
                case('tls-fragments', parts=[(0, WIRE[:30]), (0, WIRE[30:65]), (0, WIRE[65:])], body=PAYLOAD, status=200, secure=True)
                case('tls-incomplete', HEAD + b'2\r\nx', secure=True)
                case('tls-untrusted-reject', WIRE, secure=True, trusted=False)
            row['expected_cases'] = 25 if tls else 21
            row['complete'] = len(row['cases']) == row['expected_cases']
            assert row['complete'], row
        report['compiler_sha256'] = {p: sha(root / p) for p in ('build/minyarc', 'build/tooling/tools/clang-driver')}
        clang = Path(shutil.which(env.get('LLVM_CC', 'clang-23'))).resolve()
        report['clang'] = {'path': str(clang), 'sha256': sha(clang), 'bytes': clang.stat().st_size}
    except Exception as error:
        failures.append('setup-or-parser')
        report.update(error=repr(error), traceback=traceback.format_exc())
    report['failures'] = failures
    report['passed'] = not failures
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('HTTP chunked proof:', output / 'report.json', flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
