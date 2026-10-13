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
           "images":{"sim":[SIM],"server":[IMAGE,PEER],"client":[IMAGE,PEER]},"minyar_image":IMAGE,
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
    strict_capabilities=True
    if case=="successful-cleanup":
        simulator=state["containers"]["1"*64]
        simulator["HostConfig"]["CapAdd"]=["CAP_NET_ADMIN","CAP_NET_RAW"]
        for role,identity in (("sim","1"*64),("server","2"*64),("client","3"*64)):
            state["containers"][identity]["State"]={"Running":False,"ExitCode":0 if role=="client" else 137 if role=="server" else 143,"OOMKilled":False,"FinishedAt":"2026-10-11T16:00:10Z" if role=="client" else "2026-10-11T16:00:20Z"}
        state["containers"]["2"*64]["Image"]=PEER
        raw=owner.paths["artifacts"]/"daemon-commands"/"compose-output";raw.mkdir(parents=True)
        stdout=raw/"stdout";stderr=raw/"stderr"
        stdout.write_text(owner.project+"-client exited with code 0\n")
        stderr.write_text("Compose Stopping Aborting on container exit...\n"+"".join(
            "Container "+owner.project+"-"+role+" Stopping\nContainer "+owner.project+"-"+role+" Stopped\n"
            for role in ("sim","server")))
        receipt={"argv":["/usr/bin/docker","compose","--project-name",owner.project,"--file",str(owner.paths["compose_path"]),
                         "--env-file",str(owner.paths["runner_root"]/"empty.env"),"up","--timeout","10","--abort-on-container-exit","sim","client","server"],
                 "status":0,"timed_out":False,"primary_exception":None,"finalization_errors":[],
                 "lifetime":{"state":"closed","certified":True},
                 "stdout":adapter.binding(stdout),"stderr":adapter.binding(stderr)}
        intent={"project":owner.project,"nonce":owner.nonce,"state":"closed","certified":True,
                "created_ids":list(state["containers"]),"up_receipt":receipt}
        adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",intent)
        for field,value in (("certified",False),("created_ids",[])):
            mutant=json.loads(json.dumps(intent));mutant[field]=value
            adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",mutant)
            strict_capabilities=not adapter.recorded_compose_stop(owner,"1"*64,simulator,list(state["containers"].values()),None) and strict_capabilities
        mutant=json.loads(json.dumps(intent));mutant["up_receipt"]["status"]=1
        adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",mutant)
        strict_capabilities=not adapter.recorded_compose_stop(owner,"1"*64,simulator,list(state["containers"].values()),None) and strict_capabilities
        adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",intent)
        original_stderr=stderr.read_bytes();stderr.write_bytes(original_stderr+b"unbound edit")
        strict_capabilities=not adapter.recorded_compose_stop(owner,"1"*64,simulator,list(state["containers"].values()),None) and strict_capabilities
        stderr.write_bytes(original_stderr)
        peer=state["containers"]["2"*64]
        for field,value in (("Image",IMAGE),("OOMKilled",True),("FinishedAt","2026-10-11T16:00:11Z")):
            mutant=json.loads(json.dumps(peer))
            if field=="Image":mutant[field]=value
            else:mutant["State"][field]=value
            strict_capabilities=not adapter.recorded_compose_stop(owner,"2"*64,mutant,list(state["containers"].values()),None) and strict_capabilities
        for invalid in (["CAP_NET_ADMIN","CAP_NET_RAW","CAP_SYS_ADMIN"],
                        ["CAP_NET_ADMIN","CAP_NET_ADMIN"],
                        ["CAP_NET_ADMIN","NET_RAW"], []):
            mutant=json.loads(json.dumps(simulator));mutant["HostConfig"]["CapAdd"]=invalid
            try:owner.container(mutant)
            except adapter.OwnershipError:pass
            else:strict_capabilities=False
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
        if case=="successful-cleanup":result["checks"]["exact_simulator_capabilities"]=strict_capabilities
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
    retention=adapter.TreeRetention(root/"retained");real_copy=adapter.stream_binding;copied=[]
    def copy(path,*args,**kwargs):
        result=real_copy(path,*args,**kwargs)
        copy_to=kwargs.get("copy_to",args[2] if len(args)>2 else None)
        if copy_to is not None:
            if copied:copied[0].write_bytes(b"changed-after-first-copy")
            else:copied.append(Path(path))
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
    import ast
    run=next(node for node in ast.walk(ast.parse((root/"derived/interop.py").read_text()))
             if isinstance(node,ast.FunctionDef) and node.name=="_run_test")
    timed=[node for node in run.body if isinstance(node,ast.Try) and
           any(isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and
               isinstance(call.func.value,ast.Name) and call.func.value.id=="subprocess" and
               call.func.attr=="run" for call in ast.walk(node))]
    prepared=[node for node in run.body if isinstance(node,ast.Expr) and
              isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and
              node.value.func.id=="prepare_runner_phase"]
    before_timeout=bool(prepared) and len(timed)==1 and prepared[0].lineno<timed[0].lineno
    timeout_unchanged=all(ast.unparse(keyword.value)=="test.timeout()" for call in
        ast.walk(timed[0]) if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
        and isinstance(call.func.value,ast.Name) and call.func.value.id=="subprocess"
        and call.func.attr=="run" for keyword in call.keywords if keyword.arg=="timeout")
    (root/"phase-control").mkdir()
    mock_owner,mock_daemon=setup(root/"phase-control")
    real=adapter.runner_daemon
    phase_cleaned=False
    try:
        adapter.runner_daemon=lambda:(mock_owner,mock_daemon)
        if hasattr(adapter,"prepare_runner_phase"):
            adapter.prepare_runner_phase()
            phase_cleaned=not mock_daemon.containers() and not mock_daemon.networks() and bool(
                list(mock_owner.paths["artifacts"].glob("between-up-*/cleanup.json")))
    finally:adapter.runner_daemon=real
    return {"status":"passed","checks":{"official_criteria_unchanged":report["official_criteria_unchanged"],"pinned_original_hash":report["original_files"]["testcases_quic.py"]["sha256"]==adapter.PINNED["testcases_quic.py"],
                                      "previous_phase_prepared_before_timeout":before_timeout,"original_test_timeout_unchanged":timeout_unchanged,"previous_owned_objects_retained_and_removed":phase_cleaned,"explicit_never_pull":good[good.index("--pull")+1]=="never","exact_project":good[good.index("--project-name")+1]==owner.project,
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
            if operation=="up" and "--no-start" in args:operation="create"
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
    records=adapter.RawCommands(root/"commands");marker=root/"delayed-create.json";pidfile=root/"descendant.json";parentfile=root/"parent.json";permit=root/"create-permit"
    child=root/"plugin.py"
    child.write_text("import json,os,sys,time\n"+("os.setsid()\n" if case=="raw-cli-escaped-descendant" else "")+"from pathlib import Path\nPath(sys.argv[2]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\nend=time.monotonic()+3\nwhile not Path(sys.argv[3]).exists():\n if time.monotonic()>end:raise SystemExit(5)\n time.sleep(.01)\nPath(sys.argv[1]).write_text(json.dumps({'mock_created_id':'2'*64,'owner':'controlled-only'}))\ntime.sleep(.15)\n")
    argvchild=[sys.executable,str(child),str(marker),str(parentfile),str(permit)]
    source=root/"cli.py"
    source.write_text("import json,subprocess,time\nfrom pathlib import Path\nchild=subprocess.Popen("+repr(argvchild)+")\nPath("+repr(str(pidfile))+").write_text(json.dumps({'pid':child.pid}))\ntime.sleep(.12)\n")
    argv=[sys.executable,str(source)];descendant=None
    try:
        raw=records.run(argv,3)
        permit.touch()
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
    child.write_text("import json,os,sys,time\nfrom pathlib import Path\nos.setsid()\nPath(sys.argv[2]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\ntime.sleep(5)\nPath(sys.argv[1]).write_text('delayed mock create')\ntime.sleep(10)\n")
    root_cli=root/"cli.py"
    root_cli.write_text("import subprocess,time\nsubprocess.Popen("+repr([sys.executable,str(child),str(marker),str(parent)])+")\ntime.sleep(10)\n")
    argv=[sys.executable,str(root_cli)];prior=subreaper_value();caught=None
    try:records.run(argv,2)
    except subprocess.TimeoutExpired as error:caught=error
    row=records.rows[0];actual=json.loads(parent.read_bytes())
    receipts=row["lifetime"]["receipts"]
    return {"status":"passed","actual_parent":actual,"checks":{"actual_timeout":caught is not None and row["timed_out"] is True,"actual_descendant":actual["parent_pid"]==row["process_identity"]["pid"],"both_root_and_escaped_descendant_gone":adapter.process_identity(actual["pid"]) is None and adapter.process_identity(row["process_identity"]["pid"]) is None,"escaped_birthday_bound":any(r["identity"]["pid"]==actual["pid"] and type(r["identity"]["start_ticks"]) is int and any(member["pid"]==actual["pid"] and member["session"]==actual["pid"] and member["start_ticks"]==r["identity"]["start_ticks"] for member in row["lifetime"]["members"]) for r in receipts),"no_delayed_create":not marker.exists(),"interrupted_lifetime_nonpass":row["lifetime"]["certified"] is False,"subreaper_restored":subreaper_value()==prior}},"passed"

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


REVIEW_CASES=("up-status-one","up-status-unsupported","created-declared-networks","stopped-declared-networks","admission-not-opened-revoked","admission-closed-revoked","watch-late-object","pidfd-check-signal-race","session-extinction-latch","root-wnowait-before-drain","close-secondary-preserves-primary","close-state-secondary-preserves-primary")
CASES+=REVIEW_CASES

def receipt_daemon(root,status=0):
    owner,base=setup(root);template=base.read()
    for entry in template["containers"].values():entry["State"]={"Running":False,"ExitCode":0}
    adapter.atomic_json(base.path,{"containers":{},"networks":{},"events":[]})
    class Fake(adapter.JsonDaemon):
        def __init__(self,path):super().__init__(path);self.commands=type("Rows",(),{"rows":[]})();self.after=False;self.events=[]
        def row(self,operation,code=0,stderr=b""):
            path=root/("raw-"+str(len(self.commands.rows))+".stderr");path.write_bytes(stderr)
            self.commands.rows.append({"operation":operation,"status":code,"stderr":adapter.binding(path),"lifetime":{"certified":True}})
        def command(self,*args,**kwargs):
            operation=next((v for v in args if v in ("create","up")),args[0]);self.events.append(operation)
            if operation=="create":adapter.atomic_json(self.path,template)
            self.row(operation,status if operation=="up" else 0,b"exact up stderr\n" if operation=="up" else b"inspection stderr\n")
            if operation=="up" and kwargs.get("stream_output",False):sys.stderr.buffer.write(b"exact up stderr\n")
            if operation=="up":self.after=True
            return b""
        def containers(self):
            if self.after:self.row("post-ps")
            return super().containers()
        def inspect(self,identity):
            if self.after:self.row("post-inspect")
            return super().inspect(identity)
        def networks(self):
            if self.after:self.row("post-network")
            return super().networks()
    return owner,Fake(base.path)

def invoke_fake(owner,daemon):
    real=adapter.runner_daemon;previous={key:os.environ.get(key) for key in ("SERVER","CLIENT")}
    adapter.runner_daemon=lambda:(owner,daemon);os.environ["SERVER"]=IMAGE;os.environ["CLIENT"]=IMAGE
    import io
    class Output:
        def __init__(self):self.buffer=io.BytesIO()
        def flush(self):pass
    out=Output();err=Output();real_out=sys.stdout;real_err=sys.stderr;sys.stdout=out;sys.stderr=err
    try:status=adapter.docker_entry(["compose","--env-file","empty.env","up","--abort-on-container-exit","--timeout","10","sim","client","server"])
    finally:
        sys.stdout=real_out;sys.stderr=real_err;adapter.runner_daemon=real
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    return status,out.buffer.getvalue(),err.buffer.getvalue()

def up_receipt_control(case,root):
    code=1 if case=="up-status-one" else 127;owner,daemon=receipt_daemon(root,code)
    status,out,err=invoke_fake(owner,daemon);intent=json.loads((owner.paths["artifacts"]/"create-admission.json").read_bytes())
    return {"status":"passed","checks":{"exact_up_status":status==code,"exact_up_stderr":err==b"exact up stderr\n","intent_binds_up_status":intent.get("workload_status")==code,"successful_later_inspection_present":any(row["operation"].startswith("post-") and row["status"]==0 for row in daemon.commands.rows)}},"passed"

def declared_topology_control(case,root):
    owner,daemon=setup(root);state=daemon.read()
    configured={}
    for entry in state["containers"].values():
        entry["State"]={"Running":False,"ExitCode":0,"Status":"created" if case.startswith("created") else "exited"}
        configured[entry["Id"]]={name:value["NetworkID"] for name,value in entry["NetworkSettings"]["Networks"].items()}
        for value in entry["NetworkSettings"]["Networks"].values():value["NetworkID"]="";value["EndpointID"]=""
    for network in state["networks"].values():network["Containers"]={}
    adapter.atomic_json(owner.paths["artifacts"]/"configured-topology.json",{"schema_version":1,"project":owner.project,"nonce":owner.nonce,"containers":configured,"networks":{v["Name"]:v["Id"] for v in state["networks"].values()}})
    accepted=False
    try:adapter.verified_topology(owner,list(state["containers"].values()),list(state["networks"].values()));accepted=True
    except adapter.OwnershipError:pass
    return {"status":"passed","checks":{"honest_declared_phase_accepted":accepted,"no_live_endpoint_members":all(not network["Containers"] for network in state["networks"].values())}},"passed"

def revoked_control(case,root):
    owner,daemon=receipt_daemon(root)
    if case=="admission-closed-revoked":adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",{"schema_version":1,"project":owner.project,"nonce":owner.nonce,"state":"closed","certified":True})
    adapter.close_admission(owner);refused=False
    try:invoke_fake(owner,daemon)
    except (adapter.OwnershipError,adapter.CleanupError):refused=True
    return {"status":"passed","checks":{"delayed_wrapper_refused":refused,"no_create_after_closure":not daemon.events,"persistent_revocation":(owner.paths["artifacts"]/"admission-revoked.json").exists()}},"passed"

def late_object_control(root):
    owner,daemon=setup(root);template=daemon.read();real=adapter.TreeRetention.capture;current=adapter.process_identity(os.getpid())
    def capture(self,path,label):
        result=real(self,path,label)
        if label=="runner_root":
            late=json.loads(json.dumps(template));late["containers"]={"2"*64:late["containers"]["2"*64]};late["networks"]={"8"*64:late["networks"]["8"*64]};late["networks"]["8"*64]["Containers"]={"2"*64:{}}
            adapter.atomic_json(daemon.path,late)
        return result
    adapter.TreeRetention.capture=capture;caught=None
    try:
        try:adapter.watch_owned(owner,daemon,current,current,time.monotonic()-.01,root/"watch",interval=.5)
        except adapter.CleanupError as error:caught=error
    finally:adapter.TreeRetention.capture=real
    final=json.loads((root/"watch/watch-final.json").read_bytes())
    return {"status":"passed","checks":{"late_object_forces_nonpass":caught is not None and final["status"]=="failed","late_immutable_identity_retained":final["remaining_ids"]==["2"*64],"tree_retention_survives":(root/"watch/retained-trees/retention.json").exists()}},"passed"

def pidfd_control(case,root):
    member={"pid":424242,"start_ticks":77,"pgid":424243,"session":424243};identity={"pid":424243,"start_ticks":76};done=[False];numeric=[];held=[];opens=[]
    real_members=adapter.cli_members;real_identity=adapter.process_identity;real_kill=adapter.os.kill;real_open=getattr(adapter,"open_process_handle",None)
    class Handle:
        def __init__(self,value):self.identity=value;self.exited=False;self.closed=False
        def send(self,sig):held.append({"identity":self.identity,"signal":sig});done[0]=True;self.exited=True
        def close(self):self.closed=True
        def ready(self):return self.exited
    def members(*args,**kwargs):return [] if done[0] else [dict(member)]
    def open_handle(value,*args,**kwargs):opens.append(dict(value));return Handle(dict(value))
    adapter.cli_members=members;adapter.process_identity=lambda pid:{"pid":pid,"start_ticks":77 if pid==424242 else 76}
    adapter.os.kill=lambda pid,sig:(numeric.append(pid),done.__setitem__(0,True))
    adapter.open_process_handle=open_handle;known={};receipts=[]
    try:
        if case=="session-extinction-latch":
            done[0]=True;adapter.drain_cli(identity,known,receipts,time.monotonic()+1)
            done[0]=False
            adapter.drain_cli(identity,known,receipts,time.monotonic()+1)
            checks={"permanent_extinction_refuses_numeric_reuse":not numeric and not held,"no_reopened_membership":not known}
        else:
            adapter.drain_cli(identity,known,receipts,time.monotonic()+1)
            checks={"no_numeric_pid_signal":not numeric,"signal_uses_held_birth_handle":bool(held) and bool(opens),"owned_signal_receipt":bool(receipts)}
    finally:
        adapter.cli_members=real_members;adapter.process_identity=real_identity;adapter.os.kill=real_kill
        if real_open is None:del adapter.open_process_handle
        else:adapter.open_process_handle=real_open
    return {"status":"passed","scope":"mock transition only; no actual PID reuse or signal","checks":checks,"numeric_requests":numeric,"held_requests":held},"passed"

def wnowait_control(root):
    records=adapter.RawCommands(root/"commands");real=adapter.subprocess.Popen;children=[];polls=[]
    class NoEarlyReap(real):
        def poll(self):polls.append(self.pid);raise RuntimeError("sole reap before final drain")
    def popen(*args,**kwargs):
        child=NoEarlyReap(*args,**kwargs);children.append(child);return child
    adapter.subprocess.Popen=popen;completed=False
    try:
        try:records.run([sys.executable,"-c","print('harmless completion')"],3);completed=True
        except BaseException:pass
    finally:
        adapter.subprocess.Popen=real
        for child in children:
            if real.poll(child) is None:child.kill()
            child.wait(timeout=2)
    return {"status":"passed","checks":{"no_poll_before_drain":not polls,"actual_harmless_completion":completed,"raw_receipt_retained":(root/"commands/commands.json").exists()}},"passed"

def close_primary_control(root,close_state_failure=False):
    records=adapter.RawCommands(root/"commands");original=RuntimeError("original second registration sentinel")
    real_popen=adapter.subprocess.Popen;real_selector=adapter.selectors.DefaultSelector;children=[];attempts=[];prior=subreaper_value()
    class Stream:
        def __init__(self,stream,name):self.stream=stream;self.name=name;self.failed=False
        def fileno(self):return self.stream.fileno()
        def close(self):
            attempts.append(self.name)
            if self.name=="stdout" and not self.failed:self.failed=True;raise OSError("secondary stdout close failure")
            return self.stream.close()
        def __getattr__(self,name):
            if name=="closed" and close_state_failure:raise OSError("secondary close state failure")
            return getattr(self.stream,name)
    class Partial:
        def __init__(self):self.real=real_selector();self.count=0
        def register(self,*args,**kwargs):
            self.count+=1
            if self.count==2:raise original
            return self.real.register(*args,**kwargs)
        def close(self):attempts.append("selector");return self.real.close()
    def popen(*args,**kwargs):
        child=real_popen(*args,**kwargs);child.stdout=Stream(child.stdout,"stdout");child.stderr=Stream(child.stderr,"stderr");children.append(child);return child
    adapter.subprocess.Popen=popen;adapter.selectors.DefaultSelector=Partial;caught=None
    try:
        try:records.run([sys.executable,"-c","import time;time.sleep(10)"],3)
        except BaseException as error:caught=error
        flag=subreaper_value()
    finally:
        adapter.subprocess.Popen=real_popen;adapter.selectors.DefaultSelector=real_selector
        for child in children:
            for stream in (child.stdout,child.stderr):
                try:stream.close()
                except OSError:stream.close()
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
        import ctypes
        ctypes.CDLL(None).prctl(36,prior,0,0,0)
    row=records.rows[0]
    return {"status":"passed","checks":{"original_primary_identity":caught is original,"stderr_and_selector_attempted":"stderr" in attempts and "selector" in attempts,"restoration_attempted":flag==prior,"secondary_ledger":any("stdout close" in e["message"] for e in row["finalization_errors"]),"secondary_note":any("stdout close" in n for n in getattr(original,"__notes__",[])),"final_raw_ledger":(root/"commands/commands.json").exists()}},"passed"

def review_control(case,root):
    if case.startswith("up-status-"):return up_receipt_control(case,root)
    if case.startswith(("created-","stopped-")):return declared_topology_control(case,root)
    if case.startswith("admission-"):return revoked_control(case,root)
    if case=="watch-late-object":return late_object_control(root)
    if case in ("pidfd-check-signal-race","session-extinction-latch"):return pidfd_control(case,root)
    if case=="root-wnowait-before-drain":return wnowait_control(root)
    return close_primary_control(root,case=="close-state-secondary-preserves-primary")


BOOT_CASES=("admitted-cli-success","admitted-cli-publication-failure","admitted-cli-revoked-at-spawn","admitted-cli-controller-death","admission-close-lock-race","phase-next-admission","created-wrong-configured-id","stopped-wrong-configured-id","raw-birthday-failure","raw-birthday-failure-escaped")
CASES+=BOOT_CASES

def admitted_control(case,root):
    owner,daemon=setup(root);records=adapter.RawCommands(root/"commands");marker=root/"executed"
    intent={"schema_version":1,"project":owner.project,"nonce":owner.nonce,"state":"creating","certified":False}
    adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",intent)
    original=RuntimeError("original publication failure");real=records.save;raised=[False]
    if case=="admitted-cli-publication-failure":
        def save():
            if records.rows[0]["process_identity"] is not None and not raised[0]:raised[0]=True;raise original
            return real()
        records.save=save
    if case=="admitted-cli-revoked-at-spawn":
        try:adapter.close_admission(owner)
        except adapter.CleanupError:pass
    caught=None
    argv=[sys.executable,"-c","from pathlib import Path;Path("+repr(str(marker))+").write_text('owned harmless execution');print('admitted')"]
    try:raw=records.run(argv,3,admission_spec=owner)
    except BaseException as error:caught=error;raw=None
    row=records.rows[0]
    checks={"raw_ledger":(records.root/"commands.json").exists(),"no_remaining_children":not adapter.direct_children()}
    if case=="admitted-cli-success":checks.update({"actual_owned_execution":raw==b"admitted\n" and marker.exists(),"launcher_and_intended_argv_bound":row["argv"]==argv and bool(row.get("launcher_argv")) and row["launcher_source"]==adapter.binding(MODULE),"status_and_lifetime":row["status"]==0 and row["lifetime"]["certified"]})
    elif case=="admitted-cli-publication-failure":checks.update({"primary_identity":caught is original,"no_unpublished_execution":not marker.exists(),"birthday_published":row["process_identity"] is not None,"nonpass":row["lifetime"]["certified"] is False})
    else:checks.update({"revocation_rejected":isinstance(caught,adapter.OwnershipError),"never_spawned":row["process_identity"] is None,"no_execution":not marker.exists()})
    return {"status":"passed","checks":checks},"passed"

def birthday_failure_control(root,escaped=False):
    records=adapter.RawCommands(root/"commands");original=RuntimeError("original root birthday failure");real=adapter.child_birthday;created=[];popen=adapter.subprocess.Popen
    def create(*a,**k):
        child=popen(*a,**k);created.append(child);return child
    parent=root/"escaped-birthday.json";escaped_source=root/"escaped.py";root_source=root/"root.py"
    if escaped:
        escaped_source.write_text("import json,os,sys,time\nfrom pathlib import Path\nos.setsid()\nPath(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid()}))\ntime.sleep(10)\n")
        root_source.write_text("import subprocess,time\nsubprocess.Popen("+repr([sys.executable,str(escaped_source),str(parent)])+")\ntime.sleep(10)\n")
    def birthday(child):
        raise original
    adapter.subprocess.Popen=create;adapter.child_birthday=birthday;caught=None
    try:
        try:records.run([sys.executable,str(root_source)] if escaped else [sys.executable,"-c","import time;time.sleep(10)"],2)
        except BaseException as error:caught=error
        checks={"primary_identity":caught is original,"owned_child_gone":not any(adapter.process_identity(child.pid) for child in created),"raw_ledger":(records.root/"commands.json").exists(),"no_numeric_signal":all(r.get("authority")=="held-pidfd" for r in records.rows[0]["lifetime"]["receipts"])}
        if escaped:
            checks.update({"would_escape_target_never_executed":not parent.exists(),"bootstrap_closed_before_restore":records.rows[0]["bootstrap_gate"]["owned_bootstrap_reaped"] is True,"no_target_permit":records.rows[0]["bootstrap_gate"]["permit_sent"] is False})
    finally:
        adapter.child_birthday=real;adapter.subprocess.Popen=popen
        for child in created:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
    return {"status":"passed","checks":checks},"passed"

def parent_death_control(root):
    owner,daemon=setup(root);marker=root/"executed";receipt=root/"published.json"
    adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",{"schema_version":1,"project":owner.project,"nonce":owner.nonce,"state":"creating","certified":False})
    source=root/"controller.py"
    source.write_text("import importlib.util,json,os,sys\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location('owned',"+repr(str(MODULE))+")\nm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nowner=m.OwnerSpec(json.loads(Path("+repr(str(root/"spec.json"))+").read_bytes()))\nr=m.RawCommands(Path("+repr(str(root/"inner"))+"))\nreal=r.save\ndef save():\n if r.rows and r.rows[0]['process_identity'] is not None:\n  m.atomic_json(Path("+repr(str(receipt))+"),r.rows[0]);os._exit(23)\n real()\nr.save=save\nr.run([sys.executable,'-c',"+repr("from pathlib import Path;Path("+repr(str(marker))+").write_text('must not execute')")+"],3,admission_spec=owner)\n")
    libc,prior=adapter.subreaper_begin();child=None;held=None;bootstrap=None;boot_handle=None;known={};actions=[]
    try:
        with (root/"controller.stdout").open("wb") as out,(root/"controller.stderr").open("wb") as err:
            argv=[sys.executable,str(source)];child=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
            identity=adapter.child_birthday(child);held=adapter.open_process_handle(identity)
            deadline=time.monotonic()+3
            while not held.ready() and time.monotonic()<deadline:time.sleep(.01)
            if not held.ready():raise RuntimeError("controlled controller did not exit")
            published=json.loads(receipt.read_bytes());bootstrap=published["process_identity"];boot_handle=adapter.open_process_handle(bootstrap)
            while not boot_handle.ready() and time.monotonic()<deadline:time.sleep(.01)
            natural=boot_handle.ready();status=child.wait(timeout=2)
            fields=Path("/proc/"+str(bootstrap["pid"])+"/stat").read_text().rpartition(") ")[2].split()
            known[bootstrap["pid"]]={**bootstrap,"pgid":int(fields[2]),"session":int(fields[3]),"origin":"recorded-bootstrap"}
            drained=adapter.drain_cli(identity,known,actions,time.monotonic()+2,adopt=False)
        adapter.atomic_json(root/"actual-death.json",{"scope":"owned harmless child, no Docker","controller":identity,"bootstrap":bootstrap,"argv":argv,"status":status,"natural_bootstrap_exit":natural,"actions":actions,"stdout":adapter.binding(root/"controller.stdout"),"stderr":adapter.binding(root/"controller.stderr")})
        return {"status":"passed","checks":{"actual_controller_death":status==23,"blocked_child_exits_on_eof":natural,"no_unpublished_execution":not marker.exists(),"drained_and_no_signal_needed":drained and not actions,"durable_identity_before_permit":bool(published.get("launcher_argv")) and published["lifetime"]["state"]=="running"}},"passed"
    finally:
        if boot_handle is not None:
            if not boot_handle.ready():boot_handle.send(signal.SIGKILL)
            try:os.waitpid(bootstrap["pid"],os.WNOHANG)
            except ChildProcessError:pass
            boot_handle.close()
        if held is not None:
            if not held.ready():held.send(signal.SIGKILL)
            held.close()
        if child is not None:child.wait(timeout=2)
        if libc.prctl(36,prior,0,0,0)!=0:raise RuntimeError("control subreaper restoration failed")

def lock_race_control(root):
    owner,daemon=setup(root);adapter.atomic_json(owner.paths["artifacts"]/"create-admission.json",{"schema_version":1,"project":owner.project,"nonce":owner.nonce,"state":"closed","certified":True})
    source=root/"closer.py"
    source.write_text("import importlib.util,json\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location('owned',"+repr(str(MODULE))+")\nm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nowner=m.OwnerSpec(json.loads(Path("+repr(str(root/"spec.json"))+").read_bytes()))\nm.close_admission(owner)\n")
    child=None
    with (root/"close.stdout").open("wb") as out,(root/"close.stderr").open("wb") as err:
        with adapter.admission_lock(owner):
            child=subprocess.Popen([sys.executable,str(source)],stdout=out,stderr=err,start_new_session=True)
            time.sleep(.05)
            before=not (owner.paths["artifacts"]/"admission-revoked.json").exists()
        status=child.wait(timeout=3)
    caught=None
    try:adapter.admission_write(owner,{"schema_version":1,"project":owner.project,"nonce":owner.nonce,"state":"creating","certified":False})
    except adapter.OwnershipError as error:caught=error
    adapter.atomic_json(root/"closer-command.json",{"argv":[sys.executable,str(source)],"timeout_seconds":3,"status":status,"stdout":adapter.binding(root/"close.stdout"),"stderr":adapter.binding(root/"close.stderr")})
    return {"status":"passed","checks":{"closure_waited_for_atomic_scope":before,"actual_closer_success":status==0,"permanent_closure_refuses_write":caught is not None,"no_reopened_intent":json.loads((owner.paths["artifacts"]/"create-admission.json").read_bytes())["state"]=="closed"}},"passed"

def phase_next_control(root):
    owner,daemon=receipt_daemon(root,0)
    first,_,_=invoke_fake(owner,daemon)
    second,_,_=invoke_fake(owner,daemon)
    return {"status":"passed","checks":{"two_owned_phases":first==second==0,"phase_cleanup_not_global_revocation":not (owner.paths["artifacts"]/"admission-revoked.json").exists(),"previous_owned_ids_retained":bool(list(owner.paths["artifacts"].glob("between-up-*/cleanup.json")))}},"passed"

def wrong_configured_control(case,root):
    owner,daemon=setup(root);state=daemon.read()
    for entry in state["containers"].values():
        entry["State"]["Running"]=False
        for value in entry["NetworkSettings"]["Networks"].values():value.update({"NetworkID":"","EndpointID":""})
    for network in state["networks"].values():network["Containers"]={}
    configured={"schema_version":1,"project":owner.project,"nonce":owner.nonce,"containers":{entry["Id"]:{name:("7" if name.endswith("leftnet") else "8")*64 for name in entry["NetworkSettings"]["Networks"]} for entry in state["containers"].values()},"networks":{n["Name"]:n["Id"] for n in state["networks"].values()}}
    configured["containers"]["2"*64][owner.project+"_rightnet"]="f"*64
    adapter.atomic_json(owner.paths["artifacts"]/"configured-topology.json",configured)
    caught=None
    try:adapter.verified_topology(owner,list(state["containers"].values()),list(state["networks"].values()))
    except adapter.OwnershipError as error:caught=error
    return {"status":"passed","checks":{"foreign_configured_bridge_rejected":caught is not None,"no_daemon_mutation":not daemon.read()["events"]}},"passed"

def bootstrap_control(case,root):
    if case in ("raw-birthday-failure","raw-birthday-failure-escaped"):return birthday_failure_control(root,case.endswith("-escaped"))
    if case=="admitted-cli-controller-death":return parent_death_control(root)
    if case=="admission-close-lock-race":return lock_race_control(root)
    if case=="phase-next-admission":return phase_next_control(root)
    if case in ("created-wrong-configured-id","stopped-wrong-configured-id"):return wrong_configured_control(case,root)
    return admitted_control(case,root)

NEXT_CASES=("held-empty-nonready","held-empty-later-ready","held-empty-already-ready","compose-server-renewal","compose-client-renewal","compose-workload-attachment","retained-file-sentinel","retained-file-timeout","retained-file-nonzero","pidfd-post-popen-emfile","pidfd-post-popen-attribute","pidfd-post-popen-gate-close","sigchld-preflight-ignored","server-exit-live-simulator","compose-unknown-service","compose-dependency-recreation","compose-dependency-foreign-object")
CASES+=NEXT_CASES

def held_empty_control(case,root):
    identity={"pid":424255,"start_ticks":901};member={"pid":424256,"start_ticks":902,"pgid":424255,"session":424255}
    events=[];state=[case=="held-empty-already-ready"];real=adapter.cli_members;numeric=adapter.os.kill
    class Held:
        def __init__(self):self.identity=dict(member);self.closed=False
        def ready(self):return state[0]
        def send(self,sig):
            events.append({"identity":dict(self.identity),"signal":sig})
            if case=="held-empty-later-ready":state[0]=True
            return True
        def close(self):self.closed=True
    handle=Held();known={member["pid"]:dict(member)};handles={member["pid"]:handle};receipts=[]
    adapter.cli_members=lambda *a,**k:[];adapter.os.kill=lambda *a,**k:(_ for _ in ()).throw(RuntimeError("numeric signal forbidden"))
    try:
        result=adapter.drain_cli(identity,known,receipts,time.monotonic()+.05,handles=handles)
        latched=adapter.cli_key(identity) in adapter._extinct_cli
    finally:
        adapter.cli_members=real;adapter.os.kill=numeric;adapter._extinct_cli.discard(adapter.cli_key(identity))
    checks={"empty_rows_do_not_override_held_life":result==(case!="held-empty-nonready"),"extinction_only_when_ready":latched==(case!="held-empty-nonready"),"held_signal_when_nonready":bool(events)==(case!="held-empty-already-ready"),"no_early_handle_release":not handle.closed}
    adapter.atomic_json(root/"held-transitions.json",{"scope":"mock thread-group-exit transition only; no real foreign PID/reuse","known":known,"events":events,"receipts":receipts,"ready":state[0],"result":result,"latched":latched})
    return {"status":"passed","checks":checks},"passed"

def exact_compose_control(case,root,pinned_runner):
    import shutil
    records=adapter.RawCommands(root/"pinned-input-commands")
    git=shutil.which("git")
    if git is None:raise adapter.OwnershipError("existing git missing for pinned source fixture")
    pinned=records.run([git,"-C",str(pinned_runner),"show",adapter.PIN+":docker-compose.yml"],5,max_bytes=65536)
    fixture=root/"pinned-compose.yml";fixture.write_bytes(pinned)
    graph={};role=None;depends=False
    for line in pinned.decode("utf-8").splitlines():
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            role=line.strip()[:-1];graph[role]=[];depends=False
        elif role is not None and line=="    depends_on:":depends=True
        elif depends and line.startswith("      - "):graph[role].append(line[8:])
        elif line and not line.startswith("      "):depends=False
    selected_graph={r:graph.get(r) for r in adapter.ROLES}
    if selected_graph!={"sim":[],"server":["sim"],"client":["sim"]}:raise adapter.OwnershipError("pinned endpoint dependency graph differs")
    server_phase=case in ("compose-server-renewal","server-exit-live-simulator","compose-dependency-recreation","compose-dependency-foreign-object")
    owner,base=receipt_daemon(root,127 if case=="server-exit-live-simulator" else 0);commands=[];original=base.command;model={}
    def command(*args,**kwargs):
        commands.append(list(args));prepare="create" in args or "--no-start" in args
        modeled=list(args)
        if "--no-start" in modeled:modeled[modeled.index("up")]="create"
        raw=original(*modeled,**kwargs)
        state=base.read()
        if prepare:
            roles={v for v in args if v in adapter.ROLES}
            state["containers"]={k:v for k,v in state["containers"].items() if v["Config"]["Labels"]["com.docker.compose.service"] in roles}
            for network in state["networks"].values():network["Containers"]={k:v for k,v in network["Containers"].items() if k in state["containers"]}
            model["created_ids"]=sorted(state["containers"])
        else:
            monitored=[v for v in args if v in adapter.ROLES]
            started=[]
            def visit(role):
                if role in started:return
                if "--no-deps" not in args:
                    for dependency in selected_graph[role]:visit(dependency)
                started.append(role)
            for role in monitored:visit(role)
            model.update({"monitored_services":monitored,"started_services":started,"dependency_graph":selected_graph,"recreate":False if "--no-recreate" in args else True})
            if case=="server-exit-live-simulator":
                for identity,entry in state["containers"].items():
                    role=entry["Config"]["Labels"]["com.docker.compose.service"]
                    entry["State"]={"Running":role=="sim" and role in started,"ExitCode":127 if role=="server" else 0}
                    for name,value in entry["NetworkSettings"]["Networks"].items():
                        network=next(v for v in state["networks"].values() if v["Name"]==name)
                        if entry["State"]["Running"]:network["Containers"][identity]={};value["NetworkID"]=network["Id"]
                        else:network["Containers"].pop(identity,None);value["NetworkID"]=""
                model["events"]=[{"service":"sim","event":"running"},{"service":"server","event":"exited","status":127}]
                model["simulator_alive"]=state["containers"]["1"*64]["State"]["Running"]
                model["monitor_complete"]=all(not entry["State"]["Running"] for entry in state["containers"].values() if entry["Config"]["Labels"]["com.docker.compose.service"] in monitored)
                adapter.atomic_json(base.path,state)
                adapter.atomic_json(root/"monitor-model.json",model)
                if not model["monitor_complete"]:raise subprocess.TimeoutExpired(list(args),kwargs["timeout"])
                raw=b"mock server UNSUPPORTED\n"
                if kwargs.get("stream_output",False):sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
                return raw
            if case in ("compose-dependency-recreation","compose-dependency-foreign-object"):
                entry=json.loads(json.dumps(state["containers"]["1"*64]))
                if case=="compose-dependency-recreation":state["containers"].pop("1"*64)
                else:entry["Config"]["Labels"]["com.docker.compose.service"]="foreign"
                entry["Id"]="9"*64;state["containers"]["9"*64]=entry
                model["injected_unreviewed_id"]="9"*64
        adapter.atomic_json(base.path,state)
        return raw
    base.command=command
    argv=["compose","--env-file","empty.env","up"]+(
        ["-V","server"] if server_phase else
        ["--timeout","0","--abort-on-container-exit","-V","sim","client"] if case=="compose-client-renewal" else
        ["--abort-on-container-exit","--timeout","10","sim","client","server"])
    if case=="compose-unknown-service":argv.append("foreign")
    real=adapter.runner_daemon;keys=("SERVER","CLIENT","TESTCASE_SERVER");old={k:os.environ.get(k) for k in keys};out=sys.stdout;err=sys.stderr
    import io
    class Output:
        def __init__(self):self.buffer=io.BytesIO()
        def flush(self):pass
    captured_out=Output();captured_err=Output()
    adapter.runner_daemon=lambda:(owner,base);os.environ["SERVER"]=IMAGE;os.environ["CLIENT"]=IMAGE
    if case=="server-exit-live-simulator":os.environ["TESTCASE_SERVER"]="mock-unsupported"
    sys.stdout=captured_out;sys.stderr=captured_err;status=None;caught=None
    try:
        try:status=adapter.docker_entry(argv)
        except (adapter.OwnershipError,subprocess.TimeoutExpired) as error:caught=error
    finally:
        adapter.runner_daemon=real;sys.stdout=out;sys.stderr=err
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    prefix=["compose","--project-name",owner.project,"--file",str(owner.paths["compose_path"]),"--env-file",str(owner.paths["runner_root"]/"empty.env")]
    created_roles=["sim","server"] if server_phase else ["sim","client"] if case=="compose-client-renewal" else ["sim","server","client"]
    attached_roles=["server"] if server_phase else ["sim","client"] if case=="compose-client-renewal" else ["sim","client","server"]
    flags=[] if server_phase else ["--timeout","0","--abort-on-container-exit"] if case=="compose-client-renewal" else ["--abort-on-container-exit","--timeout","10"]
    expected_prepare=prefix+(["up","--no-start","--pull","never","--no-build","-V"] if "-V" in argv else ["create","--pull","never","--no-build","--no-recreate"])+created_roles
    expected_attached=prefix+["up","--no-build","--no-recreate","--pull","never"]+flags+attached_roles
    adapter.atomic_json(root/"phase-argv.json",{"scope":"mock pinned source phases and monitor; no actual Docker behavior proof","pinned_commit":adapter.PIN,"pinned_fixture":adapter.binding(fixture),"pinned_source_commands":records.rows,"dependency_graph":selected_graph,"upstream":argv,"commands":commands,"expected_prepare":expected_prepare,"expected_attached":expected_attached,"model":model,"caught":None if caught is None else {"type":type(caught).__name__,"message":str(caught)}})
    if case=="compose-unknown-service":
        checks={"unknown_selected_service_rejected":isinstance(caught,adapter.OwnershipError),"no_daemon_command":not commands}
    elif case in ("compose-dependency-recreation","compose-dependency-foreign-object"):
        admission=json.loads((owner.paths["artifacts"]/"create-admission.json").read_bytes())
        checks={"changed_dependency_objects_rejected":isinstance(caught,adapter.OwnershipError),"admission_uncertified":admission["state"]=="interrupted-uncertified" and admission["certified"] is False,"exact_precreated_dependency_ids":admission["created_ids"]==model["created_ids"],"injected_object_retained":model["injected_unreviewed_id"] in base.read()["containers"]}
    else:
        checks={"exact_setup_and_attached_argv":commands==[expected_prepare,expected_attached],"no_flag_conflict":all(not ("-V" in c and "--no-recreate" in c) for c in commands),"attached_abort_timeout_preserved":commands[-1]==expected_attached,"exact_up_status":status==(127 if case=="server-exit-live-simulator" else 0),"original_selected_monitor_roles":model.get("monitored_services")==attached_roles,"dependency_start_order":model.get("started_services")==(["sim","server"] if server_phase else ["sim","client"] if case=="compose-client-renewal" else ["sim","client","server"]),"no_dependency_recreation":model.get("recreate") is False}
        if case=="server-exit-live-simulator":checks.update({"server_returns_with_simulator_alive":caught is None and model.get("monitor_complete") is True and model.get("simulator_alive") is True,"exact_unsupported_output":captured_out.buffer.getvalue()==b"mock server UNSUPPORTED\n"})
    return {"status":"passed","checks":checks},"passed"

def retained_file_control(case,root):
    records=adapter.RawCommands(root/"commands");original=RuntimeError("original retained file sentinel")
    real_open=Path.open;real_selector=adapter.selectors.DefaultSelector;closed=[];injections=[]
    class Retained:
        def __init__(self,file,name):self.file=file;self.name=name;self.failed=False
        def __getattr__(self,name):return getattr(self.file,name)
        def __enter__(self):return self
        def __exit__(self,*args):self.close()
        def close(self):
            closed.append(self.name)
            self.file.close()
            if not self.failed:self.failed=True;injections.append(self.name);raise OSError("secondary retained "+self.name+" FILE close")
    def opened(path,*args,**kwargs):
        file=real_open(path,*args,**kwargs)
        if Path(path).parent==records.root and Path(path).name in ("000.stdout","000.stderr") and (args[0] if args else kwargs.get("mode"))=="wb":return Retained(file,Path(path).name)
        return file
    timeout_original=subprocess.TimeoutExpired([sys.executable,"-c","owned"],.1)
    class Selected:
        def __init__(self):self.real=real_selector()
        def register(self,*args,**kwargs):return self.real.register(*args,**kwargs)
        def get_map(self):return self.real.get_map()
        def select(self,*args,**kwargs):raise timeout_original if case=="retained-file-timeout" else original
        def close(self):return self.real.close()
    Path.open=opened
    if case!="retained-file-nonzero":adapter.selectors.DefaultSelector=Selected
    caught=None
    try:
        try:records.run([sys.executable,"-c","import sys;print('status37');sys.exit(37)"] if case=="retained-file-nonzero" else [sys.executable,"-c","import time;time.sleep(10)"],3)
        except BaseException as error:caught=error
    finally:Path.open=real_open;adapter.selectors.DefaultSelector=real_selector
    row=records.rows[0]
    desired=isinstance(caught,adapter.CleanupError) and str(caught)=="owned command failed: 37" and row["status"]==37 if case=="retained-file-nonzero" else caught is (timeout_original if case=="retained-file-timeout" else original)
    return {"status":"passed","checks":{"original_primary_identity_or_exact37":desired,"both_retained_FILES_closed":set(injections)=={"000.stdout","000.stderr"},"secondary_FILE_errors_retained":sum("retained" in e["message"] and "FILE close" in e["message"] for e in row["finalization_errors"])==2,"secondary_notes_on_primary":sum("FILE close" in n for n in getattr(caught,"__notes__",[]))==2,"owned_children_drained":not adapter.direct_children(),"final_raw_ledger":(records.root/"commands.json").exists()}},"passed"

def post_pidfd_control(case,root):
    import errno
    records=adapter.RawCommands(root/"commands");target=root/"target-executed";created=[];restored=[];real_popen=adapter.subprocess.Popen;real_open=adapter.os.pidfd_open;real_begin=adapter.subreaper_begin
    original=AttributeError("one-shot post-Popen pidfd missing") if case=="pidfd-post-popen-attribute" else OSError(errno.EMFILE,"one-shot post-Popen pidfd allocation")
    failed=[False];prior=subreaper_value();pipe_pairs=[];close_fault=[False];real_pipe=adapter.os.pipe;real_close=adapter.os.close
    def pipe():
        pair=real_pipe();pipe_pairs.append(pair);return pair
    def close(fd):
        if case=="pidfd-post-popen-gate-close" and pipe_pairs and fd==pipe_pairs[0][1] and not close_fault[0]:
            close_fault[0]=True;raise OSError("secondary bootstrap gate FILE descriptor close")
        return real_close(fd)
    def popen(*args,**kwargs):
        child=real_popen(*args,**kwargs);created.append(child);return child
    def opened(pid,*args,**kwargs):
        if created and pid==created[-1].pid and not failed[0]:failed[0]=True;raise original
        return real_open(pid,*args,**kwargs)
    class Libc:
        def __init__(self,real):self.real=real
        def prctl(self,*args):
            if args[0]==36:restored.append(all(child.returncode is not None for child in created))
            return self.real.prctl(*args)
    def begin():
        libc,value=real_begin();return Libc(libc),value
    adapter.subprocess.Popen=popen;adapter.os.pidfd_open=opened;adapter.subreaper_begin=begin;adapter.os.pipe=pipe;adapter.os.close=close;caught=None
    try:
        argv=[sys.executable,"-c","from pathlib import Path;import time;Path("+repr(str(target))+").write_text('must not execute');time.sleep(10)"]
        try:records.run(argv,3)
        except BaseException as error:caught=error
        time.sleep(.1)
        checks={"actual_post_Popen_fault":failed[0] and bool(created),"original_fd_error_identity":caught is original,"target_never_executed":not target.exists(),"exact_bootstrap_reaped":all(child.returncode is not None for child in created),"restore_after_owned_closure":bool(restored) and all(restored),"nonpass_raw_ledger":records.rows[0]["lifetime"]["certified"] is False and (records.root/"commands.json").exists(),"no_numeric_signal_fallback":all(r.get("authority")=="held-pidfd" for r in records.rows[0]["lifetime"]["receipts"])}
        if case=="pidfd-post-popen-gate-close":
            checks.update({"actual_secondary_gate_close":close_fault[0],"gate_close_preserves_primary":caught is original and any("gate FILE descriptor close" in n for n in getattr(original,"__notes__",[]))})
    finally:
        adapter.subprocess.Popen=real_popen;adapter.os.pidfd_open=real_open;adapter.subreaper_begin=real_begin;adapter.os.pipe=real_pipe;adapter.os.close=real_close
        # Exact test-owned Popen cleanup after recording assertions. This is
        # not a production numeric fallback nor a foreign/reuse probe.
        for child in created:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
        import ctypes
        ctypes.CDLL(None).prctl(36,prior,0,0,0)
    return {"status":"passed","checks":checks},"passed"

def sigchld_control(root):
    records=adapter.RawCommands(root/"commands");real=adapter.subprocess.Popen;created=[];old=signal.getsignal(signal.SIGCHLD);caught=None
    def popen(*args,**kwargs):child=real(*args,**kwargs);created.append(child);return child
    adapter.subprocess.Popen=popen;signal.signal(signal.SIGCHLD,signal.SIG_IGN)
    try:
        try:records.run([sys.executable,"-c","import time;time.sleep(3)"],.1)
        except BaseException as error:caught=error
        checks={"SIGCHLD_ignored_rejected_prelaunch":isinstance(caught,adapter.OwnershipError),"no_child_spawned":not created,"raw_rejection_ledger":(records.root/"commands.json").exists()}
    finally:
        signal.signal(signal.SIGCHLD,old);adapter.subprocess.Popen=real
        for child in created:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
    return {"status":"passed","checks":checks},"passed"

def next_control(case,root,pinned_runner):
    if case.startswith("held-empty-"):return held_empty_control(case,root)
    if case.startswith("compose-") or case=="server-exit-live-simulator":return exact_compose_control(case,root,pinned_runner)
    if case.startswith("retained-file-"):return retained_file_control(case,root)
    if case=="sigchld-preflight-ignored":return sigchld_control(root)
    return post_pidfd_control(case,root)

FORWARD_CASES=("raw-forward-incremental","raw-forward-stderr-status","raw-forward-no-duplicate",
               "raw-forward-empty","raw-forward-private-json","raw-forward-backpressure")
CASES+=FORWARD_CASES

def forwarding_death_setup(parent_pid):
    # Test-only, single-threaded Linux pre-exec setup. The production bootstrap
    # still performs its original gate/publication and lifetime protocol.
    import ctypes
    libc=ctypes.CDLL(None,use_errno=True)
    def install():
        if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:os._exit(125)
        # Close the parent-death race before running any bootstrap/target code.
        if os.getppid()!=parent_pid:os._exit(125)
    return install

def forwarding_replay_control(root):
    # Actual docker_entry branch, mock Docker boundaries, no processes/daemon.
    owner,daemon=receipt_daemon(root);real_command=daemon.command;calls=[]
    payload=b"ready-out\ntail-out\n"
    def command(*args,**kwargs):
        raw=real_command(*args,**kwargs);calls.append({"argv":list(args),"stream_output":kwargs.get("stream_output",False)})
        if "up" in args:
            if kwargs.get("stream_output",False):sys.stdout.buffer.write(payload)
            return payload
        return raw
    daemon.command=command
    status,out,err=invoke_fake(owner,daemon)
    intent=json.loads((owner.paths["artifacts"]/"create-admission.json").read_bytes())
    ups=[value for value in calls if "up" in value["argv"]]
    return {"status":"passed","scope":"actual docker_entry with mocked Docker boundaries only",
            "checks":{"adapter_branch_completed":status==0 and intent["state"]=="closed" and intent["certified"] is True,
                      "actual_workload_opt_in":len(ups)==1 and ups[0]["stream_output"] is True,
                      "stdout_replay_absent":out==payload,"stderr_replay_absent":err==b"exact up stderr\n",
                      "create_not_forwarded":all(value["stream_output"] is False for value in calls if "create" in value["argv"])}},"passed"

def forwarding_control(case,root):
    if case=="raw-forward-no-duplicate":return forwarding_replay_control(root)
    # Real harmless subprocesses only. The caller survives communicate(timeout).
    mode="private" if case=="raw-forward-private-json" else "blocked" if case=="raw-forward-backpressure" else "stream"
    empty=case=="raw-forward-empty";code=7 if case=="raw-forward-stderr-status" else 0
    ready=b"" if empty else b'{"inspect":"mock"}\n' if mode=="private" else b"ready-out\n"
    warning=b"" if empty or mode=="private" else b"ready-err\n"
    tail=b"" if empty or mode=="private" else b"tail-out\n";tailerr=b"" if empty or mode=="private" else b"tail-err\n"
    emitted=root/"emitted.json";release=root/"release";worker_result=root/"worker-result.json"
    producer=root/"producer.py";worker=root/"worker.py";worker_ready=root/"worker-ready.json"
    producer.write_text(
        "import ctypes,json,os,time\nfrom pathlib import Path\n"
        +"libc=ctypes.CDLL(None);death=ctypes.c_int();assert libc.prctl(2,ctypes.byref(death),0,0,0)==0\n"
        +"fields=Path('/proc/self/stat').read_text().rpartition(') ')[2].split()\n"
        +"birth={'pid':os.getpid(),'start_ticks':int(fields[19]),'pgid':int(fields[2]),'session':int(fields[3]),'parent_pid':os.getppid(),'parent_death_signal':death.value}\n"
        +"os.write(1,"+repr(ready)+");os.write(2,"+repr(warning)+")\n"
        +"published=Path("+repr(str(emitted))+ ");temporary=published.with_suffix('.tmp');temporary.write_text(json.dumps(birth));os.replace(temporary,published)\n"
        +("os.write(1,b'x'*(2*1024*1024))\n" if mode=="blocked" else
          "deadline=time.monotonic()+8\nwhile not Path("+repr(str(release))+").exists():\n"
          +" if time.monotonic()>deadline:raise SystemExit(9)\n time.sleep(.01)\n")
        +"os.write(1,"+repr(tail)+");os.write(2,"+repr(tailerr)+")\nraise SystemExit("+str(code)+")\n")
    worker.write_text(
        "import ctypes,hashlib,importlib.util,inspect,json,os,signal,sys\nfrom pathlib import Path\n"
        +"path=Path("+repr(str(MODULE))+");before=path.read_bytes()\n"
        +"spec=importlib.util.spec_from_file_location('owned',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
        +"libc=ctypes.CDLL(None,use_errno=True);death=ctypes.c_int();assert libc.prctl(2,ctypes.byref(death),0,0,0)==0\n"
        +"m.atomic_json(Path("+repr(str(worker_ready))+"),{'identity':m.process_identity(os.getpid()),'pgid':os.getpgrp(),'parent_pid':os.getppid(),'parent_death_signal':death.value})\n"
        +"expected=os.getpid();original_popen=m.subprocess.Popen\n"
        +"def install():\n if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:os._exit(125)\n if os.getppid()!=expected:os._exit(125)\n"
        +"def owned_popen(*args,**kwargs):\n assert kwargs.get('preexec_fn') is None\n kwargs['preexec_fn']=install\n return original_popen(*args,**kwargs)\n"
        +"m.subprocess.Popen=owned_popen\n"
        +"r=m.RawCommands(Path("+repr(str(root/"commands"))+"));failure=None;raw=b''\n"
        +"available='stream_output' in inspect.signature(r.run).parameters\n"
        +"stream=available and "+repr(mode!="private")+"\n"
        +"options={'stream_output':stream} if available else {}\n"
        +"blocking=[os.get_blocking(1),os.get_blocking(2)]\n"
        +"try:raw=r.run([sys.executable,'-B',"+repr(str(producer))+"],"+("1.0" if mode=="blocked" else "5.0")+",check=False,**options)\n"
        +"except BaseException as e:failure={'type':type(e).__name__,'message':str(e)}\n"
        +"finally:m.subprocess.Popen=original_popen\n"
        +"value={'row':r.rows[0],'failure':failure,'api_present':available,'blocking_before':blocking,'blocking_after':[os.get_blocking(1),os.get_blocking(2)],'source_equal':path.read_bytes()==before,'raw_sha256':hashlib.sha256(raw).hexdigest()}\n"
        +"m.atomic_json(Path("+repr(str(worker_result))+"),value)\n"
        # Old valid API + its original late replay are the genuine baseline.
        +"if "+repr(mode!="private")+" and not available and failure is None:\n"
        +" sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()\n"
        +" sys.stderr.buffer.write(Path(r.rows[0]['stderr']['path']).read_bytes());sys.stderr.buffer.flush()\n"
        +"raise SystemExit("+str(code)+" if failure is None else 0)\n")
    subreaper=adapter.subreaper_begin();proc=None;handles=[];worker_handle=None;producer_handle=None
    custody={"outer_group":os.getpgrp(),"driver_identity":adapter.process_identity(os.getpid()),"forced_cleanup":False,"signals":[],"reaped":[],"handles":[],"subreaper_restored":False}
    worker_identity=None;producer_identity=None;early_stdout=None;early_stderr=None;expired=False;forced=False
    early_private_stdout=b"";early_private_stderr=b"";live_at_observation=False;stdout=b"";stderr=b""
    try:
        # Stay in the accepted outer guard's group, with kernel death coupling
        # as well; the worker's producer is still RawCommands' own new session.
        proc=subprocess.Popen([sys.executable,"-B",str(worker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              preexec_fn=forwarding_death_setup(os.getpid()))
        worker_handle=adapter.open_owned_child_handle(proc);handles.append(worker_handle)
        worker_identity=adapter.process_identity(proc.pid);custody["worker_identity"]=worker_identity
        if worker_identity is None:raise RuntimeError("worker birth unavailable")
        worker_handle.identity=dict(worker_identity)
        deadline=time.monotonic()+4
        while not emitted.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        if not emitted.exists():raise RuntimeError("harmless producer did not start")
        producer_identity=json.loads(emitted.read_bytes());custody["producer_identity"]=producer_identity
        producer_handle=adapter.open_process_handle(producer_identity);handles.append(producer_handle)
        if mode=="blocked":
            # Do not drain until the original command deadline has completed.
            deadline=time.monotonic()+7
            while not worker_result.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            if not worker_result.exists():raise RuntimeError("backpressure did not finish within the control bound")
        else:
            try:stdout,stderr=proc.communicate(timeout=.4)
            except subprocess.TimeoutExpired as error:
                expired=True;early_stdout=error.stdout;early_stderr=error.stderr
                live_at_observation=proc.poll() is None
                for filename,stream in (("000.stdout","stdout"),("000.stderr","stderr")):
                    p=root/"commands"/filename;data=p.read_bytes() if p.exists() else b""
                    if stream=="stdout":early_private_stdout=data
                    else:early_private_stderr=data
            release.touch()
        stdout,stderr=proc.communicate(timeout=8)
    finally:
        release.touch(exist_ok=True)
        if proc is not None and proc.poll() is None:
            try:stdout,stderr=proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                forced=True
                if worker_handle is None:worker_handle=adapter.open_owned_child_handle(proc);handles.append(worker_handle)
                worker_handle.send(signal.SIGTERM);custody["signals"].append({"identity":worker_identity,"signal":"SIGTERM","authority":"held-pidfd"})
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    worker_handle.send(signal.SIGKILL);custody["signals"].append({"identity":worker_identity,"signal":"SIGKILL","authority":"held-pidfd"});proc.wait(timeout=2)
        # Parent is the exclusive subreaper: if the worker failed before its
        # result/identity publication, a producer killed by PDEATHSIG is adopted
        # here. Discovery never opens or signals an unrelated session by PID.
        for identity in adapter.direct_children():
            forced=True;handle=adapter.open_process_handle(identity);handles.append(handle)
            if not handle.ready():
                handle.send(signal.SIGKILL);custody["signals"].append({"identity":identity,"signal":"SIGKILL","authority":"exclusive-subreaper-held-pidfd"})
            expiry=time.monotonic()+2
            while True:
                pid,status=os.waitpid(identity["pid"],os.WNOHANG)
                if pid:break
                if time.monotonic()>=expiry:
                    adapter.atomic_json(root/"custody.json",custody)
                    raise RuntimeError("adopted harmless producer did not reap within bound")
                time.sleep(.01)
            custody["reaped"].append({"identity":identity,"pid":pid,"wait_status":status})
        deadline=time.monotonic()+2
        while not all(handle.ready() for handle in handles) and time.monotonic()<deadline:time.sleep(.01)
        custody["forced_cleanup"]=forced;custody["handles"]=[{"identity":handle.identity,"ready":handle.ready()} for handle in handles]
        if not all(handle.ready() for handle in handles):
            adapter.atomic_json(root/"custody.json",custody)
            raise RuntimeError("harmless test lifetime remains unresolved")
        for handle in handles:handle.close()
        libc,prior=subreaper
        if libc.prctl(36,prior,0,0,0)!=0:raise RuntimeError("harmless test subreaper restoration failed")
        custody["subreaper_restored"]=True;adapter.atomic_json(root/"custody.json",custody)
    value=json.loads(worker_result.read_bytes());row=value["row"];lifetime=row["lifetime"]
    worker_birth=json.loads(worker_ready.read_bytes())
    private_stdout=Path(row["stdout"]["path"]).read_bytes();private_stderr=Path(row["stderr"]["path"]).read_bytes()
    def absent(identity):
        # A zombie with the same birthday is still an unreaped lifetime.
        try:fields=Path("/proc/"+str(identity["pid"])+"/stat").read_text().rpartition(") ")[2].split()
        except (FileNotFoundError,ProcessLookupError):return True
        return int(fields[19])!=identity["start_ticks"]
    identities=lifetime.get("members",[])
    physical_closed=all(absent(identity) for identity in identities)
    worker_absent=worker_identity is not None and absent(worker_identity)
    producer_absent=producer_identity is not None and absent(producer_identity)
    checks={"real_child_executed":row["process_identity"] is not None,"source_unchanged":value["source_equal"],
            "physical_lifetime_closed":physical_closed and worker_absent and producer_absent and all(item["ready"] for item in custody["handles"]),
            "root_wait_recorded":type(row["status"]) is int,"no_forced_worker_cleanup":not forced,
            "sink_mode_restored":value["blocking_before"]==value["blocking_after"],
            "outer_group_owns_worker":worker_birth["pgid"]==custody["outer_group"],
            "kernel_death_chain":worker_birth["parent_pid"]==os.getpid() and worker_birth["parent_death_signal"]==signal.SIGKILL and producer_identity["parent_pid"]==proc.pid and producer_identity["parent_death_signal"]==signal.SIGKILL,
            "producer_separate_session_bound":producer_identity["pid"]==producer_identity["pgid"]==producer_identity["session"] and all(row["process_identity"][key]==producer_identity[key] for key in ("pid","start_ticks")),
            "subreaper_restored":custody["subreaper_restored"]}
    if mode=="blocked":
        checks.update({"actual_timeout_preserved":value["failure"] is not None and value["failure"]["type"]=="TimeoutExpired" and row["timed_out"] is True and row["primary_exception"]["type"]=="TimeoutExpired",
                       "abort_not_certified":lifetime["certified"] is False,
                       "private_retention_bounded":row["stdout"]["bytes"]<=adapter.MAX_BYTES,
                       "control_worker_not_protocol_verdict":proc.returncode==0})
    else:
        checks.update({"normal_child_status":row["status"]==code and proc.returncode==code,
                       "normal_lifetime_state_closed":lifetime["state"]=="closed","normal_lifetime_certified":lifetime["certified"] is True,
                       "caller_timeout_observed":expired and live_at_observation,
                       "private_exact_stdout":private_stdout==ready+tail,"private_exact_stderr":private_stderr==warning+tailerr})
        if empty:
            try:early_stdout.decode("utf-8",errors="replace")
            except AttributeError:literal_error=True
            else:literal_error=False
            checks.update({"empty_still_literal_error":literal_error and early_stdout is None,
                           "no_fabricated_upstream_bytes":stdout==b"" and stderr==b""})
        elif mode=="private":
            checks.update({"structured_json_not_forwarded":early_stdout is None and early_stderr is None and stdout==b"" and stderr==b""})
            daemon=object.__new__(adapter.DockerDaemon);mock_cli=root/"mock-cli";mock_cli.write_bytes(b"mock binding, never executed")
            daemon.docker=str(mock_cli);daemon.cli=adapter.binding(mock_cli);daemon.spec=object();calls=[]
            class Capture:
                def run(self,*args,**kwargs):calls.append(kwargs);return b'{"mock":true}'
            daemon.commands=Capture();daemon.command("inspect","mock");daemon.command("compose","create","mock")
            checks["inspect_create_default_private"]=len(calls)==2 and all(x.get("stream_output",False) is False for x in calls)
        else:
            checks.update({"early_ready_stdout":early_stdout is not None and early_stdout.startswith(ready),
                           "early_ready_stderr":early_stderr is not None and early_stderr.startswith(warning),
                           "early_private_before_forward":early_private_stdout.startswith(ready) and early_private_stderr.startswith(warning),
                           "upstream_exact_once":stdout==ready+tail and stderr==warning+tailerr})
    result={"status":"passed","scope":"harmless forwarding control only; no Docker/network or official verdict",
            "checks":checks,"worker_identity":worker_identity,"worker_status":proc.returncode,"worker_result":value,"custody":custody,
            "early":{"caller_timed_out":expired,"worker_still_running":live_at_observation,
                     "stdout_bytes":None if early_stdout is None else len(early_stdout),
                     "stderr_bytes":None if early_stderr is None else len(early_stderr),
                     "private_stdout_bytes":len(early_private_stdout),"private_stderr_bytes":len(early_private_stderr)}}
    return result,"passed"


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
            if case in FORWARD_CASES:result,expected=forwarding_control(case,root)
            elif case in NEXT_CASES:result,expected=next_control(case,root,args.pinned_runner)
            elif case in BOOT_CASES:result,expected=bootstrap_control(case,root)
            elif case in REVIEW_CASES:result,expected=review_control(case,root)
            elif case=="copy-official-fixture-layout":result,expected=copy_layout_control(root)
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
