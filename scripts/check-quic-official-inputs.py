#!/usr/bin/env python3
"""Verify pinned source and Python inputs for Linux-only adapter controls.

The upstream runner is read as Git objects, never imported or executed.
Preparing the default cache may fetch the single public commit or install the
single wheel-only controls dependency. Existing inputs are verified, not repaired.
"""
import argparse
import ast
import base64
import ctypes
import hashlib
import importlib
import importlib.metadata
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT/'tests/interop/qns/owned_adapter.py'
DRIVER = ROOT/'tests/quic-official-adapter.py'
PIN = '740c05a10b61d65e8abd3ad38d60898004d335d9'
URL = 'https://github.com/quic-interop/quic-interop-runner.git'
PRIMARY_NAMES = ('run.py', 'interop.py', 'testcase.py', 'testcases_quic.py',
                 'docker-compose.yml')
FILE_COUNT = 40
REQUIREMENTS = ROOT/'tests/interop/qns/controls-requirements.txt'
COMMAND_LOGS = []


def binding(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data)}


def git_environment(source=None):
    source = os.environ if source is None else source
    environment = {key: value for key, value in source.items()
                   if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    return environment


class Commands:
    def __init__(self, environment=None):
        self.rows = []
        # This same routing policy is used by verification and control children.
        self.environment = git_environment(environment)
        COMMAND_LOGS.append(self.rows)

    def run(self, argv, timeout=30):
        tool = Path(shutil.which(str(argv[0])) or str(argv[0])).resolve()
        before = binding(tool)
        try:
            result = subprocess.run(argv, env=self.environment, stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            self.rows.append({'argv': list(map(str, argv)), 'timeout_seconds': timeout,
                              'status': None, 'timed_out': True, 'tool_before': before,
                              'stdout_base64': base64.b64encode(error.stdout or b'').decode(),
                              'stderr_base64': base64.b64encode(error.stderr or b'').decode()})
            raise
        row = {'argv': list(map(str, argv)), 'timeout_seconds': timeout,
               'status': result.returncode, 'tool_before': before,
               'stdout_base64': base64.b64encode(result.stdout).decode(),
               'stderr_base64': base64.b64encode(result.stderr).decode()}
        self.rows.append(row)
        tool_error = None
        try:
            row['tool_after'] = binding(tool)
            if before != row['tool_after']:
                tool_error = 'prerequisite command executable changed'
        except OSError as error:
            tool_error = str(error)
        if tool_error:
            row['tool_after_error'] = tool_error
        # Retain the command's failure status before a secondary binding error.
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, argv,
                                                result.stdout, result.stderr)
        if tool_error:
            raise ValueError(tool_error)
        return result.stdout


def load_contract():
    tree = ast.parse(HELPER.read_text())
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('PIN', 'PINNED'):
                    if target.id in constants:
                        raise ValueError('duplicate adapter pin contract')
                    constants[target.id] = ast.literal_eval(node.value)
    if constants.get('PIN') != PIN or set(constants.get('PINNED', {})) != set(PRIMARY_NAMES):
        raise ValueError('adapter pin contract differs')
    primary = constants['PINNED']
    if any(re.fullmatch(r'[0-9a-f]{64}', value) is None for value in primary.values()):
        raise ValueError('invalid primary source digest')
    return PIN, primary


def object_id(kind, data):
    return hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()


def verify_runner(repository, commands=None):
    repository = Path(repository)
    if not repository.is_absolute() or not repository.is_dir():
        raise ValueError('runner repository requires an existing absolute directory')
    commands = commands or Commands()
    contract_before = binding(HELPER)
    git = shutil.which('git')
    if git is None:
        raise ValueError('Git is required for pinned source controls')
    version = commands.run([git, '--version']).decode().strip()
    if not version.startswith('git version '):
        raise ValueError('Git version provenance missing')
    prefix = [git, '--no-replace-objects', '-C', str(repository)]
    git_dir = commands.run(prefix+['rev-parse', '--absolute-git-dir']).decode().strip()
    common = commands.run(prefix+['rev-parse', '--git-common-dir']).decode().strip()
    if not git_dir or not common:
        raise ValueError('missing Git repository identity')
    common_dir = Path(common)
    if not common_dir.is_absolute():
        common_dir = repository/common_dir
    for directory in (Path(git_dir), common_dir):
        if (directory/'info/grafts').exists():
            raise ValueError('runner graft ambiguity is forbidden')
    replacements = commands.run(prefix+['for-each-ref', '--format=%(refname)',
                                       'refs/replace']).strip()
    if replacements:
        raise ValueError('runner replacement objects are forbidden')
    pin, primary = load_contract()
    objects = {}

    def read_object(kind, identity):
        if re.fullmatch(r'[0-9a-f]{40}', identity) is None:
            raise ValueError('invalid pinned object identity')
        key = (kind, identity)
        if key not in objects:
            actual_kind = commands.run(prefix+['cat-file', '-t', identity]).decode().strip()
            if actual_kind != kind:
                raise ValueError('pinned object type differs')
            data = commands.run(prefix+['cat-file', kind, identity])
            if object_id(kind, data) != identity:
                raise ValueError('pinned Git object content differs')
            objects[key] = data
        return objects[key]

    commit = read_object('commit', pin)
    first = commit.split(b'\n', 1)[0]
    if not first.startswith(b'tree '):
        raise ValueError('pinned commit lacks its tree')
    root_tree = first[5:].decode('ascii')
    files, trees, seen_paths = [], [], set()

    def walk(identity, parent=PurePosixPath('.'), ancestors=()):
        if identity in ancestors or len(ancestors) > 64:
            raise ValueError('invalid pinned tree recursion')
        data = read_object('tree', identity)
        trees.append({'path': parent.as_posix(), 'object': identity,
                      'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        offset = 0
        while offset < len(data):
            space = data.find(b' ', offset)
            zero = data.find(b'\0', space+1)
            if space < offset or zero < space or zero+21 > len(data):
                raise ValueError('malformed pinned tree entry')
            mode = data[offset:space].decode('ascii')
            name = data[space+1:zero].decode('utf-8')
            if not name or name in ('.', '..') or '/' in name or '\\' in name:
                raise ValueError('unsafe pinned tree path')
            child = data[zero+1:zero+21].hex()
            path = parent/name
            key = path.as_posix()
            if key in seen_paths:
                raise ValueError('duplicate pinned path')
            seen_paths.add(key)
            offset = zero+21
            if mode in ('40000', '040000'):
                walk(child, path, ancestors+(identity,))
            elif mode in ('100644', '100755', '120000'):
                content = read_object('blob', child)
                files.append({'path': key, 'mode': mode, 'object': child,
                              'sha256': hashlib.sha256(content).hexdigest(),
                              'bytes': len(content)})
            else:
                raise ValueError('unsupported pinned Git object mode')
        if offset != len(data):
            raise ValueError('truncated pinned tree')

    walk(root_tree)
    if len(files) != FILE_COUNT:
        raise ValueError('pinned runner must contain every expected file')
    inventory = {row['path']: row for row in files}
    for name, expected in primary.items():
        if name not in inventory or inventory[name]['sha256'] != expected:
            raise ValueError('primary runner source differs: '+name)
    # A second read validates that the source provider did not change its objects.
    for (kind, identity), before in objects.items():
        after = commands.run(prefix+['cat-file', kind, identity])
        if before != after or object_id(kind, after) != identity:
            raise ValueError('pinned source changed during verification')
    contract_after = binding(HELPER)
    if contract_before != contract_after:
        raise ValueError('adapter pin contract changed during verification')
    return {'verified': True, 'scope': 'Git source objects only; no runner execution',
            'contract_before': contract_before, 'contract_after': contract_after,
            'repository': str(repository), 'git_version': version,
            'commit': pin, 'tree': root_tree,
            'files': sorted(files, key=lambda row: row['path']), 'trees': trees,
            'commands': commands.rows}


def requirements_contract(path):
    path = Path(path)
    lines = [line.strip() for line in path.read_text().splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if lines != ['PyYAML==6.0.2']:
        raise ValueError('controls require only explicit PyYAML==6.0.2')
    return {'distribution': 'PyYAML', 'version': '6.0.2',
            'requirements': binding(path)}


def require_empty_pycache(prefix):
    if prefix is None:
        raise ValueError('fresh bytecode route is required')
    path = Path(prefix)
    if (not path.is_absolute() or not path.is_dir() or path.is_symlink() or
            path.resolve() != path or any(path.iterdir())):
        raise ValueError('bytecode route must be an existing empty absolute directory')
    return path


def import_route():
    if sys.flags.safe_path is not True:
        raise ValueError('controls require the CPython3.12 safe import path')
    if sys.dont_write_bytecode is not True:
        raise ValueError('controls must disable bytecode writes on the fresh route')
    prefix = require_empty_pycache(sys.pycache_prefix)
    if any(name == 'yaml' or name.startswith('yaml.') for name in sys.modules):
        raise ValueError('controls YAML must be imported freshly from verified source')
    return {'prefix': str(prefix), 'dont_write_bytecode': True}


def fresh_python_argv(python, arguments, prefix):
    prefix = require_empty_pycache(prefix)
    return [str(python), '-E', '-B', '-P', '-X', 'pycache_prefix='+str(prefix)]+list(arguments)

def verify_python(requirements):
    route = import_route()
    contract = requirements_contract(requirements)
    actual = importlib.metadata.version('PyYAML')
    if actual != contract['version']:
        raise ValueError('controls PyYAML version differs')
    distribution = importlib.metadata.distribution('PyYAML')
    names = distribution.files
    if not names:
        raise ValueError('controls distribution inventory missing')
    paths = sorted({Path(distribution.locate_file(name)).resolve() for name in names
                    if Path(str(name)).suffix != '.pyc'})
    before = [binding(path) for path in paths]
    for name in names:
        if Path(str(name)).suffix == '.pyc' or name.hash is None:
            continue
        if name.hash.mode != 'sha256':
            raise ValueError('unsupported controls wheel record hash')
        path = Path(distribution.locate_file(name)).resolve()
        actual_hash = base64.urlsafe_b64encode(
            hashlib.sha256(path.read_bytes()).digest()).decode().rstrip('=')
        if actual_hash != name.hash.value:
            raise ValueError('controls distribution bytes differ from its wheel record')
    spec = importlib.util.find_spec('yaml')
    if (spec is None or spec.origin is None or
            Path(spec.origin).resolve() not in paths or
            type(spec.loader) is not importlib.machinery.SourceFileLoader):
        raise ValueError('controls YAML must load a verified source file')
    require_empty_pycache(route['prefix'])
    yaml = importlib.import_module('yaml')
    module = Path(yaml.__file__).resolve()
    if module not in paths or yaml.__version__ != contract['version']:
        raise ValueError('controls YAML import is outside the verified distribution')
    after = [binding(path) for path in paths]
    if before != after:
        raise ValueError('controls distribution bytes changed during import')
    require_empty_pycache(route['prefix'])
    return {'verified': True, 'scope': 'new controls dependency; not historical107 binding',
            'contract': contract, 'python': binding(Path(sys.executable).resolve()),
            'implementation': sys.implementation.name,
            'python_version': platform.python_version(), 'packages': before,
            'module': binding(module), 'bytecode_route': route}


def require_supported_python():
    if sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 12):
        raise ValueError('controls require explicit CPython3.12 and PyYAML6.0.2 wheels; other ABIs are unverified')


def require_linux():
    if platform.system() != 'Linux':
        raise ValueError('Linux adapter controls required before dependency setup')


def publish_directory(source, destination):
    # Linux-only exclusive publication; never replace a racing or existing cache.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise ValueError('exclusive cache publication unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        raise OSError(ctypes.get_errno(), 'exclusive cache publication failed')


def write_ready(path, report):
    with Path(path).open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


def prepare_runner(repository):
    require_linux()
    repository = Path(repository)
    if not repository.is_absolute() or repository.exists():
        raise ValueError('default runner cache must be fresh; existing inputs are not repaired')
    repository.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=repository.name+'.stage.', dir=repository.parent))
    commands = Commands()
    git = shutil.which('git')
    if git is None:
        raise ValueError('Git is required for pinned source preparation')
    commands.run([git, 'init', '--bare', str(stage)])
    commands.run([git, '-C', str(stage), '-c', 'maintenance.auto=false',
                  '-c', 'gc.auto=0', 'fetch', '--no-tags', '--no-write-fetch-head',
                  '--depth=1', URL, PIN], timeout=180)
    report = verify_runner(stage, commands)
    write_ready(stage/'.ready.json', report)
    publish_directory(stage, repository)
    return {'verified': True, 'published': str(repository), 'preparation': report}


def prepare_python(directory, requirements):
    require_linux()
    require_supported_python()
    directory = Path(directory)
    requirements_contract(requirements)
    if not directory.is_absolute() or directory.exists() or directory.is_symlink():
        raise ValueError('default Python cache must be fresh; existing inputs are not repaired')
    directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=directory.name+'.stage.',
                                  dir=directory.parent)).resolve()
    commands = Commands()
    commands.run([sys.executable, '-E', '-m', 'venv', str(stage)], timeout=180)
    python = stage/'bin/python'
    commands.run([str(python), '-E', '-m', 'pip', '--disable-pip-version-check',
                  'install', '--only-binary=:all:', '-r', str(requirements)], timeout=180)
    prefix = Path(tempfile.mkdtemp(prefix='verified-source.', dir=stage))
    raw = commands.run(fresh_python_argv(
        python, [str(Path(__file__).resolve()), 'verify-python',
                 '--requirements', str(requirements)], prefix), timeout=30)
    report = json.loads(raw)
    if (not isinstance(report, dict) or report.get('verified') is not True or
            report.get('contract') != requirements_contract(requirements) or
            not report.get('packages') or report.get('implementation') != 'cpython' or
            report.get('python') != binding(python.resolve()) or
            report.get('module') not in report['packages'] or
            report.get('bytecode_route') != {'prefix': str(prefix),
                                             'dont_write_bytecode': True}):
        raise ValueError('controls import verification did not produce readiness')
    require_empty_pycache(prefix)
    write_ready(stage/'.ready.json', report)
    directory.symlink_to(stage, target_is_directory=True)
    return {'verified': True, 'published': str(directory),
            'preparation_commands': commands.rows, 'python': report}


def run_controls(repository, requirements, artifacts):
    repository, artifacts = Path(repository), Path(artifacts)
    if (not repository.is_absolute() or not repository.is_dir() or
            not artifacts.is_absolute() or artifacts.exists() or
            not artifacts.parent.is_dir() or artifacts.parent.resolve() != artifacts.parent):
        raise ValueError('controls need an explicit repository and fresh absolute artifacts')
    requirements_contract(requirements)
    sources = [Path(__file__).resolve(), HELPER, DRIVER, Path(requirements)]
    before = [binding(path) for path in sources]
    prefix = Path(tempfile.mkdtemp(prefix='verified-source.', dir=artifacts.parent))
    environment = git_environment()
    commands = Commands(environment)
    raw = commands.run(fresh_python_argv(
        sys.executable, [str(Path(__file__).resolve()), 'verify',
                         '--repository', str(repository),
                         '--requirements', str(requirements)], prefix))
    inputs = json.loads(raw)
    route = {'prefix': str(prefix), 'dont_write_bytecode': True}
    if (not isinstance(inputs, dict) or inputs.get('verified') is not True or
            not isinstance(inputs.get('runner'), dict) or
            not isinstance(inputs.get('python'), dict) or
            inputs['runner'].get('verified') is not True or
            inputs['python'].get('verified') is not True or
            inputs['python'].get('bytecode_route') != route):
        raise ValueError('fresh verified inputs are required before controls')
    require_empty_pycache(prefix)
    if before != [binding(path) for path in sources]:
        raise ValueError('control sources changed before launch')
    # No new control timeout: the unchanged ordinary limiter owns the full gate.
    # Exact accepted driver, no --case or real-Docker option: all 107 safe controls.
    commands.run(fresh_python_argv(
        sys.executable, [str(DRIVER), '--pinned-runner', str(repository),
                         '--artifacts', str(artifacts)], prefix), timeout=None)
    require_empty_pycache(prefix)
    after = [binding(path) for path in sources]
    if before != after:
        raise ValueError('control sources changed during launch')
    return {'verified': True, 'scope': 'all107 safe/mock controls; no Docker authority',
            'inputs': inputs, 'sources_before': before, 'sources_after': after,
            'bytecode_route': route,
            'git_environment': {key: value for key, value in environment.items()
                                if key.startswith('GIT_')},
            'commands': commands.rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare-runner', 'prepare-python',
                                        'verify-python', 'verify', 'controls'))
    parser.add_argument('--repository', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--requirements', type=Path, default=REQUIREMENTS)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--artifacts', type=Path)
    options = parser.parse_args()
    require_linux()
    require_supported_python()
    if options.report is not None and (
            not options.report.is_absolute() or options.report.exists()):
        raise ValueError('--report must be a fresh absolute file')
    if options.mode == 'prepare-runner':
        if options.repository is None:
            parser.error('--repository required')
        report = prepare_runner(options.repository)
    elif options.mode == 'prepare-python':
        if options.directory is None:
            parser.error('--directory required')
        report = prepare_python(options.directory, options.requirements)
    elif options.mode == 'verify-python':
        report = verify_python(options.requirements)
    elif options.mode == 'controls':
        if options.repository is None or options.artifacts is None:
            parser.error('--repository and --artifacts required')
        report = run_controls(options.repository, options.requirements, options.artifacts)
    else:
        if options.repository is None:
            parser.error('--repository required')
        report = {'verified': True, 'scope': 'safe controls prerequisites; no Docker execution',
                  'runner': verify_runner(options.repository),
                  'python': verify_python(options.requirements),
                  'sources': [binding(Path(__file__).resolve()), binding(HELPER),
                              binding(options.requirements)]}
    if options.report is not None:
        write_ready(options.report, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError,
            importlib.metadata.PackageNotFoundError) as error:
        print('adapter input verification failed: '+str(error), file=sys.stderr)
        print(json.dumps({'verified': False, 'error_type': type(error).__name__,
                          'error': str(error),
                          'commands': [row for rows in COMMAND_LOGS for row in rows]},
                         sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
