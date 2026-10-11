#!/usr/bin/env python3
"""RFC5280/OpenSSL-style calendar adversaries and independent datetime oracle."""
import argparse,importlib.util,os,random,re,struct,subprocess,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def calendar_corpus(now):
    rng=random.Random(5280)
    def tlv(tag,data):return bytes((tag,len(data)))+data
    def certificate(before,after,tag):
        validity=tlv(tag,before.encode())+tlv(tag,after.encode())
        tbs=tlv(2,b"\0")+tlv(48,b"")+tlv(48,b"")+tlv(48,validity)+tlv(48,b"")+tlv(48,b"")
        cert=tlv(48,tlv(48,tbs)+tlv(48,b"")+tlv(3,b"\0"))
        return len(cert).to_bytes(3,"big")+cert+b"\0\0"
    def parse(date,tag):
        width=2 if tag==23 else 4
        if not re.fullmatch(r"[0-9]{"+str(width+10)+r"}Z",date):return None
        year=int(date[:width])
        if tag==23:year+=1900 if year>=50 else 2000
        try:return datetime(year,*(int(date[at:at+2]) for at in range(width,width+10,2)),tzinfo=timezone.utc)
        except ValueError:return None
    rows=[]
    def add(before,after,tag):
        start,end=parse(before,tag),parse(after,tag)
        expected=int(end.timestamp()*1000) if start and end and start<=now<end and start<end else 0
        rows.append((certificate(before,after,tag),expected))
    for year in range(100):add(f"{year:02}0101000000Z","491231235959Z",23)
    for n in range(1024):
        general=n%2==0
        year=rng.randint(max(2027,now.year+1),9999 if general else 2049)
        month=rng.randint(1,12);day=rng.randint(1,28)
        hour=rng.randrange(24);minute=rng.randrange(60);second=rng.randrange(60)
        after=f"{year if general else year%100:0{4 if general else 2}}{month:02}{day:02}{hour:02}{minute:02}{second:02}Z"
        before="19000101000000Z" if general else "500101000000Z"
        add(before,after,24 if general else 23)
        # Calendar and representation mutations preserve a complete DER envelope.
        width=4 if general else 2
        variant=n%8
        if variant==0:bad=after[:width]+"13"+after[width+2:]
        elif variant==1:bad=after[:width]+"0231"+after[width+4:]
        elif variant==2:bad=after[:width+4]+"24"+after[width+6:]
        elif variant==3:bad=after[:width+6]+"60"+after[width+8:]
        elif variant==4:bad=after[:width+8]+"60Z"
        elif variant==5:bad=after[:-1]+".0Z"
        elif variant==6:bad=after[:-1]+"+0000"
        else:bad=after[:-3]+"Z"
        add(before,bad,24 if general else 23)
    for year in (1,4,100,400,1600,1900,2000,2100,2400,9999):
        for day in (28,29,30):add(f"{year:04}02{day:02}000000Z","99991231235959Z",24)
    corpus=b"".join(struct.pack(">HQ",len(data),expected)+data for data,expected in rows)
    return corpus,len(rows)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');parser.add_argument('--corpus-output',type=Path);options=parser.parse_args()
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    assert int(datetime(2049,12,31,23,59,59,tzinfo=timezone.utc).timestamp()*1000)==2524607999000
    assert int(datetime(2048,2,29,tzinfo=timezone.utc).timestamp()*1000)==2466547200000
    with tempfile.TemporaryDirectory(prefix='minyar-certificate-time-') as directory:
        ca=fixtures.Certificates(directory);ca.root('root');now=datetime.now(timezone.utc).replace(microsecond=0);expires=now+timedelta(days=1)
        ca.leaf('valid','root',ec=True,validity=(now-timedelta(hours=1),expires));ca.leaf('expired','root',ec=True,validity='expired');ca.leaf('future','root',ec=True,validity='future')
        corpus,count=calendar_corpus(now);corpus_path=Path(directory)/'calendar.bin';corpus_path.write_bytes(corpus)
        if options.corpus_output:options.corpus_output.write_bytes(corpus)
        binary=Path(directory)/'validity';fixtures.compile_program(ROOT/'tests/tls-validity.min',binary)
        result=subprocess.run([str(binary),str(ca.path('valid','der')),str(int(expires.timestamp()*1000)),str(ca.path('expired','der')),str(ca.path('future','der')),str(corpus_path)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(result.returncode,result.stdout,result.stderr);print(result.stdout,end='')
if __name__=='__main__':main()
