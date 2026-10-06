#!/usr/bin/env python3
"""Retain coincident-name seam weakness and calibrate distinct GL namespaces.

Uses frozen renderer/fixture copies and already-built runtime objects. Never
changes a running soak, production source, or the original matrix evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    matrix_path = args.matrix.resolve()
    matrix = json.loads(matrix_path.read_text())
    assert matrix['status'] == 'passed'
    frozen = matrix_path.parent / 'sources'
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application-round2' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix=args.label + '-', dir=ROOT / 'build/native-research-round2'))
    fixture = frozen / 'tests/native-research-round2.c'
    graphics = frozen / 'runtime/native/graphics.c'
    original_fixture, original_graphics = fixture.read_text(), graphics.read_text()
    namespace_anchor = 'MAX_NAMES = 512'
    buffer_anchor = 'static void gen_buffers(GLsizei count, GLuint *names) {\n    assert(count == 1);\n    GLuint name = 1;'
    assert original_fixture.count(namespace_anchor) == original_fixture.count(buffer_anchor) == 1
    distinct_fixture = original_fixture.replace(namespace_anchor, 'MAX_NAMES = 1024').replace(
        buffer_anchor, buffer_anchor.replace('GLuint name = 1;', 'GLuint name = 513;'))
    swap_anchor = 'glBindBuffer(GL_ARRAY_BUFFER, mesh->buffer);'
    assert original_graphics.count(swap_anchor) == 2
    mutant = work / 'graphics-swapped.c'
    mutant.write_text(original_graphics.replace(swap_anchor, 'glBindBuffer(GL_ARRAY_BUFFER, mesh->array);'))
    report = {'status': 'running', 'matrix_sha256': digest(matrix_path), 'work': str(work),
              'sources': {'fixture_sha256': digest(fixture), 'graphics_sha256': digest(graphics),
                          'mutant_sha256': digest(mutant)}, 'commands': [], 'controls': [],
              'namespace_recipe': {'before': [namespace_anchor, buffer_anchor],
                                   'after': ['MAX_NAMES = 1024', buffer_anchor.replace('GLuint name = 1;', 'GLuint name = 513;')]},
              'graphics_mutation': {'before': swap_anchor, 'after': 'glBindBuffer(GL_ARRAY_BUFFER, mesh->array);', 'occurrences': 2},
              'scope': 'Fixture calibration, not a production fix. Original matrix uses coincident numeric names in distinct namespaces; a field swap can survive that seam.'}
    (evidence / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (evidence / 'distinct-fixture.c').write_text(distinct_fixture)

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    environment = {**os.environ, **{key: value for key, value in matrix['sanitizers'].items() if key.endswith('_OPTIONS')}}
    for mode in ['o2', 'sanitize']:
        name = 'system-' + mode
        original_command = next(row['command'] for row in matrix['commands'] if row['label'] == name + '-native')
        for namespace, source_code, native_source, expected_failure in [
                ('coincident-mutant', original_fixture, mutant, False),
                ('distinct-green', distinct_fixture, graphics, False),
                ('distinct-mutant', distinct_fixture, mutant, True)]:
            label = name + '-' + namespace
            prepared = work / (label + '.c')
            prepared.write_text(source_code.replace('#include "../runtime/minyar_native.h"',
                                 '#include "' + str(frozen / 'runtime/minyar_native.h') + '"').replace(
                                 '#include "../runtime/native/graphics.c"', '#include "' + str(native_source) + '"'))
            binary = work / label
            command = [part for part in original_command]
            command[command.index(str(fixture))] = str(prepared)
            command[command.index('-o') + 1] = str(binary)
            command[1:1] = ['-I', str(frozen / 'runtime/native')]
            result = subprocess.run(command, cwd=frozen, env=environment, capture_output=True, text=True, timeout=30)
            report['commands'].append({'label': label + '-compile', 'command': command,
                                       'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                                       'fixture_sha256': digest(prepared)})
            save()
            assert result.returncode == 0, result.stderr
            for seed in (0x51f37, 0x91a53, 0xffffffff, 0):
                command = [str(binary), 'mesh', str(seed), '1024', '0']
                result = subprocess.run(command, cwd=frozen, env=environment, capture_output=True, text=True, timeout=30)
                row = {'label': label, 'seed': seed, 'command': command, 'returncode': result.returncode,
                       'stdout': result.stdout, 'stderr': result.stderr, 'expected_failure': expected_failure}
                report['controls'].append(row)
                save()
                if expected_failure:
                    assert result.returncode != 0 and 'buffers[name].used' in result.stderr, (result.returncode, result.stderr)
                    assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr
                    row['detected'] = True
                else:
                    assert result.returncode == 0 and not result.stderr
                    stats = json.loads(result.stdout)
                    row['stats'] = stats
                    assert stats['mixed_iterations'] == 1024 and stats['capacity'] == 256
                    assert stats['creates'] == stats['deletes'] and stats['updates'] == stats['uploads'] == stats['draw_calls']
                    assert stats['active'] == stats['array_live'] == stats['buffer_live'] == 0
                    wanted = next(item['evidence'] for item in matrix['contracts'] if item['label'] == f'{name}-mesh-{seed}')
                    assert stats['trace_hash'] == wanted['trace_hash']
                    row['mutant_survived'] = namespace == 'coincident-mutant'
                    row['passed'] = True
                save()
    report.update(status='passed', coincident_mutant_survivals=sum(row.get('mutant_survived', False) for row in report['controls']),
                  distinct_mutants_detected=sum(row.get('detected', False) for row in report['controls']),
                  distinct_green_executions=sum(row['label'].endswith('distinct-green') for row in report['controls']))
    save()
    print(json.dumps({'status': report['status'], 'survivals': report['coincident_mutant_survivals'],
                      'distinct_detected': report['distinct_mutants_detected'], 'results': str(evidence / 'results.json')}, indent=2))


if __name__ == '__main__':
    main()
