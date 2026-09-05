#!/usr/bin/env python3
"""Profile record creation, access, and complete reclamation.

Phase markers are inserted into a temporary LLVM copy. The bounded runtime is
fully drained at the end of the measurement."""
from pathlib import Path
import argparse,hashlib,json,random,re,statistics,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--compiler',type=Path,default=ROOT/'build/minyarc')
p.add_argument('--before-runtime',type=Path,default=ROOT/'build/minyar-runtime.o')
p.add_argument('--after-runtime',type=Path,required=True)
p.add_argument('--repeats',type=int,default=21)
p.add_argument('--count',type=int,default=800000)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--after-scalar-set',action='store_true',help='After-only experiment: select scalar setter for the two Point fields in temporary LLVM')
p.add_argument('--after-uninitialized',action='store_true',help='After-only experiment: use compiler-specific uninitialized scalar constructor in temporary LLVM')
a=p.parse_args()
d=Path(tempfile.mkdtemp(prefix='minyar-record-phases-'))
ll=d/'benchmark.ll'
subprocess.run([str(a.compiler),str(ROOT/'tests/performance/runtime.min'),str(ll)],check=True)
s=ll.read_text();begin=s.index('define i64 @recordWorkload(');end=s.index('\n}\n',begin)+3
kernel=s[begin:end]
# Normalize existing scalar specialization on the control side. This keeps the
# runtime-only comparison valid after a compiler begins emitting the new API.
kernel=kernel.replace('call void @minyar_record_set_scalar(', 'call void @minyar_record_set(')
kernel=kernel.replace('call ptr @minyar_record_new_scalar_uninitialized(', 'call ptr @minyar_record_new_scalar(')
assert kernel.count('while.end.2:\n')==1 and kernel.count('while.end.5:\n')==1
kernel=kernel.replace('entry:\n','entry:\n  call void @record_phase_mark(i32 0)\n',1)
kernel=kernel.replace('while.end.2:\n','while.end.2:\n  call void @record_phase_mark(i32 1)\n',1)
kernel=kernel.replace('while.end.5:\n','while.end.5:\n  call void @record_phase_mark(i32 2)\n',1)
s=s[:begin]+kernel+s[end:]
s=s.replace('define i32 @main(', 'define i32 @unused_benchmark_main(',1)
s+='\ndeclare void @record_phase_mark(i32)\n';ll.write_text(s)
(d/'driver.c').write_text('''#include <stdio.h>
#include <stdint.h>
#include <time.h>
static uint64_t times[4];
void record_phase_mark(int phase) {
    struct timespec t; clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t);
    times[phase]=(uint64_t)t.tv_sec*1000000000+(uint64_t)t.tv_nsec;
}
extern long long recordWorkload(long long);
#ifdef AFTER_BOUNDED
extern size_t minyar_rc_poll(size_t);
#endif
int main(void) {
    long long result=recordWorkload('''+str(a.count)+''');
#ifdef AFTER_BOUNDED
    while(minyar_rc_poll(32)) {}
#endif
    record_phase_mark(3);
    printf("{\\"result\\":%lld,\\"creation_ms\\":%.6f,\\"access_ms\\":%.6f,\\"cleanup_ms\\":%.6f,\\"total_ms\\":%.6f}\\n",
      result,(times[1]-times[0])/1e6,(times[2]-times[1])/1e6,(times[3]-times[2])/1e6,(times[3]-times[0])/1e6);
}
''')
executables={}
for name,obj in [('before',a.before_runtime),('after',a.after_runtime)]:
    exe=d/name
    selected_ll=ll
    if name=='after' and (a.after_scalar_set or a.after_uninitialized):
        selected_ll=d/'benchmark-scalar-set.ll'
        changed=ll.read_text()
        start=changed.index('define i64 @recordWorkload(');stop=changed.index('\n}\n',start)+3
        function=changed[start:stop]
        record=re.search(r'(?m)^  (%[-.a-zA-Z0-9_]+) = call ptr @minyar_record_new_scalar\(i64 2\)$',function)
        assert record, 'expected one scalar Point constructor'
        marker='call void @minyar_record_set(ptr '+record.group(1)+', '
        assert function.count(marker)==2
        if a.after_scalar_set:
            function=function.replace(marker,'call void @minyar_record_set_scalar(ptr '+record.group(1)+', ')
        if a.after_uninitialized:
            function=function.replace('call ptr @minyar_record_new_scalar(', 'call ptr @minyar_record_new_scalar_uninitialized(')
        changed=changed[:start]+function+changed[stop:]+('\ndeclare void @minyar_record_set_scalar(ptr, i64, i64)\n' if 'declare void @minyar_record_set_scalar(' not in changed else '')
        if a.after_uninitialized and 'declare ptr @minyar_record_new_scalar_uninitialized(' not in changed:
            changed+='\ndeclare ptr @minyar_record_new_scalar_uninitialized(i64)\n'
        selected_ll.write_text(changed)
    cmd=['clang','-O2','-Wno-override-module',str(selected_ll),str(d/'driver.c'),str(obj),'-o',str(exe)]
    if name=='after':cmd.insert(1,'-DAFTER_BOUNDED=1')
    subprocess.run(cmd,check=True);executables[name]=exe
    subprocess.run([str(exe)],check=True,stdout=subprocess.PIPE)
rng=random.Random(428719);samples={'before':[],'after':[]}
for repeat in range(a.repeats):
    order=['before','after'];rng.shuffle(order)
    for name in order:
        result=subprocess.run([str(executables[name])],check=True,capture_output=True,text=True)
        row=json.loads(result.stdout);assert row['result']==a.count*(a.count-1)//2
        samples[name].append(row)
medians={name:{phase:statistics.median(row[phase] for row in rows) for phase in ('creation_ms','access_ms','cleanup_ms','total_ms')} for name,rows in samples.items()}
report={'method':'Temporary markers in actual generated recordWorkload LLVM; process CPU; IR linkedO2 (after-only scalar-set experiment explicitly flagged when enabled); bounded side includes explicit full drain; seeded interleaved fresh processes after warmup.','directory':str(d),'count':a.count,'repeats':a.repeats,'medians':medians,'samples':samples,'before_runtime':str(a.before_runtime),'after_runtime':str(a.after_runtime),'after_scalar_set_experiment':a.after_scalar_set,'after_uninitialized_experiment':a.after_uninitialized,'sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (a.compiler,a.before_runtime,a.after_runtime,ll,ROOT/'tests/performance/runtime.min')}}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(medians,indent=2))
