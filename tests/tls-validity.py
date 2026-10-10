#!/usr/bin/env python3
"""RFC5280/OpenSSL-style calendar adversaries and independent datetime oracle."""
import argparse,importlib.util,os,subprocess,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');options=parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    assert int(datetime(2049,12,31,23,59,59,tzinfo=timezone.utc).timestamp()*1000)==2524607999000
    assert int(datetime(2048,2,29,tzinfo=timezone.utc).timestamp()*1000)==2466547200000
    with tempfile.TemporaryDirectory(prefix='minyar-certificate-time-') as directory:
        ca=fixtures.Certificates(directory);ca.root('root');now=datetime.now(timezone.utc).replace(microsecond=0);expires=now+timedelta(days=1)
        ca.leaf('valid','root',ec=True,validity=(now-timedelta(hours=1),expires));ca.leaf('expired','root',ec=True,validity='expired');ca.leaf('future','root',ec=True,validity='future')
        binary=Path(directory)/'validity';fixtures.compile_program(ROOT/'tests/tls-validity.min',binary)
        result=subprocess.run([str(binary),str(ca.path('valid','der')),str(int(expires.timestamp()*1000)),str(ca.path('expired','der')),str(ca.path('future','der'))],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(result.returncode,result.stdout,result.stderr);print(result.stdout,end='')
if __name__=='__main__':main()
