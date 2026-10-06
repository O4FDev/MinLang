#!/usr/bin/env python3
"""One approved isolated real-shader mutation, with the original pixel oracle."""
import datetime
import difflib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('round6', ROOT / 'tests/native-research-round6.py')
round6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round6)
BASE = round6.BASE
FIRST = BASE / 'first-control'
LABEL = 'color-oracle-calibration'


def main():
    evidence = BASE / LABEL
    evidence.mkdir(exist_ok=False)
    work = ROOT / 'build/native-research-round6' / LABEL
    work.mkdir(parents=True, exist_ok=False)
    first_files = {str(p.relative_to(FIRST)): round6.digest(p) for p in FIRST.rglob('*') if p.is_file()}
    report = {'status': 'preparing', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'commands': [], 'real_context_attempts': 0, 'production_edits': False,
              'source_mutation': 'world vertex shader fragmentColor=color*0.5',
              'limits': {'one_native_child': True, 'wall_seconds': 30, 'rss_bytes': 256 * 1024**2},
              'limitations': 'Oracle sensitivity only, not additional feature correctness, sanitizer, leak or performance evidence.'}
    try:
        authorization = json.loads((BASE / 'authorization-calibration.json').read_text())
        assert authorization['approved'] and authorization['scope'] == 'one-isolated-color-oracle-calibration'
        prior = json.loads((FIRST / 'results.json').read_text())
        assert prior['status'] == 'passed_first_control'
        assert round6.digest(Path(prior['compiler']['path'])) == prior['compiler']['sha256']
        report['compiler'] = prior['compiler']
        for name, expected in round6.ACCEPTED.items():
            assert round6.digest(ROOT / name) == expected, name
        runtime = next(obj for obj in prior['objects'] if obj.get('mode') == 'o2')
        runtime_path = Path(runtime['path'])
        assert round6.digest(runtime_path) == runtime['sha256']
        report['reused_runtime'] = runtime
        frozen = evidence / 'sources'
        shutil.copytree(FIRST / 'sources', frozen)
        source_path = frozen / 'runtime/native/graphics.c'
        source = source_path.read_text()
        anchor = ('    "    fragmentUv = uv;\\n"\n'
                  '    "    fragmentColor = color;\\n"\n'
                  '    "    fragmentLighting = lighting;\\n"')
        assert source.count(anchor) == 1
        mutant = source.replace(anchor, anchor.replace('fragmentColor = color;', 'fragmentColor = color * 0.5;'), 1)
        source_path.write_text(mutant)
        patch = ''.join(difflib.unified_diff(source.splitlines(True), mutant.splitlines(True),
                                          fromfile='accepted/graphics.c', tofile='isolated/graphics.c'))
        (evidence / 'single-shader-color-factor.patch').write_text(patch)
        report['mutation'] = {'anchor_matches': 1, 'anchor': anchor, 'changed_lines': 1,
                              'original_sha256': round6.digest(FIRST / 'sources/runtime/native/graphics.c'),
                              'mutant_sha256': round6.digest(source_path),
                              'patch_sha256': round6.digest(evidence / 'single-shader-color-factor.patch')}
        for name in ['triangle-120.bin', 'expected-pixels.json']:
            shutil.copy2(FIRST / name, evidence / name)
            assert round6.digest(FIRST / name) == round6.digest(evidence / name)
        shutil.copy2(evidence / 'triangle-120.bin', work / 'triangle-120.bin')
        oracle = json.loads((evidence / 'expected-pixels.json').read_text())
        report['unchanged_oracle_sha256'] = round6.digest(evidence / 'expected-pixels.json')
        report['unchanged_triangle_sha256'] = round6.digest(evidence / 'triangle-120.bin')
        report['runner_sha256'] = round6.digest(Path(__file__))
        shutil.copy2(Path(__file__), evidence / Path(__file__).name)
        proposal = {'status': 'approved_one_calibration', 'authorization': str(BASE / 'authorization-calibration.json'),
                    'visibility_and_limits': 'identical to first-control; hidden/unfocused64x64; one context/child;30s/256MiB',
                    'seam': 'first-control C fixture unchanged, accepted renderer copy modified at exactly one anchored world shader line',
                    'mutation': report['mutation'], 'oracle': 'first-control expected-pixels.json and triangle bytes unchanged',
                    'anticipated': 'compile/link/native setup/draw/readback/deletion/cleanup succeed; original independent interior pixel assertion rejects halved color',
                    'cleanup_order': 'native returns normally and atexit cleanup finishes before Python validates pixels',
                    'no_further_cases': True}
        round6.write_json(ROOT / 'research/2026-10-memory/native-application-round6-calibration-proposal.json', proposal)
        round6.write_json(evidence / 'proposal.json', proposal)
        report['sources'] = [{'path': str(p.relative_to(frozen)), 'sha256': round6.digest(p)}
                             for p in sorted(frozen.rglob('*')) if p.is_file()]
        round6.write_json(evidence / 'results.json', report)
        cflags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'glfw3'], text=True))
        libraries = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'glfw3'], text=True))
        obj, binary = work / 'fixture.o', work / 'fixture'
        round6.monitored('compile-o2', ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2', *cflags,
                                      '-c', frozen / 'tests/native-research-round6.c', '-o', obj], work, evidence, report)
        report['object_sha256'] = round6.digest(obj)
        round6.monitored('link-o2', ['clang', '-O2', obj, runtime_path, *libraries,
                                   '-framework', 'OpenGL', '-lm', '-o', binary], work, evidence, report)
        report['binary_sha256'] = round6.digest(binary)
        report['status'] = 'approved_calibration_context_started'
        report['real_context_attempts'] = 1
        round6.write_json(evidence / 'results.json', report)
        round6.monitored('native-o2', [binary, '--approved-hidden64'], work, evidence, report)
        report['native_process_succeeded'] = True
        observations = [json.loads(row) for row in (evidence / 'native-o2.stdout').read_text().splitlines()]
        report['driver_observations'] = observations
        programs = [row for row in observations if row['kind'] == 'program']
        assert len(programs) == 2 and all(row['linked'] and len(row['attached_shaders']) == 2 and
                                         all(shader['compiled'] for shader in row['attached_shaders'])
                                         for row in programs)
        report['actual_shader_compile_and_program_link_succeeded'] = True
        cleanup = next(row for row in observations if row['kind'] == 'cleanup')
        assert cleanup['completed'] and cleanup['gl_error'] == 0 and cleanup['context_destroyed']
        report['normal_native_cleanup_before_oracle'] = cleanup
        payload = (work / 'pixels-rgba8.bin').read_bytes()
        (evidence / 'pixels-rgba8.bin').write_bytes(payload)
        report['pixels_sha256'] = round6.digest(evidence / 'pixels-rgba8.bin')
        try:
            round6.validate_pixels(payload, oracle)
        except AssertionError as error:
            report['independent_pixel_assertion'] = {'expected_rejection': True, 'error': repr(error),
                                                    'tolerance_codes': oracle['tolerance_codes']}
            (evidence / 'pixel-assertion.txt').write_text(repr(error) + '\n')
        else:
            raise AssertionError('isolated color mutant unexpectedly survived original pixel oracle')
        report['status'] = 'calibration_detected'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = repr(error)
        if (work / 'pixels-rgba8.bin').is_file():
            shutil.copy2(work / 'pixels-rgba8.bin', evidence / 'pixels-rgba8.bin')
        raise
    finally:
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['accepted_sources_unchanged'] = {name: round6.digest(ROOT / name) == expected
                                               for name, expected in round6.ACCEPTED.items()}
        report['first_control_files_unchanged'] = all((FIRST / name).is_file() and round6.digest(FIRST / name) == expected
                                                     for name, expected in first_files.items())
        round6.write_json(evidence / 'first-control-entry-hashes.json', first_files)
        round6.write_json(evidence / 'results.json', report)
        shutil.rmtree(work)
        print(json.dumps({'status': report['status'], 'real_context_attempts': report['real_context_attempts'],
                          'evidence': str(evidence)}))


if __name__ == '__main__':
    main()
