"""Contained native Windows command owner; no MSYS process-group assumptions."""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

# Explicit Win32 widths also keep static structure review meaningful on POSIX.
U32, I32, U64, I64 = ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint64, ctypes.c_int64
HANDLE, SIZE = ctypes.c_void_p, ctypes.c_size_t


class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', I64), ('job_time', I64), ('flags', U32),
                ('minimum_working_set', SIZE), ('maximum_working_set', SIZE),
                ('active_limit', U32), ('affinity', SIZE), ('priority', U32), ('scheduling', U32)]


class IOCounters(ctypes.Structure):
    _fields_ = [(name, U64) for name in ('read_operations', 'write_operations', 'other_operations',
                                       'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IOCounters), ('process_memory', SIZE),
                ('job_memory', SIZE), ('peak_process_memory', SIZE), ('peak_job_memory', SIZE)]


class Accounting(ctypes.Structure):
    _fields_ = [('user_time', I64), ('kernel_time', I64), ('period_user', I64),
                ('period_kernel', I64), ('page_faults', U32), ('total_processes', U32),
                ('active_processes', U32), ('terminated_processes', U32)]


class Startup(ctypes.Structure):
    _fields_ = [('size', U32), ('reserved', ctypes.c_wchar_p), ('desktop', ctypes.c_wchar_p),
                ('title', ctypes.c_wchar_p), ('x', U32), ('y', U32), ('width', U32),
                ('height', U32), ('chars_x', U32), ('chars_y', U32), ('fill', U32),
                ('flags', U32), ('show', ctypes.c_uint16), ('reserved_size', ctypes.c_uint16),
                ('reserved_bytes', ctypes.c_void_p), ('stdin', HANDLE), ('stdout', HANDLE),
                ('stderr', HANDLE)]


class StartupEx(ctypes.Structure):
    _fields_ = [('startup', Startup), ('attributes', ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [('process', HANDLE), ('thread', HANDLE), ('pid', U32), ('tid', U32)]


class WinAPI:
    """Only native NT Python loads APIs; the command is atomically born in our job."""
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Contained Windows launch requires native NT Python')
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        definitions = {
            'CreateJobObjectW': (HANDLE, [ctypes.c_void_p, ctypes.c_wchar_p]),
            'SetInformationJobObject': (I32, [HANDLE, I32, ctypes.c_void_p, U32]),
            'QueryInformationJobObject': (I32, [HANDLE, I32, ctypes.c_void_p, U32, ctypes.c_void_p]),
            'GetHandleInformation': (I32, [HANDLE, ctypes.POINTER(U32)]),
            'IsProcessInJob': (I32, [HANDLE, HANDLE, ctypes.POINTER(I32)]),
            'GetCurrentProcess': (HANDLE, []),
            'DuplicateHandle': (I32, [HANDLE, HANDLE, HANDLE, ctypes.POINTER(HANDLE), U32, I32, U32]),
            'InitializeProcThreadAttributeList': (I32, [ctypes.c_void_p, U32, U32, ctypes.POINTER(SIZE)]),
            'UpdateProcThreadAttribute': (I32, [ctypes.c_void_p, U32, SIZE, ctypes.c_void_p,
                                               SIZE, ctypes.c_void_p, ctypes.c_void_p]),
            'DeleteProcThreadAttributeList': (None, [ctypes.c_void_p]),
            'CreateProcessW': (I32, [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
                                   ctypes.c_void_p, I32, U32, ctypes.c_void_p, ctypes.c_wchar_p,
                                   ctypes.c_void_p, ctypes.POINTER(ProcessInfo)]),
            'ResumeThread': (U32, [HANDLE]),
            'TerminateJobObject': (I32, [HANDLE, U32]),
            'WaitForSingleObject': (U32, [HANDLE, U32]),
            'GetExitCodeProcess': (I32, [HANDLE, ctypes.POINTER(U32)]),
            'CloseHandle': (I32, [HANDLE]),
        }
        for name, (result, arguments) in definitions.items():
            function = getattr(self.k, name)
            function.restype, function.argtypes = result, arguments
        self.attributes, self.handles, self.files = None, [], []
        self.attributes_initialized = False
        self.attribute_values = []

    def checked(self, name, *args):
        result = getattr(self.k, name)(*args)
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def create_job(self):
        job = self.checked('CreateJobObjectW', None, None)
        self.handles.append(job)
        information = ExtendedLimits()
        # No breakaway or silent-breakaway flags; this job is not inherited.
        information.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.checked('SetInformationJobObject', job, 9, ctypes.byref(information),
                     ctypes.sizeof(information))
        flags = U32()
        self.checked('GetHandleInformation', job, ctypes.byref(flags))
        if flags.value & 1:
            raise RuntimeError('Owned job unexpectedly inheritable')
        return job

    def spawn_suspended(self, job, command, cwd, stdout, stderr):
        import msvcrt
        std = []
        for path, mode in (('NUL', 'rb'), (stdout, 'wb'), (stderr, 'wb')):
            file = open(path, mode, buffering=0)
            self.files.append(file)
            duplicated = HANDLE()
            self.checked('DuplicateHandle', self.k.GetCurrentProcess(),
                         HANDLE(msvcrt.get_osfhandle(file.fileno())),
                         self.k.GetCurrentProcess(), ctypes.byref(duplicated), 0, 1, 2)
            std.append(duplicated.value)
            self.handles.append(duplicated.value)
        size = SIZE()
        result = self.k.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        if result or ctypes.get_last_error() != 122 or not size.value:
            raise RuntimeError('Windows job attribute sizing failed')
        self.attributes = ctypes.create_string_buffer(size.value)
        self.checked('InitializeProcThreadAttributeList', self.attributes, 2, 0,
                     ctypes.byref(size))
        self.attributes_initialized = True
        job_list = (HANDLE * 1)(job)
        handle_list = (HANDLE * 3)(*std)
        # Microsoft requires lpValue buffers to live until attribute deletion.
        # Own both before the first update, including partial-update failures.
        self.attribute_values.extend((job_list, handle_list))
        self.checked('UpdateProcThreadAttribute', self.attributes, 0, 0x0002000D,
                     job_list, ctypes.sizeof(job_list), None, None)
        self.checked('UpdateProcThreadAttribute', self.attributes, 0, 0x00020002,
                     handle_list, ctypes.sizeof(handle_list), None, None)
        startup = StartupEx()
        startup.startup.size = ctypes.sizeof(startup)
        startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = std
        startup.attributes = ctypes.cast(self.attributes, ctypes.c_void_p)
        info = ProcessInfo()
        argv = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        environment = ctypes.create_unicode_buffer(
            '\0'.join(key + '=' + value for key, value in sorted(
                os.environ.items(), key=lambda row: row[0].upper())) + '\0\0')
        self.checked('CreateProcessW', command[0], argv, None, None, 1,
                     0x00080000 | 0x00000400 | 0x00000004,  # extended/unicode/suspended
                     environment, str(cwd), ctypes.byref(startup), ctypes.byref(info))
        self.handles.extend((info.process, info.thread))
        return info

    def verify_assignment(self, job, process):
        assigned = I32()
        self.checked('IsProcessInJob', process.process, job, ctypes.byref(assigned))
        if assigned.value != 1:
            raise RuntimeError('Original command was not atomically assigned to the owned job')

    def resume(self, process):
        previous = self.k.ResumeThread(process.thread)
        if previous != 1:
            raise RuntimeError('Unexpected suspended-thread resume count: ' + str(previous))

    def active(self, job):
        information = Accounting()
        self.checked('QueryInformationJobObject', job, 1, ctypes.byref(information),
                     ctypes.sizeof(information), None)
        return int(information.active_processes)

    def terminate(self, job):
        self.checked('TerminateJobObject', job, 253)

    def status(self, process):
        wait = self.k.WaitForSingleObject(process.process, 0)
        if wait != 0:
            raise RuntimeError('Owned root is not terminal after job closure: ' + str(wait))
        status = U32()
        self.checked('GetExitCodeProcess', process.process, ctypes.byref(status))
        return int(status.value)

    def close(self):
        failures = []
        if self.attributes_initialized:
            try:
                self.k.DeleteProcThreadAttributeList(self.attributes)
            except BaseException as error:
                failures.append(error)
            else:
                self.attributes_initialized = False
                self.attributes = None
                self.attribute_values.clear()
        else:
            self.attributes = None
            self.attribute_values.clear()
        # Process/thread/std duplicates close before the final job handle.
        for handle in reversed(self.handles):
            try:
                self.checked('CloseHandle', handle)
            except BaseException as error:
                failures.append(error)
        self.handles.clear()
        for file in self.files:
            try:
                file.close()
            except BaseException as error:
                failures.append(error)
        self.files.clear()
        return failures


def owned_job_run(api, request, report):
    """Backend-independent ownership ordering and fail-closed cleanup."""
    job, process, primary = None, None, None
    report.update(started=False, resumed=False, timed_out=False, status=None,
                  active_processes=None, cleanup_errors=[], ownership='owned-Windows-job')

    def cleanup_attempt(stage, action):
        try:
            return True, action()
        except BaseException as error:
            report['cleanup_errors'].append(stage + ': ' + str(error))
            return False, None

    def count():
        active = api.active(job)
        if type(active) is not int or active < 0:
            raise RuntimeError('Invalid owned job accounting count')
        report['active_processes'] = active
        return active

    try:
        timeout = request['timeout_seconds']
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Owned command timeout must be positive and finite')
        job = api.create_job()
        report['job_created'] = True
        process = api.spawn_suspended(job, request['argv'], request['cwd'],
                                     request['stdout_path'], request['stderr_path'])
        report.update(started=True, pid=int(process.pid), tid=int(process.tid),
                      creation_flags='EXTENDED_STARTUPINFO_PRESENT|CREATE_UNICODE_ENVIRONMENT|CREATE_SUSPENDED',
                      assignment='atomic-PROC_THREAD_ATTRIBUTE_JOB_LIST',
                      job_inheritable=False, breakaway_allowed=False)
        api.verify_assignment(job, process)
        report['assignment_verified'] = True
        api.resume(process)
        report['resumed'] = True
        deadline = time.monotonic() + timeout
        while count() != 0:
            if time.monotonic() >= deadline:
                report['timed_out'] = True
                raise subprocess.TimeoutExpired(request['argv'], timeout)
            time.sleep(.02)
        report['status'] = api.status(process)
    except BaseException as error:
        primary = error
        report['exception'] = type(error).__name__ + ': ' + str(error)
    finally:
        if job is not None:
            if report['active_processes'] != 0:
                stopped, _ = cleanup_attempt('job termination', lambda: api.terminate(job))
                report['termination_requested'] = stopped
                clock_ready, deadline = cleanup_attempt('cleanup deadline', lambda: time.monotonic() + 5)
                while clock_ready:
                    counted, active = cleanup_attempt('job accounting', count)
                    if not counted or active == 0:
                        break
                    timed, now = cleanup_attempt('cleanup clock', time.monotonic)
                    if not timed:
                        break
                    if now >= deadline:
                        report['cleanup_errors'].append('owned job still has active processes')
                        break
                    slept, _ = cleanup_attempt('cleanup pacing', lambda: time.sleep(.02))
                    if not slept:
                        break
            if process is not None and report['active_processes'] == 0 and report['status'] is None:
                status_ready, status = cleanup_attempt('root terminal status', lambda: api.status(process))
                if status_ready:
                    report['status'] = status
        closed, failures = cleanup_attempt('handle closure', api.close)
        if closed:
            for error in failures:
                report['cleanup_errors'].append('handle close: ' + str(error))
        report['closed'] = report['active_processes'] == 0 and not report['cleanup_errors']
    if primary is not None:
        for message in report['cleanup_errors']:
            primary.add_note('Windows job cleanup: ' + message)
        raise primary
    if report['cleanup_errors'] or not report['closed']:
        raise RuntimeError('Contained Windows command cleanup is not certified')


class WindowsJobProcess:
    """MSYS launches only a trusted NT helper, never an uncontained test command."""
    def __init__(self, command, executable, cwd, evidence, label, timeout, row):
        from clang_helpers import native_path
        from host_paths import host_path
        selected = (sys.executable if os.name == 'nt' else
                    os.environ.get('MINYAR_WINDOWS_JOB_PYTHON') or
                    os.environ.get('PEER_GRPC_PYTHON'))
        if not selected:
            raise RuntimeError('Windows job preparation needs existing native NT Python; '
                               'set MINYAR_WINDOWS_JOB_PYTHON or PEER_GRPC_PYTHON')
        interpreter = host_path(selected).resolve()
        if not interpreter.is_file():
            raise RuntimeError('Windows job native interpreter is missing')
        self.path = evidence/(label + '-job')
        self.path.mkdir()
        self.receipt = self.path/'receipt.json'
        helper = Path(__file__).resolve()
        self.request = {
            'schema_version': 1, 'nonce': str(uuid.uuid4()),
            'argv': [native_path(executable), *(
                native_path(host_path(value)) if os.path.isabs(value) and host_path(value).exists()
                else value for value in command[1:])],
            'cwd': native_path(cwd), 'timeout_seconds': timeout,
            'stdout_path': native_path(self.path/'target.stdout.bin'),
            'stderr_path': native_path(self.path/'target.stderr.bin'),
            'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
            'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        }
        request_file = self.path/'request.json'
        request_file.write_text(json.dumps(self.request, indent=2) + '\n')
        self.row, self.data, self.returncode = row, None, None
        self.timeout_reported = False
        row['windows_owner'] = {
            'interpreter': str(interpreter),
            'interpreter_sha256': hashlib.sha256(interpreter.read_bytes()).hexdigest(),
            'helper_sha256': self.request['helper_sha256'],
            'request_path': str(request_file), 'receipt_path': str(self.receipt),
        }
        self.parent = subprocess.Popen(
            [native_path(interpreter), '-I', native_path(helper), '--request',
             native_path(request_file), '--receipt', native_path(self.receipt)],
            cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=False)
        self.pid, self.stdout, self.stderr = self.parent.pid, self.parent.stdout, self.parent.stderr

    def communicate(self, timeout):
        helper_out, helper_err = self.parent.communicate(timeout=timeout + 15)
        self.row['windows_owner']['helper_status'] = self.parent.returncode
        (self.path/'helper.stdout.bin').write_bytes(helper_out)
        (self.path/'helper.stderr.bin').write_bytes(helper_err)
        if not self.receipt.is_file():
            raise RuntimeError('Windows owner produced no durable closure receipt')
        self.data = json.loads(self.receipt.read_text())
        for key in ('nonce', 'argv', 'cwd', 'helper_sha256', 'executable_sha256',
                    'timeout_seconds', 'stdout_path', 'stderr_path'):
            if self.data.get(key) != self.request[key]:
                raise RuntimeError('Windows owner receipt disagrees with request: ' + key)
        self.row['windows_owner']['receipt_sha256'] = hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        self.returncode = self.data.get('status')
        raw = tuple((self.path/('target.' + name + '.bin')).read_bytes()
                    if (self.path/('target.' + name + '.bin')).exists() else b''
                    for name in ('stdout', 'stderr'))
        if self.data.get('timed_out') and not self.timeout_reported:
            self.timeout_reported = True
            raise subprocess.TimeoutExpired(self.request['argv'],
                                            self.request['timeout_seconds'],
                                            output=raw[0], stderr=raw[1])
        if not self.data.get('closed') or self.data.get('cleanup_errors'):
            raise RuntimeError('Windows job closure not certified: ' + str(self.data))
        if self.parent.returncode and not self.data.get('exception'):
            raise RuntimeError('Windows owner failed without a matching receipt error')
        if self.data.get('exception') and not self.data.get('timed_out'):
            raise RuntimeError('Windows job preparation/launch failed: ' + self.data['exception'])
        return raw

    def terminate_owned(self):
        if self.data and self.data.get('closed') and self.data.get('active_processes') == 0:
            return
        primary = RuntimeError('Windows owner interrupted; final zero-active receipt unavailable')
        for label, action in (('helper kill', self.parent.kill),
                              ('helper wait', lambda: self.parent.wait(timeout=5))):
            try:
                action()
            except BaseException as error:
                primary.add_note(label + ': ' + str(error))
        raise primary

    def kill(self):
        self.parent.kill()

    def wait(self, timeout):
        return self.parent.wait(timeout=timeout)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    report, primary = {'closed': False, 'started': False}, None
    try:
        request = json.loads(args.request.read_text())
        report.update({key: request[key] for key in (
            'nonce', 'argv', 'cwd', 'helper_sha256', 'executable_sha256',
            'timeout_seconds', 'stdout_path', 'stderr_path')})
        if sys.flags.optimize:
            raise RuntimeError('Windows job owner requires Python assertions')
        if os.name != 'nt':
            raise RuntimeError('Windows job owner requires native NT Python')
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != request['helper_sha256']:
            raise ValueError('Windows owner source changed before launch')
        executable = Path(request['argv'][0])
        if hashlib.sha256(executable.read_bytes()).hexdigest() != request['executable_sha256']:
            raise ValueError('Windows original executable changed before launch')
        owned_job_run(WinAPI(), request, report)
        if hashlib.sha256(executable.read_bytes()).hexdigest() != request['executable_sha256']:
            raise ValueError('Windows original executable changed during execution')
    except BaseException as error:
        primary = error
        report['exception'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        try:
            pending = args.receipt.with_suffix('.tmp')
            pending.write_text(json.dumps(report, indent=2) + '\n')
            os.replace(pending, args.receipt)
        except BaseException as error:
            if primary is not None:
                primary.add_note('Windows owner receipt retention: ' + str(error))
            else:
                raise


if __name__ == '__main__':
    main()
