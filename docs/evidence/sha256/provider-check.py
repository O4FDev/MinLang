import hashlib, json, os
from pathlib import Path
import subprocess, sys
root = Path.cwd()
(root / 'logs').mkdir(exist_ok=True)
sys.path.insert(0, str(root / 'tools'))
from format_provider import provider_info
from sha256_provider import sha256_provider
commands=[]
def run(argv):
    command=list(map(str,argv)); commands.append(command)
    result=subprocess.run(command,capture_output=True,text=True,timeout=120)
    if result.returncode: raise RuntimeError((command,result.returncode,result.stdout,result.stderr))
    return result.stdout
clang=os.environ.get('MINYAR_TEST_CLANG','clang')
info=provider_info('sha256',clang)
cflags,libraries=sha256_provider(clang)
assert (cflags,libraries)==(info['cflags'],info['libraries'])
compiler=root/'build/minyarc'; runtime=root/'build/minyar-default-runtime.o'
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p.relative_to(root)):hashfile(p) for p in (compiler,runtime)}
run([compiler,'tests/sha256.min','build/sha256-provider-check.ll','--library','library'])
ir=(root/'build/sha256-provider-check.ll').read_text()
assert 'securecrypto' not in ir and 'monocypher' not in ir
run([clang,'-O2',*cflags,'-c','runtime/native/sha256.c','-o','build/sha256-provider-check.o'])
run([clang,'-O2','-Wno-override-module','build/sha256-provider-check.ll',runtime,'build/sha256-provider-check.o',*libraries,'-lm','-o','build/sha256-provider-check'])
direct=run(['build/sha256-provider-check'])
# The parent prepared this compiler/runtime; a normal launcher must reuse them.
dry=run(['make','-n','build/minyarc','build/minyar-default-runtime.o'])
assert 'clang ' not in dry and 'cc ' not in dry, dry
launcher_build=run(['./minyar','tests/sha256.min','-o','build/sha256-normal-launcher'])
launcher=run(['build/sha256-normal-launcher'])
assert direct==launcher
assert before=={str(p.relative_to(root)):hashfile(p) for p in (compiler,runtime)}
receipt={'provider':info,'parent_files':{p:hashfile(root/p) for p in ('tools/format_provider.py','tools/sha256_provider.py','tools/clang-driver.py')},'toolchain_hashes':before,'commands':commands,'direct_stdout':direct,'launcher_stdout':launcher,'launcher_build_stdout':launcher_build,'make_dry_run':dry,'ir_sha256':hashfile(root/'build/sha256-provider-check.ll')}
(root/'logs/parent-provider-launcher-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(direct,end=''); print('Parent matched-provider direct link and normal launcher passed; compiler/runtime identity unchanged')
