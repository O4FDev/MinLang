#!/usr/bin/env python3
"""Tokenizer decoding, ownership and demand-driven literal scratch storage."""
from pathlib import Path
import argparse, itertools, os, re, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
# This file may also run from an isolated candidate directory.
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=ROOT)
parser.add_argument('--compiler',type=Path)
parser.add_argument('--source',type=Path)
parser.add_argument('--clang',default=os.environ.get('MINYAR_TEST_CLANG','clang'))
args=parser.parse_args();ROOT=args.root.resolve()
compiler=(args.compiler or Path(os.environ.get('MINYAR_TEST_COMPILER',ROOT/'build/minyarc'))).resolve()
source=(args.source or ROOT/'src/compiler.min').resolve()
temporary=tempfile.TemporaryDirectory(prefix='minyar-tokenizer-storage-');D=Path(temporary.name)
environment={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=0'}
def run(command):
 return subprocess.run(list(map(str,command)),capture_output=True,timeout=120,env=environment)
def must(command):
 r=run(command);assert r.returncode==0,(command,r.stdout,r.stderr);return r

fixture=Path(__file__).with_suffix('.c')
def oracle(s):
 rows=[];i=0;line=1;escaped_literals=0
 def put(k,t,l):rows.append((str(k),str(l),t.encode().hex()))
 while i<len(s):
  c=s[i]
  if c in ' \t\r\n':
   if c=='\n':
    if rows and int(rows[-1][0]) in [1,2,3,5]:put(6,'end of line',line)
    line+=1
   i+=1;continue
  if c=='"':
   startline=line;i+=1;text=[];escaped=False
   while i<len(s) and s[i]!='"':
    c=s[i]
    if c=='\\' and i+1<len(s):
     escaped=True;c=s[i+1];line+=c=='\n';text.append({'n':'\n','r':'\r','t':'\t'}.get(c,c));i+=2
    else:line+=c=='\n';text.append(c);i+=1
   if i==len(s):return None,f'line {startline}: Text literal is missing its closing quote',0
   i+=1;escaped_literals+=escaped;put(3,''.join(text),startline);continue
  assert c.isascii() and (c.isalpha() or c=='_'),repr(c)
  start=i
  while i<len(s) and s[i].isascii() and (s[i].isalnum() or s[i]=='_'):i+=1
  put(1,s[start:i],line)
 put(0,'',line);return rows,None,escaped_literals
cases=[('prefix','\r\nalpha "plain" beta\r\n"é🙂" tail\n'),('nul','head "a\x00b" next\n"\\\x00" end'),('lines','\n\nhead "before\r\n\\\nafter\\nlast" tail\r\nend'),('quote_boundary','"\\\"""next" tail'),('slash_parity','"\\\\" "\\\\\\\"end" next'),('empty','\n"" next "\\q\\é\\🙂"\n'),('long','before "'+'é'*1024+'\\n'+'a'*4096+'" after\n'),('missing_plain','\r\nhead\n"plain\nunterminated'),('missing_escape','\n\n"prefix\\nlast'),('trailing_slash','\nhead\n"abc\\'),('consumed_quote','\n\n"abc\\"')]
atoms=['a','é','🙂','\n','\r','\t','\\n','\\r','\\t','\\\\','\\"','\\q','\\é','\\🙂','\\\n']
composed=['',*atoms,*(''.join(parts) for parts in itertools.product(atoms,repeat=2))]
cases.append(('composed',' '.join('"'+raw+'"' for raw in composed)))
for name,text in cases:(D/(name+'.min')).write_text(text)
llvm=D/'compiler.ll';must([compiler,source,llvm]);ir=llvm.read_text()
ir,n=re.subn(r'^define i32 @main\(','define i32 @compiler_main(',ir,flags=re.M);assert n==1
match=re.search(r'^define void @tokenize\([^\n]*\) \{\n.*?^\}',ir,re.M|re.S);assert match
body=match.group();assert body.count('call ptr @minyar_list_new()')==1
body=body.replace('call ptr @minyar_list_new()','call ptr @probe_tokenizer_list()')
ir=ir[:match.start()]+body+ir[match.end():]+'\ndeclare ptr @probe_tokenizer_list()\n';llvm.write_text(ir)
san=D/'sanitized.ll';must(['python3',ROOT/'tests/llvm_sanitizer.py',llvm,san])
checks=0
for profile,extra in [('eager',[]),('system',['-DMINYAR_SYSTEM_HEAP=1'])]:
 for optimization in ['-O0','-O2']:
  for mode in ['native','sanitize']:
   flags=[optimization,*extra];input_ir=llvm
   if mode=='sanitize':flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g'];input_ir=san
   exe=D/(profile+optimization+mode)
   must([args.clang,*flags,'-Wno-override-module','-I',ROOT,input_ir,fixture,'-o',exe])
   for name,text in cases:
    expected,error,lists=oracle(text);r=run([exe,D/(name+'.min')])
    context=(profile,optimization,mode,name,r.stderr)
    if error:assert r.returncode==1 and error.encode() in r.stderr,context
    else:
     assert r.returncode==0 and b'OWNERS clean=1' in r.stderr,context
     actual=[tuple(line.split('\t')) for line in r.stdout.decode().splitlines()];assert actual==expected,(context,actual,expected)
     count=re.search(rb'TOKEN_LISTS=(\d+)',r.stderr);assert count,context
     # Permit future allocation elimination; unescaped literals need no List,
     # and each escaped literal may use at most one scratch List per pass.
     assert int(count[1])<=3*lists,('unexpected tokenizer scratch Lists',context,int(count[1]),3*lists)
    checks+=1
print(f'Tokenizer storage passed: {checks} checks, including {len(composed)} composed literals per successful matrix run.')
