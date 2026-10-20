#!/usr/bin/env python3
"""Relink two JS ablations using the exact already-frozen generated object."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import runpy
import shutil
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('run only through bx perfcs')
    original = args.manifest.resolve()
    out = original.parent
    manifest = json.loads(original.read_text())
    assert manifest['status'] == 'ready'
    for path, expected in manifest['immutable_files'].items():
        assert digest(path) == expected, path
    work = next(row for row in manifest['workloads'] if row['id'] == 'js-create-default')
    for role in ['baseline', 'candidate']:
        wrapper = out / ('js-default-' + role + '-runtime.c')
        assert '#define MINYAR_RC_TESTING 1' not in wrapper.read_text(), 'JS ablation needs shipping runtime'
    directory = out / 'ablations'
    directory.mkdir(exist_ok=False)
    transform = runpy.run_path(str(out / 'products.py'))['cycle_source']
    marker = '            /* Sole owner queue:'
    end_marker = '            /* End sole owner queue batching. */'
    candidate_header = (out / 'candidate-runtime/minyar_cycle_bounded_rc.h').read_text()
    assert candidate_header.count(marker) == candidate_header.count(end_marker) == 1
    first = candidate_header.index(marker)
    last = candidate_header.index(end_marker, first) + len(end_marker)
    roles = {}
    commands = []
    for role in ['cache-only', 'cycle-only']:
        tree = directory / (role + '-runtime')
        source_tree = out / ('candidate-runtime' if role == 'cache-only' else 'baseline-runtime')
        shutil.copytree(source_tree, tree)
        if role == 'cache-only':
            header = candidate_header[:first] + candidate_header[last:]
        else:
            header = candidate_header.replace('rc_bounded_chunk_retire(chunk);', 'rc_heap_deallocate(chunk);')
            assert header.count('rc_heap_deallocate(chunk);') == 1
        (tree / 'minyar_cycle_bounded_rc.h').write_text(header)
        source = transform((tree / 'minyar_runtime.c').read_text())
        wrapper = directory / (role + '.c')
        wrapper.write_text('#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 32\n' + source + '\n#include "minyar_stack_frames.h"\n')
        runtime = directory / (role + '.o')
        binary = directory / role
        clang, flags = manifest['clang']['path'], manifest['flags']
        sequence = [
            [clang, *flags, '-std=c11', '-fvisibility=hidden', '-iquote', str(tree), '-c', str(wrapper), '-o', str(runtime)],
            [clang, *flags, str(out / 'js-default.o'), str(out / 'js-native-files.o'),
             str(out / 'js-native-system.o'), str(runtime), '-lm', '-pthread', '-ldl', '-o', str(binary)]]
        for number, command in enumerate(sequence):
            record = {'role': role, 'argv': command}
            commands.append(record)
            with (directory / f'{role}-{number}.stdout').open('wb') as stdout, (directory / f'{role}-{number}.stderr').open('wb') as stderr:
                result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=600, check=False)
            record['exit'] = result.returncode
            (directory / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
            assert result.returncode == 0, command
        roles[role] = [str(binary)]
    work['roles'].update(roles)
    manifest['ablation'] = {'scope': 'exact same js-default.o and native objects as complete pair; runtime-only role differences',
                            'parent_manifest_sha256': digest(original), 'script_sha256': digest(__file__)}
    for path in directory.rglob('*'):
        if path.is_file():
            manifest['immutable_files'][str(path)] = digest(path)
    destination = out / 'ablation-manifest.json'
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('ABLATION_READY', destination)


if __name__ == '__main__':
    main()
