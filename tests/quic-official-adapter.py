#!/usr/bin/env python3
"""Mock daemon and harmless process controls; no Docker or network execution."""
import argparse
import contextlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

MODULE=Path(__file__).parent/"interop/qns/owned_adapter.py"
LOADED_INPUT_BYTES={"driver":Path(__file__).read_bytes(),"helper":MODULE.read_bytes()}
spec=importlib.util.spec_from_file_location("owned_adapter",MODULE)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
CASES=("successful-cleanup","partial-setup-retention","controller-death","guard-death",
       "deadline","resource-abort","unknown-container-id","colliding-service","wrong-label",
       "wrong-image","cleanup-command-failure","primary-retention-failure","retention-bounds","criteria-no-pull",
       "tree-primary-finalization","raw-nonzero-status","root-exited-descendant","unexpected-endpoint-exit","unsupported-compliance-exit",
       "controller-before-create","controller-partial-create","controller-before-retention","controller-after-criterion","retention-late-mutation",
       "raw-evidence-reuse","raw-primary-finalization","duplicate-container-ids","wrong-network-label","unowned-network-member","fixture-access","fixture-access-unowned")
IMAGE="sha256:"+"a"*64;PEER="sha256:"+"b"*64;SIM="sha256:"+"c"*64


def setup(root):
    paths={name:root/name for name in ("runner","fixtures","evidence")}
    for path in paths.values():path.mkdir()
    value={"schema_version":1,"runner_commit":adapter.PIN,"project":"minyar-qns-"+"d"*24,"nonce":"e"*64,
           "images":{"sim":[SIM],"server":[IMAGE,PEER],"client":[IMAGE,PEER]},
           "runner_root":str(paths["runner"]),"compose_path":str(paths["runner"]/"docker-compose.yml"),
           "fixture_root":str(paths["fixtures"]),"artifacts":str(paths["evidence"])}
    owner=adapter.OwnerSpec(value);containers={}
    for index,role in enumerate(adapter.ROLES):
        identity=str(index+1)*64
        mounts=[]
        if role!="sim":
            for destination in ("/www","/downloads","/certs"):
                source=paths["fixtures"]/(role+destination.replace("/","-"));source.mkdir()
                (source/"fixture").write_bytes((role+destination).encode())
                mounts.append({"Type":"bind","Source":str(source),"Destination":destination,"RW":destination=="/downloads"})
        labels=owner.labels(role)
        labels.update({"com.docker.compose.project.working_dir":str(paths["runner"]),"com.docker.compose.project.config_files":str(paths["runner"]/"docker-compose.yml")})
        containers[identity]={"Id":identity,"Name":"/"+owner.project+"-"+role,"Image":SIM if role=="sim" else IMAGE,
                             "Config":{"Labels":labels,"User":"" if role=="sim" else "65534:65534"},
                             "Mounts":mounts,"State":{"Running":True,"ExitCode":0},
                             "HostConfig":{"Privileged":False,"NetworkMode":owner.project+("_leftnet" if role=="client" else "_rightnet"),
                                           "CpusetCpus":"7","NanoCpus":1000000000,"CapAdd":["NET_ADMIN","NET_RAW"] if role=="sim" else None,
                                           "CapDrop":None if role=="sim" else ["ALL"],"SecurityOpt":[] if role=="sim" else ["no-new-privileges:true"]}}
    for entry in containers.values():
        role=entry["Config"]["Labels"]["com.docker.compose.service"]
        entry["HostConfig"].update({"PidMode":"","IpcMode":"private"})
        entry["NetworkSettings"]={"Networks":{owner.project+"_"+name:{"NetworkID":("7" if name=="leftnet" else "8")*64} for name in adapter.NETWORK_ROLES[role]}}
    networks={}
    for index,name in enumerate(("leftnet","rightnet")):
        identity=str(index+7)*64
        networks[identity]={"Id":identity,"Name":owner.project+"_"+name,"Labels":owner.labels(),"Driver":"bridge","Internal":False,
                            "Containers":{key:{} for key,entry in containers.items() if owner.project+"_"+name in entry["NetworkSettings"]["Networks"]}}
    state=root/"daemon.json";adapter.atomic_json(state,{"scope":"mock daemon only","containers":containers,"networks":networks,"events":[]})
    adapter.atomic_json(root/"spec.json",value)
    return owner,adapter.JsonDaemon(state)


def stopped_or_error(owner,daemon,root,reason="control",primary=None):
    try:return adapter.cleanup_owned(owner,daemon,root/"cleanup",reason,primary)
    except adapter.CleanupError:
        return json.loads((root/"cleanup/cleanup.json").read_bytes())


def mock_cleanup(case,root):
    owner,daemon=setup(root);state=daemon.read()
    if case=="partial-setup-retention":
        state["containers"]={"2"*64:state["containers"]["2"*64]}
        state["networks"]={"8"*64:state["networks"]["8"*64]}
        state["networks"]["8"*64]["Containers"]={"2"*64:{}}
        adapter.atomic_json(daemon.path,state)
        registry=adapter.FixtureRegistry(owner.paths["fixture_root"],root/"retained-fixtures")
        temp=registry.temporary_directory(dir=str(owner.paths["fixture_root"]),prefix="partial-")
        payload=Path(temp.name)/"server.pk8";payload.write_bytes(b"mock private fixture bytes")
        original=RuntimeError("controlled partial setup failure")
        registry.finish(original)
        result=stopped_or_error(owner,daemon,root,primary=original)
        result["checks"]={"fixture_retained":any(value["files"].get("server.pk8",{}).get("original_before",{}).get("sha256")==adapter.digest(b"mock private fixture bytes") for value in registry.retention.rows),
                          "source_fixture_cleaned":not Path(temp.name).exists(),"primary_identity":result["primary_exception"]["message"]==str(original)}
    else:
        if case=="unknown-container-id":
            entry=state["containers"].pop("2"*64);entry["Id"]="2"*12;state["containers"]["2"*12]=entry
        elif case=="colliding-service":
            state["containers"]["3"*64]["Config"]["Labels"]["com.docker.compose.service"]="server"
        elif case=="wrong-label":state["containers"]["2"*64]["Config"]["Labels"][adapter.OWNER_LABEL]="f"*64
        elif case=="wrong-image":state["containers"]["2"*64]["Image"]="sha256:"+"f"*64
        elif case=="cleanup-command-failure":state["fail"]="stop"
        elif case=="unexpected-endpoint-exit":state["containers"]["2"*64]["State"]={"Running":False,"ExitCode":139}
        elif case=="wrong-network-label":state["networks"]["7"*64]["Labels"][adapter.OWNER_LABEL]="f"*64
        elif case=="unowned-network-member":state["networks"]["7"*64]["Containers"]["f"*64]={}
        adapter.atomic_json(daemon.path,state)
        if case=="duplicate-container-ids":daemon.containers=lambda:["2"*64,"2"*64]
        result=stopped_or_error(owner,daemon,root)
        events=daemon.read()["events"]
        rejected=case in ("unknown-container-id","colliding-service","wrong-label","wrong-image","duplicate-container-ids","wrong-network-label","unowned-network-member")
        result["checks"]={"no_unowned_mutation":not events if rejected else True,
                          "exact_immutable_ids":all(event["immutable_id"] is None or len(event["immutable_id"])==64 for event in events)}
        if case=="cleanup-command-failure":result["checks"].update({"failure_is_not_passed":result["status"]=="failed","remove_after_stop_failure":not daemon.containers()})
    expected="failed" if case in ("unknown-container-id","colliding-service","wrong-label","wrong-image","cleanup-command-failure","unexpected-endpoint-exit","duplicate-container-ids","wrong-network-label","unowned-network-member") else "passed"
    return result,expected


def process_control(case,root):
    owner,daemon=setup(root);children=[]
    if case.startswith("controller-") and case!="controller-death":
        state=daemon.read()
        count=0 if case=="controller-before-create" else 1 if case=="controller-partial-create" else 3
        state["containers"]={key:value for key,value in list(state["containers"].items())[:count]}
        for network in state["networks"].values():network["Containers"]={key:{} for key,entry in state["containers"].items() if network["Name"] in entry["NetworkSettings"]["Networks"]}
        adapter.atomic_json(daemon.path,state)
        adapter.atomic_json(root/"phase-marker.json",{"scope":"simulated controller phase; no official workload","phase":case,"created_objects":count})
    try:
        controller=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);children.append(controller)
        guard=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);children.append(guard)
        controller_id=adapter.process_identity(controller.pid);guard_id=adapter.process_identity(guard.pid)
        adapter.atomic_json(root/"controller.json",controller_id);adapter.atomic_json(root/"guard.json",guard_id)
        if case=="guard-death" or case.startswith("controller-"):
            deadline=time.monotonic()+4
            argv=[sys.executable,str(MODULE),"--mock-watch",str(daemon.path),"--spec",str(root/"spec.json"),
                  "--controller",str(root/"controller.json"),"--guard",str(root/"guard.json"),"--deadline",str(deadline),"--output",str(root/"watch")]
            with (root/"watch.stdout").open("wb") as out,(root/"watch.stderr").open("wb") as err:
                watcher=subprocess.Popen(argv,start_new_session=True,stdout=out,stderr=err);children.append(watcher)
                watcher_id=adapter.process_identity(watcher.pid)
                victim=guard if case=="guard-death" else controller
                victim.terminate();victim.wait(timeout=2)
                status=watcher.wait(timeout=6)
            adapter.atomic_json(root/"watch-command.json",{"argv":argv,"timeout_seconds":6,"status":status,"stdout":adapter.binding(root/"watch.stdout"),"stderr":adapter.binding(root/"watch.stderr"),
                                                         "watchdog_identity":watcher_id,"victim_identity":guard_id if case=="guard-death" else controller_id,
                                                         "separate_session":os.getpgid(os.getpid())!=watcher_id["pid"]})
            result=json.loads((root/"watch/cleanup/cleanup.json").read_bytes())
            monitor=json.loads((root/"watch/monitor.json").read_bytes())
            result["checks"]={"watcher_exit_zero":status==0,"independent_watch_survived_victim":monitor["reason"]==("guard-death" if case=="guard-death" else "controller-death"),
                              "watchdog_separate_session":os.getpgid(os.getpid())!=watcher_id["pid"],"all_daemon_objects_removed":not daemon.containers() and not daemon.networks()}
        else:
            samples=[{"cpu_percent":75.0,"ram_percent":0.0}] if case=="resource-abort" else None
            result=adapter.watch_owned(owner,daemon,controller_id,guard_id,time.monotonic()+.05,root/"watch",interval=.05,samples=samples)
            monitor=json.loads((root/"watch/monitor.json").read_bytes())
            result["checks"]={"exact_reason":monitor["reason"]==case,"threshold_not_loosened":case!="resource-abort" or monitor["samples"][0]["cpu_percent"]==75.0,
                              "abort_before_retention":case!="resource-abort" or [event["operation"] for event in daemon.read()["events"]][:3]==["abort"]*3}
        return result,"passed"
    finally:
        for child in reversed(children):
            if child.poll() is None:
                identity=adapter.process_identity(child.pid)
                if identity is not None:
                    child.terminate()
                    try:child.wait(timeout=2)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)



def tree_primary_control(root):
    owner,_=setup(root);tree=owner.paths["fixture_root"]/"partial";tree.mkdir();fixture=tree/"fixture";fixture.write_bytes(b"fixture")
    retention=adapter.TreeRetention(root/"retained")
    original=RuntimeError("original read failure");real_read=adapter.stream_binding;real_json=adapter.atomic_json;failed=[False]
    def read(path,*args,**kwargs):
        if Path(path)==fixture:raise original
        return real_read(path,*args,**kwargs)
    def write_json(path,value):
        if Path(path).name=="retention.json" and not failed[0]:
            failed[0]=True;raise OSError("secondary finalization failure")
        return real_json(path,value)
    adapter.stream_binding=read;adapter.atomic_json=write_json
    try:
        try:retention.capture(tree,"partial")
        except BaseException as caught:
            result={"status":"passed" if caught is original else "failed","checks":{"primary_identity":caught is original,"secondary_note":bool(getattr(original,"__notes__",[])),"secondary_ledger":any(error.get("stage")=="retention-finalization" for error in retention.errors)}}
        else:result={"status":"failed","checks":{"primary_identity":False}}
    finally:adapter.stream_binding=real_read;adapter.atomic_json=real_json
    return result,"passed"


def raw_status_control(root):
    records=adapter.RawCommands(root/"commands")
    argv=[sys.executable,"-c","import sys;sys.stdout.buffer.write(b'controlled unsupported\\n');sys.stderr.buffer.write(b'raw stderr\\n');raise SystemExit(127)"]
    data=records.run(argv,5,check=False)
    return {"status":"passed","checks":{"exact_nonzero_status":records.rows[0]["status"]==127,"raw_stdout":data==b"controlled unsupported\n","raw_stderr":Path(records.rows[0]["stderr"]["path"]).read_bytes()==b"raw stderr\n","actual_argv":records.rows[0]["argv"]==argv}},"passed"


def descendant_control(root):
    owner,daemon=setup(root);identity="2"*64
    child_source=root/"daemon-descendant.py"
    child_source.write_text("import json,os,sys,time\nfrom pathlib import Path\nroot=Path(sys.argv[3]);(root/'actual-parent.json').write_text(json.dumps({'parent_pid':os.getppid(),'pid':os.getpid()}))\nend=time.monotonic()+6\nwhile time.monotonic()<end:\n if sys.argv[2] not in json.loads(Path(sys.argv[1]).read_bytes())['containers']:\n  (root/'descendant-exit.json').write_text(json.dumps({'status':0}));raise SystemExit(0)\n time.sleep(.02)\n(root/'descendant-exit.json').write_text(json.dumps({'status':4}));raise SystemExit(4)\n")
    child_argv=[sys.executable,str(child_source),str(daemon.path),identity,str(root)]
    controller_source=root/"controller.py"
    controller_source.write_text("import json,subprocess,time\nfrom pathlib import Path\nroot=Path("+repr(str(root))+")\nwith (root/'descendant.stdout').open('wb') as out,(root/'descendant.stderr').open('wb') as err:\n child=subprocess.Popen("+repr(child_argv)+",start_new_session=True,stdout=out,stderr=err)\n (root/'descendant-pid.json').write_text(json.dumps({'pid':child.pid}))\ntime.sleep(.15)\n")
    controller_argv=[sys.executable,str(controller_source)]
    with (root/"controller.stdout").open("wb") as out,(root/"controller.stderr").open("wb") as err:
        controller=subprocess.Popen(controller_argv,start_new_session=True,stdout=out,stderr=err)
        controller_id=adapter.process_identity(controller.pid);descendant_id=None
        try:
            deadline=time.monotonic()+2
            while not (root/"descendant-pid.json").exists() and time.monotonic()<deadline:time.sleep(.01)
            descendant_pid=json.loads((root/"descendant-pid.json").read_bytes())["pid"]
            descendant_id=adapter.process_identity(descendant_pid)
            controller.wait(timeout=2)
            result=adapter.watch_owned(owner,daemon,controller_id,adapter.process_identity(os.getpid()),time.monotonic()+3,root/"watch",interval=.02)
            deadline=time.monotonic()+3
            while adapter.process_identity(descendant_pid)==descendant_id and time.monotonic()<deadline:time.sleep(.02)
            exit_record=json.loads((root/"descendant-exit.json").read_bytes())
            actual_parent=json.loads((root/"actual-parent.json").read_bytes())
            adapter.atomic_json(root/"descendant-command.json",{"argv":child_argv,"status":exit_record["status"],"timeout_seconds":3,"stdout":adapter.binding(root/"descendant.stdout"),"stderr":adapter.binding(root/"descendant.stderr"),"controller_argv":controller_argv,"controller_identity":controller_id,"descendant_identity":descendant_id,"controller_exit_status":controller.returncode,"actual_parent":actual_parent})
            result["checks"]={"controller_natural_exit":controller.returncode==0,"actual_descendant_parent":actual_parent["parent_pid"]==controller.pid,"separate_descendant_removed":exit_record["status"]==0 and adapter.process_identity(descendant_pid) is None,"daemon_ids_removed":not daemon.containers(),"controller_death_detected":result["reason"]=="controller-death"}
            return result,"passed"
        finally:
            if controller.poll() is None:controller.terminate();controller.wait(timeout=2)
            if descendant_id is not None and adapter.process_identity(descendant_id["pid"])==descendant_id:os.kill(descendant_id["pid"],signal.SIGTERM)

def unsupported_control(root):
    owner,daemon=setup(root);state=daemon.read()
    state["containers"]["2"*64]["State"]={"Running":False,"ExitCode":127}
    state["containers"]["2"*64]["Config"]["Env"]=["ROLE=server","TESTCASE=unknown-safe-control"]
    adapter.atomic_json(daemon.path,state)
    result=adapter.cleanup_owned(owner,daemon,root/"cleanup","unsupported-control",unsupported_compliance={"role":"server","testcase":"unknown-safe-control"})
    result["checks"]={"specific_unsupported_mode":result["states_before_cleanup"]["2"*64]["ExitCode"]==127,"all_owned_ids_removed":not daemon.containers()}
    return result,"passed"


def late_mutation_control(root):
    owner,_=setup(root);tree=owner.paths["fixture_root"]/"mutable";tree.mkdir()
    (tree/"a").write_bytes(b"original-a");(tree/"b").write_bytes(b"original-b")
    retention=adapter.TreeRetention(root/"retained");real_copy=adapter.stream_binding
    def copy(path,*args,**kwargs):
        result=real_copy(path,*args,**kwargs)
        copy_to=kwargs.get("copy_to",args[2] if len(args)>2 else None)
        if Path(path).name=="b" and copy_to is not None:(tree/"a").write_bytes(b"changed-after-first-copy")
        return result
    adapter.stream_binding=copy
    try:
        try:retention.capture(tree,"mutable")
        except adapter.OwnershipError as error:result={"status":"failed","reason":str(error)}
        else:result={"status":"passed"}
    finally:adapter.stream_binding=real_copy
    return result,"failed"


def raw_reuse_control(root):
    records=adapter.RawCommands(root/"commands");records.run([sys.executable,"-c","print('retained')"],5)
    prior=(root/"commands/commands.json").read_bytes()
    try:adapter.RawCommands(root/"commands")
    except FileExistsError:rejected=True
    else:rejected=False
    return {"status":"passed","checks":{"reused_artifact_root_rejected":rejected,"old_bytes_unchanged":(root/"commands/commands.json").read_bytes()==prior}},"passed"


def raw_primary_control(root):
    records=adapter.RawCommands(root/"commands");original=RuntimeError("original process setup failure")
    real_run=adapter.subprocess.Popen;real_json=adapter.atomic_json;failed=[False]
    def run(*args,**kwargs):raise original
    def write_json(path,value):
        if Path(path).name=="commands.json" and value["commands"][0].get("primary_exception") is not None and not failed[0]:failed[0]=True;raise OSError("secondary raw finalization failure")
        return real_json(path,value)
    adapter.subprocess.Popen=run;adapter.atomic_json=write_json
    try:
        try:records.run([sys.executable,"-c","pass"],5)
        except BaseException as caught:
            result={"status":"passed" if caught is original else "failed","checks":{"primary_identity":caught is original,"secondary_ledger":bool(records.rows[0]["finalization_errors"]),"secondary_note":bool(getattr(original,"__notes__",[])),"durable_failure":(root/"commands/commands.json").is_file()}}
        else:result={"status":"failed"}
    finally:adapter.subprocess.Popen=real_run;adapter.atomic_json=real_json
    return result,"passed"


def fixture_access_control(case,root):
    owner,daemon=setup(root);state=daemon.read()
    source=Path(state["containers"]["2"*64]["Mounts"][2]["Source"])/"fixture"
    source.chmod(0o600);before=source.stat().st_mode&0o777
    if case=="fixture-access-unowned":
        state["containers"]["3"*64]["Config"]["Labels"][adapter.OWNER_LABEL]="f"*64;adapter.atomic_json(daemon.path,state)
    try:
        receipt=adapter.prepare_fixture_access(owner,daemon)
        adapter.atomic_json(root/"permission-receipt.json",receipt)
        downloads=Path(state["containers"]["2"*64]["Mounts"][1]["Source"])
        result={"status":"passed","checks":{"ephemeral_cert_readable":source.stat().st_mode&0o777==0o644,"downloads_writable":downloads.stat().st_mode&0o777==0o777,"only_fixture_prefix":all(Path(row["path"])==owner.paths["fixture_root"] or owner.paths["fixture_root"] in Path(row["path"]).parents for row in receipt["permissions"])}}
    except adapter.OwnershipError as error:result={"status":"failed","reason":str(error),"checks":{"unowned_rejected_before_permission_change":source.stat().st_mode&0o777==before}}
    return result,"failed" if case=="fixture-access-unowned" else "passed"

def primary_retention(root):
    owner,_=setup(root)
    registry=adapter.FixtureRegistry(owner.paths["fixture_root"],root/"retained")
    original=RuntimeError("original setup failure")
    directory=registry.temporary_directory(dir=str(owner.paths["fixture_root"]),prefix="primary-")
    (Path(directory.name)/"fixture").write_bytes(b"retained fixture")
    real_capture=registry.retention.capture
    def capture(*args,**kwargs):raise OSError("controlled retention failure")
    registry.retention.capture=capture
    try:
        try:raise original
        except BaseException as primary:
            registry.finish(primary)
            raise
    except BaseException as caught:
        result={"status":"passed" if caught is original else "failed","checks":{"primary_identity":caught is original,"secondary_retained":bool(registry.errors),"secondary_note":bool(getattr(original,"__notes__",[]))}}
    finally:
        registry.retention.capture=real_capture;directory.inner.cleanup()
    adapter.atomic_json(root/"primary-result.json",result)
    return result,"passed"


def retention_bounds(root):
    owner,_=setup(root);tree=owner.paths["fixture_root"]/"large";tree.mkdir();(tree/"a").write_bytes(b"1234")
    retention=adapter.TreeRetention(root/"retained",max_bytes=3)
    try:retention.capture(tree,"bound")
    except adapter.OwnershipError as error:
        result={"status":"passed","checks":{"bound_fails_coverage":str(error)=="retention bound exceeded","failed_inventory_retained":retention.rows[0]["status"]=="failed"}}
    else:result={"status":"failed","checks":{"bound_fails_coverage":False}}
    return result,"passed"


def criteria_control(root,pinned):
    owner,_=setup(root)
    # The private derived tree is fresh. No upstream runner or daemon runs.
    owner.value["runner_root"]=str(root/"derived")
    owner.value["compose_path"]=str(root/"derived/docker-compose.yml")
    owner=adapter.OwnerSpec(owner.value)
    report=adapter.derive_runner(pinned,root/"derived",owner,{"minyar":IMAGE,"quiche":PEER})
    good=adapter.compose_up_argv(owner,["compose","--env-file","empty.env","up","--abort-on-container-exit","--timeout","10","sim","client","server"])
    rejected=0
    for command in (["pull","anything"],["compose","--env-file","empty.env","up","--pull","always","server"],["compose","--env-file","empty.env","up","iperf_client"],["compose","--env-file","empty.env","up","--build","server"]):
        try:adapter.compose_up_argv(owner,command)
        except adapter.OwnershipError:rejected+=1
    config=json.loads((root/"derived/owned-runner.json").read_bytes())
    wrapper=root/"derived/owned-bin/docker"
    process=subprocess.run([sys.executable,str(wrapper),"compose","--env-file","empty.env","up","server"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
    (root/"wrapper.stdout").write_bytes(process.stdout);(root/"wrapper.stderr").write_bytes(process.stderr)
    adapter.atomic_json(root/"wrapper-command.json",{"argv":[sys.executable,str(wrapper),"compose","--env-file","empty.env","up","server"],"status":process.returncode,"timeout_seconds":5,"stdout":adapter.binding(root/"wrapper.stdout"),"stderr":adapter.binding(root/"wrapper.stderr")})
    return {"status":"passed","checks":{"official_criteria_unchanged":report["official_criteria_unchanged"],"pinned_original_hash":report["original_files"]["testcases_quic.py"]["sha256"]==adapter.PINNED["testcases_quic.py"],
                                      "explicit_never_pull":good[good.index("--pull")+1]=="never","exact_project":good[good.index("--project-name")+1]==owner.project,
                                      "all_unreviewed_commands_rejected":rejected==4,"execution_stays_held":config["execution_authorized"] is False and process.returncode!=0 and b"official Docker execution remains held" in process.stderr}},"passed"


ROUND2_CASES=("startup-permissions-before-start","watch-cleanup-retains-tree","watch-sample-failure","watch-identity-failure","watch-monitor-failure","author-registry-primary","late-reinspection-failure","foreign-network-mode","host-pid-mode","host-ipc-mode","extra-network-membership","wrong-network-id","raw-cli-exited-descendant","raw-cli-delayed-create","retention-stream-bound","retention-lazy-file-bound","retention-final-deadline","copy-size-bound")
CASES+=ROUND2_CASES

def startup_control(root,case="startup-permissions-before-start"):
    owner,base=setup(root);template=base.read();events=[]
    for entry in template["containers"].values():
        entry["State"]={"Running":False,"ExitCode":0}
        for mount in entry["Mounts"]:
            Path(mount["Source"]).chmod(0o700)
            (Path(mount["Source"])/"fixture").chmod(0o600)
    adapter.atomic_json(base.path,{"containers":{},"networks":{},"events":[]})
    class MockCompose(adapter.JsonDaemon):
        def __init__(self,path):
            super().__init__(path);self.commands=type("Rows",(),{"rows":[]})()
        def command(self,*args,**kwargs):
            operation=next((part for part in args if part in ("up","create","start")),None)
            events.append(operation)
            if operation=="create":
                selected={r for r in args if r in adapter.ROLES};created=json.loads(json.dumps(template));created["containers"]={k:v for k,v in created["containers"].items() if v["Config"]["Labels"]["com.docker.compose.service"] in selected}
                for network in created["networks"].values():network["Containers"]={k:v for k,v in network["Containers"].items() if k in created["containers"]}
                adapter.atomic_json(self.path,created)
            elif operation=="up" and not self.containers():adapter.atomic_json(self.path,template)
            if operation in ("up","start"):
                entries=self.read()["containers"].values()
                readable=all(Path(m["Source"]).stat().st_mode&0o777==(0o777 if m["Destination"]=="/downloads" else 0o755) and (Path(m["Source"])/"fixture").stat().st_mode&0o777==(0o666 if m["Destination"]=="/downloads" else 0o644) for e in entries for m in e["Mounts"])
                events.append("permissions-ready" if readable else "permissions-private")
            stderr=root/("command-"+str(len(events))+".stderr");stderr.write_bytes(b"")
            self.commands.rows.append({"status":0,"stderr":adapter.binding(stderr)})
            return b""
    daemon=MockCompose(base.path);real=adapter.runner_daemon;old={k:os.environ.get(k) for k in ("SERVER","CLIENT")}
    adapter.runner_daemon=lambda:(owner,daemon)
    os.environ["SERVER"]=IMAGE;os.environ["CLIENT"]=IMAGE
    try:
        argv=["compose","--env-file","empty.env","up"]+(["-V","server"] if case=="startup-server-compliance" else ["-V","sim","client"] if case=="startup-client-compliance" else ["--abort-on-container-exit","--timeout","10","sim","client","server"])
        status=adapter.docker_entry(argv)
    finally:
        adapter.runner_daemon=real
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    return {"status":"passed","events":events,"checks":{"entry_status":status==0,"created_before_started":events[:1]==["create"] and ("start" in events or "up" in events[1:]),"verified_permissions_before_start":"permissions-ready" in events and "permissions-private" not in events}},"passed"

def watch_fault_control(case,root):
    owner,daemon=setup(root);original=RuntimeError("controlled primary "+case)
    current=adapter.process_identity(os.getpid());real_sample=adapter.resource_sample;real_identity=adapter.process_identity;real_json=adapter.atomic_json
    if case=="watch-cleanup-retains-tree":
        state=daemon.read();state["fail"]="remove";adapter.atomic_json(daemon.path,state)
    elif case=="watch-sample-failure":adapter.resource_sample=lambda *a,**k:(_ for _ in ()).throw(original)
    elif case=="watch-identity-failure":adapter.process_identity=lambda *a,**k:(_ for _ in ()).throw(original)
    elif case=="watch-monitor-failure":
        once=[False]
        def write(path,value):
            if Path(path).name=="monitor.json" and not once[0]:once[0]=True;raise original
            return real_json(path,value)
        adapter.atomic_json=write
    caught=None
    try:
        try:adapter.watch_owned(owner,daemon,current,current,time.monotonic()-.01,root/"watch",interval=.5)
        except BaseException as error:caught=error
    finally:adapter.resource_sample=real_sample;adapter.process_identity=real_identity;adapter.atomic_json=real_json
    retained=root/"watch/retained-trees/retention.json";final=root/"watch/watch-final.json"
    return {"status":"passed","caught":None if caught is None else str(caught),"checks":{"failure_not_pass":caught is not None,"primary_preserved":case=="watch-cleanup-retains-tree" or caught is original,"tree_retained_despite_failure":retained.is_file(),"durable_final_inventory":final.is_file(),"cleanup_attempted":bool(daemon.read()["events"])}},"passed"

def registry_primary_control(root):
    original=RuntimeError("controlled main primary");secondary=OSError("controlled registry init failure")
    real=adapter.runner_registry;real_file=adapter.__file__;adapter.__file__=str(root/"owned_adapter.py")
    def registry():raise secondary
    adapter.runner_registry=registry
    try:
        try:adapter.author_execute(lambda:(_ for _ in ()).throw(original))
        except BaseException as caught:result={"status":"passed","checks":{"primary_identity":caught is original,"secondary_note":any(str(secondary) in note for note in getattr(original,"__notes__",[])),"durable_primary_secondary":(root/"author-finalization-failure.json").is_file()}}
        else:result={"status":"failed"}
    finally:adapter.runner_registry=real;adapter.__file__=real_file
    return result,"passed"

def reinspect_control(root):
    owner,daemon=setup(root);real=daemon.inspect;counts={}
    def inspect(identity):
        counts[identity]=counts.get(identity,0)+1
        if identity=="1"*64 and counts[identity]==4:raise OSError("controlled late reinspect failure")
        return real(identity)
    daemon.inspect=inspect;primary=RuntimeError("main remains primary")
    try:result=adapter.cleanup_owned(owner,daemon,root/"cleanup","late-inspect",primary=primary,unsupported_compliance={"role":"server","testcase":"unknown-control"})
    except BaseException as caught:result={"status":"failed","escaped":str(caught)}
    return {"status":"passed","checks":{"durable_cleanup":(root/"cleanup/cleanup.json").is_file(),"nonpass_secondary":result["status"]=="failed","cleanup_continued":not daemon.containers(),"primary_not_replaced":"escaped" not in result}},"passed"

def network_control(case,root):
    owner,daemon=setup(root);state=daemon.read();entry=state["containers"]["2"*64]
    if case=="foreign-network-mode":entry["HostConfig"]["NetworkMode"]="foreign_bridge"
    elif case=="host-pid-mode":entry["HostConfig"]["PidMode"]="host"
    elif case=="host-ipc-mode":entry["HostConfig"]["IpcMode"]="host"
    else:
        entry.setdefault("NetworkSettings",{})["Networks"]={owner.project+"_rightnet":{"NetworkID":"8"*64}}
        if case=="extra-network-membership":entry["NetworkSettings"]["Networks"]["foreign"]={"NetworkID":"f"*64}
        else:entry["NetworkSettings"]["Networks"][owner.project+"_rightnet"]["NetworkID"]="f"*64
    adapter.atomic_json(daemon.path,state);result=stopped_or_error(owner,daemon,root)
    return {"status":"passed","checks":{"foreign_network_rejected":result["status"]=="failed","no_foreign_mutation":not daemon.read()["events"]}},"passed"

def cli_descendant_control(case,root):
    records=adapter.RawCommands(root/"commands");marker=root/"delayed-create.json";pidfile=root/"descendant.json";parentfile=root/"parent.json"
    child=root/"plugin.py"
    child.write_text("import json,os,sys,time\n"+("os.setsid()\n" if case=="raw-cli-escaped-descendant" else "")+"from pathlib import Path\nPath(sys.argv[2]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\ntime.sleep(.35)\nPath(sys.argv[1]).write_text(json.dumps({'mock_created_id':'2'*64,'owner':'controlled-only'}))\ntime.sleep(.15)\n")
    argvchild=[sys.executable,str(child),str(marker),str(parentfile)]
    source=root/"cli.py"
    source.write_text("import json,subprocess,time\nfrom pathlib import Path\nchild=subprocess.Popen("+repr(argvchild)+")\nPath("+repr(str(pidfile))+").write_text(json.dumps({'pid':child.pid}))\ntime.sleep(.12)\n")
    argv=[sys.executable,str(source)];descendant=None
    try:
        raw=records.run(argv,3)
        pid=json.loads(pidfile.read_bytes())["pid"];descendant=adapter.process_identity(pid)
        time.sleep(.55)
        actual=json.loads(parentfile.read_bytes())
        return {"status":"passed","checks":{"real_root_exited_descendant":actual["parent_pid"]==records.rows[0].get("process_identity",{}).get("pid"),"descendant_drained_before_return":descendant is None,"delayed_create_prevented":not marker.exists(),"lifetime_certified":records.rows[0].get("lifetime",{}).get("certified") is True},"argv":argv,"actual_parent":actual},"passed"
    finally:
        if descendant is not None and adapter.process_identity(descendant["pid"])==descendant:os.kill(descendant["pid"],signal.SIGTERM)

def bounded_retention_control(case,root):
    owner,_=setup(root);tree=root/"bounded-source";tree.mkdir();file=tree/"a";file.write_bytes(b"abcd")
    retention=adapter.TreeRetention(root/"retained",max_bytes=3 if case=="retention-stream-bound" else 20,max_files=2)
    real_read=Path.read_bytes;real_glob=Path.rglob;real_time=adapter.time.monotonic;attempts=[];clock=[0];yielded=[0]
    if case=="retention-stream-bound":
        def read(path):
            if path==file:attempts.append("whole-read");raise RuntimeError("whole overlimit input was read")
            return real_read(path)
        Path.read_bytes=read
    elif case=="retention-lazy-file-bound":
        for n in range(6):(tree/str(n)).write_bytes(b"x")
        def glob(path,pattern):
            for value in real_glob(path,pattern):
                if path==tree:
                    yielded[0]+=1
                    if yielded[0]>3:raise RuntimeError("enumerated past the admission bound")
                yield value
        Path.rglob=glob
    else:
        def monotonic():
            clock[0]+=1
            return 0 if clock[0]<=2 else 31
        adapter.time.monotonic=monotonic
    caught=None
    try:
        try:retention.capture(tree,"bounded")
        except BaseException as error:caught=error
    finally:Path.read_bytes=real_read;Path.rglob=real_glob;adapter.time.monotonic=real_time
    return {"status":"passed","checks":{"bound_rejected_before_unbounded_read":isinstance(caught,adapter.OwnershipError),"whole_read_not_attempted":not attempts,"enumeration_bounded":yielded[0]<=3,"failed_manifest":bool(retention.rows) and retention.rows[0]["status"]=="failed"}},"passed"

def copy_bound_control(root):
    import io,tarfile
    owner,base=setup(root)
    daemon=object.__new__(adapter.DockerDaemon);daemon.spec=owner;daemon.inspect=base.inspect
    commands=[]
    def command(*args,**kwargs):
        commands.append(args)
        if args[0]=="cp":
            header=tarfile.TarInfo("oversize");header.size=536870913
            raw=root/"archive.tar";raw.write_bytes(header.tobuf());return raw
        return b"mock log"
    daemon.command=command
    try:daemon.retain("2"*64,root/"copy")
    except adapter.OwnershipError:rejected=True
    else:rejected=False
    return {"status":"passed","checks":{"oversize_copy_rejected":rejected,"copy_bound_precedes_second_copy":sum(args[0]=="cp" for args in commands)<=1}},"passed"

def round2_control(case,root):
    if case=="startup-permissions-before-start":return startup_control(root)
    if case.startswith("watch-"):return watch_fault_control(case,root)
    if case=="author-registry-primary":return registry_primary_control(root)
    if case=="late-reinspection-failure":return reinspect_control(root)
    if case in ("foreign-network-mode","host-pid-mode","host-ipc-mode","extra-network-membership","wrong-network-id"):return network_control(case,root)
    if case.startswith("raw-cli-"):return cli_descendant_control(case,root)
    if case.startswith("retention-"):return bounded_retention_control(case,root)
    return copy_bound_control(root)


EXTRA_CASES=("raw-cli-escaped-descendant","admission-kill-before-create","admission-kill-partial-create","admission-kill-before-retention","admission-kill-after-criterion","admission-quiet-inflight","admission-foreign-intent","raw-stream-overlimit","copy-safe-archive","copy-unsafe-archive")
CASES+=EXTRA_CASES

def admission_control(case,root):
    owner,daemon=setup(root);state=daemon.read()
    count=0 if case in ("admission-kill-before-create","admission-quiet-inflight","admission-foreign-intent") else 1 if case=="admission-kill-partial-create" else 3
    state["containers"]={k:v for k,v in list(state["containers"].items())[:count]}
    for network in state["networks"].values():network["Containers"]={k:{} for k,v in state["containers"].items() if network["Name"] in v["NetworkSettings"]["Networks"]}
    adapter.atomic_json(daemon.path,state)
    closed=case=="admission-kill-after-criterion"
    intent={"schema_version":1,"project":owner.project,"nonce":"f"*64 if case=="admission-foreign-intent" else owner.nonce,"state":"closed" if closed else "creating","certified":closed,
            "intended_containers":[{"name":owner.project+"-"+r,"role":r,"image":SIM if r=="sim" else IMAGE,"labels":owner.labels(r)} for r in adapter.ROLES],"scope":"mock phase only"}
    adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",intent)
    result=stopped_or_error(owner,daemon,root)
    return {"status":"passed","checks":{"exact_nonpass_unless_closed":result["status"]==("passed" if closed else "failed"),"daemon_final_inventory_retained":"remaining_ids" in result and not result["remaining_ids"],"creation_uncertainty_retained":closed or any(e["stage"]=="create-admission" for e in result["errors"])}},"passed"

def raw_stream_control(root):
    records=adapter.RawCommands(root/"commands");caught=None
    try:records.run([sys.executable,"-c","import os;os.write(1,b'x'*4096)"],3,max_bytes=32)
    except adapter.OwnershipError as error:caught=error
    row=records.rows[0]
    return {"status":"passed","checks":{"stream_bound_failed":caught is not None,"retained_stream_bounded":row.get("stdout",{}).get("bytes",999)<=32,"process_lifetime_nonpass":row["lifetime"]["certified"] is False,"raw_failure_ledger":(root/"commands/commands.json").exists()}},"passed"

def archive_control(case,root):
    import io,tarfile
    owner,base=setup(root);daemon=object.__new__(adapter.DockerDaemon);daemon.spec=owner;daemon.inspect=base.inspect
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode="w") as archive:
        member=tarfile.TarInfo("../foreign" if case=="copy-unsafe-archive" else "log.txt");member.size=3
        archive.addfile(member,io.BytesIO(b"log"))
    raw=root/"archive.tar";raw.write_bytes(buffer.getvalue())
    daemon.command=lambda *a,**k:raw
    try:daemon.copy_bounded("2"*64,"/logs/.",root/"copy")
    except adapter.OwnershipError:rejected=True
    else:rejected=False
    return {"status":"passed","checks":{"archive_expected_result":rejected==(case=="copy-unsafe-archive"),"no_foreign_write":not (root/"foreign").exists(),"positive_exact_bytes":case!="copy-safe-archive" or (root/"copy/log.txt").read_bytes()==b"log"}},"passed"

def extra_control(case,root):
    if case=="raw-cli-escaped-descendant":return cli_descendant_control(case,root)
    if case.startswith("admission-"):return admission_control(case,root)
    if case=="raw-stream-overlimit":return raw_stream_control(root)
    return archive_control(case,root)


FINAL_CASES=("raw-partial-initialization","raw-escaped-timeout","raw-foreign-child-boundary","startup-server-compliance","startup-client-compliance","watch-primary-cleanup-secondary")
CASES+=FINAL_CASES

def subreaper_value():
    import ctypes
    value=ctypes.c_int();libc=ctypes.CDLL(None)
    if libc.prctl(37,ctypes.byref(value),0,0,0)!=0:raise RuntimeError("cannot inspect subreaper control")
    return value.value

def partial_cli_control(root):
    records=adapter.RawCommands(root/"commands");original=RuntimeError("controlled second pipe registration failure")
    real_selector=adapter.selectors.DefaultSelector;prior=subreaper_value();registered=[0]
    class PartialSelector:
        def __init__(self):self.real=real_selector()
        def register(self,*args,**kwargs):
            registered[0]+=1
            if registered[0]==2:raise original
            return self.real.register(*args,**kwargs)
        def close(self):self.real.close()
    adapter.selectors.DefaultSelector=PartialSelector;caught=None
    try:
        try:records.run([sys.executable,"-c","import time;time.sleep(10)"],3)
        except BaseException as error:caught=error
    finally:adapter.selectors.DefaultSelector=real_selector
    row=records.rows[0]
    return {"status":"passed","checks":{"primary_identity":caught is original,"owned_root_gone":row["process_identity"] is not None and adapter.process_identity(row["process_identity"]["pid"]) is None,"no_adopted_descendants":not adapter.direct_children(),"subreaper_restored":subreaper_value()==prior,"exact_cleanup_receipts":bool(row["lifetime"]["receipts"]) and all(type(r["identity"]["start_ticks"]) is int for r in row["lifetime"]["receipts"]),"failure_ledger_retained":row["primary_exception"]["message"]==str(original) and (root/"commands/commands.json").exists()}},"passed"

def timeout_cli_control(root):
    records=adapter.RawCommands(root/"commands");marker=root/"delayed-create.json";parent=root/"actual-parent.json"
    child=root/"escaped.py"
    child.write_text("import json,os,sys,time\nfrom pathlib import Path\nos.setsid()\nPath(sys.argv[2]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\ntime.sleep(.6)\nPath(sys.argv[1]).write_text('delayed mock create')\ntime.sleep(10)\n")
    root_cli=root/"cli.py"
    root_cli.write_text("import subprocess,time\nsubprocess.Popen("+repr([sys.executable,str(child),str(marker),str(parent)])+")\ntime.sleep(10)\n")
    argv=[sys.executable,str(root_cli)];prior=subreaper_value();caught=None
    try:records.run(argv,.2)
    except subprocess.TimeoutExpired as error:caught=error
    row=records.rows[0];actual=json.loads(parent.read_bytes())
    receipts=row["lifetime"]["receipts"]
    return {"status":"passed","actual_parent":actual,"checks":{"actual_timeout":caught is not None and row["timed_out"] is True,"actual_descendant":actual["parent_pid"]==row["process_identity"]["pid"],"both_root_and_escaped_descendant_gone":adapter.process_identity(actual["pid"]) is None and adapter.process_identity(row["process_identity"]["pid"]) is None,"escaped_birthday_bound":any(r["identity"]["pid"]==actual["pid"] and r["identity"]["session"]==actual["pid"] and type(r["identity"]["start_ticks"]) is int for r in receipts),"no_delayed_create":not marker.exists(),"interrupted_lifetime_nonpass":row["lifetime"]["certified"] is False,"subreaper_restored":subreaper_value()==prior}},"passed"

def foreign_cli_control(root):
    foreign=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    birthday=adapter.process_identity(foreign.pid);prior=subreaper_value();records=adapter.RawCommands(root/"commands");caught=None
    try:
        try:records.run([sys.executable,"-c","pass"],2)
        except adapter.OwnershipError as error:caught=error
        return {"status":"passed","checks":{"foreign_boundary_rejected":caught is not None,"foreign_process_untouched":foreign.poll() is None and adapter.process_identity(foreign.pid)==birthday,"no_arbitrary_signal":not records.rows[0]["lifetime"]["receipts"],"subreaper_unchanged":subreaper_value()==prior}},"passed"
    finally:
        if foreign.poll() is None:foreign.terminate();foreign.wait(timeout=2)

def watch_secondary_control(root):
    owner,daemon=setup(root);state=daemon.read();state["fail"]="stop";adapter.atomic_json(daemon.path,state)
    original=RuntimeError("original monitor failure");real=adapter.resource_sample;current=adapter.process_identity(os.getpid())
    adapter.resource_sample=lambda *a,**k:(_ for _ in ()).throw(original);caught=None
    try:
        try:adapter.watch_owned(owner,daemon,current,current,time.monotonic()+1,root/"watch",interval=.5)
        except BaseException as error:caught=error
    finally:adapter.resource_sample=real
    final=json.loads((root/"watch/watch-final.json").read_bytes())
    return {"status":"passed","checks":{"main_primary_identity":caught is original,"secondary_cleanup_ledger":any(e["stage"]=="stop" for e in final["cleanup"]["errors"]),"secondary_note":any("controlled mock stop failure" in n for n in getattr(original,"__notes__",[])),"nonpass_preserved":final["status"]=="failed","tree_retained":(root/"watch/retained-trees/retention.json").exists(),"final_ids_empty":final["remaining_ids"]==[]}},"passed"

def final_control(case,root):
    if case=="raw-partial-initialization":return partial_cli_control(root)
    if case=="raw-escaped-timeout":return timeout_cli_control(root)
    if case=="raw-foreign-child-boundary":return foreign_cli_control(root)
    if case.startswith("startup-"):return startup_control(root,case)
    return watch_secondary_control(root)


TAIL_CASES=("raw-restoration-failure","retention-manifest-deadline")
CASES+=TAIL_CASES

def restoration_control(root):
    records=adapter.RawCommands(root/"commands");real=adapter.subreaper_begin;prior=subreaper_value()
    class Failure:
        def __init__(self,libc):self.libc=libc
        def prctl(self,*args):
            actual=self.libc.prctl(*args)
            if actual!=0:raise RuntimeError("real restoration unexpectedly failed")
            return -1
    def begin():
        libc,value=real();return Failure(libc),value
    adapter.subreaper_begin=begin;caught=None
    try:
        try:records.run([sys.executable,"-c","print('harmless')"],3)
        except adapter.CleanupError as error:caught=error
    finally:adapter.subreaper_begin=real
    return {"status":"passed","checks":{"restoration_failure_nonpass":caught is not None,"failure_raw_ledger":any("restoration" in e["message"] for e in records.rows[0]["finalization_errors"]),"actual_control_restores_flag":subreaper_value()==prior,"owned_lifetime_closed":not adapter.direct_children()}},"passed"

def manifest_deadline_control(root):
    tree=root/"tree";tree.mkdir();(tree/"a").write_bytes(b"retained")
    retention=adapter.TreeRetention(root/"retained");real_time=adapter.time.monotonic;real_json=adapter.atomic_json;clock=[0]
    adapter.time.monotonic=lambda:clock[0]
    def write(path,value):
        if Path(path).name=="retention.json":clock[0]=31
        return real_json(path,value)
    adapter.atomic_json=write;caught=None
    try:
        try:retention.capture(tree,"late-finalization")
        except adapter.OwnershipError as error:caught=error
    finally:adapter.time.monotonic=real_time;adapter.atomic_json=real_json
    retained=json.loads((retention.root/"retention.json").read_bytes())
    return {"status":"passed","checks":{"whole_operation_deadline_nonpass":caught is not None,"late_manifest_not_retained_success":retained["trees"][0]["status"]=="failed","raw_bound_failure_retained":bool(retained["errors"])}},"passed"

def tail_control(case,root):
    return restoration_control(root) if case=="raw-restoration-failure" else manifest_deadline_control(root)


CASES+=("copy-official-fixture-layout",)
def copy_layout_control(root):
    import io,tarfile
    owner,base=setup(root);daemon=object.__new__(adapter.DockerDaemon);daemon.spec=owner;daemon.inspect=base.inspect;daemon.containers=base.containers
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode="w") as archive:
        member=tarfile.TarInfo("keys.log");member.size=3;archive.addfile(member,io.BytesIO(b"log"))
    raw=root/"archive.tar";raw.write_bytes(buffer.getvalue());daemon.command=lambda *a,**k:raw
    destination=owner.paths["fixture_root"]/"official-logdir";destination.mkdir()
    real=adapter.runner_daemon;adapter.runner_daemon=lambda:(owner,daemon)
    try:adapter.copy_runner_logs("server",destination)
    finally:adapter.runner_daemon=real
    return {"status":"passed","checks":{"upstream_logdir_contents_preserved":(destination/"keys.log").is_file(),"no_unrequested_subdirectory":not (destination/"owned-logs").exists()}},"passed"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--artifacts",type=Path,required=True)
    parser.add_argument("--case",choices=CASES,action="append")
    parser.add_argument("--pinned-runner",type=Path,default=Path("/home/user/minyar-overnight/security/interop-lab/runner"))
    args=parser.parse_args()
    if not args.artifacts.is_absolute() or args.artifacts.exists():raise ValueError("--artifacts requires a fresh absolute path")
    args.artifacts.mkdir(parents=True);cases=args.case or CASES;results=[]
    input_root=args.artifacts/"inputs";input_root.mkdir()
    input_bindings={}
    for role,data in LOADED_INPUT_BYTES.items():
        retained=input_root/(role+".py");retained.write_bytes(data)
        input_bindings[role]={"original_before":{"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)},"retained":adapter.binding(retained)}
    for case in cases:
        root=args.artifacts/case;root.mkdir()
        try:
            if case=="copy-official-fixture-layout":result,expected=copy_layout_control(root)
            elif case in TAIL_CASES:result,expected=tail_control(case,root)
            elif case in FINAL_CASES:result,expected=final_control(case,root)
            elif case in EXTRA_CASES:result,expected=extra_control(case,root)
            elif case in ROUND2_CASES:result,expected=round2_control(case,root)
            elif case.startswith("controller-") or case in ("guard-death","deadline","resource-abort"):result,expected=process_control(case,root)
            elif case=="tree-primary-finalization":result,expected=tree_primary_control(root)
            elif case=="raw-nonzero-status":result,expected=raw_status_control(root)
            elif case=="root-exited-descendant":result,expected=descendant_control(root)
            elif case=="unsupported-compliance-exit":result,expected=unsupported_control(root)
            elif case=="retention-late-mutation":result,expected=late_mutation_control(root)
            elif case=="raw-evidence-reuse":result,expected=raw_reuse_control(root)
            elif case=="raw-primary-finalization":result,expected=raw_primary_control(root)
            elif case.startswith("fixture-access"):result,expected=fixture_access_control(case,root)
            elif case=="primary-retention-failure":result,expected=primary_retention(root)
            elif case=="retention-bounds":result,expected=retention_bounds(root)
            elif case=="criteria-no-pull":result,expected=criteria_control(root,args.pinned_runner)
            else:result,expected=mock_cleanup(case,root)
            matched=result["status"]==expected and all(result.get("checks",{}).values())
        except BaseException as error:
            result={"status":"setup-or-control-error","exception":{"type":type(error).__name__,"message":str(error)}};expected="defined-control-result";matched=False
        adapter.atomic_json(root/"result.json",result)
        results.append({"case":case,"expected":expected,"status":result["status"],"matched":matched})
    for role,path in (("driver",Path(__file__)),("helper",MODULE)):
        input_bindings[role]["original_after"]=adapter.binding(path)
        expected=input_bindings[role]["original_before"]
        input_bindings[role]["copied_exact"]=all(value["sha256"]==expected["sha256"] and value["bytes"]==expected["bytes"] for value in (input_bindings[role]["retained"],input_bindings[role]["original_after"]))
    files={path.relative_to(args.artifacts).as_posix():adapter.binding(path) for path in sorted(args.artifacts.rglob("*")) if path.is_file()}
    report={"schema_version":1,"scope":"mock daemon and owned harmless process controls only; no actual Docker, peer, compiler or network traffic",
            "status":"passed" if all(row["matched"] for row in results) and all(row["copied_exact"] for row in input_bindings.values()) else "failed","inputs":input_bindings,
            "declared_cases":list(cases),"results":results,"files":files}
    adapter.atomic_json(args.artifacts/"results.json",report);print(json.dumps({key:value for key,value in report.items() if key!="files"},indent=2))
    return 0 if report["status"]=="passed" else 1
if __name__=="__main__":raise SystemExit(main())
