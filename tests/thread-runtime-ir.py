#!/usr/bin/env python3
"""Inspect the thread artifact's local/plain versus native/atomic RC split."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path, without_asm_source_locations


def body(ir, name):
    match = re.search(r'^define\b[^\n]*@' + re.escape(name) + r'\([^\n]*\)[^{]*\{(.*?)^}', ir, re.M | re.S)
    if not match:
        raise AssertionError('Missing runtime function: ' + name)
    return match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tsan', action='store_true')
    args = parser.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    cycle = build / 'thread-cycle-engine.c'
    cycle.write_text(engine_source(ROOT))
    compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for label, source in [('rc', ROOT / 'runtime/minyar_runtime.c'), ('cycle', cycle)]:
        output = build / ('thread-' + label + '-ownership.ll')
        command = [compiler, '-std=c11', '-O1', '-S', '-emit-llvm', '-DMINYAR_THREADED=1',
                   '-DMINYAR_SYSTEM_HEAP=1', '-I' + native_path(ROOT / 'runtime'),
                   native_path(source), '-o', native_path(output)]
        subprocess.run(command, check=True, timeout=60)
        ir = output.read_text()
        retain = body(ir, 'minyar_rc_retain')
        if not re.search(r'\bload\b', retain) or not re.search(r'\bstore\b', retain):
            raise AssertionError('Local RC lost its direct load/store path')
        if re.search(r'atomicrmw|cmpxchg|\b(?:load|store) atomic\b', retain):
            raise AssertionError('Local RC became atomic')
        release = body(ir, 'rc_thread_control_release')
        if not re.search(r'atomicrmw sub\b[^\n]*acq_rel', release):
            raise AssertionError('Native release lost atomic acquire/release lifetime')
        required = ['rc_frames', 'rc_free_frames', 'rc_pending_count', 'rc_bounded_head',
                    'rc_bounded_frame_head', 'rc_bounded_chunk_head']
        if label == 'cycle':
            required += ['rc_cycle_head', 'rc_cycle_pending', 'rc_cycle_shading', 'rc_cycle_enabled']
        for name in required:
            if not re.search(r'^@' + name + r' = [^\n]*thread_local', ir, re.M):
                raise AssertionError('Missing TLS state: ' + name)
        if args.tsan:
            instrumented = build / ('thread-' + label + '-tsan.ll')
            flags = list(command)
            flags.insert(1, '-fsanitize=thread')
            flags[-1] = native_path(instrumented)
            subprocess.run(flags, check=True, timeout=60)
            tsan = instrumented.read_text()
            local = body(tsan, 'minyar_rc_retain')
            shared = body(tsan, 'rc_thread_control_release')
            payload = body(tsan, 'minyar_frozen_bytes_get_uint8')
            if '__tsan_read' not in local or '__tsan_write' not in local:
                raise AssertionError('Local RC accesses lack TSan instrumentation')
            if '__tsan_atomic64_fetch_sub' not in shared or '__tsan_read1' not in payload:
                raise AssertionError('Shared lifetime/payload lacks TSan instrumentation')
        ordinary = []
        for selector in (None, '0'):
            plain = build / (label + '-ordinary-' + str(selector) + '.ll')
            flags = [arg for arg in command if arg != '-DMINYAR_THREADED=1']
            flags[-1] = native_path(plain)
            if selector is not None:
                flags.insert(1, '-DMINYAR_THREADED=' + selector)
            subprocess.run(flags, check=True, timeout=60)
            ordinary.append(without_asm_source_locations(plain.read_bytes()))
        if ordinary[0] != ordinary[1]:
            raise AssertionError('Zero selector changed ordinary artifact')
        print(label + ': plain local RC, atomic native lifetime, domain TLS, ordinary absent/0 identity passed')


if __name__ == '__main__':
    main()
