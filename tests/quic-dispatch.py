#!/usr/bin/env python3
"""Published SipHash-2-4 vectors plus independent timer/routing oracles."""
import argparse,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');options=parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-quic-dispatch-') as temporary:
        binary=Path(temporary)/'dispatch';fixtures.compile_program(ROOT/'tests/quic-dispatch.min',binary)
        expected=Path(temporary)/'vectors';fixture=json.loads((ROOT/'tests/fixtures/siphash-vectors.json').read_text());expected.write_bytes(bytes.fromhex(''.join(fixture['vectors'])))
        result=subprocess.run([str(binary),str(expected)],capture_output=True,text=True,timeout=120)
        assert result.returncode==0,(result.returncode,result.stdout,result.stderr);print(result.stdout,end='')
if __name__=='__main__':main()
