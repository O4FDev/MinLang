#!/usr/bin/env python3
"""RFC7748/8439 adversarial primitive checks independent of TLS serializers."""
import argparse,importlib.util,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');options=parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-native-crypto-') as temporary:
        binary=Path(temporary)/'crypto';fixtures.compile_program(ROOT/'tests/securecrypto.min',binary)
        result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=120)
        assert result.returncode==0 and not result.stderr,(result.returncode,result.stdout,result.stderr);print(result.stdout,end='')
        shared=Path(temporary)/'shared';fixtures.compile_program(ROOT/'tests/securecrypto-update.min',shared)
        result=subprocess.run([str(shared)],capture_output=True,text=True,timeout=120)
        assert (result.returncode,result.stdout,result.stderr)==(0,'true\ntrue\n',''),(result.returncode,result.stdout,result.stderr)
if __name__=='__main__':main()
