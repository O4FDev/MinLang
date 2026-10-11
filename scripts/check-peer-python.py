#!/usr/bin/env python3
"""Verify pinned independent peer imports in the selected Python interpreter."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'h2': 'h2', 'hpack': 'hpack', 'hyperframe': 'hyperframe',
           'grpcio': 'grpc', 'protobuf': 'google.protobuf',
           'typing-extensions': 'typing_extensions'}


def verify(requirements):
    rows = []
    for line in requirements.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_-]+)==([A-Za-z0-9.+-]+)', line.strip())
        if not match or match[1] not in MODULES:
            raise ValueError('unsupported peer requirement: ' + line)
        distribution, expected = match.groups()
        actual = importlib.metadata.version(distribution)
        if actual != expected:
            raise ValueError(f'{distribution}: expected {expected}, found {actual}')
        module = importlib.import_module(MODULES[distribution])
        path = Path(module.__file__)
        rows.append({'distribution': distribution, 'version': actual,
                     'module': MODULES[distribution], 'file': str(path),
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if {row['distribution'] for row in rows} != set(MODULES) or len(rows) != len(MODULES):
        raise ValueError('peer requirements must contain each expected package exactly once')
    native = Path(importlib.import_module('grpc._cython.cygrpc').__file__)
    return {'verified': True, 'python': sys.executable,
            'python_version': platform.python_version(), 'platform': platform.platform(),
            'requirements_sha256': hashlib.sha256(requirements.read_bytes()).hexdigest(),
            'packages': rows, 'grpc_native': str(native),
            'grpc_native_sha256': hashlib.sha256(native.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requirements', type=Path,
                        default=ROOT / 'tests/interop/peergrpc/requirements.txt')
    options = parser.parse_args()
    try:
        print(json.dumps(verify(options.requirements), sort_keys=True))
    except (OSError, ImportError, ValueError, importlib.metadata.PackageNotFoundError) as error:
        print('peer Python verification failed: ' + str(error), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
