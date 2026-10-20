#!/usr/bin/env python3
"""Linux x86_64 hardware retired-instruction runner. Run on bx with sudo -n.

Example:
  sudo -n python3 build/frames-measure-baseline/frames-instructions.py \
      --directory build/frames-measure-baseline --samples 7

perf_event_open attaches to a stopped child and enables on exec. Only compiler
user-space instructions count; Python, hashing, linking, and kernel work do not.
The child drops sudo privileges before exec. No kernel settings are changed.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import statistics
import struct
import sys
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(command, stdout_path, stderr_path):
    pid = os.fork()
    if pid == 0:
        try:
            stdout_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            stderr_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
            if 'SUDO_GID' in os.environ:
                os.setgroups([])
                os.setgid(int(os.environ['SUDO_GID']))
                os.setuid(int(os.environ['SUDO_UID']))
            os.kill(os.getpid(), signal.SIGSTOP)
            os.execv(command[0], command)
        except BaseException as error:
            os.write(2, str(error).encode() + b'\n')
            os._exit(127)
    waited, status = os.waitpid(pid, os.WUNTRACED)
    if waited != pid or not os.WIFSTOPPED(status):
        raise RuntimeError('compiler child did not stop before exec: ' + repr(status))
    # PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS, PERF_ATTR_SIZE_VER0.
    # disabled, inherit, pinned, exclude_kernel, exclude_hv, enable_on_exec.
    flags = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 5) | (1 << 6) | (1 << 12)
    attr = ctypes.create_string_buffer(64)
    # read_format = TOTAL_TIME_ENABLED | TOTAL_TIME_RUNNING.
    struct.pack_into('<IIQQQQQ', attr, 0, 0, 64, 1, 0, 0, 3, flags)
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.syscall(298, ctypes.byref(attr), pid, -1, -1, 8)
    if fd < 0:
        code = ctypes.get_errno()
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        raise OSError(code, os.strerror(code), 'perf_event_open')
    began = time.perf_counter_ns()
    os.kill(pid, signal.SIGCONT)
    waited, status, usage = os.wait4(pid, 0)
    wall_ns = time.perf_counter_ns() - began
    raw = os.read(fd, 24)
    os.close(fd)
    if len(raw) != 24:
        raise RuntimeError('pinned hardware counter did not run: ' + repr(raw))
    instructions, enabled_ns, running_ns = struct.unpack('<QQQ', raw)
    if not instructions or not running_ns or running_ns != enabled_ns:
        raise RuntimeError('hardware counter did not run continuously: ' + repr((instructions, enabled_ns, running_ns)))
    return {'retired_instructions': instructions, 'counter_enabled_ns': enabled_ns,
        'counter_running_ns': running_ns, 'counter_scaled': False,
        'wall_ns': wall_ns, 'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
        'maximum_rss_kib': usage.ru_maxrss, 'exit': os.waitstatus_to_exitcode(status),
        'command': command}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='build/frames-measure-baseline')
    parser.add_argument('--samples', type=int, default=7)
    parser.add_argument('--profile', action='append', help='name=compiler-executable; default arena/eager/incremental in directory')
    parser.add_argument('--input', help='fixed source; default directory/compiler.min')
    parser.add_argument('--library', help='fixed library; default directory/library')
    parser.add_argument('--report', help='JSON report; default directory/instructions.json')
    options = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('this runner requires Linux x86_64 (syscall 298)')
    if options.samples < 1:
        parser.error('--samples must be positive')
    directory = Path(options.directory)
    input_path = Path(options.input) if options.input else directory / 'compiler.min'
    library = Path(options.library) if options.library else directory / 'library'
    report_path = Path(options.report) if options.report else directory / 'instructions.json'
    output = directory / 'self-compile.ll'
    profile_paths = dict(item.split('=', 1) for item in options.profile) if options.profile else {
        name: str(directory / ('compiler-' + name)) for name in ['arena', 'eager', 'incremental']}
    names = list(profile_paths)
    report = {'method': {'counter': 'PERF_TYPE_HARDWARE/PERF_COUNT_HW_INSTRUCTIONS',
        'scope': 'compiler process and inherited descendants; user-space only; enable-on-exec; pinned; no scaling',
        'samples': options.samples, 'warmups_per_profile': 1,
        'order': 'listed order on even iterations; reversed on odd; warmup is iteration zero',
        'child_uid': int(os.environ.get('SUDO_UID', os.getuid())),
        'python_parent_is_counted': False, 'kernel_is_counted': False},
        'host': {'kernel': platform.release(), 'machine': platform.machine(),
            'perf_event_paranoid': Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip()},
        'input': {'path': str(input_path), 'sha256': sha256(input_path)},
        'library': {'path': str(library), 'tree_sha256': hashlib.sha256(''.join(str(p.relative_to(library)) + ':' + sha256(p) + '\n' for p in sorted(library.rglob('*')) if p.is_file()).encode()).hexdigest()},
        'compiler_llvm': {'path': str(directory / 'compiler-stage2.ll'), 'sha256': sha256(directory / 'compiler-stage2.ll')},
        'profiles': {name: {'executable': path, 'executable_sha256': sha256(path), 'observations': []} for name, path in profile_paths.items()},
        'runner_sha256': sha256(__file__)}
    for iteration in range(options.samples + 1):
        order = names if iteration % 2 == 0 else list(reversed(names))
        for name in order:
            output.unlink(missing_ok=True)
            command = [str(Path(profile_paths[name]).resolve()), str(input_path), str(output), '--library', str(library)]
            observation = measure(command, str(directory / 'instructions.stdout'), str(directory / 'instructions.stderr'))
            observation.update({'sample': iteration - 1, 'warmup': iteration == 0,
                'output_sha256': sha256(output) if output.exists() else None,
                'output_bytes': output.stat().st_size if output.exists() else 0,
                'stdout': (directory / 'instructions.stdout').read_text(),
                'stderr': (directory / 'instructions.stderr').read_text()})
            report['profiles'][name]['observations'].append(observation)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
            print(json.dumps({'profile': name, 'sample': observation['sample'],
                'instructions': observation['retired_instructions'], 'exit': observation['exit'],
                'output_sha256': observation['output_sha256']}), flush=True)
            if observation['exit'] != 0:
                raise RuntimeError(json.dumps(observation))
    hashes = set()
    medians = {}
    for name, record in report['profiles'].items():
        measured = [o for o in record['observations'] if not o['warmup']]
        values = [o['retired_instructions'] for o in measured]
        record['instructions'] = values
        record['median_instructions'] = statistics.median(values)
        record['minimum_instructions'] = min(values)
        record['maximum_instructions'] = max(values)
        medians[name] = record['median_instructions']
        hashes.update(o['output_sha256'] for o in record['observations'])
    report['all_outputs_identical'] = len(hashes) == 1
    if 'arena' in medians:
        report['median_ratios_to_arena'] = {name: value / medians['arena'] for name, value in medians.items()}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('FRAMES_INSTRUCTIONS_RESULT ' + json.dumps(report, sort_keys=True), flush=True)
    if len(hashes) != 1:
        raise RuntimeError('compiler profiles emitted different LLVM')


if __name__ == '__main__':
    main()
