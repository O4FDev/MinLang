#!/usr/bin/env python3
"""Check that visibility-withdrawal tests detect weakened invalidation."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / 'build/minyarc-modules'


def run(command):
    return subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=60)


def main():
    source = (ROOT / 'build/module-compiler.min').read_text()
    before = 'if owner != module { exported[symbol] = stamp }'
    after = 'if owner != module { exported[symbol] = 0 }'
    assert source.count(before) == 1
    with tempfile.TemporaryDirectory(prefix='minyar-interface-mutation-') as name:
        d = Path(name)
        mutated = d / 'compiler.min'; mutated.write_text(source.replace(before, after))
        for command in ([ROOT / 'build/minyarc', mutated, d / 'compiler.ll'],
                        ['clang', '-O2', '-Wno-override-module', '-flto', d / 'compiler.ll',
                         ROOT / 'build/minyar-compiler-runtime.ll', '-o', d / 'mutant']):
            result = run(command); assert result.returncode == 0, result.stderr
        entry = d / 'main.min'; leaf = d / 'leaf.min'; empty = d / 'empty'; empty.write_text('')
        entry.write_text('use "./leaf.min" as leaf\nfunction main() {\n    let value = leaf.Hidden { value: 7 }\n    print(value.value)\n}\n')
        public = 'public record Hidden { value: Integer }\npublic function make(): Hidden { return Hidden { value: 40 } }\n'
        results = {}
        for label, compiler in [('control', COMPILER), ('mutant', d / 'mutant')]:
            leaf.write_text(public)
            result = run([compiler, entry, d / 'out.ll', '--module-state', empty, d / 'state', d / 'stats'])
            assert result.returncode == 0, result.stderr
            # Visibility alone changes: the layout, source spelling of the
            # caller, and public factory return type remain identical.
            leaf.write_text(public.replace('public record', 'record'))
            result = run([compiler, entry, d / 'out.ll', '--module-state', d / 'state', d / 'next', d / 'stats'])
            results[label] = {'exit_code': result.returncode, 'stderr': result.stderr}
        assert results['control']['exit_code'] != 0 and 'private to its module' in results['control']['stderr']
        assert results['mutant']['exit_code'] == 0, results
        report = {'mutation': 'Remove exported visibility from interface identity',
                  'outcome': 'oracle detects the weakened invalidation',
                  'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                  'compiler_sha256': hashlib.sha256(COMPILER.read_bytes()).hexdigest(),
                  'results': results}
        (ROOT / 'build/incremental-module-mutation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('interface visibility oracle rejects the weakened invalidation mutant')


if __name__ == '__main__':
    main()
