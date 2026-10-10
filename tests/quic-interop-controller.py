#!/usr/bin/env python3
"""Remote kernel oracle for pinned namespaces and host-namespace rejection."""
import importlib.util,os,platform,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('interop',ROOT/'tests/quic-interop.py');interop=importlib.util.module_from_spec(spec);spec.loader.exec_module(interop)
def main():
    if platform.system()!='Linux' or os.geteuid()!=0 or os.environ.get('MINYAR_REMOTE_LOAD')!='1':raise RuntimeError('remote admin correctness test required')
    for mode in ('host','bridge'):
        try:interop.network_namespace({'State':{'Pid':os.getpid()},'HostConfig':{'NetworkMode':mode}})
        except RuntimeError:pass
        else:raise AssertionError('host namespace accepted')
    child=subprocess.Popen(['unshare','--net','sleep','30']);descriptor=None
    try:
        host=os.stat('/proc/self/ns/net');deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                descriptor=interop.network_namespace({'State':{'Pid':child.pid},'HostConfig':{'NetworkMode':'bridge'}});break
            except RuntimeError:time.sleep(.01)
        assert descriptor is not None,'new namespace was not created'
        pinned=os.fstat(descriptor);child.terminate();child.wait(timeout=5)
        assert not Path(f'/proc/{child.pid}/ns/net').exists()
        actual=subprocess.check_output(['nsenter',f'--net=/proc/self/fd/{descriptor}','stat','-Lc','%i','/proc/self/ns/net'],pass_fds=(descriptor,),text=True)
        assert int(actual)==pinned.st_ino and pinned.st_ino!=host.st_ino
        after=os.stat('/proc/self/ns/net');assert (after.st_dev,after.st_ino)==(host.st_dev,host.st_ino)
        print('Interop namespaces: host mode/inode rejected; pinned FD survives endpoint exit and host namespace remains unchanged')
    finally:
        if descriptor is not None:os.close(descriptor)
        if child.poll() is None:child.terminate();child.wait(timeout=5)
if __name__=='__main__':main()
