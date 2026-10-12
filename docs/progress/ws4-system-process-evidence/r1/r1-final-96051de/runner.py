from pathlib import Path
import subprocess,hashlib,json,os,datetime,stat,platform
root=Path('/home/user/ws4/system-r2'); os.chdir(root)
manifest=json.loads(Path('source-96051de.json').read_text())
assert manifest['source_commit']=='96051dedc6c5716819d2f0fcd5a2240ab8d1314f'
for f in manifest['files']:
 p=Path(f['path']); assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']; assert oct(stat.S_IMODE(p.stat().st_mode))==f['mode']
expected={'build/minyarc':'f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b','build/minyar-default-runtime.o':'effee3192380318446fa53efc9d223dfb98aa04a37bb0c236889bf1131ff306a'}
for name,sha in expected.items(): assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha
out=Path('evidence/r1-final-96051de');out.mkdir()
Path('build/tmp').mkdir(parents=True,exist_ok=True)
env=dict(os.environ,TMPDIR=str(root/'build/tmp'),ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
records=[]
def captured(command,name,timeout=240):
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 result=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 log=out/(name+'.log');log.write_bytes(result.stdout)
 records.append({'command':list(map(str,command)),'exit_code':result.returncode,'started_utc':started,'log':str(log),'log_sha256':hashlib.sha256(result.stdout).hexdigest()})
 receipt={'source':manifest,'artifacts':expected,'host':platform.platform(),'runner_pid':os.getpid(),'environment':{k:env[k] for k in ('TMPDIR','ASAN_OPTIONS','UBSAN_OPTIONS')},'commands':records}
 (out/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(name,'exit',result.returncode,flush=True); print(result.stdout.decode(errors='replace'),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 return result.stdout
captured(['clang','--version'],'clang-version')
captured(['python3','--version'],'python-version')
captured(['uname','-a'],'uname')
for i,cmd in enumerate([
 ['python3','tests/system-services.py','--language','--prebuilt'],
 ['python3','tests/system-services.py','--mode','sanitize','--language','--prebuilt'],
 ['python3','tests/system-process.py','--language','--prebuilt'],
 ['python3','tests/system-process.py','--mode','sanitize','--language','--prebuilt'],
 ['python3','tests/system-process.py','--root'],
 ['python3','tests/system-process.py','--mode','sanitize','--root']]): captured(cmd,f'qualification-{i}')
captured(['python3','tests/system-process-boundary.py','--evidence',str(out/'boundary')],'boundary-controls',timeout=300)
for name,sha in expected.items(): assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha
(out/'complete.json').write_text(json.dumps({'source_commit':manifest['source_commit'],'all_suite_exit_codes_zero':True,'compiler_and_runtime_unchanged':True,'boundary_controls_failures':0,'native_aarch64_execution':False},indent=2)+'\n')
print('source-pinned R1 correction qualification complete',flush=True)
