#!/usr/bin/env python3
"""Correctness/negative matrix for system allocation with bounded traversal."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:allocator_may_return_null=1'}
with tempfile.TemporaryDirectory(prefix='minyar-system-configurations-') as temporary:
    for budget in (1,32,1024):
        for sanitized in (False,True):
            binary=Path(temporary)/f'system-{budget}-{sanitized}'
            command=['clang','-std=c11','-Wall','-Wextra','-Werror','-O1' if sanitized else '-O2',f'-DMINYAR_RC_POLL_BUDGET={budget}']
            if sanitized:command+=['-g','-fsanitize=address,undefined']
            command +=[str(root/'tests/system-bounded-runtime.c'),'-o',str(binary)]
            subprocess.run(command,check=True,env=env)
            subprocess.run([str(binary)],check=True,env=env,stdout=subprocess.PIPE)
            oom=subprocess.run([str(binary),'oom'],capture_output=True,text=True,env=env)
            assert oom.returncode!=0 and 'ran out of memory' in oom.stderr,oom.stderr
            if sanitized:
                stale=subprocess.run([str(binary),'stale'],capture_output=True,text=True,env=env)
                assert stale.returncode!=0 and 'heap-use-after-free' in stale.stderr,stale.stderr
            print(f'budget{budget} {"ASan/UBSan" if sanitized else "native"}:80MiB, graph/frame recovery, OOM/stale passed',flush=True)
    for other in ('MINYAR_BOUNDED_HEAP','MINYAR_LAZY_HEAP'):
        command=['clang','-std=c11','-DMINYAR_SYSTEM_HEAP=1','-D'+other+'=1','-fsyntax-only',str(root/'runtime/minyar_runtime.c')]
        conflict=subprocess.run(command,capture_output=True,text=True)
        assert conflict.returncode!=0 and ('not both' in conflict.stderr or 'cannot be combined' in conflict.stderr)
        subprocess.run(command[:3]+['-DMINYAR_COMPILER_ARENA=1']+command[3:],check=True)
    print('conflicting backends rejected; compiler arena ignores allocator profiles',flush=True)
