#!/usr/bin/env python3
"""Remote official runner orchestration, with capability-free nonroot peers.
The trusted host configures only each endpoint's network namespace. Endpoints
have no Docker socket, host tokens, or NET_ADMIN/NET_RAW capabilities.
"""
import argparse, json, os, platform, re, subprocess, sys, time
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
def configure(node):
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
        if not str(path).startswith('/home/minyar/lab/quic-runner-tmp/'):
            raise RuntimeError('endpoint mount is outside ephemeral runner files')
        os.chmod(path,0o755 if mount['Destination']!='/downloads' else 0o777)
        for entry in path.rglob('*'):
            if entry.is_symlink():raise RuntimeError('unexpected fixture symlink')
            if entry.is_dir():os.chmod(entry,0o755)
            elif mount['Destination']!='/downloads':os.chmod(entry,0o444)
    command(['docker','exec','--user','65534:65534',data['Id'],'sh','-c','mkdir -p /logs/qlog && touch /tmp/network-ready'],stdout=subprocess.DEVNULL)
    return data['Id']
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runner',required=True);parser.add_argument('--artifacts',required=True);parser.add_argument('--servers',default='minyar');parser.add_argument('--clients',default='minyar,quiche,ngtcp2,msquic');parser.add_argument('--tests',default='handshake,transfer');parser.add_argument('--must-include',default='minyar');options=parser.parse_args()
    if platform.system()!='Linux' or os.geteuid()!=0 or os.environ.get('MINYAR_REMOTE_LOAD')!='1':raise RuntimeError('remote Linux admin orchestration required')
    runner=Path(options.runner).resolve();artifacts=Path(options.artifacts).resolve();artifacts.mkdir(parents=True,exist_ok=True)
    temporary=Path('/home/minyar/lab/quic-runner-tmp');temporary.mkdir(exist_ok=True)
    # The upstream runner explicitly chooses /tmp at several fixture sites.
    # Relocate those paths only, preserving every protocol test and assertion.
    for source in runner.glob('*.py'):
        contents=source.read_text();changed=contents.replace('dir="/tmp"',f'dir="{temporary}"')
        if changed!=contents:source.write_text(changed)
    for name in ('servers','clients','tests','must_include'):
        if not re.fullmatch('[a-zA-Z0-9,_-]+',getattr(options,name)):raise RuntimeError('invalid matrix selection')
    registry=runner/'implementations_quic.json'; implementations=json.loads(registry.read_text());implementations['minyar']={'image':'minyar-interop:development','url':'local-development','role':'both'};registry.write_text(json.dumps(implementations,indent=2)+'\n')
    # Apply only endpoint capability removals; the official simulator retains
    # its required NET_ADMIN/NET_RAW. Host nsenter handles endpoint routing.
    compose=runner/'docker-compose.yml'; original=compose.read_text(); original=original.replace('    cap_add:\n      - NET_ADMIN\n    ulimits:', '    ulimits:');compose.write_text(original)
    image_tags={'quiche':'minyar-quiche:lab','ngtcp2':os.environ.get('MINYAR_NGTCP2_IMAGE','minyar-ngtcp2:lab'),'msquic':'minyar-msquic:lab'}
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
                            found=configure(node)
                            if found:configured.add(identifier)
                    except subprocess.CalledProcessError:pass
                time.sleep(.1)
            status=process.returncode
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=20)
            cleanup_environment=dict(environment,SERVER='minyar-interop:development',CLIENT='minyar-interop:development',SERVER_WWW=str(temporary),CLIENT_WWW=str(temporary),SERVER_DOWNLOADS=str(temporary),CLIENT_DOWNLOADS=str(temporary),CERTS=str(temporary))
            subprocess.run(['docker','compose','--env-file','empty.env','down','--timeout','5'],cwd=runner,env=cleanup_environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    manifest={'runner_commit':subprocess.check_output(['git','-c',f'safe.directory={runner}','rev-parse','HEAD'],cwd=runner,text=True).strip(),'tshark':subprocess.check_output(['tshark','--version'],text=True,stderr=subprocess.DEVNULL).splitlines()[0],'status':status,'elapsed_seconds':time.monotonic()-started,'configured_endpoints':len(configured),'tests':options.tests}
    (artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
    return status
if __name__=='__main__':sys.exit(main())
