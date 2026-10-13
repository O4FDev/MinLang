#!/usr/bin/env python3
"""Run already compiled QNS endpoints over local UDP; setup is separate."""
import argparse,hashlib,hmac,importlib.util,json,os,select,socket,subprocess,sys,threading,time
from quic_protocol_artifacts import ProtocolArtifacts
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("qns_certificates",ROOT/"tests/tls-local.py")
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
CASES=("multiplex1999","multiconnect50","keyupdate","chacha20","ipv6","preferred","preferred-ipv6","resumption40","zerortt40","rebind-routes","rebind-pending","rebind-silent")
class RebindingProxy:
 def __init__(self,port,chunk=1048576,delay=.003,silent=False):
  self.chunk=chunk;self.delay=delay;self.delivery_at=None
  self.silent=silent;self.holding=False;self.quiet_at=0;self.quiet_rebounds=0;self.client_after_rebind=0
  self.started=time.monotonic();self.forwarded=0;self.packets=0;self.waited=0;self.last_forward=0;self.bindings=[]
  self.target=("127.0.0.1",port);self.front=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.front.bind(("127.0.0.1",port+2))
  self.port=self.front.getsockname()[1];self.back=None;self.ports=set();self.stopping=threading.Event();self.error=None
  self.rebind();self.thread=threading.Thread(target=self.run);self.thread.start()
 def rebind(self):
  old=self.back;self.back=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.back.bind(("127.0.0.1",0));self.ports.add(self.back.getsockname()[1])
  self.bindings.append({"elapsed":time.monotonic()-self.started,"bytes":self.forwarded,"port":self.back.getsockname()[1]})
  if old is not None:old.close()
 def delivery_delay(self,now):
  if self.delivery_at is None:self.delivery_at=now
  self.delivery_at=max(self.delivery_at,now-8*self.delay)+self.delay
  return max(0,self.delivery_at-now)
 def run(self):
  client=None;received=0
  try:
   while not self.stopping.is_set():
    ready,_,_=select.select([self.front,self.back],[],[],.1)
    for stream in ready:
     data,address=stream.recvfrom(65535)
     if stream is self.front:
      client=address;self.back.sendto(data,self.target);self.quiet_at=time.monotonic()
      if self.quiet_rebounds:self.client_after_rebind+=1
     elif client is not None:
      if self.holding:continue
      before=time.monotonic();self.stopping.wait(self.delivery_delay(before));self.waited+=time.monotonic()-before
      self.front.sendto(data,client);received+=len(data)
      self.forwarded+=len(data);self.packets+=1;self.last_forward=time.monotonic()-self.started
      if received>=self.chunk and len(self.ports)<16:
       if self.silent:
        if not self.quiet_rebounds:self.holding=True;self.quiet_at=time.monotonic()
       else:received=0;self.rebind()
    if self.holding and time.monotonic()-self.quiet_at>=.2:
     self.rebind();self.quiet_rebounds+=1;self.holding=False
  except BaseException as error:self.error=error
 def close(self):
  self.stopping.set();self.thread.join(timeout=2);self.front.close();self.back.close()
  if self.thread.is_alive():raise RuntimeError("rebinding proxy did not stop")
  if self.error is not None:raise self.error
 def progress(self):
  return {"elapsed":time.monotonic()-self.started,"bytes":self.forwarded,"packets":self.packets,"wait_seconds":self.waited,"last_forward":self.last_forward,"bindings":self.bindings,"quiet_rebounds":self.quiet_rebounds,"client_after_rebind":self.client_after_rebind}
def main():
 p=argparse.ArgumentParser();p.add_argument("--client",type=Path,required=True);p.add_argument("--server",type=Path,required=True)
 p.add_argument("--case",action="append",choices=CASES);p.add_argument("--expect-old-code",action="store_true");p.add_argument("--port",type=int,default=44300)
 p.add_argument("--artifacts",type=Path)
 a=p.parse_args();results=[]
 with ProtocolArtifacts("minyar-qns-local",a.artifacts,inputs=[Path(__file__),a.client,a.server,ROOT/"tests/tls-local.py",ROOT/"tests/quic_protocol_artifacts.py",ROOT/"tests/test_evidence.py",ROOT/"tests/interop/qns/client.min",ROOT/"tests/interop/qns/server.min",ROOT/"tests/interop/qns/endpoint.py"],declared_cases=a.case or CASES) as artifacts:
  artifacts.fixture(fixtures)
  d=artifacts.workspace;ca=fixtures.Certificates(d);ca.root("root");ca.leaf("server","root",san="DNS:localhost,IP:127.0.0.1,IP:::1")
  artifacts.certificates_ready()
  for case in a.case or CASES:
   www=d/(case+"-www");downloads=d/(case+"-downloads");www.mkdir();downloads.mkdir()
   count=1999 if case=="multiplex1999" else (50 if case=="multiconnect50" else (40 if case in ("resumption40","zerortt40") else 1))
   size=32 if count==1999 else (1024 if count==50 else (5000 if count==40 else 1048576))
   if case=="rebind-routes":size=16777216
   names=["file"+str(i) for i in range(count)]
   payload=bytes((i*17+3)%256 for i in range(size))
   for name in names:(www/name).write_bytes(payload)
   serverlog=d/(case+"-server.keys");clientlog=d/(case+"-client.keys")
   artifacts.bind_files(case,"payloads",[www]);artifacts.bind_files(case,"downloads",[downloads]);artifacts.bind_files(case,"keylogs",[serverlog,clientlog])
   testcase={"multiplex1999":"transfer","multiconnect50":"multiconnect","ipv6":"transfer","preferred":"connectionmigration","preferred-ipv6":"connectionmigration","resumption40":"resumption","zerortt40":"zerortt","rebind-routes":"transfer","rebind-pending":"transfer","rebind-silent":"transfer"}.get(case,case)
   command=[str(a.server.resolve()),str(ca.path("server","pk8")),str(ca.path("root","der")),str(serverlog),str(www),testcase,str(ca.path("server","der"))]
   if not a.expect_old_code or case=="rebind-silent":command+=["--port="+str(a.port)]
   if case=="preferred":command+=["--preferred-ipv4=7f000001","--preferred-port="+str(a.port+1)]
   if case=="preferred-ipv6":command+=["--preferred-ipv4=00000000","--preferred-ipv6=00000000000000000000000000000001","--preferred-port="+str(a.port+1)]
   server=artifacts.endpoint(command,case+"-server",case=case,peer_timeout=180)
   proxy=None
   try:
    greeting=server.ready_line()
    if greeting!="QNS server ready\n":
     raise RuntimeError(("server setup",server.process.poll(),greeting))
    host="::1" if case in ("ipv6","preferred-ipv6") else "127.0.0.1"
    if case=="rebind-routes":proxy=RebindingProxy(a.port)
    if case=="rebind-pending":proxy=RebindingProxy(a.port,65536,0)
    if case=="rebind-silent":proxy=RebindingProxy(a.port,65536,0,silent=True)
    command=[str(a.client.resolve()),str(ca.path("root","der")),host,str(proxy.port if proxy else a.port),str(clientlog),str(downloads),testcase,*names]
    c=artifacts.run(command,capture_output=True,text=True,timeout=180,case=case)
   finally:
    try:
     if proxy is not None:
      proxy.close()
      if sys.exc_info()[0] is not None:print("QNS rebinding progress "+json.dumps(proxy.progress()),file=sys.stderr,flush=True)
    finally:serverout,servererr=server.stop(primary=sys.exc_info()[1])
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
   preferred_tuple_ok=True;preferred_tuples=[]
   if case in ("preferred","preferred-ipv6"):
    # This comes from the authenticated peer transport-parameter decoder,
    # independently of the server fixture flag-to-port mapping under test.
    preferred_tuples=[line for line in c.stdout.splitlines() if line.startswith("QNS authenticated preferred address ")]
    expected_tuple=("QNS authenticated preferred address ipv4=7f000001:"+str(a.port+1)+" ipv6=00000000000000000000000000000000:0") if case=="preferred" else ("QNS authenticated preferred address ipv4=00000000:0 ipv6=00000000000000000000000000000001:"+str(a.port+1))
    preferred_tuple_ok=preferred_tuples==[expected_tuple]
   semantic=0
   if case=="multiplex1999" and (c.returncode or not files_ok):semantic=42
   elif case=="multiconnect50" and (c.returncode or not files_ok or labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET")!=50):semantic=52
   elif case=="keyupdate" and (c.returncode or not files_ok or "CLIENT_TRAFFIC_SECRET_1" not in labels or "SERVER_TRAFFIC_SECRET_1" not in serverlabels or not reciprocal):semantic=62
   elif case=="chacha20" and (c.returncode or not files_ok):semantic=82
   elif case=="ipv6" and (c.returncode or not files_ok):semantic=72
   elif case in ("preferred","preferred-ipv6") and (c.returncode or not files_ok or not preferred_tuple_ok or "QNS preferred path validated" not in c.stdout):semantic=92
   elif case in ("resumption40","zerortt40") and (c.returncode or not files_ok or labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET")!=2):semantic=102
   elif case in ("rebind-routes","rebind-pending") and (c.returncode or not files_ok or len(proxy.ports)<12):semantic=112
   elif case=="rebind-silent" and (c.returncode or not files_ok or len(proxy.ports)!=2 or proxy.quiet_rebounds!=1 or proxy.client_after_rebind<1):semantic=113
   expected={"multiplex1999":42,"multiconnect50":52,"keyupdate":62,"ipv6":72,"rebind-silent":113}.get(case,0) if a.expect_old_code else 0
   matched=semantic==expected
   if case=="rebind-silent" and a.expect_old_code:
    matched=matched and c.returncode==13 and len(proxy.ports)==2 and proxy.quiet_rebounds==1 and proxy.client_after_rebind==0 and proxy.forwarded>=65536
   results.append({"case":case,"client_status":c.returncode,"semantic_status":semantic,"expected":expected,"matched":matched,
      "client_stdout":c.stdout,"client_stderr":c.stderr,"server_stdout":serverout,"server_stderr":servererr,
      "files_match":files_ok,"rebound_routes":len(proxy.ports) if proxy else 0,"quiet_rebounds":proxy.quiet_rebounds if proxy else 0,"client_after_rebind":proxy.client_after_rebind if proxy else 0,"preferred_tuple_match":preferred_tuple_ok,"authenticated_preferred_tuples":preferred_tuples,"reciprocal_epoch_secrets":reciprocal,"handshakes":labels.count("CLIENT_HANDSHAKE_TRAFFIC_SECRET"),
      "client_epochs":sorted(set(x for x in labels if x.startswith("CLIENT_TRAFFIC_SECRET_"))),
      "server_epochs":sorted(set(x for x in serverlabels if x.startswith("SERVER_TRAFFIC_SECRET_")))})
  passed=all(x["matched"] and not x["client_stderr"] and not x["server_stderr"] for x in results)
  report={"binary_hashes":{n:hashlib.sha256(x.read_bytes()).hexdigest() for n,x in [("client",a.client),("server",a.server)]},"results":results}
  artifacts.publish(report,passed)
 print(json.dumps(report,indent=2))
 return 0 if passed else 1
if __name__=="__main__":raise SystemExit(main())
