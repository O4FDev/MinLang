#!/usr/bin/env python3
"""Private official-runner retention and owned-daemon lifetime adapter.

No workload is started by this module. Real daemon operations require an explicit
allow_real constructor argument; controls use JsonDaemon and retain that scope.
"""
import ast
import hashlib
import ctypes
import contextlib
import fcntl
import select
import threading
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import stat
import tarfile
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PIN="740c05a10b61d65e8abd3ad38d60898004d335d9"
PINNED={
 "run.py":"e6242d2fc0ed77fc894976d656abcfd2b15283a546a5f1be5fa3c8fcdf0dde0e",
 "interop.py":"19bf7696ba0558a9d381b81ba7742a411a9a9ec47b328f6cfa684a0dedddf511",
 "testcase.py":"e87106cbac52a66640fdca3e52dc936ff1c3cc6735dc61c376a6575e3a8cefcf",
 "testcases_quic.py":"8e004e1e58a1b5a83e8e02c59ff7cf53dfb397b756e868629aa241b523a12e91",
 "docker-compose.yml":"be0cb079b0c41ad6d398daec6924b8ef8b8a689e4632434404d141b3c0267eec"}
OWNER_LABEL="io.minyar.qns.owner"
ROLES=("sim","server","client")
MAX_BYTES=536870912
MAX_FILES=10000
CHUNK=65536
NETWORK_ROLES={"sim":("leftnet","rightnet"),"server":("rightnet",),"client":("leftnet",)}


def digest(data):return hashlib.sha256(data).hexdigest()
def stream_binding(path,limit=MAX_BYTES,deadline=None,copy_to=None):
    path=Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):raise OwnershipError("nonregular bound input")
    if path.stat().st_size>limit:raise OwnershipError("retention bound exceeded")
    total=0;hashed=hashlib.sha256()
    with path.open("rb") as source:
        output=None if copy_to is None else Path(copy_to).open("wb")
        try:
            while True:
                if deadline is not None and time.monotonic()>deadline:raise OwnershipError("retention bound exceeded")
                data=source.read(min(CHUNK,limit-total+1))
                if not data:break
                total+=len(data)
                if total>limit:raise OwnershipError("retention bound exceeded")
                hashed.update(data)
                if output is not None:output.write(data)
        finally:
            if output is not None:output.close()
    if deadline is not None and time.monotonic()>deadline:raise OwnershipError("retention bound exceeded")
    return {"sha256":hashed.hexdigest(),"bytes":total}
def binding(path):
    return {"path":str(Path(path).resolve()),**stream_binding(path)}
def bounded_paths(root,max_entries=MAX_FILES,deadline=None):
    # Lazy traversal: no complete-tree list before admission, including directories.
    count=0;pending=[iter(os.scandir(root))]
    try:
        while pending:
            if deadline is not None and time.monotonic()>deadline:raise OwnershipError("retention bound exceeded")
            try:entry=next(pending[-1])
            except StopIteration:pending.pop().close();continue
            count+=1
            if count>max_entries:raise OwnershipError("retention bound exceeded")
            path=Path(entry.path)
            if entry.is_symlink():raise OwnershipError("symlink in retained tree")
            if entry.is_dir(follow_symlinks=False):pending.append(iter(os.scandir(path)))
            elif not entry.is_file(follow_symlinks=False):raise OwnershipError("nonregular retained input")
            yield path
    finally:
        for iterator in pending:iterator.close()

def atomic_json(path,value):
    path=Path(path);temporary=path.with_name(path.name+".tmp")
    data=(json.dumps(value,indent=2)+"\n").encode()
    temporary.write_bytes(data)
    if temporary.read_bytes()!=data:raise RuntimeError("retained JSON write mismatch")
    temporary.replace(path)
    if path.read_bytes()!=data:raise RuntimeError("retained JSON final mismatch")


class OwnershipError(RuntimeError):pass
class CleanupError(RuntimeError):pass


class OwnerSpec:
    def __init__(self,value):
        self.value=dict(value)
        if type(value.get("schema_version")) is not int or value["schema_version"]!=1:raise OwnershipError("owner schema must be exact integer 1")
        self.project=value.get("project");self.nonce=value.get("nonce")
        if not isinstance(self.project,str) or re.fullmatch(r"minyar-qns-[0-9a-f]{24}",self.project) is None:raise OwnershipError("invalid unique project")
        if not isinstance(self.nonce,str) or re.fullmatch(r"[0-9a-f]{64}",self.nonce) is None:raise OwnershipError("invalid owner nonce")
        self.images=value.get("images")
        if not isinstance(self.images,dict) or set(self.images)!=set(ROLES):raise OwnershipError("three exact image roles required")
        for role,images in self.images.items():
            if not isinstance(images,list) or not images or len(set(images))!=len(images) or any(not isinstance(image,str) or re.fullmatch(r"sha256:[0-9a-f]{64}",image) is None for image in images):raise OwnershipError("invalid pinned image ID")
            if (role=="sim" and len(images)!=1) or (role!="sim" and len(images)>2):raise OwnershipError("unbounded cell image set")
        self.paths={}
        for name in ("runner_root","compose_path","fixture_root","artifacts"):
            path=Path(value.get(name,""))
            if not path.is_absolute() or path.resolve()!=path or path.is_symlink():raise OwnershipError("owner path must be canonical absolute")
            self.paths[name]=path
        if self.paths["compose_path"].parent!=self.paths["runner_root"]:raise OwnershipError("compose path outside private runner")
        if self.paths["fixture_root"]==self.paths["artifacts"] or self.paths["fixture_root"] in self.paths["artifacts"].parents or self.paths["artifacts"] in self.paths["fixture_root"].parents:raise OwnershipError("fixture and evidence trees overlap")
        if value.get("runner_commit")!=PIN:raise OwnershipError("unreviewed runner")
    def labels(self,role=None):
        value={"com.docker.compose.project":self.project,OWNER_LABEL:self.nonce}
        if role is not None:value["com.docker.compose.service"]=role
        return value
    def container(self,entry):
        identity=entry.get("Id")
        if not isinstance(identity,str) or re.fullmatch(r"[0-9a-f]{64}",identity) is None:raise OwnershipError("full immutable container ID required")
        config=entry.get("Config",{});labels=config.get("Labels",{})
        role=labels.get("com.docker.compose.service")
        if role not in ROLES or any(labels.get(key)!=value for key,value in self.labels(role).items()):raise OwnershipError("container owner labels differ")
        if entry.get("Name")!="/"+self.project+"-"+role or entry.get("Image") not in self.images[role]:raise OwnershipError("container name or image ID differs")
        if labels.get("com.docker.compose.project.working_dir")!=str(self.paths["runner_root"]) or labels.get("com.docker.compose.project.config_files")!=str(self.paths["compose_path"]):raise OwnershipError("container compose source differs")
        host=entry.get("HostConfig",{})
        if host.get("Privileged") is not False or host.get("NetworkMode") not in tuple(self.project+"_"+name for name in NETWORK_ROLES[role]) or host.get("PidMode")!="" or host.get("IpcMode")!="private" or host.get("CpusetCpus")!="7" or type(host.get("NanoCpus")) is not int or host["NanoCpus"]!=1000000000:raise OwnershipError("container resource/namespace configuration differs")
        if role in ("server","client"):
            if config.get("User")!="65534:65534" or host.get("CapDrop")!=["ALL"] or host.get("CapAdd") not in (None,[]) or host.get("SecurityOpt")!=["no-new-privileges:true"]:raise OwnershipError("endpoint capability/user configuration differs")
            mounts=entry.get("Mounts",[])
            if len(mounts)!=3 or {mount.get("Destination") for mount in mounts}!={"/www","/downloads","/certs"}:raise OwnershipError("endpoint bind mounts differ")
            for mount in mounts:
                source=Path(mount.get("Source",""))
                if mount.get("Type")!="bind" or not source.is_absolute() or self.paths["fixture_root"] not in source.resolve().parents or source.is_symlink() or mount.get("RW") is not (mount.get("Destination")=="/downloads"):raise OwnershipError("endpoint bind ownership differs")
        elif host.get("CapAdd")!=["NET_ADMIN","NET_RAW"]:raise OwnershipError("simulator capabilities differ")
        attached=entry.get("NetworkSettings",{}).get("Networks")
        expected={self.project+"_"+name for name in NETWORK_ROLES[role]}
        if not isinstance(attached,dict) or set(attached)!=expected:raise OwnershipError("complete endpoint network membership differs")
        running=entry.get("State",{}).get("Running")
        if type(running) is not bool:raise OwnershipError("endpoint phase missing")
        if any(not isinstance(v,dict) or not isinstance(v.get("NetworkID"),str) or (re.fullmatch(r"[0-9a-f]{64}",v["NetworkID"]) is None and not (running is False and v["NetworkID"]=="")) for v in attached.values()):raise OwnershipError("immutable endpoint network ID missing")
        return role
    def network(self,entry,owned_ids):
        identity=entry.get("Id")
        if not isinstance(identity,str) or re.fullmatch(r"[0-9a-f]{64}",identity) is None:raise OwnershipError("full immutable network ID required")
        if entry.get("Name") not in (self.project+"_leftnet",self.project+"_rightnet") or any(entry.get("Labels",{}).get(key)!=value for key,value in self.labels().items()):raise OwnershipError("network owner labels differ")
        if entry.get("Driver")!="bridge" or entry.get("Internal") is not False or any(identity not in owned_ids for identity in entry.get("Containers",{})):raise OwnershipError("network has unowned members or mode")
        return identity


def configured_topology(spec,entries,networks):
    # Created/stopped objects declare names, not live endpoints. Record the
    # independently owner-checked bridges before starting any endpoint.
    names={}
    for network in networks:
        spec.network(network,{entry["Id"] for entry in entries})
        if network["Name"] in names:raise OwnershipError("colliding configured bridges")
        names[network["Name"]]=network["Id"]
    containers={}
    for entry in entries:
        role=spec.container(entry)
        containers[entry["Id"]]={spec.project+"_"+name:names[spec.project+"_"+name] for name in NETWORK_ROLES[role]}
        for name,attached in entry["NetworkSettings"]["Networks"].items():
            if attached["NetworkID"] not in ("",names[name]):raise OwnershipError("declared endpoint bridge differs")
    value={"schema_version":1,"project":spec.project,"nonce":spec.nonce,"containers":containers,"networks":names}
    atomic_json(spec.paths["artifacts"]/"configured-topology.json",value)
    return value

def verified_topology(spec,entries,networks):
    owned={entry["Id"]:spec.container(entry) for entry in entries};names={};configured=None
    if len(owned)!=len(entries):raise OwnershipError("colliding endpoint identities")
    for network in networks:
        spec.network(network,set(owned))
        if network["Name"] in names:raise OwnershipError("colliding network names")
        names[network["Name"]]=network
    for entry in entries:
        running=entry["State"]["Running"]
        for name,attached in entry["NetworkSettings"]["Networks"].items():
            network=names.get(name)
            if network is None:raise OwnershipError("declared owned bridge missing")
            if running:
                if attached["NetworkID"]!=network["Id"] or entry["Id"] not in network.get("Containers",{}):raise OwnershipError("running endpoint bridge membership is not reciprocal")
            elif attached["NetworkID"]=="" or entry["Id"] not in network.get("Containers",{}):
                if configured is None:
                    configured=json.loads((spec.paths["artifacts"]/"configured-topology.json").read_bytes())
                    if type(configured.get("schema_version")) is not int or configured["schema_version"]!=1 or configured.get("project")!=spec.project or configured.get("nonce")!=spec.nonce:raise OwnershipError("configured bridge receipt ownership differs")
                expected={spec.project+"_"+n:names[spec.project+"_"+n]["Id"] for n in NETWORK_ROLES[owned[entry["Id"]]]}
                if configured.get("containers",{}).get(entry["Id"])!=expected or any(configured.get("networks",{}).get(n)!=identity for n,identity in expected.items()) or attached["NetworkID"] not in ("",network["Id"]):raise OwnershipError("stopped endpoint does not bind checked configured bridge IDs")
            elif attached["NetworkID"]!=network["Id"]:raise OwnershipError("stopped endpoint bridge ID differs")
    for name,network in names.items():
        for identity in network.get("Containers",{}):
            if name not in {spec.project+"_"+n for n in NETWORK_ROLES[owned[identity]]}:raise OwnershipError("role attached to unexpected bridge")
            entry=next(entry for entry in entries if entry["Id"]==identity)
            if entry["NetworkSettings"]["Networks"][name]["NetworkID"]!=network["Id"]:raise OwnershipError("bridge membership is not reciprocal")
    return names


class TreeRetention:
    def __init__(self,root,max_bytes=536870912,max_files=10000):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.max_bytes=max_bytes;self.max_files=max_files;self.rows=[];self.errors=[]
    def capture(self,path,label):
        original_path=Path(path)
        if original_path.is_symlink():raise OwnershipError("symlink retention root")
        path=original_path.resolve()
        if path.is_symlink() or not path.is_dir():raise OwnershipError("retention requires a real owned directory")
        target=self.root/(str(len(self.rows)).zfill(3)+"-"+re.sub(r"[^a-zA-Z0-9_-]","_",label));target.mkdir()
        row={"original":str(path),"retained":target.name,"files":{},"status":"retaining"}
        self.rows.append(row);size=0;primary=None;deadline=None
        try:
            deadline=time.monotonic()+30
            for source in bounded_paths(path,self.max_files,deadline):
                if source.is_dir():continue
                if len(row["files"])>=self.max_files:raise OwnershipError("retention bound exceeded")
                name=source.relative_to(path).as_posix()
                remaining=self.max_bytes-size
                if source.stat().st_size>remaining:raise OwnershipError("retention bound exceeded")
                output=target/name;output.parent.mkdir(parents=True,exist_ok=True)
                before=stream_binding(source,remaining,deadline,output);size+=before["bytes"]
                after=stream_binding(source,before["bytes"],deadline);copied=stream_binding(output,before["bytes"],deadline)
                record={"original_before":before,"retained":copied,"original_after":after}
                row["files"][name]=record
                if before!=copied or before!=after:raise OwnershipError("retained file changed")
            names=[p.relative_to(path).as_posix() for p in bounded_paths(path,self.max_files,deadline) if p.is_file()]
            if set(names)!=set(row["files"]):raise OwnershipError("retained tree inventory changed")
            for name,record in row["files"].items():
                record["original_final"]=stream_binding(path/name,record["original_before"]["bytes"],deadline)
                record["retained_final"]=stream_binding(target/name,record["original_before"]["bytes"],deadline)
                if record["original_before"]!=record["original_final"] or record["original_before"]!=record["retained_final"]:
                    raise OwnershipError("retained tree bytes changed before finalization")
            if time.monotonic()>deadline:raise OwnershipError("retention bound exceeded")
            row["status"]="retained"
        except BaseException as error:
            primary=error;row["status"]="failed";row["error"]={"type":type(error).__name__,"message":str(error)};self.errors.append(row["error"])
            raise
        finally:
            try:
                atomic_json(self.root/"retention.json",{"schema_version":1,"trees":self.rows,"errors":self.errors})
                if deadline is not None and time.monotonic()>deadline:raise OwnershipError("retention bound exceeded")
            except BaseException as secondary:
                if primary is None:
                    row["status"]="failed";row["error"]={"type":type(secondary).__name__,"message":str(secondary),"stage":"retention-finalization"}
                    self.errors.append(row["error"])
                    try:atomic_json(self.root/"retention.json",{"schema_version":1,"trees":self.rows,"errors":self.errors})
                    except BaseException as last:
                        if hasattr(secondary,"add_note"):secondary.add_note("retention failure ledger: "+str(last))
                    raise
                record={"type":type(secondary).__name__,"message":str(secondary),"stage":"retention-finalization"};self.errors.append(record)
                if hasattr(primary,"add_note"):primary.add_note("retention finalization: "+str(secondary))
                try:atomic_json(self.root/"retention.json",{"schema_version":1,"trees":self.rows,"errors":self.errors})
                except BaseException as final:
                    if hasattr(primary,"add_note"):primary.add_note("failure ledger finalization: "+str(final))
        return row


def child_birthday(child):
    # Popen has not reaped this owned child. Its zombie stat still binds
    # fast CLI completion; a live-only lookup would lose legitimate commands.
    fields=Path("/proc/"+str(child.pid)+"/stat").read_text().rpartition(") ")[2].split()
    if int(fields[2])!=child.pid or int(fields[3])!=child.pid:raise OwnershipError("CLI did not enter its owned session")
    return {"pid":child.pid,"start_ticks":int(fields[19])}

def direct_children():
    children=[]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():continue
        try:
            fields=(entry/"stat").read_text().rpartition(") ")[2].split()
            if int(fields[1])==os.getpid():
                children.append({"pid":int(entry.name),"start_ticks":int(fields[19]),"pgid":int(fields[2]),"session":int(fields[3]),"origin":"exclusive-subreaper-child"})
        except (FileNotFoundError,ProcessLookupError):continue
    return children

def subreaper_begin():
    if sys.platform!="linux" or threading.active_count()!=1 or direct_children():raise OwnershipError("CLI lifetime requires an exclusive Linux child scope")
    libc=ctypes.CDLL(None,use_errno=True);prior=ctypes.c_int()
    if libc.prctl(37,ctypes.byref(prior),0,0,0)!=0 or libc.prctl(36,1,0,0,0)!=0:raise OwnershipError("owned CLI subreaper setup failed")
    return libc,prior.value

def cli_members(identity,known,adopt=True):
    # Never reopen a numeric session after its bound root vanished or closed.
    root_matches=False
    try:
        fields=Path("/proc/"+str(identity["pid"])+"/stat").read_text().rpartition(") ")[2].split()
        root_matches=int(fields[19])==identity["start_ticks"]
    except (FileNotFoundError,ProcessLookupError):pass
    # Only the exclusive local subreaper may use a direct, still-unreaped
    # Popen/pidfd authority when birthday evidence failed. A watchdog never
    # trusts that serialized marker as a substitute for a birthday.
    direct_scope=adopt and identity.get("origin")=="direct-unreaped-Popen"
    root_matches=root_matches or direct_scope
    members={member["pid"]:member for member in session_members(identity["pid"])} if root_matches and cli_key(identity) not in _extinct_cli else {}
    if adopt and root_matches and cli_key(identity) not in _extinct_cli:
        for member in direct_children():
            if member["pid"]!=identity["pid"] and member["pid"] not in members:members[member["pid"]]=member
    for pid,member in known.items():
        try:
            fields=Path("/proc/"+str(pid)+"/stat").read_text().rpartition(") ")[2].split()
            if int(fields[19])==member["start_ticks"]:
                current=dict(member);current["pgid"]=int(fields[2]);current["session"]=int(fields[3])
                members.setdefault(pid,current)
        except (FileNotFoundError,ProcessLookupError):continue
    return list(members.values())

class ProcessHandle:
    """A pidfd is the signal authority; numeric IDs are evidence only."""
    def __init__(self,identity):
        self.identity=dict(identity);self.closed=False;self.fd=os.pidfd_open(identity["pid"],0)
        try:
            fields=Path("/proc/"+str(identity["pid"])+"/stat").read_text().rpartition(") ")[2].split()
            if int(fields[19])!=identity["start_ticks"]:raise OwnershipError("pidfd birthday differs")
        except BaseException:
            os.close(self.fd);self.closed=True;raise
    def ready(self):
        probe=select.poll();probe.register(self.fd,select.POLLIN)
        return bool(probe.poll(0))
    def send(self,sig):
        try:signal.pidfd_send_signal(self.fd,sig,None,0);return True
        except ProcessLookupError:
            if not self.ready():raise
            return False
    def close(self):
        if not self.closed:os.close(self.fd);self.closed=True

def open_process_handle(identity):return ProcessHandle(identity)

def open_owned_child_handle(child):
    # This exact direct Popen child has not been reaped; acquire its kernel
    # handle before any fallible birthday/session evidence lookup.
    handle=object.__new__(ProcessHandle);handle.closed=False;handle.fd=os.pidfd_open(child.pid,0)
    handle.identity={"pid":child.pid,"start_ticks":None,"origin":"direct-unreaped-Popen"}
    return handle

_extinct_cli=set()
_unresolved_cli={}
def cli_key(identity):return (identity["pid"],identity["start_ticks"])
def latch_extinction(identity):
    key=cli_key(identity)
    if key not in _extinct_cli and len(_extinct_cli)>=MAX_FILES:raise OwnershipError("owned CLI extinction ledger bound exceeded")
    _extinct_cli.add(key)

def drain_cli(identity,known,receipts,deadline,adopt=True,handles=None):
    key=cli_key(identity);local=handles is None;handles={} if local else handles;primary=None
    def discover():
        # A closed numeric session is never rediscovered. Held handles remain
        # authoritative even if a /proc leader row is Z/X or absent.
        members=[] if key in _extinct_cli else cli_members(identity,known,adopt)
        for member in members:
            prior=known.get(member["pid"])
            if prior is not None and any(prior[k]!=member[k] for k in ("pid","start_ticks")):raise OwnershipError("CLI descendant birthday changed")
            known[member["pid"]]=member
            if member["pid"] not in handles:
                try:handles[member["pid"]]=open_process_handle(member)
                except (FileNotFoundError,ProcessLookupError):continue
            if any(handles[member["pid"]].identity[k]!=member[k] for k in ("pid","start_ticks")):raise OwnershipError("held descendant birthday differs")
        return all(handle.ready() for handle in handles.values())
    def finish():
        latch_extinction(identity)
        for pid in known:
            if pid!=identity["pid"]:
                try:os.waitpid(pid,os.WNOHANG)
                except ChildProcessError:pass
        return True
    try:
        while time.monotonic()<deadline:
            if discover():return finish()
            for handle in handles.values():
                if not handle.ready():
                    attempted=handle.send(signal.SIGKILL)
                    receipts.append({"identity":handle.identity,"signal":"SIGKILL","owned_cli":identity,"authority":"held-pidfd","attempted":attempted is not False})
            time.sleep(.01)
        if discover():return finish()
        return False
    except BaseException as error:primary=error;raise
    finally:
        if local:
            try:
                if all(handle.ready() for handle in handles.values()):
                    for handle in handles.values():handle.close()
                else:_unresolved_cli[key]={"handles":handles,"known":known}
            except BaseException as error:
                _unresolved_cli[key]={"handles":handles,"known":known}
                if primary is None:raise
                if hasattr(primary,"add_note"):primary.add_note("held CLI ownership finalization: "+str(error))

def child_exited(child):
    # WNOWAIT retains the root zombie and its numeric session identity until
    # discovery and descendant drain have closed permanently.
    result=os.waitid(os.P_PID,child.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
    return result is not None


def session_members(pgid):
    result=[]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():continue
        try:
            fields=(entry/"stat").read_text().rpartition(") ")[2].split()
            if int(fields[2])==pgid and int(fields[3])==pgid:
                result.append({"pid":int(entry.name),"start_ticks":int(fields[19]),"pgid":pgid,"session":pgid})
        except (FileNotFoundError,ProcessLookupError):continue
    return result


def lifetime_preflight():
    if sys.platform!="linux" or os.uname().machine!="x86_64" or ctypes.sizeof(ctypes.c_void_p)!=8:raise OwnershipError("owned CLI kernel ABI requires Linux x86_64")
    required=((os,"pidfd_open"),(os,"waitid"),(os,"WNOWAIT"),(signal,"pidfd_send_signal"))
    if any(not hasattr(module,name) for module,name in required):raise OwnershipError("owned CLI pidfd/WNOWAIT APIs unavailable")
    if signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL:raise OwnershipError("owned CLI requires default non-autoreap SIGCHLD")
    # Linux x86_64 rt_sigaction UAPI: handler, flags, restorer, 64-bit mask.
    # Check actual kernel flags, not just Python's cached handler table.
    class Action(ctypes.Structure):
        _fields_=[("handler",ctypes.c_ulong),("flags",ctypes.c_ulong),("restorer",ctypes.c_ulong),("mask",ctypes.c_ulong)]
    libc=ctypes.CDLL(None,use_errno=True);action=Action()
    if libc.syscall(13,signal.SIGCHLD,None,ctypes.byref(action),8)!=0:raise OwnershipError("SIGCHLD kernel state unavailable")
    if action.handler!=0 or action.flags&2:raise OwnershipError("SIGCHLD kernel handler/autoreap flags differ")
    fd=os.pidfd_open(os.getpid(),0)
    try:signal.pidfd_send_signal(fd,0,None,0)
    finally:os.close(fd)
    return {"kernel_abi":"linux-x86_64","SIGCHLD":"SIG_DFL","kernel_flags":action.flags,"SA_NOCLDWAIT":False,"pidfd_kernel_probe":True,"WNOWAIT_available":True}

class RawCommands:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False);self.rows=[]
    def save(self):atomic_json(self.root/"commands.json",{"schema_version":1,"commands":self.rows})
    def run(self,argv,timeout,check=True,max_bytes=MAX_BYTES,return_bytes=True,admission_spec=None):
        index=len(self.rows);out=self.root/(str(index).zfill(3)+".stdout");err=self.root/(str(index).zfill(3)+".stderr")
        row={"argv":list(argv),"timeout_seconds":timeout,"status":None,"timed_out":False,"primary_exception":None,"finalization_errors":[],
             "owner_process_identity":process_identity(os.getpid()),"process_identity":None,"lifetime":{"state":"intent","certified":False,"receipts":[],"members":[],"root_exited_with_descendants":False},
             "bootstrap_gate":{"permit_sent":False,"owned_bootstrap_reaped":False,"preflight":None}}
        self.rows.append(row)
        primary=None;child=None;selector=None;known={};handles={};root_handle=None;deadline=time.monotonic()+timeout;total=0;subreaper=None
        stdout=None;stderr=None;gate_read=None;gate_write=None;owner_closed=True
        def secondary(stage,error):
            row["finalization_errors"].append({"stage":stage,"type":type(error).__name__,"message":str(error)})
            row["lifetime"]["certified"]=False
            if primary is not None and hasattr(primary,"add_note"):primary.add_note(stage+": "+str(error))
        def attempt(stage,call):
            try:return call()
            except BaseException as error:secondary(stage,error);return None
        def close_gate():
            nonlocal gate_read,gate_write
            for name in ("gate_read","gate_write"):
                fd=gate_read if name=="gate_read" else gate_write
                if fd is None:continue
                before=len(row["finalization_errors"])
                attempt(name+" close",lambda fd=fd:os.close(fd))
                if len(row["finalization_errors"])!=before:attempt(name+" close retry",lambda fd=fd:os.close(fd))
                if name=="gate_read":gate_read=None
                else:gate_write=None
        def capture(error):
            nonlocal primary
            primary=error;row["timed_out"]=isinstance(error,subprocess.TimeoutExpired)
            row["primary_exception"]={"type":type(error).__name__,"message":str(error)}
        try:
            stdout=out.open("wb");stderr=err.open("wb");self.save()
            if _unresolved_cli:raise OwnershipError("previous owned CLI lifetime remains unresolved")
            row["bootstrap_gate"]["preflight"]=lifetime_preflight()
            subreaper=subreaper_begin()
            context=contextlib.nullcontext() if admission_spec is None else admission_lock(admission_spec)
            with context:
                if admission_spec is not None:require_admission(admission_spec)
                gate_read,gate_write=os.pipe()
                launch=[sys.executable,str(Path(__file__).resolve()),"--owned-exec-fd",str(gate_read),"--owned-exec-json",json.dumps(list(argv))]
                row["launcher_argv"]=launch;row["launcher_source"]=binding(__file__);self.save()
                try:
                    child=subprocess.Popen(launch,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,pass_fds=(gate_read,))
                    owner_closed=False
                    root_handle=open_owned_child_handle(child)
                    identity=child_birthday(child)
                    row["process_identity"]=identity;root_handle.identity={**identity,"pgid":child.pid,"session":child.pid,"origin":"held-root-pidfd"}
                    known[child.pid]=dict(root_handle.identity);handles[child.pid]=root_handle
                    row["lifetime"]["members"]=list(known.values());row["lifetime"]["state"]="running";self.save()
                    if admission_spec is not None:require_admission(admission_spec)
                    os.write(gate_write,b"G");row["bootstrap_gate"]["permit_sent"]=True
                except BaseException as error:
                    capture(error)
                    if child is not None and row["process_identity"] is None:
                        attempt("bootstrap birthday evidence",lambda:row.update({"process_identity":child_birthday(child)}))
                    raise
                finally:close_gate()
            if row["finalization_errors"]:raise CleanupError("owned bootstrap gate finalization failed")
            selector=selectors.DefaultSelector()
            selector.register(child.stdout,selectors.EVENT_READ,stdout);selector.register(child.stderr,selectors.EVENT_READ,stderr)
            while True:
                exited=child_exited(child);members=cli_members(identity,known)
                for member in members:
                    prior=known.get(member["pid"])
                    if prior is not None and any(prior[k]!=member[k] for k in ("pid","start_ticks")):raise OwnershipError("CLI birthday changed")
                    known[member["pid"]]=member
                    if member["pid"] not in handles:
                        try:handles[member["pid"]]=open_process_handle(member)
                        except (FileNotFoundError,ProcessLookupError):pass
                row["lifetime"]["members"]=list(known.values());self.save()
                if exited and any(pid!=child.pid and not handle.ready() for pid,handle in handles.items()):
                    row["lifetime"]["root_exited_with_descendants"]=True
                    if not drain_cli(identity,known,row["lifetime"]["receipts"],time.monotonic()+2,handles=handles):raise CleanupError("CLI descendants not drained")
                if exited and not selector.get_map():break
                if time.monotonic()>deadline:raise subprocess.TimeoutExpired(argv,timeout)
                for key,_ in selector.select(.02):
                    data=os.read(key.fd,min(CHUNK,max_bytes-total+1))
                    if not data:selector.unregister(key.fileobj);continue
                    if total+len(data)>max_bytes:raise OwnershipError("command stream bound exceeded")
                    total+=len(data);key.data.write(data)
            row["lifetime"]["certified"]=drain_cli(identity,known,row["lifetime"]["receipts"],time.monotonic()+2,handles=handles)
            if not row["lifetime"]["certified"] or not all(handle.ready() for handle in handles.values()):raise CleanupError("CLI lifetime not certified closed")
            row["lifetime"]["state"]="closed";row["lifetime"]["members"]=list(known.values())
            row["status"]=child.wait(timeout=.1);owner_closed=True
            if check and row["status"]!=0:raise CleanupError("owned command failed: "+str(row["status"]))
        except BaseException as error:
            if primary is None:capture(error)
            elif error is not primary:secondary("command body",error)
            raise primary
        finally:
            close_gate()
            if child is not None and not owner_closed:
                if not row["bootstrap_gate"]["permit_sent"]:
                    def finish_bootstrap():
                        nonlocal owner_closed
                        # No target can have executed: the only child was the
                        # trusted EOF-gated bootstrap, and no permit was sent.
                        expiry=time.monotonic()+6
                        while not child_exited(child):
                            if time.monotonic()>=expiry:raise CleanupError("unreleased bootstrap exit not observed")
                            time.sleep(.01)
                        if root_handle is not None and not root_handle.ready():raise CleanupError("held bootstrap thread group exit not ready")
                        if not all(handle.ready() for handle in handles.values()):raise CleanupError("held bootstrap descendants unresolved")
                        row["status"]=child.wait(timeout=.1);owner_closed=True
                        row["bootstrap_gate"]["owned_bootstrap_reaped"]=True
                        row["bootstrap_gate"]["WNOWAIT_exit_observed"]=True
                    attempt("unreleased bootstrap closure",finish_bootstrap)
                else:
                    def finish_lifetime():
                        nonlocal owner_closed
                        identity=row["process_identity"]
                        drained=drain_cli(identity,known,row["lifetime"]["receipts"],time.monotonic()+2,handles=handles)
                        if not drained or not all(handle.ready() for handle in handles.values()):raise CleanupError("held CLI lifetime unresolved")
                        row["status"]=child.wait(timeout=.1);owner_closed=True
                    attempt("CLI descendant/root cleanup",finish_lifetime)
            row["lifetime"]["members"]=list(known.values())
            if child is not None:
                for name,stream in (("stdout",child.stdout),("stderr",child.stderr)):
                    if stream is not None:
                        before=len(row["finalization_errors"]);attempt(name+" pipe close",stream.close)
                        if len(row["finalization_errors"])!=before:attempt(name+" pipe close retry",stream.close)
            if selector is not None:attempt("selector close",selector.close)
            if owner_closed:
                for handle in handles.values():attempt("held pidfd close",handle.close)
                if root_handle is not None and child.pid not in handles:attempt("root pidfd close",root_handle.close)
                if subreaper is not None:
                    libc,prior=subreaper
                    def restore():
                        if libc.prctl(36,prior,0,0,0)!=0:raise CleanupError("owned CLI subreaper restoration failed")
                    attempt("subreaper restoration",restore)
            else:
                key=cli_key(row["process_identity"]) if row["process_identity"] is not None else (child.pid,None)
                _unresolved_cli[key]={"handles":handles,"root_handle":root_handle,"child":child,"known":known,"subreaper":subreaper}
                row["lifetime"]["state"]="ownership-retained"
                attempt("unresolved ownership evidence",lambda:row["lifetime"].update({"unresolved_handles":[handle.identity for handle in handles.values() if not handle.ready()]}))
                secondary("ownership retained",CleanupError("owned bootstrap/CLI closure unproven; handles and subreaper retained"))
            # Retained evidence FILES are independent of child pipe streams.
            # Their flush/close cannot replace the primary body exception.
            for name,file in (("stdout",stdout),("stderr",stderr)):
                if file is not None:
                    attempt("retained "+name+" FILE flush",file.flush)
                    before=len(row["finalization_errors"]);attempt("retained "+name+" FILE close",file.close)
                    if len(row["finalization_errors"])!=before:attempt("retained "+name+" FILE close retry",file.close)
            if primary is not None or row["finalization_errors"]:row["lifetime"]["certified"]=False
            for name,path in (("stdout",out),("stderr",err)):
                def bind(name=name,path=path):
                    row[name]={"path":str(path.resolve()),**stream_binding(path,max_bytes,None if primary is not None else deadline)}
                attempt(name+" evidence finalization",bind)
            attempt("command ledger finalization",self.save)
            if row["finalization_errors"]:attempt("command failure ledger",self.save)
        if row["finalization_errors"]:raise CleanupError("owned CLI cleanup/finalization failed; retained command ledger")
        return out.read_bytes() if return_bytes else out


class DockerDaemon:
    """Real backend; never constructed by the mocked control driver."""
    def __init__(self,spec,root,allow_real=False,docker_path=None):
        if allow_real is not True:raise OwnershipError("real Docker backend not authorized")
        self.spec=spec
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        self.commands=RawCommands(root/("command-"+str(os.getpid())+"-"+secrets.token_hex(12)))
        self.docker=docker_path or shutil.which("docker")
        if not self.docker:raise OwnershipError("existing Docker CLI missing")
        self.cli=binding(self.docker)
    def command(self,*args,timeout=10,check=True,return_bytes=True):
        if binding(self.docker)!=self.cli:raise OwnershipError("Docker CLI bytes changed")
        admitted=args and args[0]=="compose" and any(token in ("create","up") for token in args)
        return self.commands.run([self.docker,*args],timeout,check=check,return_bytes=return_bytes,admission_spec=self.spec if admitted else None)
    def containers(self):
        return self.command("ps","-aq","--no-trunc","--filter","label=com.docker.compose.project="+self.spec.project).decode().splitlines()
    def inspect(self,identity):return json.loads(self.command("inspect",identity))[0]
    def networks(self):
        ids=self.command("network","ls","-q","--no-trunc","--filter","label=com.docker.compose.project="+self.spec.project).decode().splitlines()
        return [json.loads(self.command("network","inspect",identity))[0] for identity in ids]
    def retain(self,identity,target):
        self.spec.container(self.inspect(identity))
        target.mkdir()
        logs=self.command("logs","--timestamps",identity,timeout=10);(target/"daemon.log").write_bytes(logs)
        self.copy_bounded(identity,"/logs/.",target/"logs")
        self.copy_bounded(identity,"/tmp/.",target/"tmp")
    def copy_bounded(self,identity,source,target):
        self.spec.container(self.inspect(identity))
        deadline=time.monotonic()+20
        archive_path=self.command("cp",identity+":"+source,"-",timeout=20,return_bytes=False)
        if not isinstance(archive_path,Path):raise OwnershipError("container copy must retain bounded raw archive bytes")
        stream_binding(archive_path,MAX_BYTES,deadline)
        target=Path(target)
        if target.is_symlink() or (target.exists() and not target.is_dir()):raise OwnershipError("container copy destination is not an owned directory")
        target.mkdir(parents=True,exist_ok=True);total=0;count=0
        with archive_path.open("rb") as raw_archive,tarfile.open(fileobj=raw_archive,mode="r|*") as archive:
            for member in archive:
                count+=1
                if count>MAX_FILES or member.size>MAX_BYTES-total or time.monotonic()>deadline:raise OwnershipError("container copy bound exceeded")
                name=Path(member.name)
                if name.is_absolute() or ".." in name.parts or not (member.isdir() or member.isfile()):raise OwnershipError("unsafe container archive member")
                if name==Path(".") and member.isdir():continue
                output=target/name;output.parent.mkdir(parents=True,exist_ok=True)
                if output.exists():
                    if member.isdir() and output.is_dir() and not output.is_symlink():continue
                    raise OwnershipError("colliding container archive member")
                if member.isdir():output.mkdir();continue
                total+=member.size
                with archive.extractfile(member) as incoming,output.open("wb") as outgoing:
                    remaining=member.size
                    while remaining:
                        if time.monotonic()>deadline:raise OwnershipError("container copy bound exceeded")
                        block=incoming.read(min(CHUNK,remaining))
                        if not block:raise OwnershipError("truncated container archive")
                        outgoing.write(block);remaining-=len(block)
        if time.monotonic()>deadline:raise OwnershipError("container copy bound exceeded")
    def abort(self,identity):
        entry=self.inspect(identity);self.spec.container(entry)
        if entry.get("State",{}).get("Running") is True:self.command("kill","--signal","KILL",identity,timeout=10)
    def stop(self,identity):
        self.spec.container(self.inspect(identity));self.command("stop","--time","5",identity,timeout=10)
    def remove(self,identity):
        self.spec.container(self.inspect(identity));self.command("rm","-f",identity,timeout=10)
    def remove_network(self,identity):self.command("network","rm",identity,timeout=10)


class JsonDaemon:
    """Persistent mocked daemon; its event argv never invokes Docker."""
    def __init__(self,path):self.path=Path(path)
    def read(self):return json.loads(self.path.read_bytes())
    def action(self,name,identity=None):
        state=self.read();state.setdefault("events",[]).append({"backend":"mock","operation":name,"immutable_id":identity})
        atomic_json(self.path,state)
        if state.get("fail")==name:raise CleanupError("controlled mock "+name+" failure")
    def containers(self):return list(self.read()["containers"])
    def inspect(self,identity):return self.read()["containers"][identity]
    def networks(self):return list(self.read().get("networks",{}).values())
    def retain(self,identity,target):
        self.action("retain",identity);target.mkdir();(target/"daemon.log").write_bytes(b"mock owned endpoint log\n")
    def abort(self,identity):
        self.action("abort",identity);state=self.read();state["containers"][identity]["State"]={"Running":False,"ExitCode":137};atomic_json(self.path,state)
    def stop(self,identity):self.action("stop",identity)
    def remove(self,identity):
        self.action("remove",identity);state=self.read();del state["containers"][identity]
        for value in state.get("networks",{}).values():value.get("Containers",{}).pop(identity,None)
        atomic_json(self.path,state)
    def remove_network(self,identity):
        self.action("remove_network",identity);state=self.read();del state["networks"][identity];atomic_json(self.path,state)


def cleanup_owned(spec,daemon,root,reason,primary=None,unsupported_compliance=None,abort_first=False,revoke_admission=True):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    result={"schema_version":1,"scope":"owned IDs only; mock backend is not actual daemon proof","reason":reason,"project":spec.project,"nonce":spec.nonce,"verified_ids":[],"errors":[],"status":"cleaning",
            "primary_exception":None if primary is None else {"type":type(primary).__name__,"message":str(primary)}}
    def error(stage,exception):
        result["errors"].append({"stage":stage,"type":type(exception).__name__,"message":str(exception)})
        if primary is not None and hasattr(primary,"add_note"):primary.add_note(stage+": "+str(exception))
    owned=[];networks=[];result["states_before_cleanup"]={}
    try:result["admission"]=close_admission(spec,revoke=revoke_admission)
    except BaseException as exception:error("create-admission",exception)

    try:
        ids=daemon.containers()
        if len(ids)!=len(set(ids)) or len(ids)>3:raise OwnershipError("duplicate/unbounded project IDs")
        roles=set()
        for identity in ids:
            entry=daemon.inspect(identity)
            if entry.get("Id")!=identity:raise OwnershipError("inspect ID mismatch")
            role=spec.container(entry)
            if role in roles:raise OwnershipError("colliding service identities")
            roles.add(role);owned.append(identity)
            state=entry.get("State",{});result["states_before_cleanup"][identity]=state
            if type(state.get("Running")) is not bool or type(state.get("ExitCode")) is not int:raise OwnershipError("endpoint state primitive types differ")
        network_entries=daemon.networks()
        verified_topology(spec,[daemon.inspect(identity) for identity in owned],network_entries)
        for entry in network_entries:networks.append(spec.network(entry,set(owned)))
        result["verified_ids"]=owned
        atomic_json(root/"owned-inspect.json",{"containers":[daemon.inspect(identity) for identity in owned],"networks":daemon.networks()})
    except BaseException as exception:
        error("ownership",exception);owned=[];networks=[]
    result["owned_abort_requests"]=[]
    if abort_first:
        for identity in owned:
            if result["states_before_cleanup"][identity]["Running"]:
                result["owned_abort_requests"].append({"immutable_id":identity,"signal":"SIGKILL"})
                try:daemon.abort(identity)
                except BaseException as exception:error("abort",exception)
    for identity in owned:
        state=result["states_before_cleanup"][identity]
        allowed_unsupported=False
        if unsupported_compliance is not None:
            try:
                entry=daemon.inspect(identity);role=spec.container(entry)
                requested=unsupported_compliance.get("role");testcase=unsupported_compliance.get("testcase")
                env=entry.get("Config",{}).get("Env",[])
                known=("handshake","transfer","retry","resumption","zerortt","multiconnect","rebind-port","rebind-addr","chacha20","keyupdate","connectionmigration")
                if requested==role and isinstance(testcase,str) and testcase and testcase not in known and env.count("ROLE="+role)==1 and env.count("TESTCASE="+testcase)==1:
                    allowed_unsupported=state["ExitCode"]==127
            except BaseException as exception:error("compliance-reinspection",exception)
        if not state["Running"] and state["ExitCode"]!=0 and not allowed_unsupported:
            error("unexpected-endpoint-exit",CleanupError("endpoint exited before owned stop: "+str(state["ExitCode"])))
        try:daemon.retain(identity,root/(identity+"-before-stop"))
        except BaseException as exception:error("retention",exception)
        try:daemon.stop(identity)
        except BaseException as exception:error("stop",exception)
        try:daemon.remove(identity)
        except BaseException as exception:error("remove",exception)
    for identity in networks:
        try:
            remaining=next((entry for entry in daemon.networks() if entry["Id"]==identity),None)
            if remaining is not None:
                spec.network(remaining,set())
                daemon.remove_network(identity)
        except BaseException as exception:error("network-remove",exception)
    try:
        result["remaining_ids"]=daemon.containers();result["remaining_networks"]=[entry["Id"] for entry in daemon.networks()]
        if result["remaining_ids"] or result["remaining_networks"]:raise CleanupError("owned daemon objects remain")
    except BaseException as exception:error("final-inventory",exception)
    result["status"]="passed" if not result["errors"] else "failed"
    try:atomic_json(root/"cleanup.json",result)
    except BaseException as exception:
        error("finalization",exception);result["status"]="failed"
        try:atomic_json(root/"cleanup.json",result)
        except BaseException as final:
            error("failure-ledger-finalization",final)
        if primary is None:raise
    if primary is not None:return result
    if result["status"]!="passed":raise CleanupError("owned cleanup failed; retained cleanup.json")
    return result


def process_identity(pid):
    try:
        parts=Path("/proc/"+str(pid)+"/stat").read_text().rpartition(") ")[2].split()
        if parts[0] in ("Z","X"):return None
        return {"pid":pid,"start_ticks":int(parts[19])}
    except (FileNotFoundError,ProcessLookupError):return None


def resource_sample(previous=None):
    cpu=Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values=[int(value) for value in cpu[:8]];total=sum(values);idle=values[3]+values[4]
    usage=0.0 if previous is None or total==previous[0] else 100*(1-(idle-previous[1])/(total-previous[0]))
    memory={}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key,value,*_=line.split();memory[key.rstrip(":")]=int(value)
    ram=100*(1-memory["MemAvailable"]/memory["MemTotal"])
    return {"cpu_percent":usage,"ram_percent":ram},(total,idle)


def watch_owned(spec,daemon,controller,guard,deadline,output,interval=1.0,samples=None):
    """Separate bounded supervisor always attempts owned cleanup and retention."""
    if type(controller.get("pid")) is not int or type(controller.get("start_ticks")) is not int or type(guard.get("pid")) is not int or type(guard.get("start_ticks")) is not int:raise OwnershipError("exact controller/guard process identities required")
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    observed=[];previous=None;reason=None;index=0;primary=None;errors=[];result=None
    def secondary(stage,error):
        errors.append({"stage":stage,"type":type(error).__name__,"message":str(error)})
        if primary is not None and hasattr(primary,"add_note"):primary.add_note(stage+": "+str(error))
    try:
        while reason is None:
            sample,previous=resource_sample(previous)
            if samples is not None:sample=samples[min(index,len(samples)-1)];index+=1
            observed.append({"time":time.monotonic(),**sample})
            if process_identity(controller["pid"])!=controller:reason="controller-death"
            elif process_identity(guard["pid"])!=guard:reason="guard-death"
            elif time.monotonic()>=deadline:reason="deadline"
            elif sample["cpu_percent"]>=75 or sample["ram_percent"]>=75:reason="resource-abort"
            else:time.sleep(max(.5,interval))
        atomic_json(output/"monitor.json",{"schema_version":1,"controller":controller,"guard":guard,"watchdog":process_identity(os.getpid()),"deadline_monotonic":deadline,"reason":reason,"samples":observed})
    except BaseException as error:primary=error;reason=reason or "monitor-failure";secondary("monitor",error)
    try:result=cleanup_owned(spec,daemon,output/"cleanup",reason,primary=primary,abort_first=True)
    except BaseException as error:
        if primary is None:primary=error
        secondary("cleanup",error)
        ledger=output/"cleanup/cleanup.json"
        if ledger.exists():
            try:result=json.loads(ledger.read_bytes())
            except BaseException as read_error:secondary("cleanup-ledger-read",read_error)
    try:
        retention=TreeRetention(output/"retained-trees")
        for name in ("runner_root","fixture_root"):
            try:retention.capture(spec.paths[name],name)
            except BaseException as error:secondary(name,error)
    except BaseException as error:secondary("retention-setup",error)
    final={"schema_version":1,"reason":reason,"status":"failed" if primary is not None or errors or result is None or result.get("status")!="passed" else "passed",
           "primary_exception":None if primary is None else {"type":type(primary).__name__,"message":str(primary)},"errors":errors,"cleanup":result,"remaining_ids":None,"remaining_networks":None}
    try:
        final["remaining_ids"]=daemon.containers();final["remaining_networks"]=[entry["Id"] for entry in daemon.networks()]
        if final["remaining_ids"] or final["remaining_networks"]:
            secondary("final-inventory",CleanupError("owned daemon objects appeared or remain after retention"));final["status"]="failed"
    except BaseException as error:secondary("final-inventory",error);final["status"]="failed"
    try:atomic_json(output/"watch-final.json",final)
    except BaseException as error:
        secondary("watch-finalization",error)
        if primary is None:primary=error
        final["status"]="failed";final["primary_exception"]={"type":type(primary).__name__,"message":str(primary)}
        try:atomic_json(output/"watch-final.json",final)
        except BaseException as last:secondary("failure-ledger-finalization",last)
    if primary is not None:raise primary
    if final["status"]!="passed":raise CleanupError("watchdog cleanup or retention failed; retained watch-final.json")
    result["retention_errors"]=errors
    return result


class RetainedTemporaryDirectory:
    def __init__(self,registry,*args,**kwargs):
        if Path(kwargs.get("dir","")).resolve()!=registry.fixture_root:raise OwnershipError("fixture temporary directory outside owned prefix")
        self.registry=registry;self.inner=tempfile.TemporaryDirectory(*args,**kwargs);self.name=self.inner.name;self.cleaned=False
        registry.directories.append(self)
    def cleanup(self):
        if self.cleaned:return
        self.registry.retention.capture(self.name,"runner-fixture")
        self.inner.cleanup();self.cleaned=True
    def __enter__(self):return self.name
    def __exit__(self,kind,value,trace):
        try:self.cleanup()
        except BaseException as error:
            if value is None:raise
            if hasattr(value,"add_note"):value.add_note("fixture cleanup: "+str(error))
            self.registry.errors.append({"type":type(error).__name__,"message":str(error)})
        return False


class FixtureRegistry:
    def __init__(self,fixture_root,artifacts):
        self.fixture_root=Path(fixture_root).resolve();self.fixture_root.mkdir(parents=True,exist_ok=True)
        self.retention=TreeRetention(artifacts);self.directories=[];self.errors=[]
    def temporary_directory(self,*args,**kwargs):return RetainedTemporaryDirectory(self,*args,**kwargs)
    def finish(self,primary=None):
        for directory in self.directories:
            try:directory.cleanup()
            except BaseException as error:
                self.errors.append({"type":type(error).__name__,"message":str(error)})
                if primary is not None and hasattr(primary,"add_note"):primary.add_note("retention: "+str(error))
        try:atomic_json(self.retention.root/"registry.json",{"schema_version":1,"errors":self.errors,"directories":[{"path":entry.name,"cleaned":entry.cleaned} for entry in self.directories]})
        except BaseException as error:
            if primary is None:raise
            if hasattr(primary,"add_note"):primary.add_note("registry finalization: "+str(error))
        if primary is None and self.errors:raise CleanupError("fixture retention failed")


_registry=None
def runner_registry():
    global _registry
    if _registry is None:
        config=json.loads(Path(__file__).with_name("owned-runner.json").read_bytes())
        _registry=FixtureRegistry(config["fixture_root"],config["retained_fixtures"])
    return _registry
def temporary_directory(*args,**kwargs):return runner_registry().temporary_directory(*args,**kwargs)
def author_execute(main):
    primary=None
    try:return main()
    except BaseException as error:primary=error;raise
    finally:
        try:runner_registry().finish(primary)
        except BaseException as secondary:
            if primary is None:raise
            if hasattr(primary,"add_note"):primary.add_note("registry cleanup: "+str(secondary))
            failure={"schema_version":1,"primary":{"type":type(primary).__name__,"message":str(primary)},
                     "secondary":{"type":type(secondary).__name__,"message":str(secondary)},"errors":[]}
            directory=Path(__file__).parent
            try:
                config=json.loads(Path(__file__).with_name("owned-runner.json").read_bytes())
                directory=Path(config["owner_spec"]["artifacts"])
            except BaseException as config_error:
                failure["errors"].append({"stage":"failure-ledger-config","type":type(config_error).__name__,"message":str(config_error)})
                if hasattr(primary,"add_note"):primary.add_note("author failure ledger config: "+str(config_error))
            try:atomic_json(directory/"author-finalization-failure.json",failure)
            except BaseException as final:
                failure["errors"].append({"stage":"failure-ledger-write","type":type(final).__name__,"message":str(final)})
                if hasattr(primary,"add_note"):primary.add_note("author failure ledger: "+str(final))
                try:atomic_json(Path(__file__).parent/"author-finalization-failure.json",failure)
                except BaseException as last:
                    if hasattr(primary,"add_note"):primary.add_note("author fallback ledger: "+str(last))

def retained_cleanup_dir(directory):
    registry=runner_registry()
    entry=next((value for value in registry.directories if value.name==directory),None)
    if entry is None:raise OwnershipError("cleanup of unregistered fixture refused")
    registry.retention.capture(directory,"pre-cleanup-fixture")


def derive_runner(pinned,destination,spec,registry_images):
    """Copy exact pinned sources and apply setup-only changes in a new tree."""
    import yaml
    pinned=Path(pinned);destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    originals={};original_bindings={}
    command_records=RawCommands(destination/"preparation-commands")
    git=shutil.which("git")
    names=command_records.run([git,"-C",str(pinned),"ls-tree","-r","--name-only",PIN],10).decode().splitlines()
    for name in names:
        data=command_records.run([git,"-C",str(pinned),"show",PIN+":"+name],10);originals[name]=data
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        retained=destination/"pinned-originals"/name;retained.parent.mkdir(parents=True,exist_ok=True);retained.write_bytes(data)
        copied=retained.read_bytes();after=command_records.run([git,"-C",str(pinned),"show",PIN+":"+name],10)
        before={"sha256":digest(data),"bytes":len(data)}
        original_bindings[name]={"original_before":before,"retained":{"sha256":digest(copied),"bytes":len(copied)},"original_after":{"sha256":digest(after),"bytes":len(after)},"retained_path":retained.relative_to(destination).as_posix()}
        if before!=original_bindings[name]["retained"] or before!=original_bindings[name]["original_after"]:raise OwnershipError("pinned source bytes changed during retention")
    for name,expected in PINNED.items():
        if digest(originals[name])!=expected:raise OwnershipError("pinned runner source hash differs: "+name)
    changes={}
    for name in ("interop.py","testcase.py","testcases_quic.py"):
        data=originals[name].decode()
        data=data.replace('dir="/tmp"','dir='+repr(str(spec.paths["fixture_root"])))
        data=data.replace("tempfile.TemporaryDirectory(","_AuthorTemporaryDirectory(")
        data="from owned_adapter import temporary_directory as _AuthorTemporaryDirectory\n"+data
        if name=="testcase.py":
            node=next(node for node in ast.parse(data).body if isinstance(node,ast.FunctionDef) and node.name=="docker_cleanup_dir")
            lines=data.splitlines(keepends=True)
            lines[node.lineno-1:node.end_lineno]=['def docker_cleanup_dir(directory: str):\n','    from owned_adapter import retained_cleanup_dir\n','    retained_cleanup_dir(directory)\n']
            data="".join(lines)
        (destination/name).write_text(data);changes[name]=digest(data.encode())
    # Criteria source must differ only in fixture constructor/path spelling.
    normalized=(destination/"testcases_quic.py").read_text().removeprefix("from owned_adapter import temporary_directory as _AuthorTemporaryDirectory\n")
    normalized=normalized.replace("_AuthorTemporaryDirectory(","tempfile.TemporaryDirectory(").replace("dir="+repr(str(spec.paths["fixture_root"])),'dir="/tmp"')
    if normalized.encode()!=originals["testcases_quic.py"]:raise OwnershipError("official testcase criteria changed")
    compose=yaml.safe_load(originals["docker-compose.yml"])
    for role,service in compose["services"].items():
        service["container_name"]=spec.project+"-"+role
        if role in ROLES:
            service["labels"]={OWNER_LABEL:spec.nonce};service["cpuset"]="7";service["cpus"]=1.0
        if role in ("server","client"):
            service["user"]="65534:65534";service.pop("cap_add",None);service["cap_drop"]=["ALL"];service["security_opt"]=["no-new-privileges:true"]
        if role=="sim":service["image"]=spec.images["sim"][0]
    for network in compose["networks"].values():network["labels"]={OWNER_LABEL:spec.nonce}
    (destination/"docker-compose.yml").write_text(json.dumps(compose,indent=2)+"\n")
    implementations=json.loads(originals["implementations_quic.json"])
    for name,image in registry_images.items():
        if not isinstance(image,str) or re.fullmatch(r"sha256:[0-9a-f]{64}",image) is None:raise OwnershipError("registry image must be pinned ID")
        if name=="minyar":implementations[name]={"image":image,"url":"local-minyar-fixture","role":"both"}
        else:
            if name not in implementations:raise OwnershipError("unknown official peer")
            implementations[name]["image"]=image
    (destination/"implementations_quic.json").write_text(json.dumps(implementations,indent=2)+"\n")
    interop=(destination/"interop.py").read_text()
    tree=ast.parse(interop)
    method=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=="_copy_logs")
    lines=interop.splitlines(keepends=True)
    lines[method.lineno-1:method.end_lineno]=["    def _copy_logs(self, container, directory):\n", "        from owned_adapter import copy_runner_logs\n", "        copy_runner_logs(container, directory.name)\n"]
    (destination/"interop.py").write_text("".join(lines))
    run=originals["run.py"].decode()
    if run.count("    sys.exit(main())")!=1:raise OwnershipError("unexpected runner entrypoint")
    run=run.replace("    sys.exit(main())","    from owned_adapter import author_execute\n    sys.exit(author_execute(main))")
    (destination/"run.py").write_text(run)
    (destination/"owned_adapter.py").write_bytes(Path(__file__).read_bytes())
    docker=shutil.which("docker")
    atomic_json(destination/"owned-runner.json",{"fixture_root":str(spec.paths["fixture_root"]),"retained_fixtures":str(spec.paths["artifacts"]/"fixtures"),"owner_spec":spec.value,"execution_authorized":False,"docker_cli":None if docker is None else binding(docker)})
    wrapper=destination/"owned-bin"/"docker";wrapper.parent.mkdir()
    wrapper.write_text("#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\nfrom owned_adapter import docker_entry\nraise SystemExit(docker_entry(sys.argv[1:]))\n")
    wrapper.chmod(0o700)
    report={"schema_version":1,"runner_commit":PIN,"original_files":{name:{"sha256":digest(data),"bytes":len(data)} for name,data in originals.items()},
            "derived_files":{path.relative_to(destination).as_posix():binding(path) for path in sorted(destination.rglob("*")) if path.is_file()},
            "original_bindings":original_bindings,"preparation_commands":command_records.rows,
            "official_criteria_unchanged":True,"scope":"source preparation only; no runner, Docker or network execution"}
    atomic_json(destination/"derivation.json",report)
    return report


def compose_up_argv(spec,argv):
    """Validate upstream up options; bind private project/file and never pull."""
    if not isinstance(argv,list) or len(argv)<4 or argv[:3]!=["compose","--env-file","empty.env"] or argv[3]!="up":raise OwnershipError("unreviewed compose command")
    allowed={"--timeout","--abort-on-container-exit","-V"}
    roles=[];index=4
    while index<len(argv):
        token=argv[index]
        if token in ROLES:roles.append(token);index+=1
        elif token=="--timeout":
            if index+1>=len(argv) or argv[index+1] not in ("0","10"):raise OwnershipError("unreviewed compose timeout")
            index+=2
        elif token in allowed:index+=1
        else:raise OwnershipError("unreviewed compose option or workload")
    if not roles or len(set(roles))!=len(roles):raise OwnershipError("exact selected compose roles required")
    return ["compose","--project-name",spec.project,"--file",str(spec.paths["compose_path"]),"--env-file",str(spec.paths["runner_root"]/"empty.env"),"up","--pull","never",*argv[4:]]




def prepare_fixture_access(spec,daemon):
    """Prepare only verified ephemeral bind trees for nonroot endpoints."""
    identities=daemon.containers()
    if len(identities)!=len(set(identities)) or len(identities)>3:raise OwnershipError("ambiguous fixture endpoint IDs")
    mounts=[]
    for identity in identities:
        entry=daemon.inspect(identity)
        if entry.get("Id")!=identity:raise OwnershipError("fixture endpoint ID mismatch")
        role=spec.container(entry)
        if role!="sim":mounts.extend(entry["Mounts"])
    verified_topology(spec,[daemon.inspect(identity) for identity in identities],daemon.networks())
    candidates=[(spec.paths["fixture_root"],0o755)]
    for mount in mounts:
        root=Path(mount["Source"])
        for ancestor in root.parents:
            if ancestor==spec.paths["fixture_root"]:break
            if spec.paths["fixture_root"] not in ancestor.parents:raise OwnershipError("fixture ancestor outside owned prefix")
            candidates.append((ancestor,0o755))
        for path in __import__("itertools").chain((root,),bounded_paths(root,MAX_FILES,time.monotonic()+30)):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):raise OwnershipError("unreviewed fixture path")
            mode=(0o777 if path.is_dir() else 0o666) if mount["Destination"]=="/downloads" else (0o755 if path.is_dir() else 0o644)
            candidates.append((path,mode))
    receipt=[]
    for path,mode in candidates:
        before=path.stat().st_mode&0o777
        path.chmod(mode)
        after=path.stat().st_mode&0o777
        if after!=mode:raise OwnershipError("fixture permission preparation failed")
        receipt.append({"path":str(path),"mode_before":before,"mode_after":after})
    return {"schema_version":1,"scope":"ephemeral verified endpoint bind mounts only","verified_ids":identities,"permissions":receipt}

def runner_daemon():
    config=json.loads(Path(__file__).with_name("owned-runner.json").read_bytes())
    if config.get("execution_authorized") is not True:raise OwnershipError("official Docker execution remains held")
    spec=OwnerSpec(config["owner_spec"])
    cli=config.get("docker_cli",{})
    if binding(cli.get("path",""))!=cli:raise OwnershipError("configured Docker CLI binding differs")
    return spec,DockerDaemon(spec,spec.paths["artifacts"]/"daemon-commands",allow_real=True,docker_path=cli["path"])


def copy_runner_logs(role,directory):
    spec,daemon=runner_daemon()
    if role not in ROLES:raise OwnershipError("unknown runner log role")
    directory=Path(directory).resolve()
    if spec.paths["fixture_root"] not in directory.parents:raise OwnershipError("log copy outside fixture tree")
    ids=[]
    for identity in daemon.containers():
        entry=daemon.inspect(identity)
        if spec.container(entry)==role:ids.append(identity)
    if len(ids)!=1:raise OwnershipError("log copy requires one verified immutable endpoint ID")
    daemon.copy_bounded(ids[0],"/logs/.",directory)


@contextlib.contextmanager
def admission_lock(spec,timeout=2):
    path=spec.paths["artifacts"]/"admission.lock"
    with path.open("a+b") as lock:
        deadline=time.monotonic()+timeout
        while True:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise CleanupError("admission lock deadline exceeded")
                time.sleep(.01)
        try:yield
        finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def require_admission(spec):
    if (spec.paths["artifacts"]/"admission-revoked.json").exists():raise OwnershipError("daemon creation admission permanently revoked")
    path=spec.paths["artifacts"]/"create-admission.json"
    if path.exists():
        value=json.loads(path.read_bytes())
        if value.get("project")!=spec.project or value.get("nonce")!=spec.nonce or value.get("state")=="interrupted-uncertified":raise OwnershipError("creation admission is interrupted or foreign")

def admission_write(spec,value):
    with admission_lock(spec):
        require_admission(spec)
        atomic_json(spec.paths["artifacts"]/"create-admission.json",value)

def close_admission(spec,revoke=True):
    path=spec.paths["artifacts"]/"create-admission.json"
    with admission_lock(spec):
        if revoke:
            revoked=spec.paths["artifacts"]/"admission-revoked.json"
            if not revoked.exists():atomic_json(revoked,{"schema_version":1,"project":spec.project,"nonce":spec.nonce,"revoked":True})
        if not path.exists():return {"state":"not-opened","certified":True,"revoked":revoke}
        value=json.loads(path.read_bytes())
        if value.get("project")!=spec.project or value.get("nonce")!=spec.nonce:raise OwnershipError("create intent ownership differs")
    if value.get("state")!="closed":
        errors=[]
        root=spec.paths["artifacts"]/"daemon-commands"
        for record_path in bounded_paths(root,MAX_FILES,time.monotonic()+10) if root.exists() else ():
            if record_path.name!="commands.json":continue
            receipt=json.loads(record_path.read_bytes())
            for command in receipt.get("commands",[]):
                identity=command.get("process_identity")
                if not isinstance(identity,dict) or type(identity.get("pid")) is not int or type(identity.get("start_ticks")) is not int:continue
                known={}
                for member in command.get("lifetime",{}).get("members",[]):
                    if not isinstance(member,dict) or any(type(member.get(key)) is not int for key in ("pid","start_ticks","pgid","session")):raise OwnershipError("CLI descendant receipt types differ")
                    if process_identity(member["pid"])=={"pid":member["pid"],"start_ticks":member["start_ticks"]}:known[member["pid"]]=member
                actions=[]
                drain_cli(identity,known,actions,time.monotonic()+2,adopt=False)
                errors.extend(actions)
        value["state"]="interrupted-uncertified";value["certified"]=False;value["owned_cli_abort_receipts"]=errors
        with admission_lock(spec):atomic_json(path,value)
        raise CleanupError("in-flight create/start admission cannot certify daemon absence")
    if value.get("certified") is not True:raise CleanupError("create admission did not close successfully")
    return value


def docker_entry(argv):
    spec,daemon=runner_daemon()
    if argv[:4]==["compose","--env-file","empty.env","up"]:
        with admission_lock(spec):require_admission(spec)
        command=compose_up_argv(spec,argv)
        for role in ("server","client"):
            if os.environ.get(role.upper()) not in spec.images[role]:raise OwnershipError("selected endpoint image is outside pinned cell")
        # A repeated upstream compliance phase may leave stopped owned objects.
        # Verify them and retain before removing; foreign collisions fail closed.
        if daemon.containers() or daemon.networks():
            index=len(list(spec.paths["artifacts"].glob("between-up-*")))
            phase_path=spec.paths["artifacts"]/"phase.json"
            phase=json.loads(phase_path.read_bytes()) if phase_path.exists() else {}
            cleanup_owned(spec,daemon,spec.paths["artifacts"]/("between-up-"+str(index)),"upstream-next-phase",unsupported_compliance=phase.get("unsupported_compliance"),revoke_admission=False)
        requested=argv[4:]
        role="client" if requested[-2:]==["sim","client"] else "server" if requested==["-V","server"] else None
        testcase=None if role is None else os.environ.get("TESTCASE_"+role.upper())
        known=("handshake","transfer","retry","resumption","zerortt","multiconnect","rebind-port","rebind-addr","chacha20","keyupdate","connectionmigration")
        unsupported=None if role is None or not testcase or testcase in known else {"role":role,"testcase":testcase}
        atomic_json(spec.paths["artifacts"]/"phase.json",{"schema_version":1,"actual_argv":command,"unsupported_compliance":unsupported,"selected_images":{role:os.environ.get(role.upper()) for role in ("server","client")}})
        requested_roles=[token for token in requested if token in ROLES]
        roles=[r for r in ROLES if r in requested_roles or (r=="sim" and any(v in ("server","client") for v in requested_roles))]
        prefix=command[:command.index("up")]
        create=prefix+(["up","--no-start","--pull","never","--no-build","-V"] if "-V" in requested else ["create","--pull","never","--no-build","--no-recreate"])+roles
        intent={"schema_version":1,"project":spec.project,"nonce":spec.nonce,"state":"creating","certified":False,
                "intended_containers":[{"name":spec.project+"-"+r,"role":r,"image":spec.images["sim"][0] if r=="sim" else os.environ[r.upper()],"labels":spec.labels(r)} for r in roles],
                "create_argv":create,"upstream_argv":argv,"workload_argv":command}
        admission_write(spec,intent)
        try:
            daemon.command(*create,timeout=30)
            created_ids=daemon.containers()
            created_entries=[daemon.inspect(identity) for identity in created_ids]
            if {spec.container(entry) for entry in created_entries}!=set(roles) or len(created_ids)!=len(roles):raise OwnershipError("created endpoint roles differ from intent")
            if any(entry.get("State",{}).get("Running") is not False for entry in created_entries):raise OwnershipError("endpoint started before fixture preparation")
            created_networks=daemon.networks()
            configured_topology(spec,created_entries,created_networks)
            verified_topology(spec,created_entries,created_networks)
            permissions=prepare_fixture_access(spec,daemon)
            atomic_json(spec.paths["artifacts"]/"fixture-permissions.json",permissions)
            intent["state"]="starting";intent["created_ids"]=created_ids
            admission_write(spec,intent)
            # Preserve explicit upstream monitored roles and dependency startup.
            # Expanded precreate ownership must not expand attached monitoring;
            # all dependency IDs stay identical and interrupted up is nonpass.
            up_index=command.index("up")
            command=command[:up_index+1]+["--no-build","--no-recreate"]+[token for token in command[up_index+1:] if token not in ROLES and token!="-V"]+requested_roles
            intent["workload_argv"]=command;admission_write(spec,intent)
            raw=daemon.command(*command,timeout=330,check=False)
            up_receipt=dict(daemon.commands.rows[-1])
            intent["up_receipt"]=up_receipt
            if set(daemon.containers())!=set(created_ids):raise OwnershipError("workload container IDs changed after precreate")
            verified_topology(spec,[daemon.inspect(identity) for identity in created_ids],daemon.networks())
            rows=daemon.commands.rows
            if any(row.get("lifetime",{}).get("root_exited_with_descendants") for row in rows):raise CleanupError("compose root exited with active descendants; admission uncertified")
            intent["state"]="closed";intent["certified"]=True;intent["workload_status"]=up_receipt["status"]
            admission_write(spec,intent)
        except BaseException as primary:
            intent["state"]="interrupted-uncertified";intent["primary_exception"]={"type":type(primary).__name__,"message":str(primary)}
            try:admission_write(spec,intent)
            except BaseException as secondary:
                if hasattr(primary,"add_note"):primary.add_note("admission failure ledger: "+str(secondary))
            raise
        sys.stdout.buffer.write(raw)
        sys.stderr.buffer.write(Path(up_receipt["stderr"]["path"]).read_bytes())
        return up_receipt["status"]
    if argv[:4]==["compose","--env-file","empty.env","stop"]:
        roles=argv[4:]
        if not roles or any(role not in ROLES for role in roles) or len(roles)!=len(set(roles)):raise OwnershipError("unreviewed stop roles")
        ids=[]
        for identity in daemon.containers():
            if spec.container(daemon.inspect(identity)) in roles:ids.append(identity)
        for identity in ids:daemon.stop(identity)
        return 0
    raise OwnershipError("Docker operation outside reviewed official adapter")

def owned_exec(fd,argv):
    # Parent publishes immutable command PID/birthday under the admission lock
    # before releasing this child. Parent death before publication closes EOF.
    deadline=time.monotonic()+5
    readable,_,_=select.select([fd],[],[],max(0,deadline-time.monotonic()))
    if not readable or os.read(fd,1)!=b"G":return 125
    os.close(fd)
    if not isinstance(argv,list) or not argv or any(not isinstance(v,str) for v in argv):return 125
    os.execv(argv[0],argv)
    return 125

def main():
    if len(sys.argv)==5 and sys.argv[1]=="--owned-exec-fd" and sys.argv[3]=="--owned-exec-json":
        return owned_exec(int(sys.argv[2]),json.loads(sys.argv[4]))
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--mock-watch",type=Path);parser.add_argument("--spec",type=Path);parser.add_argument("--controller",type=Path);parser.add_argument("--guard",type=Path)
    parser.add_argument("--deadline",type=float);parser.add_argument("--output",type=Path);args=parser.parse_args()
    if not all((args.mock_watch,args.spec,args.controller,args.guard,args.deadline,args.output)):parser.error("only explicit mocked watchdog controls are exposed")
    spec=OwnerSpec(json.loads(args.spec.read_bytes()))
    watch_owned(spec,JsonDaemon(args.mock_watch),json.loads(args.controller.read_bytes()),json.loads(args.guard.read_bytes()),args.deadline,args.output,interval=.05)
    return 0
if __name__=="__main__":raise SystemExit(main())
