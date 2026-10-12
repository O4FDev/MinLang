"""Per-run cache of compiled test programs.

A check recipe opts in by pointing MINYAR_TEST_PROGRAM_CACHE at a fresh
directory. Within that run, building the same source under the same
MINYAR_*/PATH environment reuses the first binary instead of compiling again.
Sources cannot change during one run, so the source bytes, path and build
environment fully identify the output. Builds that record link evidence
(MINYAR_LINK_ARTIFACTS) always compile.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

VARIABLE = 'MINYAR_TEST_PROGRAM_CACHE'
# Switches read only by test peers or harnesses at run time, never by the
# launcher or toolchain driver. Every other MINYAR_* variable keys the build.
RUNTIME_ONLY = (VARIABLE, 'MINYAR_TEST_JOBS', 'MINYAR_QUINN_', 'MINYAR_PEER_')


def key(source, env, extra=()):
    source = Path(source).resolve()
    build = {name: value for name, value in env.items()
             if (name.startswith('MINYAR_') and not name.startswith(RUNTIME_ONLY)) or name == 'PATH'}
    text = json.dumps([str(source), hashlib.sha256(source.read_bytes()).hexdigest(), build, list(extra)], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def build(source, output, env, compile, extra=()):
    """Run compile(path) to produce output, reusing a cached binary when enabled."""
    directory = env.get(VARIABLE)
    if not directory or env.get('MINYAR_LINK_ARTIFACTS'):
        compile(Path(output))
        return
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    cached = directory / key(source, env, extra)
    if not cached.is_file():
        staging = Path(tempfile.mkdtemp(prefix='build.', dir=directory))
        try:
            compile(staging / 'program')
            # Concurrent builders of one key produce equivalent binaries.
            os.replace(staging / 'program', cached)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    shutil.copy2(cached, output)


@contextlib.contextmanager
def scope(parent):
    """Enable a fresh cache under parent for this process and its children."""
    if os.environ.get(VARIABLE):
        yield
        return
    Path(parent).mkdir(parents=True, exist_ok=True)
    directory = tempfile.mkdtemp(prefix='program-cache.', dir=parent)
    os.environ[VARIABLE] = directory
    try:
        yield
    finally:
        os.environ.pop(VARIABLE, None)
        shutil.rmtree(directory, ignore_errors=True)


def jobs():
    """Concurrent case bound for harnesses; MINYAR_TEST_JOBS, default 2."""
    return max(1, int(os.environ.get('MINYAR_TEST_JOBS') or 2))
