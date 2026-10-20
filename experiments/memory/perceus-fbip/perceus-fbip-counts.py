#!/usr/bin/env python3
"""BX-only generated-code allocation/refcount proof, no timing thresholds."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path('build/perceus-measurement-20261020').resolve()
OUT = ROOT/'fbip/synthetic'
OUT.mkdir(parents=True, exist_ok=False)
FROZEN = ROOT/'fbip/candidate/tree'
RUNTIME = OUT/'runtime'
shutil.copytree(FROZEN/'runtime', RUNTIME)
commands = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def run(argv):
    argv = [str(v) for v in argv]
    result = subprocess.run(argv, text=True, capture_output=True, timeout=120)
    index = len(commands)
    (OUT/('command-%03d.stdout'%index)).write_text(result.stdout)
    (OUT/('command-%03d.stderr'%index)).write_text(result.stderr)
    commands.append({'argv': argv, 'exit': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr})
    save(OUT/'commands.json', commands)
    if result.returncode:
        raise RuntimeError('synthetic command failed: '+repr(commands[-1]))
    return result


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError('instrumentation anchor ambiguous: '+repr(before))
    return text.replace(before, after, 1)


header = (RUNTIME/'minyar_rc.h').read_text()
header = replace_once(header, '    object->ownership = 8 | kind;',
    '    if (kind == RC_SCALAR_RECORD) { measured_allocs++; measured_bytes += sizeof(*object) + size; }\n    object->ownership = 8 | kind;')
header = replace_once(header, '    object->ownership += 8;',
    '    measured_retains++;\n    object->ownership += 8;')
header = replace_once(header, '    object->ownership -= 8;',
    '    measured_releases++;\n    object->ownership -= 8;')
(RUNTIME/'minyar_rc.h').write_text(header)
scope = (RUNTIME/'minyar_scope_ownership.h').read_text()
scope = replace_once(scope, '            object->ownership = ownership - 8;',
    '            measured_releases++;\n            object->ownership = ownership - 8;')
(RUNTIME/'minyar_scope_ownership.h').write_text(scope)
collections = (RUNTIME/'minyar_collections.h').read_text()
collections = replace_once(collections,
    'MinyarRecord *minyar_record_reuse_scalar_take(MinyarRecord *record, long long field_count) {',
    'MinyarRecord *minyar_record_reuse_scalar_take(MinyarRecord *record, long long field_count) {\n    measured_reuse_calls++;')
collections = replace_once(collections, '        record->length == field_count) {',
    '        record->length == field_count) {\n        measured_reuse_hits++;')
(RUNTIME/'minyar_collections.h').write_text(collections)
runtime = (RUNTIME/'minyar_runtime.c').read_text()
runtime = '''#define MINYAR_RC_TESTING 1
static unsigned long long measured_allocs, measured_bytes, measured_retains, measured_releases;
static unsigned long long measured_reuse_calls, measured_reuse_hits;
''' + runtime + r'''
#include <assert.h>
__attribute__((destructor)) static void measured_finish(void) {
    assert(rc_frames == NULL);
    assert(rc_scopes == NULL);
    assert(rc_pending_count == 0);
    assert(rc_object_count == rc_immortal_object_count);
    fprintf(stderr, "{\"scalar_record_allocations\":%llu,\"requested_record_bytes\":%llu,"
        "\"retains\":%llu,\"releases\":%llu,\"reuse_calls\":%llu,\"reuse_hits\":%llu,"
        "\"complete_cleanup\":true}\n", measured_allocs, measured_bytes, measured_retains,
        measured_releases, measured_reuse_calls, measured_reuse_hits);
}
'''
(RUNTIME/'minyar_runtime.c').write_text(runtime)
run(['clang-23','-O2','-c',RUNTIME/'minyar_runtime.c','-o',OUT/'runtime.o'])
sources = {}
sources['unique'] = '''record Pair { x: Integer; y: Integer }
function evolve(limit: Integer): Pair {
    let p = Pair { x: 0; y: 11 }
    for index in 0..limit { p = Pair { x: p.x + 1; y: p.y } }
    return p
}
let result = evolve(10000)
print(result.x); print(result.y)
'''
sources['persistent-alias'] = '''record Pair { x: Integer; y: Integer }
function evolve(limit: Integer, saved: List<Pair>): Pair {
    let p = Pair { x: 0; y: 11 }
    for index in 0..limit {
        saved.add(p)
        p = Pair { x: p.x + 1; y: p.y }
    }
    return p
}
let saved: List<Pair> = []
let result = evolve(10000, saved)
for index in 0..saved.length {
    if saved[index].x != index || saved[index].y != 11 { fail("persistent alias changed") }
}
print(result.x); print(result.y); print(saved.length)
'''
results = {}
for case, source in sources.items():
    path = OUT/(case+'.min')
    path.write_text(source)
    results[case] = {}
    for arm, compiler in [('control',ROOT/'fbip/control-tree/build/minyarc'),
                          ('candidate',ROOT/'fbip/candidate/tree/build/minyarc')]:
        for lowering, flags in [('legacy',[]),('scope',['--scope-owners'])]:
            ir = OUT/(case+'-'+arm+'-'+lowering+'.ll')
            run([compiler,path,ir,'--library',ROOT/'baseline/tree/library',*flags])
            eligible = len(re.findall(r'^\s*%[^\n=]+ = call ptr @minyar_record_reuse_scalar_take\(',ir.read_text(),re.M))
            if eligible != (1 if arm=='candidate' else 0):
                raise RuntimeError('unexpected generated helper sites')
            for opt in [0,2]:
                binary = OUT/(case+'-'+arm+'-'+lowering+'-O'+str(opt))
                run(['clang-23','-O'+str(opt),'-Wno-override-module',ir,OUT/'runtime.o',
                     '-pthread','-lm','-o',binary])
                executed = run([binary])
                expected = '10000\n11\n' + ('10000\n' if case=='persistent-alias' else '')
                if executed.stdout != expected:
                    raise RuntimeError('synthetic output mismatch')
                row = json.loads(executed.stderr)
                row.update(llvm_sha256=sha(ir),binary_sha256=sha(binary),output=executed.stdout)
                if row['scalar_record_allocations'] != (1 if case=='unique' and arm=='candidate' else 10001):
                    raise RuntimeError('unexpected actual record allocation count')
                if row['reuse_calls'] != (10000 if arm=='candidate' else 0):
                    raise RuntimeError('unexpected reuse helper count')
                if row['reuse_hits'] != (10000 if arm=='candidate' and case=='unique' else 0):
                    raise RuntimeError('alias/unique reuse decision incorrect')
                results[case][arm+'-'+lowering+'-O'+str(opt)] = row
                save(OUT/'progress.json',results)
report = {'iterations':10000,'cases':results,
          'method':'actual generated code, true eager malloc/free runtime; one identical instrumented runtime.o across both compiler arms, both lowerings, both optimizations; actual RC increments/decrements including scope fast decrements; no timing claim',
          'instrumented_runtime_sha256':sha(RUNTIME/'minyar_runtime.c'),
          'instrumented_runtime_object_sha256':sha(OUT/'runtime.o'),
          'runtime_headers':{p.name:sha(p) for p in sorted(RUNTIME.glob('*.h'))},
          'source_sha256':{case:hashlib.sha256(source.encode()).hexdigest() for case,source in sources.items()}}
save(OUT/'results.json',report)
print(json.dumps(report,indent=2))
