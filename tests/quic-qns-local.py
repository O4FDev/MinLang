#!/usr/bin/env python3
"""Run already compiled QNS endpoints over local UDP; setup is separate."""
import argparse,hashlib,hmac,importlib.util,json,os,select,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("qns_certificates",ROOT/"tests/tls-local.py")
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
CASES=("multiplex1999","multiconnect50","keyupdate","chacha20","ipv6","preferred","resumption40","zerortt40")
def main():
 p=argparse.ArgumentParser();p.add_argument("--client",type=Path,required=True);p.add_argument("--server",type=Path,required=True)
 p.add_argument("--case",action="append",choices=CASES);p.add_argument("--expect-old-code",action="store_true");p.add_argument("--port",type=int,default=44300)
 a=p.parse_args();results=[]
 with tempfile.TemporaryDirectory(prefix="minyar-qns-local-") as d:
  d=Path(d);ca=fixtures.Certificates(d);ca.root("root");ca.leaf("server","root",san="DNS:localhost,IP:127.0.0.1,IP:::1")
  for case in a.case or CASES:
   www=d/(case+"-www");downloads=d/(case+"-downloads");www.mkdir();downloads.mkdir()
   count=1999 if case=="multiplex1999" else (50 if case=="multiconnect50" else (40 if case in ("resumption40","zerortt40") else 1))
   size=32 if count==1999 else (1024 if count==50 else (5000 if count==40 else 1048576))
   names=["file"+str(i) for i in range(count)]
   payload=bytes((i*17+3)%256 for i in range(size))
   for name in names:(www/name).write_bytes(payload)
   serverlog=d/(case+"-server.keys");clientlog=d/(case+"-client.keys")
   testcase={"multiplex1999":"transfer","multiconnect50":"multiconnect","ipv6":"transfer","preferred":"connectionmigration","resumption40":"resumption","zerortt40":"zerortt"}.get(case,case)
   command=[str(a.server.resolve()),str(ca.path("server","pk8")),str(ca.path("root","der")),str(serverlog),str(www),testcase,str(ca.path("server","der"))]
   if not a.expect_old_code:command+=["--port="+str(a.port)]
   if case=="preferred":command+=["--preferred-ipv4=7f000001","--preferred-port="+str(a.port+1)]
   server=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
   ready=select.select([server.stdout],[],[],10)[0]
   greeting=server.stdout.readline() if ready else ""
   if greeting!="QNS server ready\n":
    server.terminate();stdout,stderr=server.communicate(timeout=5)
    raise RuntimeError(("server setup",server.returncode,greeting,stdout,stderr))
   try:
    host="::1" if case=="ipv6" else "127.0.0.1"
    command=[str(a.client.resolve()),str(ca.path("root","der")),host,str(a.port),str(clientlog),str(downloads),testcase,*names]
    c=subprocess.run(command,capture_output=True,text=True,timeout=180)
   finally:
    server.terminate()
    try:serverout,servererr=server.communicate(timeout=5)
    except subprocess.TimeoutExpired:server.kill();serverout,servererr=server.communicate(timeout=5)
   labels=[line.split()[0] for line in clientlog.read_text().splitlines()] if clientlog.exists() else []
   serverlabels=[line.split()[0] for line in serverlog.read_text().splitlines()] if serverlog.exists() else []
   reciprocal=True
   if case=="keyupdate":
    clientsecrets={line.split()[0]:bytes.fromhex(line.split()[2]) for line in clientlog.read_text().splitlines()}
    serversecrets={line.split()[0]:bytes.fromhex(line.split()[2]) for line in serverlog.read_text().splitlines()}
    label=b"tls13 quic ku";info=bytes([0,32,len(label)])+label+b"\x00"
    for side in ("CLIENT","SERVER"):
     old=clientsecrets.get(side+"_TRAFFIC_SECRET_0",b"")
     updated=hmac.new(old,info+b"\x01",hashlib.sha256).digest()
     reciprocal=reciprocal and clientsecrets.get(side+"_TRAFFIC_SECRET_1")==updated and serversecrets.get(side+"_TRAFFIC_SECRET_1")==updated
   files_ok=all((downloads/n).is_file() and (downloads/n).read_bytes()==payload for n in names)
   semantic=0
   if case=="multiplex1999" and (c.returncode or not files_ok):semantic=42
   elif case=="multiconnect50" and (c.returncode or not files_ok or labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET")!=50):semantic=52
   elif case=="keyupdate" and (c.returncode or not files_ok or "CLIENT_TRAFFIC_SECRET_1" not in labels or "SERVER_TRAFFIC_SECRET_1" not in serverlabels or not reciprocal):semantic=62
   elif case=="chacha20" and (c.returncode or not files_ok):semantic=82
   elif case=="ipv6" and (c.returncode or not files_ok):semantic=72
   elif case=="preferred" and (c.returncode or not files_ok or "QNS preferred path validated" not in c.stdout):semantic=92
   elif case in ("resumption40","zerortt40") and (c.returncode or not files_ok or labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET")!=2):semantic=102
   expected={"multiplex1999":42,"multiconnect50":52,"keyupdate":62,"ipv6":72}.get(case,0) if a.expect_old_code else 0
   results.append({"case":case,"client_status":c.returncode,"semantic_status":semantic,"expected":expected,"matched":semantic==expected,
      "client_stdout":c.stdout,"client_stderr":c.stderr,"server_stdout":serverout,"server_stderr":servererr,
      "files_match":files_ok,"reciprocal_epoch_secrets":reciprocal,"handshakes":labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET"),
      "client_epochs":sorted(set(x for x in labels if x.startswith("CLIENT_TRAFFIC_SECRET_"))),
      "server_epochs":sorted(set(x for x in serverlabels if x.startswith("SERVER_TRAFFIC_SECRET_")))})
 print(json.dumps({"binary_hashes":{n:hashlib.sha256(x.read_bytes()).hexdigest() for n,x in [("client",a.client),("server",a.server)]},"results":results},indent=2))
 return 0 if all(x["matched"] and not x["client_stderr"] and not x["server_stderr"] for x in results) else 1
if __name__=="__main__":raise SystemExit(main())
