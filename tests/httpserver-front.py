#!/usr/bin/env python3
"""Portable fixture smoke: actual server API, independent LRU and causal async HoL."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from clang_helpers import launcher_command, windows_host

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('httpserver_compare', ROOT/'benchmarks/httpserver/compare.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


def main():
    with tempfile.TemporaryDirectory(prefix='httpserver-front-', dir=ROOT/'build') as temporary:
        directory = Path(temporary)
        suffix = '.exe' if windows_host() else ''
        for name, source in [('cache', 'tests/httpserver-cache.min'), ('front', 'benchmarks/httpserver/front.min')]:
            program = directory/(name + suffix)
            subprocess.run([*launcher_command(ROOT), '--release', ROOT/source, '-o', program],
                           check=True, cwd=ROOT, timeout=90)
            if name == 'cache':
                result = subprocess.run([program], capture_output=True, text=True, check=True, timeout=5)
                assert result.stdout == 'cache fixture exact LRU verified\n' and not result.stderr
        queries = ['a b', 'second', 'third', 'fourth']
        bodies = [json.dumps(dict(query=q, total_us=1000)).encode() for q in queries]
        with compare.replay(queries, bodies, [0.001] * 4) as upstream:
            compare.verify_lru(directory/('front'+suffix), upstream.server_port, queries, bodies, directory)
            compare.verify_hol(directory/('front'+suffix), upstream, queries, bodies, directory)
        compare.controls()
    print('HTTP server cache-front exact bytes/LRU, raw key and causal HoL verified')


if __name__ == '__main__':
    main()
