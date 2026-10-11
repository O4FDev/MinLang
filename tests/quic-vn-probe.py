#!/usr/bin/env python3
"""Reserved-version server probe independent of the disabled runner case."""
import argparse,hashlib,importlib.util,json,os,socket,sys
from quic_protocol_artifacts import ProtocolArtifacts
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument("--server",type=Path,required=True);p.add_argument("--port",type=int,default=44300);p.add_argument("--artifacts",type=Path);a=p.parse_args()
 spec=importlib.util.spec_from_file_location("vn_certificates",ROOT/"tests/tls-local.py");f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
 with ProtocolArtifacts("minyar-vn",a.artifacts,inputs=[Path(__file__),a.server,ROOT/"tests/tls-local.py",ROOT/"tests/quic_protocol_artifacts.py",ROOT/"tests/test_evidence.py",ROOT/"tests/interop/qns/server.min",ROOT/"tests/interop/qns/endpoint.py"],declared_cases=["reserved-version"]) as artifacts:
  artifacts.fixture(f)
  d=artifacts.workspace;ca=f.Certificates(d);ca.root("root");ca.leaf("server","root");www=d/"www";www.mkdir()
  artifacts.certificates_ready()
  artifacts.bind_files("reserved-version","packets",[d/"request.bin",d/"response.bin"]);artifacts.bind_files("reserved-version","keylogs",[d/"keys"])
  command=[str(a.server.resolve()),str(ca.path("server","pk8")),str(ca.path("root","der")),str(d/"keys"),str(www),"transfer",str(ca.path("server","der")),"--port="+str(a.port)]
  server=artifacts.endpoint(command,"vn-server",case="reserved-version",peer_timeout=3)
  try:
   line=server.ready_line()
   if line!="QNS server ready\n":
    raise RuntimeError(("server setup",line))
   source=os.urandom(8);destination=os.urandom(8);reserved=0x0a0a0a0a
   header=b"\xc0"+reserved.to_bytes(4,"big")+bytes([8])+destination+bytes([8])+source
   packet=header+bytes(1200-len(header));(d/"request.bin").write_bytes(packet)
   with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as client:
    client.settimeout(3);client.sendto(packet,("127.0.0.1",a.port));response,address=client.recvfrom(65535)
   (d/"response.bin").write_bytes(response)
   if len(response)<27 or response[0]&128==0 or response[1:5]!=bytes(4):raise AssertionError("not a Version Negotiation packet")
   at=5;dl=response[at];at+=1;dcid=response[at:at+dl];at+=dl;sl=response[at];at+=1;scid=response[at:at+sl];at+=sl
   if (len(response)-at)%4:raise AssertionError("malformed version list")
   versions=[int.from_bytes(response[x:x+4],"big") for x in range(at,len(response),4)]
   if dcid!=source or scid!=destination or 1 not in versions or reserved in versions:raise AssertionError("VN bindings or v1 policy failed")
   if len(response)>3*len(packet):raise AssertionError("strict3x unvalidated response budget exceeded")
   report={"request_path":"fixtures/request.bin","response_path":"fixtures/response.bin","reserved_version":hex(reserved),"versions":versions,"request_bytes":len(packet),"response_bytes":len(response),"request_sha256":hashlib.sha256(packet).hexdigest(),"response_sha256":hashlib.sha256(response).hexdigest(),"server_sha256":hashlib.sha256(a.server.read_bytes()).hexdigest(),"result":"passed","official_case_disabled":True}
  finally:
   out,err=server.stop(primary=sys.exc_info()[1])
   if err and sys.exc_info()[1] is None:raise AssertionError(err)
  artifacts.publish(report,True)
 print(json.dumps(report))
if __name__=="__main__":main()
