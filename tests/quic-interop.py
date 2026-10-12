#!/usr/bin/env python3
"""Remote official runner orchestration, with capability-free nonroot peers.
The trusted host configures only each endpoint's network namespace. Endpoints
have no Docker socket, host tokens, or NET_ADMIN/NET_RAW capabilities.
"""
import argparse, hashlib, json, os, platform, re, subprocess, sys, time
from pathlib import Path

def command(args, **kwargs):return subprocess.run(args,check=True,**kwargs)
def runner_environment(temporary):
    # Compose v2 validates mounts even for `down`. Upstream's per-case cleanup
    # inherits no inline variables from the earlier `up` command; safe defaults
    # let it actually remove the old simulator/network between test cases.
    defaults={name:str(temporary) for name in ('CERTS','SERVER_WWW','CLIENT_WWW','SERVER_DOWNLOADS','CLIENT_DOWNLOADS','SERVER_LOGS','CLIENT_LOGS')}
    defaults.update(SERVER='minyar-interop:development',CLIENT='minyar-interop:development',REQUESTS_SERVER='',REQUESTS_CLIENT='')
    return dict(os.environ,**defaults,TMPDIR=str(temporary),PYTHONUNBUFFERED='1')
def network_namespace(data):
    # Pin the namespace itself: Docker's PID can exit and be reused between
    # inspect and nsenter. Never configure the host namespace, even on a race.
    if data['HostConfig'].get('NetworkMode') == 'host':
        raise RuntimeError('host network mode is forbidden')
    pid=data['State']['Pid']
    if not isinstance(pid,int) or pid<=0:raise RuntimeError('endpoint has no running namespace')
    descriptor=os.open(f'/proc/{pid}/ns/net',os.O_RDONLY|os.O_CLOEXEC)
    try:
        actual=os.fstat(descriptor);host=os.stat('/proc/self/ns/net')
        if (actual.st_dev,actual.st_ino)==(host.st_dev,host.st_ino):
            raise RuntimeError('endpoint namespace equals host namespace')
        return descriptor
    except BaseException:
        os.close(descriptor);raise
def configure(node, temporary=Path('/home/minyar/lab/quic-runner-tmp')):
    data=json.loads(subprocess.check_output(['docker','inspect',node],stderr=subprocess.DEVNULL))[0]
    pid=data['State']['Pid']
    if not pid:return None
    if data['Config']['User']!='65534:65534' or data['HostConfig'].get('CapAdd'):
        raise RuntimeError(f'{node} must have a nonroot user and no additional capabilities')
    namespace=network_namespace(data)
    try:
        enter=['nsenter',f'--net=/proc/self/fd/{namespace}']
        network=f'193.167.{100 if node=="server" else 0}.2'
        command([*enter,'ip','-4','route','replace','default','via',network],pass_fds=(namespace,),stdout=subprocess.DEVNULL)
        v6=f'fd00:cafe:cafe:{100 if node=="server" else 0}::2'
        command([*enter,'ip','-6','route','replace','default','via',v6],pass_fds=(namespace,),stdout=subprocess.DEVNULL)
        # Same checksum setting as upstream /setup.sh, in the pinned endpoint
        # namespace only. ns3 needs complete UDP checksums.
        command([*enter,'ethtool','-K','eth0','tx','off'],pass_fds=(namespace,),stdout=subprocess.DEVNULL)
    finally:os.close(namespace)
    for mount in data['Mounts']:
        if mount['Destination'] not in ('/certs','/www','/downloads'):raise RuntimeError('unexpected endpoint mount')
        path=Path(mount['Source']).resolve()
        if temporary not in path.parents:
            raise RuntimeError('endpoint mount is outside ephemeral runner files')
        os.chmod(path,0o755 if mount['Destination']!='/downloads' else 0o777)
        for entry in path.rglob('*'):
            if entry.is_symlink():raise RuntimeError('unexpected fixture symlink')
            if entry.is_dir():os.chmod(entry,0o755)
            elif mount['Destination']!='/downloads':os.chmod(entry,0o444)
    command(['docker','exec','--user','65534:65534',data['Id'],'sh','-c','mkdir -p /logs/qlog && touch /tmp/network-ready'],stdout=subprocess.DEVNULL)
    return data['Id']
def selected_names(value, label):
    names = value.split(',')
    if (not names or len(names) != len(set(names)) or
            any(not re.fullmatch('[a-zA-Z0-9_-]+', name) for name in names)):
        raise ValueError('invalid ' + label + ' selection')
    return names

def unique_json_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError('duplicate JSON field: ' + name)
        result[name] = value
    return result

def validate_matrix(matrix, selected_servers, selected_clients, selected_tests, must_include):
    servers = selected_names(selected_servers, 'server')
    clients = selected_names(selected_clients, 'client')
    tests = selected_names(selected_tests, 'test')
    included = selected_names(must_include, 'required implementation')
    if len(included) != 1:
        raise ValueError('exactly one required implementation is supported by the official runner')
    if not any(server == must_include or client == must_include
               for server in servers for client in clients):
        raise ValueError('selection contains no pair with ' + must_include)
    if not isinstance(matrix, dict):
        raise ValueError('official matrix must be a JSON object')
    axes = {}
    for label, expected in (('servers', servers), ('clients', clients)):
        actual = matrix.get(label)
        if (not isinstance(actual, list) or not actual or
                any(not isinstance(name, str) for name in actual) or
                len(actual) != len(set(actual)) or set(actual) != set(expected)):
            raise ValueError('official matrix ' + label + ' differ from the requested selection')
        axes[label] = actual
    metadata = matrix.get('tests')
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError('official matrix has no test metadata')
    abbreviations = {}
    for name in tests:
        matches = [abbreviation for abbreviation, row in metadata.items()
                   if isinstance(row, dict) and row.get('name') == name]
        if len(matches) != 1:
            raise ValueError('missing or ambiguous official metadata for ' + name)
        abbreviations[name] = matches[0]
    cells = matrix.get('results')
    if (not isinstance(cells, list) or
            len(cells) != len(axes['servers']) * len(axes['clients'])):
        raise ValueError('official matrix has missing or extra pair cells')
    pairs = []
    succeeded = 0
    # Upstream InteropRunner._export_results emits clients first, then servers.
    # Axis order is exported from sets and can differ from CLI order.
    for client_index, client in enumerate(axes['clients']):
        for server_index, server in enumerate(axes['servers']):
            if must_include not in (server, client):
                continue
            cell = cells[client_index * len(axes['servers']) + server_index]
            if not isinstance(cell, list) or not cell:
                raise ValueError('empty official results for ' + server + '/' + client)
            names = []
            codes = []
            for row in cell:
                if (not isinstance(row, dict) or not isinstance(row.get('name'), str) or
                        not isinstance(row.get('abbr'), str)):
                    raise ValueError('malformed official result for ' + server + '/' + client)
                names.append(row['name'])
                codes.append(row['abbr'])
            if len(names) != len(set(names)) or len(codes) != len(set(codes)):
                raise ValueError('ambiguous official results for ' + server + '/' + client)
            for name in tests:
                matching = [row for row in cell if row['name'] == name]
                if len(matching) != 1 or matching[0]['abbr'] != abbreviations[name]:
                    raise ValueError('missing or mismatched ' + name + ' result for ' + server + '/' + client)
                result = matching[0].get('result')
                if result != 'succeeded':
                    raise ValueError(name + ' for ' + server + '/' + client +
                                     ' did not succeed: ' + repr(result))
                succeeded += 1
            pairs.append({'server': server, 'client': client})
    return {'status': 'succeeded', 'pairs': pairs, 'succeeded_cases': succeeded}

def matrix_evidence(path, options, runner_status):
    raw = None
    try:
        raw = path.read_bytes()
        matrix = json.loads(raw, object_pairs_hook=unique_json_object)
        verdict = validate_matrix(matrix, options.servers, options.clients,
                                  options.tests, options.must_include)
    except (OSError, UnicodeError, ValueError) as error:
        verdict = {'status': 'failed', 'error': str(error)}
    return {'runner_status': runner_status,
            'status': runner_status if runner_status != 0 else
                      (0 if verdict['status'] == 'succeeded' else 1),
            'matrix_sha256': hashlib.sha256(raw).hexdigest() if raw is not None else None,
            'matrix_bytes': len(raw) if raw is not None else None,
            'result_validation': verdict}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runner',required=True);parser.add_argument('--artifacts',required=True);parser.add_argument('--servers',default='minyar');parser.add_argument('--clients',default='minyar,quiche,ngtcp2,msquic');parser.add_argument('--tests',default='handshake,transfer');parser.add_argument('--must-include',default='minyar');parser.add_argument('--temporary',type=Path,default=Path('/home/minyar/lab/quic-runner-tmp'));options=parser.parse_args()
    if platform.system()!='Linux' or os.geteuid()!=0 or os.environ.get('MINYAR_REMOTE_LOAD')!='1':raise RuntimeError('remote Linux admin orchestration required')
    runner=Path(options.runner).resolve();artifacts=Path(options.artifacts).resolve();artifacts.mkdir(parents=True,exist_ok=True)
    temporary=options.temporary.resolve();temporary.mkdir(parents=True,exist_ok=True)
    # The upstream runner explicitly chooses /tmp at several fixture sites.
    # Relocate those paths only, preserving every protocol test and assertion.
    for source in runner.glob('*.py'):
        contents=source.read_text();changed=contents.replace('dir="/tmp"',f'dir="{temporary}"')
        if changed!=contents:source.write_text(changed)
    for name in ('servers','clients','tests','must_include'):
        selected_names(getattr(options,name), name)
    if len(selected_names(options.must_include, 'required implementation')) != 1:
        raise ValueError('exactly one required implementation is supported by the official runner')
    registry=runner/'implementations_quic.json'; implementations=json.loads(registry.read_text());implementations['minyar']={'image':'minyar-interop:development','url':'local-development','role':'both'};registry.write_text(json.dumps(implementations,indent=2)+'\n')
    # Apply only endpoint capability removals; the official simulator retains
    # its required NET_ADMIN/NET_RAW. Host nsenter handles endpoint routing.
    compose=runner/'docker-compose.yml'; original=compose.read_text(); original=original.replace('    cap_add:\n      - NET_ADMIN\n    ulimits:', '    ulimits:');compose.write_text(original)
    image_tags={'quiche':'minyar-quiche:lab','quinn':'minyar-quinn:lab','ngtcp2':os.environ.get('MINYAR_NGTCP2_IMAGE','minyar-ngtcp2:lab'),'msquic':'minyar-msquic:lab'}
    replacements=','.join(f'{name}={image}' for name,image in image_tags.items())
    environment=runner_environment(temporary)
    logs=artifacts/'runner.log'
    selected=','.join(sorted(set((options.servers+','+options.clients).split(','))))
    invocation=[sys.executable,str(runner/'run.py'),'-s',options.servers,'-c',options.clients,'-i',options.must_include,'-t',options.tests,'-r',replacements,'-j',str(artifacts/'matrix.json'),'-l',str(artifacts/'logs'),'-n',selected]
    started=time.monotonic();configured=set()
    with logs.open('w') as output:
        process=subprocess.Popen(invocation,cwd=runner,env=environment,stdout=output,stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if time.monotonic()-started>2400:raise RuntimeError('interop matrix deadline exceeded')
                for node in ('server','client'):
                    try:
                        identifier=subprocess.check_output(['docker','inspect','--format','{{.Id}} {{.State.Running}}',node],stderr=subprocess.DEVNULL,text=True).strip()
                        if identifier.endswith(' true') and identifier not in configured:
                            found=configure(node,temporary)
                            if found:configured.add(identifier)
                    except subprocess.CalledProcessError:pass
                time.sleep(.1)
            status=process.returncode
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=20)
            cleanup_environment=dict(environment,SERVER='minyar-interop:development',CLIENT='minyar-interop:development',SERVER_WWW=str(temporary),CLIENT_WWW=str(temporary),SERVER_DOWNLOADS=str(temporary),CLIENT_DOWNLOADS=str(temporary),CERTS=str(temporary))
            subprocess.run(['docker','compose','--env-file','empty.env','down','--timeout','5'],cwd=runner,env=cleanup_environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    manifest={'runner_commit':subprocess.check_output(['git','-c',f'safe.directory={runner}','rev-parse','HEAD'],cwd=runner,text=True).strip(),'tshark':subprocess.check_output(['tshark','--version'],text=True,stderr=subprocess.DEVNULL).splitlines()[0],'elapsed_seconds':time.monotonic()-started,'configured_endpoints':len(configured),'tests':options.tests,'servers':options.servers,'clients':options.clients,'must_include':options.must_include,'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest.update(matrix_evidence(artifacts/'matrix.json',options,status))
    (artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
    return manifest['status']
if __name__=='__main__':sys.exit(main())
