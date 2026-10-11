"""Independent RFC v1 anti-amplification trace accounting.

Scope: established test captures with known server policy. Handshake AEAD proves
the RFC 9000 8.1 boundary. Earlier CID/token validation needs separately bound
policy evidence; an unknown peer policy is a coverage limitation, not a failure.
No endpoint implementation, runner dissector or tolerance is reused.
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import struct
import sys
import cryptography

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305


class CoverageError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crypto_provider():
    files={}
    for name,module in sorted(sys.modules.items()):
        path=getattr(module,"__file__",None)
        if name.startswith("cryptography") and path is not None and Path(path).is_file():
            resolved=str(Path(path).resolve())
            files[resolved]={"sha256":sha(Path(resolved).read_bytes()),"bytes":Path(resolved).stat().st_size}
    return {"version":cryptography.__version__,"python_version":sys.version.split()[0],"inputs":files}


def need(data, at, size):
    if at < 0 or size < 0 or at+size > len(data):
        raise CoverageError("truncated capture or protocol field")
    return data[at:at+size]


def options(data,endian):
    at=0
    while at<len(data):
        kind,size=struct.unpack(endian+"HH",need(data,at,4));at+=4
        if kind==0:
            if size or any(data[at:]):raise CoverageError("malformed pcapng option terminator")
            return
        value=need(data,at,size);at+=(size+3)&~3
        if at>len(data):raise CoverageError("truncated pcapng option")
        yield kind,value


def capture(data):
    """Yield exact file order; one interface prevents double capture credits."""
    if data[:4] == b"\x0a\x0d\x0d\x0a":
        at = 0
        endian = None
        interfaces = []
        section = -1
        while at < len(data):
            header = need(data,at,12)
            if header[:4] == b"\x0a\x0d\x0d\x0a":
                if header[8:12] == b"\x4d\x3c\x2b\x1a":endian = "<"
                elif header[8:12] == b"\x1a\x2b\x3c\x4d":endian = ">"
                else:raise CoverageError("invalid pcapng byte order")
                interfaces = [];section += 1
            if endian is None:raise CoverageError("pcapng packet before section")
            kind,size = struct.unpack(endian+"II",header[:8])
            if size < 12 or size % 4:raise CoverageError("invalid pcapng block length")
            block = need(data,at,size)
            if struct.unpack(endian+"I",block[-4:])[0] != size:
                raise CoverageError("pcapng block length mismatch")
            body = block[8:-4]
            if kind == 1:
                link,reserved,snaplen = struct.unpack(endian+"HHI",need(body,0,8))
                interfaces.append((link,snaplen))
            elif kind == 6:
                interface,high,low,caplen,original = struct.unpack(endian+"IIIII",need(body,0,20))
                if interface >= len(interfaces):raise CoverageError("unknown pcapng interface")
                if caplen != original:raise CoverageError("truncated pcapng packet")
                if interfaces[interface][1] and caplen>interfaces[interface][1]:
                    raise CoverageError("pcapng packet exceeds snapshot length")
                frame = need(body,20,caplen)
                for option,value in options(body[20+((caplen+3)&~3):],endian):
                    if option==4 and (len(value)!=8 or struct.unpack(endian+"Q",value)[0]):
                        raise CoverageError("capture reports dropped packets")

                yield {"offset":at,"timestamp":[high,low],"interface":interface,"section":section,
                       "linktype":interfaces[interface][0],"frame":frame}
            elif kind==5:
                interface,high,low=struct.unpack(endian+"III",need(body,0,12))
                if interface>=len(interfaces):raise CoverageError("unknown statistics interface")
                for option,value in options(body[12:],endian):
                    if option in (5,7) and (len(value)!=8 or struct.unpack(endian+"Q",value)[0]):
                        raise CoverageError("capture reports dropped packets")
            elif kind in (2,3):
                raise CoverageError("unsupported packet block cannot be omitted")
            elif kind not in (0x0a0d0d0a,4,5,10,0x00000bad,0x40000bad):
                raise CoverageError("unknown pcapng block cannot be omitted")
            at += size
    else:
        magic = data[:4]
        variants = {b"\xd4\xc3\xb2\xa1":"<",b"\xa1\xb2\xc3\xd4":">",
                    b"\x4d\x3c\xb2\xa1":"<",b"\xa1\xb2\x3c\x4d":">"}
        if magic not in variants:raise CoverageError("unsupported capture format")
        endian = variants[magic]
        major,minor,zone,sigfigs,snaplen,linktype = struct.unpack(endian+"HHiIII",need(data,4,20))
        if (major,minor)!=(2,4):raise CoverageError("unsupported pcap version")
        at = 24
        while at < len(data):
            seconds,fraction,caplen,original = struct.unpack(endian+"IIII",need(data,at,16))
            if caplen != original:raise CoverageError("truncated pcap packet")
            if snaplen and caplen>snaplen:raise CoverageError("pcap packet exceeds snapshot length")
            yield {"offset":at,"timestamp":[seconds,fraction],"interface":0,"section":0,
                   "linktype":linktype & 0xffff,"frame":need(data,at+16,caplen)}
            at += 16+caplen


def udp(frame,linktype):
    if linktype == 1:
        protocol = int.from_bytes(need(frame,12,2),"big");at=14
        while protocol in (0x8100,0x88a8):
            protocol=int.from_bytes(need(frame,at+2,2),"big");at+=4
        if protocol not in (0x800,0x86dd):return None
        frame=frame[at:]
    elif linktype == 113:
        protocol=int.from_bytes(need(frame,14,2),"big")
        if protocol not in (0x800,0x86dd):return None
        frame=frame[16:]
    elif linktype == 276:
        protocol=int.from_bytes(need(frame,0,2),"big")
        if protocol not in (0x800,0x86dd):return None
        frame=frame[20:]
    elif linktype not in (101,228,229):
        raise CoverageError("unsupported capture linktype")
    version=need(frame,0,1)[0]>>4
    if version == 4:
        header=need(frame,0,20);length=int.from_bytes(header[2:4],"big")
        at=(header[0]&15)*4
        if at<20 or length<at:raise CoverageError("invalid IPv4 length")
        frame=need(frame,0,length)
        if int.from_bytes(header[6:8],"big")&0x3fff:raise CoverageError("fragmented IPv4 is outside ledger scope")
        if header[9]!=17:return None
        src=str(ipaddress.ip_address(header[12:16]));dst=str(ipaddress.ip_address(header[16:20]))
    elif version == 6:
        header=need(frame,0,40);length=int.from_bytes(header[4:6],"big")
        if not length:raise CoverageError("IPv6 jumbogram is outside ledger scope")
        frame=need(frame,0,40+length);at=40;protocol=header[6]
        for _ in range(16):
            if protocol not in (0,43,60,51):break
            extension=need(frame,at,2);size=(extension[1]+(2 if protocol==51 else 1))*(4 if protocol==51 else 8)
            need(frame,at,size);protocol=extension[0];at+=size
        if protocol==44:raise CoverageError("fragmented IPv6 is outside ledger scope")
        if protocol!=17:return None
        src=str(ipaddress.ip_address(header[8:24]));dst=str(ipaddress.ip_address(header[24:40]))
    else:raise CoverageError("invalid captured IP version")
    header=need(frame,at,8);source,destination,size,checksum=struct.unpack("!HHHH",header)
    if size<8 or at+size!=len(frame):raise CoverageError("UDP and IP length mismatch")
    return (src,source,dst,destination),need(frame,at+8,size-8)


def varint(data,at):
    first=need(data,at,1)[0];width=1<<(first>>6)
    value=int.from_bytes(need(data,at,width),"big")&((1<<(8*width-2))-1)
    return value,at+width


def packets(data):
    at=0
    while at<len(data):
        start=at;first=need(data,at,1)[0]
        if first&0x80==0:
            yield {"type":"short","packet":data[at:],"dcid":None,"scid":None};return
        version=int.from_bytes(need(data,at+1,4),"big")
        if version!=1:raise CoverageError("non-v1 long packet is outside ledger scope")
        at+=5
        size=need(data,at,1)[0];at+=1
        if size>20:raise CoverageError("oversized destination CID")
        dcid=need(data,at,size);at+=size
        size=need(data,at,1)[0];at+=1
        if size>20:raise CoverageError("oversized source CID")
        scid=need(data,at,size);at+=size
        kind=(first>>4)&3
        if kind==3:raise CoverageError("Retry requires separately bound token policy")
        if kind==0:
            size,at=varint(data,at);need(data,at,size);at+=size
        length,at=varint(data,at);offset=at-start
        packet=need(data,start,offset+length)
        if not length:raise CoverageError("empty protected QUIC packet")
        yield {"type":("initial","zerortt","handshake")[kind],"packet":packet,
               "dcid":dcid,"scid":scid,"pn_offset":offset}
        at=start+len(packet)


def expand(secret,label,length,algorithm):
    label=b"tls13 "+label
    info=length.to_bytes(2,"big")+bytes([len(label)])+label+b"\0"
    result=b"";previous=b"";counter=1
    while len(result)<length:
        previous=hmac.new(secret,previous+info+bytes([counter]),algorithm).digest()
        result+=previous;counter+=1
    return result[:length]


def mask(key,sample,chacha):
    if len(sample)!=16:raise CoverageError("missing header protection sample")
    cipher=Cipher(algorithms.ChaCha20(key,sample),mode=None) if chacha else Cipher(algorithms.AES(key),modes.ECB())
    encryptor=cipher.encryptor()
    return (encryptor.update(bytes(5)) if chacha else encryptor.update(sample))[:5]


def decoded_frames(data):
    at=0;types=[];acks=[];closed=False
    if not data:return None
    try:
        while at<len(data):
            type_start=at;kind,at=varint(data,at);types.append(kind)
            if at-type_start!=1:return None
            if kind in (0,1):continue
            if kind in (2,3):
                largest,at=varint(data,at);delay,at=varint(data,at);ranges,at=varint(data,at);first,at=varint(data,at)
                if first>largest or ranges>len(data):return None
                low=largest-first;acks.append([low,largest])
                for _ in range(ranges):
                    gap,at=varint(data,at);width,at=varint(data,at)
                    high=low-gap-2;low=high-width
                    if low<0:return None
                    acks.append([low,high])
                if kind==3:
                    for _ in range(3):_,at=varint(data,at)
            elif kind==6:
                offset,at=varint(data,at);size,at=varint(data,at)
                if offset+size>=1<<62:return None
                need(data,at,size);at+=size
            elif kind==0x1c:
                error,at=varint(data,at);frame,at=varint(data,at);size,at=varint(data,at);need(data,at,size);at+=size;closed=True
            else:return None
    except CoverageError:return None
    return {"frame_types":types,"ack_ranges":acks,"closing":closed}


class HandshakeKeys:
    def __init__(self, logs):
        self.secrets={};self.largest={};self.processed=set()
        for data in logs:
            for line in data.decode("ascii").splitlines():
                if not line or line.startswith("#"):continue
                fields=line.split()
                if fields[0] not in ("CLIENT_HANDSHAKE_TRAFFIC_SECRET","SERVER_HANDSHAKE_TRAFFIC_SECRET"):continue
                direction="client" if fields[0].startswith("CLIENT") else "server"
                if len(fields)!=3:raise CoverageError("malformed handshake keylog")
                random,secret=bytes.fromhex(fields[1]),bytes.fromhex(fields[2])
                if len(random)!=32 or len(secret) not in (32,48):raise CoverageError("unsupported handshake keylog")
                identity=(direction,sha(random))
                if identity in self.secrets and self.secrets[identity]!=secret:
                    raise CoverageError("conflicting handshake keylog")
                self.secrets[identity]=secret
        if not any(direction=="client" for direction,_ in self.secrets):raise CoverageError("client Handshake secrets absent")

    def authenticate(self, entry, connection, direction="client"):
        packet=entry["packet"];offset=entry["pn_offset"]
        for (secret_direction,identity),secret in self.secrets.items():
            if secret_direction!=direction:continue
            suites=(("AES128",16,hashlib.sha256,False),("CHACHA20",32,hashlib.sha256,True)) if len(secret)==32 else (("AES256",32,hashlib.sha384,False),)
            for suite,size,algorithm,chacha in suites:
                hp=expand(secret,b"quic hp",size,algorithm)
                if offset+20>len(packet):continue
                hp_mask=mask(hp,packet[offset+4:offset+20],chacha)
                first=packet[0]^(hp_mask[0]&15);width=(first&3)+1
                if first&0x0c or first&0xc0!=0xc0 or (first>>4)&3!=2:continue
                pn=bytes(packet[offset+i]^hp_mask[i+1] for i in range(width))
                truncated=int.from_bytes(pn,"big");largest=self.largest.get((connection,direction,identity),-1)
                expected=largest+1;window=1<<(8*width);half=window//2
                number=(expected&~(window-1))|truncated
                if number<=expected-half and number+window<1<<62:number+=window
                elif number>expected+half and number>=window:number-=window
                aad=bytes([first])+packet[1:offset]+pn
                key=expand(secret,b"quic key",size,algorithm);iv=expand(secret,b"quic iv",12,algorithm)
                nonce=(int.from_bytes(iv,"big")^number).to_bytes(12,"big")
                try:
                    plaintext=(ChaCha20Poly1305(key) if chacha else AESGCM(key)).decrypt(nonce,packet[offset+width:],aad)
                except InvalidTag:continue
                frames=decoded_frames(plaintext)
                if frames is None:continue
                self.largest[(connection,direction,identity)]=max(largest,number)
                processed=(connection,direction,identity,number)
                duplicate=processed in self.processed;self.processed.add(processed)
                return {"key_identifier":identity,"suite":suite,"packet_number":number,"duplicate":duplicate,**frames}
        return None


class Attribution:
    def __init__(self):
        self.client={};self.server={};self.connections={}
    def bind(self,registry,cid,connection):
        if not cid:raise CoverageError("zero-length CID attribution is outside ledger scope")
        if cid in registry and registry[cid]!=connection:raise CoverageError("CID belongs to another connection")
        registry[cid]=connection
    def packet(self,entry,direction):
        if entry["type"]=="short":
            registry=self.server if direction=="client" else self.client
            matches={value for cid,value in registry.items() if entry["packet"][1:].startswith(cid)}
            if len(matches)!=1:raise CoverageError("unknown or ambiguous short-header attribution")
            return next(iter(matches))
        dcid,scid=entry["dcid"],entry["scid"]
        if direction=="client":
            connection=self.client.get(scid)
            if connection is None:
                if entry["type"]!="initial":raise CoverageError("unknown client connection")
                connection=sha(dcid+b"\0"+scid)
                self.connections[connection]={"original_dcid":dcid,"client_scid":scid,"key_identifier":None}
                self.bind(self.client,scid,connection)
            bound=self.server.get(dcid)
            if bound is not None and bound!=connection:raise CoverageError("cross-connection client CID")
            if bound is None and dcid!=self.connections[connection]["original_dcid"]:
                raise CoverageError("client uses an unknown server CID")
        else:
            connection=self.client.get(dcid)
            if connection is None:raise CoverageError("unknown server connection")
            self.bind(self.server,scid,connection)
        return connection


class Ledger:
    def __init__(self,policy):
        if policy not in ("handshake-only","peer-unknown"):raise ValueError("explicit validation policy required")
        self.policy=policy;self.routes={};self.rows=[];self.violations=[]
    def record(self,connection,route,direction,size,authentication=None,**capture_fields):
        key=(connection,tuple(route))
        state=self.routes.setdefault(key,{"received":0,"sent":0,"validated":False,"boundary":None})
        before=state["validated"]
        if direction=="client":
            state["received"]+=size
            if authentication is not None:
                state["validated"]=True;state["boundary"]=len(self.rows)
        else:
            state["sent"]+=size
            if not before and state["sent"]>3*state["received"]:
                self.violations.append(len(self.rows))
        row={"order":len(self.rows),"connection":connection,"tuple":list(route),"direction":direction,
             "udp_payload_bytes":size,"received":state["received"],"sent":state["sent"],
             "budget":3*state["received"],"validated_before":before,"validated_after":state["validated"],
             "authentication":authentication,**capture_fields}
        self.rows.append(row)
    def result(self):
        boundaries=[state["boundary"] for state in self.routes.values() if state["boundary"] is not None]
        status="failed" if self.violations and self.policy=="handshake-only" else "coverage-limited" if self.violations or not boundaries else "passed"
        return {"schema_version":1,"scope":"RFC v1 connection establishment, explicit validation policy",
                "policy":self.policy,"status":status,"violations":self.violations,"authenticated_boundaries":boundaries,
                "connection_count":len({key[0] for key in self.routes}),"rows":self.rows,
                "limitation":"Unknown peer CID/token validation policy cannot be inferred from PCAP." if self.policy=="peer-unknown" else None}


def analyze(capture_bytes,keylogs,server_addresses,port=443,policy="peer-unknown",expected_connections=1):
    server_addresses={str(ipaddress.ip_address(address)) for address in server_addresses}
    keys=HandshakeKeys(keylogs);attribution=Attribution();ledger=Ledger(policy)
    interface=None;duplicates=set();issued_handshake={};closing_connections=set();uncertain_handshake=set();limitations=[]
    for index,record in enumerate(capture(capture_bytes)):
        parsed=udp(record["frame"],record["linktype"])
        if parsed is None:continue
        endpoint,payload=parsed
        src,source,dst,destination=endpoint
        if src in server_addresses and source==port:direction="server";route=(dst,destination,src,source)
        elif dst in server_addresses and destination==port:direction="client";route=(src,source,dst,destination)
        else:continue
        if interface is not None and (record["section"],record["interface"])!=interface:
            raise CoverageError("multiple capture interfaces can duplicate UDP credits")
        interface=(record["section"],record["interface"])
        duplicate=(interface,tuple(record["timestamp"]),sha(record["frame"]))
        if duplicate in duplicates:raise CoverageError("ambiguous exact capture duplicate")
        duplicates.add(duplicate)
        entries=list(packets(payload))
        connections={attribution.packet(entry,direction) for entry in entries}
        if len(connections)!=1:raise CoverageError("coalesced datagram attribution is ambiguous")
        connection=next(iter(connections));authentication=None
        rejected = []
        for entry in entries:
            if entry["type"]!="handshake":continue
            found=keys.authenticate(entry,connection,direction)
            if found is None:
                if direction=="server":uncertain_handshake.add(connection)
                continue
            bound=attribution.connections[connection]["key_identifier"]
            if bound is not None and bound!=found["key_identifier"]:
                raise CoverageError("connection changed handshake secret identity")
            attribution.connections[connection]["key_identifier"]=found["key_identifier"]
            if direction=="server":
                issued_handshake.setdefault(connection,set()).add(found["packet_number"])
                if found["closing"]:closing_connections.add(connection)
            else:
                known=issued_handshake.get(connection,set())
                if found["ack_ranges"] and (("server",found["key_identifier"]) not in keys.secrets or connection in uncertain_handshake):
                    limitations.append("server-handshake-ack-ownership-unproved")
                owns_ack=all(high-low+1<=len(known) and all(number in known for number in range(low,high+1)) for low,high in found["ack_ranges"])
                if found["duplicate"]:
                    rejected.append("already-processed-handshake-packet")
                elif found["closing"] or connection in closing_connections:
                    rejected.append("authenticated-closing-packet")
                elif not owns_ack:
                    rejected.append("unknown-handshake-ack-ownership")
                else:
                    authentication=found
        ledger.record(connection,route,direction,len(payload),authentication,
                      capture_index=index,file_offset=record["offset"],timestamp=record["timestamp"],
                      interface=record["interface"],section=record["section"],udp_payload_sha256=sha(payload),frame_sha256=sha(record["frame"]),
                      packet_types=[entry["type"] for entry in entries],boundary_rejections=rejected)
    if not ledger.rows:raise CoverageError("no selected server UDP datagrams")
    result=ledger.result()
    result["coverage_limitations"]=sorted(set(limitations))
    if limitations:result["status"]="coverage-limited"
    if result["connection_count"]!=expected_connections:raise CoverageError("unexpected number of attributed connections")
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture",required=True,type=Path)
    parser.add_argument("--capture-origin",required=True,choices=("synthetic-control","official-server-trace"))
    parser.add_argument("--keylog",required=True,action="append",type=Path)
    parser.add_argument("--server-address",required=True,action="append")
    parser.add_argument("--server-port",type=int,default=443)
    parser.add_argument("--policy",required=True,choices=("handshake-only","peer-unknown"))
    parser.add_argument("--policy-source",type=Path)
    parser.add_argument("--policy-binary",type=Path)
    parser.add_argument("--artifacts",required=True,type=Path)
    args=parser.parse_args()
    if not args.artifacts.is_absolute() or args.artifacts.exists():
        raise ValueError("--artifacts requires a fresh absolute path")
    if args.policy=="handshake-only" and (args.policy_source is None or args.policy_binary is None):
        raise ValueError("handshake-only requires exact source and binary policy inputs")
    args.artifacts.mkdir(parents=True)
    inputs=[Path(__file__),args.capture,*args.keylog]+[p for p in (args.policy_source,args.policy_binary) if p is not None]
    bindings={};snapshots={}
    for index,path in enumerate(inputs):
        data=path.read_bytes();retained=args.artifacts/("input-"+str(index).zfill(3)+".bin")
        retained.write_bytes(data);snapshots[path]=data
        bindings[str(path.resolve())]={"sha256":sha(data),"bytes":len(data),
                                      "retained_path":retained.relative_to(args.artifacts).as_posix()}
    try:
        report=analyze(snapshots[args.capture],[snapshots[path] for path in args.keylog],
                       args.server_address,args.server_port,args.policy)
    except (CoverageError,ValueError) as error:
        report={"schema_version":1,"status":"coverage-limited","exception":type(error).__name__,"reason":str(error)}
    report["inputs"]=bindings
    report["crypto_provider"]=crypto_provider()
    report["policy_bindings"]={role:str(path.resolve()) for role,path in (("source",args.policy_source),("binary",args.policy_binary)) if path is not None}
    report["capture_origin"]=args.capture_origin
    report["server_addresses"]=args.server_address;report["server_port"]=args.server_port
    (args.artifacts/"ledger.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},indent=2))
    return 0 if report["status"]=="passed" else 1 if report["status"]=="failed" else 2
if __name__=="__main__":raise SystemExit(main())
