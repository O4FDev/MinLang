#!/usr/bin/env python3
"""Check scalar initializer selection and mixed-record cleanup service."""
import argparse, os, re, subprocess, tempfile
from pathlib import Path
from llvm_sanitizer import prepare_llvm_for_link
CASES = [
('scalar', '''record Value { x: Integer; flag: Boolean; letter: Character }
function make(n: Integer): Value { return Value { letter: 'z'; flag: true; x: n } }
let value = make(37)
print(value.x)
print(value.flag)
print(value.letter)
''', '37\ntrue\nz\n', 3, 0),
('mixed', '''record Value { x: Integer; label: Text }
function make(n: Integer): Value { return Value { x: n; label: "mixed" } }
let value = make(41)
print(value.x)
print(value.label)
''', '41\nmixed\n', 0, 1),
('nested', '''record Leaf { x: Integer }
record Parent { tag: Integer; child: Leaf }
function make(n: Integer): Parent { return Parent { child: Leaf { x: n }; tag: 8 } }
let value = make(13)
print(value.tag)
print(value.child.x)
''', '8\n13\n', 1, 1),
('effects', '''record Value { x: Integer; y: Integer }
function next(values: List<Integer>): Integer { values[0] = values[0] + 1; return values[0] }
function make(values: List<Integer>): Value { return Value { y: next(values); x: next(values) } }
let state = [10]
let value = make(state)
print(value.x)
print(value.y)
print(state[0])
''', '12\n11\n12\n', 2, 0),
]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--clang',default='clang');p.add_argument('--sanitize',action='store_true');args=p.parse_args()
 env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1'}
 with tempfile.TemporaryDirectory(prefix='minyar-scalar-initialization-') as work:
  work=Path(work)
  for name,source,expected,scalar,generic in CASES:
   path=work/(name+'.min');path.write_text(source);ir=path.with_suffix('.ll')
   result=subprocess.run([str(args.compiler.resolve()),str(path),str(ir)],capture_output=True,text=True,timeout=30)
   assert result.returncode==0,(name,result.stderr)
   text=ir.read_text();found_scalar=len(re.findall(r'call void @minyar_record_set_scalar\(',text));found_generic=len(re.findall(r'call void @minyar_record_set\(',text))
   assert (found_scalar,found_generic)==(scalar,generic),(name,'wrong initialization path',found_scalar,found_generic,scalar,generic)
   if args.sanitize: prepare_llvm_for_link(ir, ['-fsanitize=address'])
   for opt in ['-O0','-O2']:
    exe=path.with_suffix("." + opt[1:]);flags=['-g','-fsanitize=address,undefined'] if args.sanitize else []
    result=subprocess.run([args.clang,opt,*flags,'-Wno-override-module',str(ir),str(args.runtime.resolve()),'-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,(name,result.stderr)
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15,env=env)
    assert result.returncode==0 and result.stdout==expected,(name,result.stdout,result.stderr,expected)
   print(name+': scalar/mixed selection and execution passed',flush=True)
if __name__=='__main__':main()
