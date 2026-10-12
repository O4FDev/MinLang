"""Independent RFC v1 anti-amplification trace accounting.

Scope: established test captures with known server policy. Handshake AEAD proves
the RFC 9000 8.1 boundary. Earlier CID/token validation needs separately bound
policy evidence; an unknown peer policy is a coverage limitation, not a failure.
No endpoint implementation, runner dissector or tolerance is reused.
"""
import argparse
from fractions import Fraction
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import struct
import sys
CRYPTO_IMPORT_ERROR=None
try:
    import cryptography
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
except ImportError as error:
    CRYPTO_IMPORT_ERROR=error


class CoverageError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crypto_provider():
    if CRYPTO_IMPORT_ERROR is not None:raise CRYPTO_IMPORT_ERROR
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
                denominator=1000000;time_offset=0;seen=set()
                for option,value in options(body[8:],endian):
                    if option in (9,14):
                        if option in seen:raise CoverageError("duplicate pcapng timestamp option")
                        seen.add(option)
                    if option==9:
                        if len(value)!=1:raise CoverageError("invalid pcapng timestamp resolution")
                        denominator=(1<<(value[0]&127)) if value[0]&128 else 10**value[0]
                    elif option==14:
                        if len(value)!=8:raise CoverageError("invalid pcapng timestamp offset")
                        time_offset=struct.unpack(endian+"q",value)[0]
                interfaces.append((link,snaplen,denominator,time_offset))
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

                denominator,time_offset=interfaces[interface][2:]
                exact=Fraction((high<<32)|low,denominator)+time_offset
                yield {"offset":at,"timestamp":[high,low],"timestamp_exact":[exact.numerator,exact.denominator],
                       "timestamp_resolution":[1,denominator],"timestamp_offset_seconds":time_offset,"interface":interface,"section":section,
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
        denominator=1000000000 if magic in (b"\x4d\x3c\xb2\xa1",b"\xa1\xb2\x3c\x4d") else 1000000
        major,minor,zone,sigfigs,snaplen,linktype = struct.unpack(endian+"HHiIII",need(data,4,20))
        if (major,minor)!=(2,4):raise CoverageError("unsupported pcap version")
        at = 24
        while at < len(data):
            seconds,fraction,caplen,original = struct.unpack(endian+"IIII",need(data,at,16))
            if caplen != original:raise CoverageError("truncated pcap packet")
            if snaplen and caplen>snaplen:raise CoverageError("pcap packet exceeds snapshot length")
            if fraction>=denominator:raise CoverageError("invalid pcap subsecond timestamp")
            exact=Fraction(seconds*denominator+fraction,denominator)
            yield {"offset":at,"timestamp":[seconds,fraction],"timestamp_exact":[exact.numerator,exact.denominator],
                   "timestamp_resolution":[1,denominator],"timestamp_offset_seconds":0,"interface":0,"section":0,
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
        kind=(first>>4)&3;token_length=0;token_sha256=None
        if kind==3:raise CoverageError("Retry requires separately bound token policy")
        if kind==0:
            size,at=varint(data,at);token=need(data,at,size);at+=size
            token_length=size;token_sha256=sha(token)
        length,at=varint(data,at);offset=at-start
        packet=need(data,start,offset+length)
        if not length:raise CoverageError("empty protected QUIC packet")
        yield {"type":("initial","zerortt","handshake")[kind],"packet":packet,
               "dcid":dcid,"scid":scid,"pn_offset":offset,"token_length":token_length,"token_sha256":token_sha256}
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
        return {"schema_version":1,"scope":"synthetic accounting or separately checked endpoint-policy receipt; no official claim from direct analyze()",
                "policy":self.policy,"status":status,"violations":self.violations,"authenticated_boundaries":boundaries,
                "connection_count":len({key[0] for key in self.routes}),"rows":self.rows,
                "limitation":"Unknown peer CID/token validation policy cannot be inferred from PCAP." if self.policy=="peer-unknown" else None}


def analyze(capture_bytes,keylogs,server_addresses,port=443,policy="peer-unknown",expected_connections=1):
    server_addresses={str(ipaddress.ip_address(address)) for address in server_addresses}
    keys=HandshakeKeys(keylogs);attribution=Attribution();ledger=Ledger(policy)
    interface=None;duplicates=set();issued_handshake={};closing_connections=set();uncertain_handshake=set();limitations=[];last_time=None;route_times={}
    for index,record in enumerate(capture(capture_bytes)):
        exact_time=Fraction(*record["timestamp_exact"])
        if last_time is not None and exact_time<last_time:raise CoverageError("capture timestamps decrease in file order")
        last_time=exact_time
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
        if any(entry.get("token_length",0) for entry in entries):raise CoverageError("Initial token validation policy is unproved")
        connections={attribution.packet(entry,direction) for entry in entries}
        if len(connections)!=1:raise CoverageError("coalesced datagram attribution is ambiguous")
        connection=next(iter(connections));authentication=None
        previous=route_times.get((connection,tuple(route)))
        if previous is not None and previous[0]==exact_time and previous[1]!=direction:
            raise CoverageError("opposite-direction UDP ordering is ambiguous at declared timestamp resolution")
        route_times[(connection,tuple(route))]=(exact_time,direction)
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
                      timestamp_exact=record["timestamp_exact"],timestamp_resolution=record["timestamp_resolution"],timestamp_offset_seconds=record["timestamp_offset_seconds"],
                      interface=record["interface"],section=record["section"],udp_payload_sha256=sha(payload),frame_sha256=sha(record["frame"]),
                      packet_types=[entry["type"] for entry in entries],boundary_rejections=rejected)
    if not ledger.rows:raise CoverageError("no selected server UDP datagrams")
    result=ledger.result()
    result["coverage_limitations"]=sorted(set(limitations))
    if limitations:result["status"]="coverage-limited"
    if result["connection_count"]!=expected_connections:raise CoverageError("unexpected number of attributed connections")
    return result



class InputRetention:
    """Copy each actual input and independently verify original/copy/original."""
    def __init__(self,root):
        self.root=root;self.inputs={};self.snapshots={}
    def capture(self,path):
        path=Path(path).resolve();key=str(path)
        if key in self.snapshots:return self.snapshots[key]
        data=path.read_bytes();before={"sha256":sha(data),"bytes":len(data)}
        retained=self.root/("input-"+str(len(self.inputs)).zfill(3)+".bin")
        entry={"sha256":before["sha256"],"bytes":before["bytes"],"original_before":before,
               "retained_path":retained.relative_to(self.root).as_posix(),"copied_exact":False}
        self.inputs[key]=entry
        retained.write_bytes(data)
        copy=retained.read_bytes();after=path.read_bytes()
        entry["retained"]={"sha256":sha(copy),"bytes":len(copy)}
        entry["original_after"]={"sha256":sha(after),"bytes":len(after)}
        entry["copied_exact"]=before==entry["retained"]==entry["original_after"]
        if not entry["copied_exact"]:raise CoverageError("input changed during retention: "+key)
        self.snapshots[key]=data
        return data
    def expected(self,binding):
        if not isinstance(binding,dict) or not isinstance(binding.get("path"),str) or type(binding.get("bytes")) is not int:
            raise CoverageError("invalid evidence input binding")
        path=Path(binding["path"])
        if not path.is_absolute():raise CoverageError("evidence input path must be absolute")
        data=self.capture(path)
        if sha(data)!=binding.get("sha256") or len(data)!=binding["bytes"]:
            raise CoverageError("evidence input bytes mismatch")
        return data
    def recheck(self):
        errors=[]
        for key,entry in self.inputs.items():
            try:
                original=Path(key).read_bytes();retained=(self.root/entry["retained_path"]).read_bytes()
                entry["original_after"]={"sha256":sha(original),"bytes":len(original)}
                entry["retained"]={"sha256":sha(retained),"bytes":len(retained)}
                entry["copied_exact"]=entry["original_before"]==entry["original_after"]==entry["retained"]
                if not entry["copied_exact"]:raise CoverageError("input changed before finalization: "+key)
            except BaseException as error:errors.append(error)
        return errors


REVIEWED_POLICY_SOURCES={
    "quic":"295dbe88c1066312b3748373cf6205af8a7a71d0019a3aa5b03c3be149f49fe4",
    "server":"5058595f3bc9c0e5ac7d330c6b85b39167cd7e619d714a2f9e437b2130fdeb44",
    "adapter":"8dd22250a1720ffd7f4120cd3204057ea19d692fdd8d799a0977b60483a417da",
}
POLICY_CONTRACT={
    "name":"minyar-handshake-only-v1","role":"server","testcase":"transfer",
    "early_cid_validation":False,"retry_validation":False,"token_validation":False,
}



def checked_link_graph(build,root,retention):
    """Validate native Linux schema2 bytes and complete actual link arguments."""
    if build.get("schema")!=2 or type(build.get("schema")) is not int or build.get("mode")!="native" or build.get("optimization")!="2":
        raise CoverageError("reviewed native O2 schema2 build required")
    if build.get("link_attempted") is not True or type(build.get("link_status")) is not int or build["link_status"]!=0 or type(build.get("link_subprocess_status")) is not int or build["link_subprocess_status"]!=0 or build.get("retention_errors")!=[]:
        raise CoverageError("successful retained link required")
    if build.get("link_flags")!=["-O2","-Wno-override-module"] or build.get("lto_flags")!=[] or build.get("address_sanitizer_enabled") is not False:
        raise CoverageError("unexpected native link flags")
    def retained(value,epochs=True):
        name=value.get("retained")
        if not isinstance(name,str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
            raise CoverageError("invalid retained build path")
        data=retention.capture(root/name);digest=sha(data)
        fields=("sha256","source_before_sha256","retained_sha256","source_after_sha256","pre_link_sha256","post_link_sha256") if epochs else ("sha256",)
        if type(value.get("bytes")) is not int or value["bytes"]!=len(data) or any(value.get(field)!=digest for field in fields):
            raise CoverageError("build input bytes or before/copy/after binding mismatch")
        return data
    program=build.get("program_input",{});raw=build.get("raw_program_input",{})
    if program.get("role")!="program" or program.get("format")!="llvm":
        raise CoverageError("one generated LLVM program required")
    raw_data=retained(raw);program_data=retained(program)
    if raw_data!=program_data or sha(raw_data)!=build.get("raw_sha256") or sha(program_data)!=build.get("linked_program_sha256"):
        raise CoverageError("native program LLVM identity mismatch")
    inputs=build.get("inputs")
    if not isinstance(inputs,list) or len(inputs)!=7 or [item.get("role") for item in inputs]!=["runtime"]+["provider"]*6:
        raise CoverageError("one runtime and six represented provider objects required")
    originals=[program.get("original")]+[item.get("original") for item in inputs]
    if any(not isinstance(path,str) or not Path(path).is_absolute() for path in originals) or len(set(originals))!=len(originals):
        raise CoverageError("ambiguous original build inputs")
    for item in inputs:
        if item.get("format")!="native_object":raise CoverageError("native runtime/provider object required")
        retained(item)
    # Preserve the reviewed legacy tool, the files/system dispatch integration and
    # the consolidated system/sha256/tararchive/zstd/deflate provider dispatch.
    pinned={"clang-driver.py":("c30f69207d809558af9affe4d2a354e759b49b5c6fd74b9c5884a7529baad6af",
                               "52943b71b8b41b85da5cdc78b9a1388699cb4b40d4e86e1bd179714fa48febd6",
                               "499d439fcb709dad8f1544506491680e48ddef198aa7a7cfbdfdeace65c92e70",
                               "405d334aa09291e429ac5f787447d1dbbd9ae7802b93a1f7df539144c37d7a69"),
            "sanitizer_llvm.py":("4d74874d1119abb31d68af4a733f9e3e90aa7788f2a767678672226592f2c3a2",)}
    tools=build.get("tool_bindings",{})
    if set(tools)!={"clang-driver.py","sanitizer_llvm.py","clang.bin"}:raise CoverageError("complete retained compiler/tool bindings required")
    for name,value in tools.items():
        data=retained(value,False);digest=sha(data)
        if any(value.get(field)!=digest for field in ("source_before_sha256","retained_sha256","source_after_sha256")) or build.get("tools",{}).get(name)!=digest:
            raise CoverageError("tool before/copy/after bytes mismatch")
        if name in pinned and digest not in pinned[name]:raise CoverageError("unreviewed canonical link tool")
    compiler=build.get("compiler_pre_link",{})
    if compiler.get("selected_command")!=build.get("compiler_selected_command") or compiler.get("resolved_path")!=tools["clang.bin"].get("original") or compiler.get("sha256")!=tools["clang.bin"].get("sha256"):
        raise CoverageError("actual compiler command or bytes not bound")
    if Path(compiler.get("selected_command","")).resolve()!=Path(compiler.get("resolved_path","")).resolve():
        raise CoverageError("selected compiler resolves to different bytes")
    staged=build.get("staged_output",{});final=build.get("final_output",{})
    if not all(isinstance(item.get("path"),str) and Path(item["path"]).is_absolute() for item in (staged,final)):
        raise CoverageError("staged/final build output paths required")
    final_path=Path(final["path"]);staged_path=Path(staged["path"])
    if staged_path.name!=final_path.name or staged_path.parent.parent!=final_path.parent or not staged_path.parent.name.startswith(".minyar-link-") or staged_path==final_path:
        raise CoverageError("unexpected staged output location")
    object_paths=[item["original"] for item in inputs]
    expected=[compiler["selected_command"],*build["link_flags"],program["original"],*object_paths[:3],"-lcrypto",*object_paths[3:],"-lcrypto","-lm"]
    if build.get("command")!=expected or build.get("actual_command")!=expected+["-o",staged["path"]] or build.get("staged_requested_path")!=staged["path"]:
        raise CoverageError("complete actual linker argv or staging mismatch")
    final_data=retained(final,False);staged_data=retained(staged,False)
    if final_data!=staged_data or build.get("binary_sha256")!=sha(final_data):
        raise CoverageError("staged/final output bytes differ")
    return {"status":"checked-byte-graph","binary_sha256":sha(final_data),"bytes":len(final_data)}


def checked_frontend_graph(record,sources,raw,retention):
    """Check canonical source/output argv and retained generated output bytes."""
    if type(record.get("status")) is not int or record["status"]!=0 or record.get("timed_out") is not False or type(record.get("timeout_seconds")) is not int or record["timeout_seconds"]!=120:
        raise CoverageError("exact successful bounded frontend status required")
    server=Path(sources["server"]["path"]);quic=Path(sources["quic"]["path"])
    if server.parts[-4:]!=("tests","interop","qns","server.min") or quic.parts[-2:]!=("library","quic.min") or server.parents[3]!=quic.parents[1]:
        raise CoverageError("reviewed source/library layout required")
    compiler=record.get("compiler",{});output=record.get("output",{})
    expected=[compiler.get("path"),str(server),raw.get("original"),"--bounded-owners","32","--library",str(quic.parent)]
    if record.get("argv")!=expected or output.get("path")!=raw.get("original"):
        raise CoverageError("canonical frontend argv/output mismatch")
    data=retention.expected(output)
    if sha(data)!=raw.get("sha256") or type(raw.get("bytes")) is not int or len(data)!=raw["bytes"]:
        raise CoverageError("frontend generated output is not actual raw program LLVM")
    for stream in ("stdout","stderr"):retention.expected(record.get(stream,{}))
    return {"status":"checked-frontend-graph","raw_sha256":sha(data)}


def checked_endpoint_mode(endpoint,run,args):
    """Bind executable mode and selected server tuple to actual inspect fields."""
    configuration=endpoint.get("Config",{})
    if endpoint.get("Path")!="python3" or endpoint.get("Args")!=["/opt/minyar/endpoint.py"] or configuration.get("Entrypoint")!=["python3","/opt/minyar/endpoint.py"] or configuration.get("Cmd") not in (None,[]):
        raise CoverageError("captured endpoint executable command mismatch")
    project=run.get("project")
    networks=endpoint.get("NetworkSettings",{}).get("Networks",{})
    if set(networks)!={project+"_rightnet"}:raise CoverageError("captured server network membership mismatch")
    network=networks[project+"_rightnet"]
    actual=[str(ipaddress.ip_address(network[field])) for field in ("IPAddress","GlobalIPv6Address") if network.get(field)]
    if not actual or run.get("server_addresses")!=actual or args.server_address!=actual or type(run.get("server_port")) is not int or run["server_port"]!=443 or type(args.server_port) is not int or args.server_port!=443:
        raise CoverageError("captured endpoint tuple mismatch")
    return {"status":"checked-endpoint-command-and-tuple","addresses":actual,"port":443}

def checked_policy_receipt(args,retention):
    """Check the graph; policy-file existence alone supplies no policy authority."""
    if args.policy_receipt is None:raise CoverageError("checked source/build/run/captured-endpoint policy receipt absent")
    receipt=json.loads(retention.capture(args.policy_receipt))
    if type(receipt.get("schema_version")) is not int or receipt["schema_version"]!=1 or receipt.get("policy")!=POLICY_CONTRACT or any(type(receipt.get("policy",{}).get(key)) is not type(value) for key,value in POLICY_CONTRACT.items()):
        raise CoverageError("unreviewed endpoint validation policy")
    if receipt.get("capture_origin")!=args.capture_origin:
        raise CoverageError("policy receipt capture origin mismatch")
    if receipt.get("evidence_kind")!="owned-official-run":
        raise CoverageError("mocked or unknown run receipt cannot prove official endpoint policy")
    sources=receipt.get("sources",{})
    for role,digest in REVIEWED_POLICY_SOURCES.items():
        if role not in sources or sha(retention.expected(sources[role]))!=digest:
            raise CoverageError("endpoint policy source lacks exact review binding")
    if Path(sources["quic"]["path"]).resolve()!=args.policy_source.resolve():
        raise CoverageError("policy source path mismatch")
    binary=retention.capture(args.policy_binary)
    binary_binding=receipt.get("binary",{})
    if Path(binary_binding.get("path","")).resolve()!=args.policy_binary.resolve() or retention.expected(binary_binding)!=binary:
        raise CoverageError("policy binary bytes mismatch")
    build=json.loads(retention.expected(receipt["build_receipt"]))
    if build.get("schema")!=2 or type(build.get("link_status")) is not int or build["link_status"]!=0 or build.get("retention_errors")!=[]:
        raise CoverageError("successful checked schema2 build receipt absent")
    checked_link_graph(build,Path(receipt["build_receipt"]["path"]).parent,retention)
    final=build.get("final_output",{})
    if final.get("sha256")!=sha(binary) or final.get("bytes")!=len(binary):
        raise CoverageError("source build output is not captured server binary")
    retained_final=Path(receipt["build_receipt"]["path"]).parent/final.get("retained","")
    if retention.capture(retained_final)!=binary:raise CoverageError("retained link output differs")
    snapshot=json.loads(retention.expected(receipt["source_build_receipt"]))
    if snapshot.get("sources")!=sources or snapshot.get("server_binary_sha256")!=sha(binary):
        raise CoverageError("source snapshot is not bound to server build")
    compile_record=snapshot.get("compiler_invocation",{})
    compiler=retention.expected(compile_record.get("compiler",{}))
    if sha(compiler)!="df167d371354ccd151801156d803b15d77ade81e973a29f22cd5b39c9c732a7d" or type(compile_record.get("status")) is not int or compile_record["status"]!=0:
        raise CoverageError("reviewed successful Minyar compiler invocation absent")
    checked_frontend_graph(compile_record,sources,build["raw_program_input"],retention)
    if snapshot.get("raw_program_sha256")!=build["raw_program_input"]["sha256"] or snapshot["raw_program_sha256"]!=build.get("raw_sha256"):
        raise CoverageError("server source is not bound to actual program LLVM")
    for field in ("raw_program_input","program_input"):
        value=build.get(field,{})
        data=retention.capture(Path(receipt["build_receipt"]["path"]).parent/value.get("retained",""))
        if any(value.get(name)!=sha(data) for name in ("sha256","source_before_sha256","retained_sha256","source_after_sha256","pre_link_sha256","post_link_sha256")) or value.get("bytes")!=len(data):
            raise CoverageError("actual generated program input not checked")
    run=json.loads(retention.expected(receipt["run_receipt"]))
    inspect=json.loads(retention.expected(run["endpoint_inspect"]))
    if not isinstance(inspect,list) or len(inspect)!=1:raise CoverageError("exact single captured endpoint inspect absent")
    endpoint=inspect[0];container=run.get("container_id")
    labels=endpoint.get("Config",{}).get("Labels",{})
    import re
    if not isinstance(container,str) or re.fullmatch(r"[0-9a-f]{64}",container) is None or not isinstance(run.get("image_id"),str) or re.fullmatch(r"sha256:[0-9a-f]{64}",run["image_id"]) is None or endpoint.get("Id")!=container or endpoint.get("Image")!=run["image_id"]:
        raise CoverageError("actual endpoint/image identity mismatch")
    project=run.get("project");nonce=run.get("ownership_nonce")
    if not isinstance(project,str) or re.fullmatch(r"minyar-qns-[0-9a-f]{24}",project) is None or not isinstance(nonce,str) or re.fullmatch(r"[0-9a-f]{64}",nonce) is None or endpoint.get("Name")!="/"+project+"-server" or labels.get("io.minyar.qns.owner")!=nonce or labels.get("com.docker.compose.project")!=project or labels.get("com.docker.compose.service")!="server":
        raise CoverageError("captured endpoint ownership mismatch")
    environment={}
    for item in endpoint.get("Config",{}).get("Env",[]):
        key,separator,value=item.partition("=")
        if separator and key in ("ROLE","TESTCASE"):
            if key in environment:raise CoverageError("ambiguous endpoint mode")
            environment[key]=value
    if environment!={"ROLE":"server","TESTCASE":"transfer"}:
        raise CoverageError("captured endpoint mode mismatch")
    for role,expected in (("server",sha(binary)),("adapter",REVIEWED_POLICY_SOURCES["adapter"])):
        if sha(retention.expected(run.get("image_contents",{}).get(role,{})))!=expected:
            raise CoverageError("actual image endpoint bytes differ from build/source")
    checked_endpoint_mode(endpoint,run,args)
    capture_binding=run.get("capture",{})
    if retention.expected(capture_binding)!=retention.capture(args.capture) or Path(capture_binding["path"]).resolve()!=args.capture.resolve():
        raise CoverageError("run receipt is not bound to selected capture")
    if run.get("server_addresses")!=args.server_address or run.get("server_port")!=args.server_port:
        raise CoverageError("captured endpoint tuple mismatch")
    keylogs=run.get("keylogs",[])
    if len(keylogs)!=len(args.keylog):raise CoverageError("captured keylog bindings missing")
    for binding,path in zip(keylogs,args.keylog):
        if Path(binding["path"]).resolve()!=path.resolve() or retention.expected(binding)!=retention.capture(path):
            raise CoverageError("captured endpoint keylog bytes mismatch")
    return {"status":"checked-bound-receipt","policy":POLICY_CONTRACT,
            "receipt_sha256":sha(retention.capture(args.policy_receipt)),
            "container_id":container,"image_id":run["image_id"]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture",required=True,type=Path)
    parser.add_argument("--capture-origin",required=True,choices=("synthetic-control","official-server-trace"))
    parser.add_argument("--keylog",required=True,action="append",type=Path)
    parser.add_argument("--server-address",required=True,action="append")
    parser.add_argument("--server-port",type=int,default=443)
    parser.add_argument("--policy",required=True,choices=("handshake-only","peer-unknown"))
    parser.add_argument("--policy-source",type=Path);parser.add_argument("--policy-binary",type=Path)
    parser.add_argument("--policy-receipt",type=Path)
    parser.add_argument("--artifacts",required=True,type=Path)
    args=parser.parse_args()
    if not args.artifacts.is_absolute() or args.artifacts.exists():
        raise ValueError("--artifacts requires a fresh absolute path")
    args.artifacts.mkdir(parents=True)
    retention=InputRetention(args.artifacts)
    report={"schema_version":1,"scope":"capture evidence or synthetic control; endpoint policy requires checked receipt",
            "status":"coverage-limited","inputs":retention.inputs,"capture_origin":args.capture_origin,
            "server_addresses":args.server_address,"server_port":args.server_port,
            "primary_exception":None,"evidence_errors":[],"finalization_errors":[]}
    primary=None
    def failed(error,stage):
        nonlocal primary
        if primary is None:
            primary=error;report["primary_exception"]={"type":type(error).__name__,"message":str(error),"stage":stage}
        else:
            if hasattr(primary,"add_note"):primary.add_note(stage+": "+str(error))
        target="finalization_errors" if stage=="finalization" else "evidence_errors"
        report[target].append({"type":type(error).__name__,"message":str(error),"stage":stage})
        report["status"]="coverage-limited"
    provider_before=None
    try:
        for path in [Path(__file__),args.capture,*args.keylog]+[p for p in (args.policy_source,args.policy_binary,args.policy_receipt) if p is not None]:
            retention.capture(path)
        provider_before=crypto_provider();report["crypto_provider"]=provider_before
        for path,binding in provider_before["inputs"].items():
            retention.expected({"path":path,**binding})
        if args.policy=="handshake-only":
            if args.policy_source is None or args.policy_binary is None:raise CoverageError("exact policy source/binary binding absent")
            report["policy_evidence"]=checked_policy_receipt(args,retention)
        result=analyze(retention.capture(args.capture),[retention.capture(path) for path in args.keylog],
                       args.server_address,args.server_port,args.policy)
        report.update(result)
        report["scope"]="checked official endpoint trace" if args.capture_origin=="official-server-trace" and args.policy=="handshake-only" else "synthetic control or unknown-peer-policy capture; no Minyar endpoint-policy claim"
    except BaseException as error:failed(error,"setup-or-analysis")
    if provider_before is not None:
        try:
            provider_after=crypto_provider();report["crypto_provider_after"]=provider_after
            if provider_after!=provider_before:raise CoverageError("loaded crypto provider bytes changed")
        except BaseException as error:failed(error,"provider-after")
    for error in retention.recheck():failed(error,"input-after")
    for attempt in range(2):
        try:
            data=(json.dumps(report,indent=2)+"\n").encode()
            temporary=args.artifacts/"ledger.json.tmp";temporary.write_bytes(data)
            if temporary.read_bytes()!=data:raise CoverageError("durable ledger bytes mismatch")
            temporary.replace(args.artifacts/"ledger.json")
            if (args.artifacts/"ledger.json").read_bytes()!=data:raise CoverageError("final ledger bytes mismatch")
            break
        except BaseException as error:failed(error,"finalization")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},indent=2))
    return 0 if report["status"]=="passed" else 1 if report["status"]=="failed" else 2
if __name__=="__main__":raise SystemExit(main())
