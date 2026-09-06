"""Bound each subprocess and terminate its entire process group on timeout."""
import os
import signal
import subprocess

def run(command, env, timeout):
    process = subprocess.Popen(command, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = process.communicate(timeout=10)
        output += f'\nPROCESS_GROUP_TIMEOUT after {timeout}s\n'
    result = subprocess.CompletedProcess(command, 124 if timed_out else process.returncode, output)
    result.timed_out = timed_out
    return result
