#!/usr/bin/env python3
"""Deterministic independent trace-ledger controls; no peers, compiler or Docker."""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM,ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
import quic_amplification_ledger as ledger

CASES=("exact3x","one-byte-over","forged-handshake","invalid-handshake-frame","coalesced-once",
       "route-credit-isolated","connection-credit-isolated","unknown-cid","cross-connection-coalescing",
       "capture-duplicate","real-retransmission","truncated-pcap","pcapng","big-endian-pcap",
       "ipv6","aes256-handshake","chacha-handshake","rfc-chacha-vector","peer-policy-unknown",
       "server-before-credit","missing-authenticated-boundary","closing-handshake","ack-never-sent","ack-issued-handshake","missing-server-keylog","pcapng-capture-loss","pcapng-dropcount","pcapng-multiple-interface","handshake-replay-same-route","handshake-replay-new-route",
       "fresh-handshake-new-route","nonminimal-frame-type","crypto-end-overflow","crypto-wide-length","pcap-time-decrease","pcapng-time-decrease",
       "pcap-nanoseconds","pcapng-decimal-resolution","pcapng-binary-resolution","pcapng-time-offset","pcap-invalid-subsecond","cli-unbound-policy","cli-retained-input-binding","cli-retained-mutation","cli-original-mutation",
       "cli-missing-input","cli-provider-error","cli-primary-finalization-error","initial-token-policy-unknown",
       "receipt-byte-graph","receipt-runtime-missing","receipt-provider-changed","receipt-extra-link-input","receipt-compiler-mismatch",
       "receipt-flags-mismatch","receipt-tool-changed","receipt-staging-mismatch","receipt-extra-program","receipt-final-mismatch",
       "pcap-client-first-equal-time","pcap-server-first-equal-time","receipt-schema-float","receipt-status-bool","receipt-raw-mismatch","receipt-policy-bool",
       "frontend-byte-graph","frontend-status-bool","frontend-status-float","frontend-help-argv","frontend-output-mismatch",
       "endpoint-command-tuple","endpoint-command-mismatch","endpoint-tuple-mismatch")
CLIENT=b"client01";SERVER=b"server01";ORIGINAL=b"original"
SECRET=bytes(range(32));RANDOM=bytes(range(32,64))
CLIENT2=b"client02";SERVER2=b"server02"
SECRET2=bytes(range(64,96));RANDOM2=bytes(range(96,128))


def number(value):
    if value<64:return bytes([value])
    if value<16384:return (value|0x4000).to_bytes(2,"big")
    raise ValueError("fixture varint out of range")


def initial(size=1200,client=CLIENT,server=SERVER,direction="client",kind=0,token=b""):
    destination=ORIGINAL if direction=="client" and kind==0 else server if direction=="client" else client
    source=client if direction=="client" else server
    header=bytes([0xc1|(kind<<4)])+bytes([0,0,0,1,len(destination)])+destination+bytes([len(source)])+source
    if kind==0:header+=number(len(token))+token
    width=1 if size-len(header)-1<64 else 2
    length=size-len(header)-width
    return header+number(length)+bytes(length)


def short(size,client=CLIENT):
    return b"\x40"+client+bytes(size-1-len(client))


def fixture_expand(secret,label,size,sha384=False):
    label=b"tls13 "+label
    info=size.to_bytes(2,"big")+bytes([len(label)])+label+b"\0"
    return HKDFExpand(algorithm=hashes.SHA384() if sha384 else hashes.SHA256(),length=size,info=info).derive(secret)


def handshake(secret=SECRET,client=CLIENT,server=SERVER,suite="AES128",payload=b"\x01\0\0\0",direction="client",packet_number=0):
    destination=server if direction=="client" else client
    source=client if direction=="client" else server
    chacha=suite=="CHACHA20";sha384=suite=="AES256";size=32 if chacha or sha384 else 16
    pn=packet_number.to_bytes(2,"big")
    header=b"\xe1"+bytes([0,0,0,1,len(destination)])+destination+bytes([len(source)])+source+number(len(pn)+len(payload)+16)
    key=fixture_expand(secret,b"quic key",size,sha384);iv=fixture_expand(secret,b"quic iv",12,sha384)
    ciphertext=(ChaCha20Poly1305(key) if chacha else AESGCM(key)).encrypt((int.from_bytes(iv,"big")^packet_number).to_bytes(12,"big"),payload,header+pn)
    packet=bytearray(header+pn+ciphertext);offset=len(header)
    hp=fixture_expand(secret,b"quic hp",size,sha384);sample=bytes(packet[offset+4:offset+20])
    cipher=Cipher(algorithms.ChaCha20(hp,sample),None) if chacha else Cipher(algorithms.AES(hp),modes.ECB())
    encryptor=cipher.encryptor()
    hp_mask=encryptor.update(bytes(5)) if chacha else encryptor.update(sample)
    packet[0]^=hp_mask[0]&15
    for index in range(2):packet[offset+index]^=hp_mask[index+1]
    return bytes(packet)


def wire(payload,direction="client",port=12345,ipv6=False):
    import ipaddress
    source="fd00:cafe::1" if ipv6 else "193.167.0.1"
    destination="fd00:cafe::100" if ipv6 else "193.167.100.100"
    sourceport,destinationport=port,443
    if direction=="server":source,destination=destination,source;sourceport,destinationport=destinationport,sourceport
    udp=struct.pack("!HHHH",sourceport,destinationport,len(payload)+8,0)+payload
    if ipv6:
        header=struct.pack("!IHBB",6<<28,len(udp),17,64)+ipaddress.ip_address(source).packed+ipaddress.ip_address(destination).packed
    else:
        header=struct.pack("!BBHHHBBH",0x45,0,len(udp)+20,0,0,64,17,0)+ipaddress.ip_address(source).packed+ipaddress.ip_address(destination).packed
    return header+udp


def pcap(frames,endian="<",duplicate=False,stamps=None,nanoseconds=False):
    magic=(b"\x4d\x3c\xb2\xa1" if endian=="<" else b"\xa1\xb2\x3c\x4d") if nanoseconds else (b"\xd4\xc3\xb2\xa1" if endian=="<" else b"\xa1\xb2\xc3\xd4")
    data=magic+struct.pack(endian+"HHiIII",2,4,0,0,65535,101)
    for index,frame in enumerate(frames):
        stamp=index if not duplicate or index!=1 else 0
        seconds,fraction=stamps[index] if stamps is not None else (1,stamp)
        data+=struct.pack(endian+"IIII",seconds,fraction,len(frame),len(frame))+frame
    return data


def pcapng(frames,drop=0,epbdrop=0,multiple=False,stamps=None,resolution=6,offset=0):
    def block(kind,body):
        body+=bytes((-len(body))%4);size=len(body)+12
        return struct.pack("<II",kind,size)+body+struct.pack("<I",size)
    interface_options=struct.pack("<HHB",9,1,resolution)+bytes(3)+struct.pack("<HHq",14,8,offset)+bytes(4)
    data=block(0x0a0d0d0a,struct.pack("<IHHq",0x1a2b3c4d,1,0,-1))+block(1,struct.pack("<HHI",101,0,65535)+interface_options)
    if multiple:data+=block(1,struct.pack("<HHI",101,0,65535))
    for index,frame in enumerate(frames):
        padding=bytes((-len(frame))%4)
        option=struct.pack("<HHQ",4,8,epbdrop)+bytes(4) if epbdrop and index==0 else b""
        stamp=stamps[index] if stamps is not None else index+1
        data+=block(6,struct.pack("<IIIII",1 if multiple and index==1 else 0,stamp>>32,stamp&0xffffffff,len(frame),len(frame))+frame+padding+option)
    data+=block(5,struct.pack("<IIIHHQ",0,0,len(frames)+1,5,8,drop)+bytes(4))
    return data


def keylog(secret=SECRET,random=RANDOM,direction="CLIENT"):
    return (direction+"_HANDSHAKE_TRAFFIC_SECRET "+random.hex()+" "+secret.hex()+"\n").encode("ascii")


def fixtures(case):
    hs=handshake();logs=keylog();connection_count=1;policy="handshake-only";expected="passed"
    sequence=[("client",initial(),12345),("server",initial(direction="server"),12345),
              ("server",short(1200),12345),("server",short(1200),12345),("client",hs,12345),
              ("server",short(5000),12345)]
    if case in ("pcap-client-first-equal-time","pcap-server-first-equal-time"):
        sequence=[("client",initial(),12345),("server",initial(direction="server"),12345),("client",hs,12345)]
        if case=="pcap-server-first-equal-time":sequence[0],sequence[1]=sequence[1],sequence[0]
        expected="coverage-limited"
    elif case=="initial-token-policy-unknown":sequence[0]=("client",initial(token=b"opaque token"),12345);expected="coverage-limited"
    elif case=="one-byte-over":sequence[3]=("server",short(1201),12345);expected="failed"
    elif case in ("forged-handshake","invalid-handshake-frame","closing-handshake","ack-never-sent"):
        bad=hs[:-1]+bytes([hs[-1]^1]) if case=="forged-handshake" else handshake(payload=b"\x1c\0\0\0" if case=="closing-handshake" else b"\x02\x01\0\0\0" if case=="ack-never-sent" else b"\x08\0\0\0")
        sequence=sequence[:4]+[("client",bad,12345),("server",short(3*len(bad)+1),12345)]
        expected="failed"
        if case=="ack-never-sent":logs+=keylog(bytes(range(128,160)),direction="SERVER")
    elif case in ("handshake-replay-same-route","handshake-replay-new-route","fresh-handshake-new-route"):
        rebound=12345 if case=="handshake-replay-same-route" else 12346
        next_hs=handshake(packet_number=1) if case=="fresh-handshake-new-route" else hs
        sequence=[("client",initial(),12345),("server",initial(direction="server"),12345),
                  ("client",hs,12345),("client",next_hs,rebound)]
        if case=="handshake-replay-new-route":
            sequence.append(("server",short(3*len(hs)+1),12346));expected="failed"
        elif case=="fresh-handshake-new-route":sequence.append(("server",short(5000),12346))
    elif case in ("nonminimal-frame-type","crypto-end-overflow","crypto-wide-length"):
        plaintext=b"\x40\x01\0\0" if case=="nonminimal-frame-type" else b"\x06"+bytes([255])*8+b"\x01z" if case=="crypto-end-overflow" else b"\x06\x40\0\x40\x01z\0"
        candidate=handshake(payload=plaintext)
        sequence=sequence[:4]+[("client",candidate,12345),("server",short(3*len(candidate)+1),12345)]
        expected="passed" if case=="crypto-wide-length" else "failed"
    elif case=="coalesced-once":
        combined=initial()+initial(200,kind=1)
        sequence=[("client",initial(),12345),("server",initial(direction="server"),12345),
                  ("client",combined,12345),("server",short(6600),12345),("client",hs,12345)]
    elif case=="route-credit-isolated":
        sequence=sequence[:2]+[("client",initial(),12346),("server",short(2401),12345),("client",hs,12345)]
        expected="failed"
    elif case=="connection-credit-isolated":
        hs2=handshake(SECRET2,CLIENT2,SERVER2)
        sequence=[("client",initial(),12345),("client",initial(client=CLIENT2,server=SERVER2),12345),
                  ("server",initial(direction="server"),12345),("server",short(2401),12345),
                  ("server",initial(direction="server",client=CLIENT2,server=SERVER2),12345),
                  ("client",hs,12345),("client",hs2,12345)]
        logs+=keylog(SECRET2,RANDOM2);connection_count=2;expected="failed"
    elif case in ("ack-issued-handshake","missing-server-keylog"):
        server_secret=bytes(range(128,160))
        issued=handshake(server_secret,direction="server")
        if case=="ack-issued-handshake":logs+=keylog(server_secret,direction="SERVER")
        else:expected="coverage-limited"
        acknowledged=handshake(payload=b"\x02\0\0\0\0")
        sequence=[("client",initial(),12345),("server",initial(direction="server"),12345),
                  ("server",issued,12345),("client",acknowledged,12345),("server",short(5000),12345)]
    elif case=="unknown-cid":
        sequence=[("client",initial(),12345),("server",initial(direction="server",client=CLIENT2),12345)]
        expected="coverage-limited"
    elif case=="cross-connection-coalescing":
        sequence=[("client",initial()+initial(client=CLIENT2,server=SERVER2),12345)]
        expected="coverage-limited"
    elif case=="capture-duplicate":
        sequence=[sequence[0],sequence[0]];expected="coverage-limited"
    elif case=="real-retransmission":
        sequence=[sequence[0],sequence[0],sequence[1],("server",short(6000),12345),("client",hs,12345)]
    elif case=="truncated-pcap":expected="coverage-limited"
    elif case=="aes256-handshake":
        secret=bytes(range(48));logs=keylog(secret)
        sequence[4]=("client",handshake(secret,suite="AES256"),12345)
    elif case=="chacha-handshake":sequence[4]=("client",handshake(suite="CHACHA20"),12345)
    elif case=="peer-policy-unknown":
        sequence[3]=("server",short(1201),12345);policy="peer-unknown";expected="coverage-limited"
    elif case=="missing-authenticated-boundary":sequence=sequence[:4];expected="coverage-limited"
    if case in ("pcapng-capture-loss","pcapng-dropcount","pcapng-multiple-interface"):expected="coverage-limited"
    frames=[wire(payload,direction,port,case=="ipv6") for direction,payload,port in sequence]
    data=pcapng(frames,drop=1 if case=="pcapng-capture-loss" else 0,epbdrop=1 if case=="pcapng-dropcount" else 0,multiple=case=="pcapng-multiple-interface") if case.startswith("pcapng") else pcap(frames,">" if case=="big-endian-pcap" else "<",case=="capture-duplicate")
    if case=="pcap-time-decrease":data=pcap(frames,stamps=[(1,2),(1,1)]+[(1,index+3) for index in range(len(frames)-2)]);expected="coverage-limited"
    elif case=="pcapng-time-decrease":data=pcapng(frames,stamps=[2,1]+list(range(3,len(frames)+1)));expected="coverage-limited"
    elif case=="pcap-invalid-subsecond":data=pcap(frames,stamps=[(1,1000000)]+[(2,index) for index in range(1,len(frames))]);expected="coverage-limited"
    elif case=="pcap-nanoseconds":data=pcap(frames,stamps=[(1,123456789+index) for index in range(len(frames))],nanoseconds=True)
    elif case=="pcapng-decimal-resolution":data=pcapng(frames,stamps=list(range(123456789,123456789+len(frames))),resolution=9)
    elif case=="pcapng-binary-resolution":data=pcapng(frames,stamps=list(range(129,129+len(frames))),resolution=0x8a)
    elif case=="pcapng-time-offset":data=pcapng(frames,resolution=9,offset=60)
    if case=="truncated-pcap":data=data[:-1]
    if case in ("pcap-client-first-equal-time","pcap-server-first-equal-time"):data=pcap(frames,stamps=[(1,0)]*len(frames))
    return data,logs,connection_count,policy,expected


def run_case(case,target=None):
    if case.startswith("cli-"):return cli_control(case,target)
    if case.startswith("receipt-"):return receipt_graph_control(case,target)
    if case.startswith(("frontend-","endpoint-")):return authority_graph_control(case,target)
    if case=="rfc-chacha-vector":
        secret=bytes.fromhex("9ac312a7f877468ebe69422748ad00a15443f18203a07d6060f688f30f21632b")
        hp=ledger.expand(secret,b"quic hp",32,hashlib.sha256)
        if hp.hex()!="25a282b9e82f06f21f488917a4fc8f1b73573685608597d0efcb076b0ab7a7a4":
            raise AssertionError("RFC9001 A.5 HKDF oracle")
        sample=bytes.fromhex("5e5cd55c41f69080575d7999c25a5bfb")
        if ledger.mask(hp,sample,True).hex()!="aefefe7d03":raise AssertionError("RFC9001 A.5 HP oracle")
        return b"",b"",{"status":"passed","oracle":"RFC9001 A.5"},"passed"
    if case=="server-before-credit":
        accounting=ledger.Ledger("handshake-only")
        route=("193.167.0.1",12345,"193.167.100.100",443)
        accounting.record("connection-a",route,"server",1)
        accounting.record("connection-a",route,"client",1200,{"synthetic_control":True})
        return b"",b"",accounting.result(),"failed"
    data,logs,count,policy,expected=fixtures(case)
    try:
        report=ledger.analyze(data,[logs],["fd00:cafe::100" if case=="ipv6" else "193.167.100.100"],policy=policy,expected_connections=count)
    except ledger.CoverageError as error:
        report={"status":"coverage-limited","exception":type(error).__name__,"reason":str(error)}
    if case=="coalesced-once" and report["status"]=="passed":
        row=report["rows"][2]
        if row["udp_payload_bytes"]!=1400 or row["received"]!=2600:raise AssertionError("coalesced UDP was counted more than once")
    if case=="connection-credit-isolated" and report["status"]=="failed":
        if report["connection_count"]!=2 or report["violations"]!=[3]:raise AssertionError("cross-connection credit was shared")
    if case.startswith("handshake-replay") and "rows" in report:
        row=report["rows"][3]
        report["control_checks"]={
            "first_boundary_retained":report["authenticated_boundaries"]==[2],
            "replay_cannot_release_boundary":row["authentication"] is None,
            "replay_udp_credit_counted":row["received"]==(1200+2*len(handshake()) if case.endswith("same-route") else len(handshake())),
            "rebound_stays_unvalidated":case.endswith("same-route") or not row["validated_after"],
        }
    if case=="fresh-handshake-new-route" and "rows" in report:
        report["control_checks"]={"distinct_packet_validates_new_route":report["authenticated_boundaries"]==[2,3]}
    if case in ("nonminimal-frame-type","crypto-end-overflow") and "rows" in report:
        report["control_checks"]={
            "invalid_plaintext_not_boundary":report["rows"][4]["authentication"] is None,
            "discarded_udp_credit_counted":report["rows"][4]["received"]==1200+len(handshake(payload=b"\x40\x01\0\0" if case=="nonminimal-frame-type" else b"\x06"+bytes([255])*8+b"\x01z")),
        }
    expected_time={"pcap-nanoseconds":[1123456789,1000000000],"pcapng-decimal-resolution":[123456789,1000000000],
                   "pcapng-binary-resolution":[129,1024],"pcapng-time-offset":[60000000001,1000000000]}
    if case in expected_time and "rows" in report:
        report["control_checks"]={"exact_declared_timestamp_resolution":report["rows"][0].get("timestamp_exact")==expected_time[case]}
    return data,logs,report,expected




def authority_graph_control(case,target):
    from types import SimpleNamespace
    expected="passed" if case in ("frontend-byte-graph","endpoint-command-tuple") else "coverage-limited"
    retention=ledger.InputRetention(target)
    try:
        if case.startswith("frontend-"):
            root=target/"mock-source";server=root/"tests/interop/qns/server.min";quic=root/"library/quic.min"
            server.parent.mkdir(parents=True);quic.parent.mkdir();server.write_bytes(b"mock server");quic.write_bytes(b"mock quic")
            output=target/"server.ll";output.write_bytes(b"mock generated LLVM")
            def binding(path):
                data=path.read_bytes();return {"path":str(path),"sha256":ledger.sha(data),"bytes":len(data)}
            compiler=target/"compiler";compiler.write_bytes(b"mock frontend bytes")
            out=target/"stdout";err=target/"stderr";out.write_bytes(b"");err.write_bytes(b"")
            raw={"original":str(output),"sha256":ledger.sha(output.read_bytes()),"bytes":len(output.read_bytes())}
            record={"compiler":binding(compiler),"argv":[str(compiler),str(server),str(output),"--bounded-owners","32","--library",str(quic.parent)],
                    "status":0,"timed_out":False,"timeout_seconds":120,"output":binding(output),"stdout":binding(out),"stderr":binding(err)}
            if case=="frontend-status-bool":record["status"]=False
            elif case=="frontend-status-float":record["status"]=0.0
            elif case=="frontend-help-argv":record["argv"]=[str(compiler),"--help",str(server)]
            elif case=="frontend-output-mismatch":raw["sha256"]="0"*64
            graph=ledger.checked_frontend_graph(record,{"server":binding(server),"quic":binding(quic)},raw,retention)
        else:
            project="minyar-qns-"+"a"*24
            addresses=["193.167.100.100","fd00:cafe:cafe:100::100"]
            endpoint={"Path":"python3","Args":["/opt/minyar/endpoint.py"],
                      "Config":{"Entrypoint":["python3","/opt/minyar/endpoint.py"],"Cmd":None},
                      "NetworkSettings":{"Networks":{project+"_rightnet":{"IPAddress":addresses[0],"GlobalIPv6Address":addresses[1]}}}}
            run={"project":project,"server_addresses":addresses,"server_port":443}
            args=SimpleNamespace(server_address=list(addresses),server_port=443)
            if case=="endpoint-command-mismatch":endpoint["Path"]="other";endpoint["Args"]=["--help"]
            elif case=="endpoint-tuple-mismatch":run["server_addresses"]=args.server_address=["193.167.100.101"]
            graph=ledger.checked_endpoint_mode(endpoint,run,args)
        report={"status":"passed","graph":graph}
    except ledger.CoverageError as error:report={"status":"coverage-limited","reason":str(error)}
    report["scope"]="mock graph shape only; no compiler or endpoint execution and no official authority"
    return b"",b"",report,expected

def receipt_graph_control(case,target):
    """Mock byte-graph metadata only; never an owned-run policy receipt."""
    import copy
    root=Path(ledger.__file__).resolve().parent.parent
    build_root=target/"build";build_root.mkdir()
    def item(name,data,original,role=None,format=None):
        (build_root/name).write_bytes(data);digest=ledger.sha(data)
        value={"original":str(original),"retained":name,"sha256":digest,"bytes":len(data)}
        value.update({field:digest for field in ("source_before_sha256","retained_sha256","source_after_sha256","pre_link_sha256","post_link_sha256")})
        if role:value["role"]=role
        if format:value["format"]=format
        return value
    raw=item("program.raw.ll",b"define i32 @main() { ret i32 0 }\n",target/"server.ll","program","llvm")
    objects=[item("runtime.o",b"mock-runtime",target/"runtime.o","runtime","native_object")]
    objects += [item("native-"+str(n)+".o",("mock-provider-"+str(n)).encode(),target/("provider-"+str(n)+".o"),"provider","native_object") for n in range(6)]
    tools={}
    for name,path in (("clang-driver.py",root/"tools/clang-driver.py"),("sanitizer_llvm.py",root/"tools/sanitizer_llvm.py"),("clang.bin",Path("/usr/bin/clang-18").resolve())):
        tools[name]=item(name,path.read_bytes(),path.resolve())
    staged_path=target/".minyar-link-control"/"server"
    final=item("program",b"mock-linked-output",target/"server")
    staged=item("program.staged",b"mock-linked-output",staged_path)
    final["path"]=str(target/"server");staged["path"]=str(staged_path)
    command=["/usr/bin/clang-18","-O2","-Wno-override-module",raw["original"],*[value["original"] for value in objects[:3]],"-lcrypto",*[value["original"] for value in objects[3:]],"-lcrypto","-lm"]
    build={"schema":2,"mode":"native","optimization":"2","link_attempted":True,"link_status":0,"link_subprocess_status":0,"retention_errors":[],
           "link_flags":["-O2","-Wno-override-module"],"lto_flags":[],"address_sanitizer_enabled":False,"raw_program_input":copy.deepcopy(raw),"program_input":raw,
           "inputs":objects,"tools":{name:value["sha256"] for name,value in tools.items()},"tool_bindings":tools,
           "raw_sha256":raw["sha256"],"linked_program_sha256":raw["sha256"],"compiler_selected_command":"/usr/bin/clang-18",
           "compiler_pre_link":{"selected_command":"/usr/bin/clang-18","resolved_path":tools["clang.bin"]["original"],"sha256":tools["clang.bin"]["sha256"]},
           "command":command,"actual_command":command+["-o",str(staged_path)],"staged_requested_path":str(staged_path),
           "staged_output":staged,"final_output":final,"binary_sha256":final["sha256"]}
    if case=="receipt-schema-float":build["schema"]=2.0
    elif case=="receipt-status-bool":build["link_status"]=False
    elif case=="receipt-raw-mismatch":build["raw_sha256"]="0"*64
    elif case=="receipt-runtime-missing":build["inputs"]=objects[1:]
    elif case=="receipt-provider-changed":(build_root/"native-0.o").write_bytes(b"changed provider")
    elif case=="receipt-extra-link-input":build["actual_command"].insert(-2,str(target/"unrepresented.o"))
    elif case=="receipt-compiler-mismatch":build["compiler_pre_link"]["selected_command"]="/different/compiler"
    elif case=="receipt-flags-mismatch":build["actual_command"].insert(1,"-O0")
    elif case=="receipt-tool-changed":(build_root/"clang-driver.py").write_bytes(b"changed tool")
    elif case=="receipt-staging-mismatch":build["actual_command"][-1]=str(target/"server")
    elif case=="receipt-extra-program":build["actual_command"].insert(-2,raw["original"])
    elif case=="receipt-final-mismatch":(build_root/"program").write_bytes(b"different output")
    (target/"mock-build.json").write_text(json.dumps(build,indent=2)+"\n")
    evidence=target/"checked-inputs";evidence.mkdir();retention=ledger.InputRetention(evidence)
    if case=="receipt-policy-bool":
        from types import SimpleNamespace
        policy=dict(ledger.POLICY_CONTRACT);policy["early_cid_validation"]=0
        receipt=target/"policy.json";receipt.write_text(json.dumps({"schema_version":1,"policy":policy,"capture_origin":"synthetic-control","evidence_kind":"mocked-control"}))
        try:
            ledger.checked_policy_receipt(SimpleNamespace(policy_receipt=receipt,capture_origin="synthetic-control"),retention)
        except ledger.CoverageError as error:
            rejected=str(error)=="unreviewed endpoint validation policy"
            return b"",b"",{"status":"coverage-limited" if rejected else "passed","reason":str(error),"scope":"policy-header exact-type control only"},"coverage-limited"
        raise AssertionError("mocked policy unexpectedly supplied official authority")
    try:
        result=ledger.checked_link_graph(build,build_root,retention)
        report={"status":"passed","graph":result}
    except ledger.CoverageError as error:report={"status":"coverage-limited","reason":str(error)}
    report["scope"]="mock byte-graph validation only; no endpoint ran and no official policy authority"
    report["retained_inputs"]=retention.inputs
    (target/"retention.json").write_text(json.dumps(retention.inputs,indent=2)+"\n")
    return b"",b"",report,"passed" if case=="receipt-byte-graph" else "coverage-limited"

def cli_control(case,target):
    import subprocess,sys
    if target is None:raise ValueError("CLI controls require retained case workspace")
    data,logs,_,_,_=fixtures("exact3x")
    (target/"trace.pcap").write_bytes(data);(target/"client.keys").write_bytes(logs)
    (target/"unreviewed.source").write_bytes(b"arbitrary policy text");(target/"unreviewed.binary").write_bytes(b"arbitrary binary")
    program='import importlib.util,json,sys\nfrom pathlib import Path\nclass OriginalProviderFailure(RuntimeError):pass\nclass RetentionFailure(RuntimeError):pass\nspec=importlib.util.spec_from_file_location("checked_ledger",sys.argv[1])\nmodule=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\ncase=sys.argv[2];root=Path(sys.argv[3]);real_write=Path.write_bytes\ninjected=[False]\ndef write(path,data):\n    result=real_write(path,data)\n    if case=="cli-retained-mutation" and path.name=="input-001.bin":real_write(path,data+b"x")\n    if case=="cli-original-mutation" and path.name=="input-001.bin":real_write(root/"trace.pcap",(root/"trace.pcap").read_bytes()+b"x")\n    if case=="cli-primary-finalization-error" and path.name.startswith("ledger") and not injected[0]:\n        injected[0]=True;raise RetentionFailure("secondary finalization failure")\n    return result\nPath.write_bytes=write\nif case in ("cli-provider-error","cli-primary-finalization-error"):\n    def provider():raise OriginalProviderFailure("original provider failure")\n    module.crypto_provider=provider\ncapture=root/("missing.pcap" if case=="cli-missing-input" else "trace.pcap")\nargs=[str(sys.argv[1]),"--capture",str(capture),"--capture-origin","official-server-trace","--keylog",str(root/"client.keys"),"--server-address","193.167.100.100","--policy","handshake-only" if case=="cli-unbound-policy" else "peer-unknown","--artifacts",str(root/"checker")]\nif case=="cli-unbound-policy":args+=["--policy-source",str(root/"unreviewed.source"),"--policy-binary",str(root/"unreviewed.binary")]\nsys.argv=args\nraise SystemExit(module.main())\n'
    child=target/"child.py";child.write_text(program)
    argv=[sys.executable,str(child),str(Path(ledger.__file__).resolve()),case,str(target)]
    process=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    (target/"child.stdout").write_bytes(process.stdout);(target/"child.stderr").write_bytes(process.stderr)
    command={"argv":argv,"status":process.returncode,"timeout_seconds":10,
             "stdout":{"path":"child.stdout","sha256":ledger.sha(process.stdout),"bytes":len(process.stdout)},
             "stderr":{"path":"child.stderr","sha256":ledger.sha(process.stderr),"bytes":len(process.stderr)}}
    (target/"command.json").write_text(json.dumps(command,indent=2)+"\n")
    expected="passed" if case=="cli-retained-input-binding" else "coverage-limited"
    result_path=target/"checker/ledger.json"
    report=json.loads(result_path.read_text()) if result_path.exists() else {"status":"missing-durable-ledger"}
    report["control_checks"]={"exact_exit_status":process.returncode==(0 if expected=="passed" else 2)}
    if case=="cli-retained-input-binding":
        report["control_checks"]["checked_before_copy_after"]=bool(report.get("inputs")) and all(
            value.get("original_before")==value.get("retained")==value.get("original_after") and value.get("copied_exact") is True for value in report["inputs"].values())
    elif case in ("cli-provider-error","cli-primary-finalization-error"):
        report["control_checks"]["primary_error_preserved"]=report.get("primary_exception",{}).get("type")=="OriginalProviderFailure"
        if case=="cli-primary-finalization-error":report["control_checks"]["secondary_error_retained"]=bool(report.get("finalization_errors"))
    return data,logs,report,expected

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--artifacts",type=Path);parser.add_argument("--case",action="append",choices=CASES);args=parser.parse_args()
    cases=args.case or CASES
    if args.artifacts is not None:
        if not args.artifacts.is_absolute() or args.artifacts.exists():raise ValueError("--artifacts requires a fresh absolute path")
        args.artifacts.mkdir(parents=True)
    manager=contextlib.nullcontext(str(args.artifacts)) if args.artifacts is not None else tempfile.TemporaryDirectory(prefix="quic-amp-controls-")
    with manager as directory:
        root=Path(directory);results=[]
        for case in cases:
            target=root/case;target.mkdir()
            data,logs,report,expected=run_case(case,target)
            (target/"trace.pcap").write_bytes(data);(target/"client.keys").write_bytes(logs)
            (target/"ledger.json").write_text(json.dumps(report,indent=2)+"\n")
            results.append({"case":case,"status":report["status"],"expected":expected,"matched":report["status"]==expected and all(report.get("control_checks",{}).values())})
        passed=all(row["matched"] for row in results)
        inputs={str(path.resolve()):ledger.sha(path.read_bytes()) for path in (Path(__file__),Path(ledger.__file__))}
        report={"schema_version":1,"scope":"synthetic capture and independent accounting controls only","status":"passed" if passed else "failed","inputs":inputs,"crypto_provider":ledger.crypto_provider(),"declared_cases":list(cases),"results":results}
        (root/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        files={path.relative_to(root).as_posix():ledger.sha(path.read_bytes()) for path in root.rglob("*") if path.is_file()}
        manifest={"schema_version":1,"status":report["status"],"inputs":inputs,"declared_cases":list(cases),"files":files,
                  "file_bytes":{name:(root/name).stat().st_size for name in files},
                  "case_inventory":[{"case":case,"files":[name for name in files if name.startswith(case+"/")]} for case in cases]}
        (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print(json.dumps(report,indent=2))
    return 0 if passed else 1
if __name__=="__main__":raise SystemExit(main())
