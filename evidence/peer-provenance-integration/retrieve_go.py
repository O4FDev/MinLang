from pathlib import Path
import datetime, hashlib, json, urllib.request, urllib.error
ROOT=Path.cwd(); OUT=ROOT/'evidence/peer-provenance-integration'; R=ROOT/'research/2026-10-memory'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
d=json.loads((R/'peer-evidence-reconciliation.json').read_text()); records=[]
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):raise urllib.error.HTTPError(req.full_url,code,'Redirect not followed; no alternative route authorized',headers,fp)
opener=urllib.request.build_opener(NoRedirect)
assert not (OUT/'go-retrieval.json').exists()
for path in ['test/for.go','test/simassign.go']:
 s=next(s for s in d['sources'] if s['repository']=='golang/go' and s['commit']=='56ebf80e57db9f61981fc0636fc6419dc6f68eda' and s['path']==path)
 url='https://raw.githubusercontent.com/'+s['repository']+'/'+s['commit']+'/'+path
 rec={'source_id':s['id'],'repository':s['repository'],'commit':s['commit'],'path':path,'requested_url':url,'expected_sha256':s['sha256'],'attempt_started_utc':now(),'historical_status':s['source_byte_status'],'historical_cutoff_utc':d['cutoff']['status_cutoff_utc'],'historical_reconciliation_unchanged':True,'route':'ordinary official pinned raw URL; single attempt; no redirects or alternate bypass'}
 try:
  with opener.open(urllib.request.Request(url,headers={'User-Agent':'Minyar documentary provenance integration'}),timeout=30) as resp:
   b=resp.read(1048577);rec.update({'http_status':resp.status,'final_url':resp.url,'content_type':resp.headers.get('Content-Type'),'response_date':resp.headers.get('Date'),'etag':resp.headers.get('ETag')})
  assert len(b)<=1048576,'selected small-text bound exceeded'
  rec.update({'actual_sha256':sha(b),'bytes':len(b),'physical_lines':len(b.splitlines()),'retrieved_utc':now(),'hash_matches_existing_pin':sha(b)==s['sha256']})
  assert rec['hash_matches_existing_pin'],'existing SHA-256 pin mismatch; no credit'
  b.decode('utf-8');dest=OUT/'upstream/go'/s['commit']/path;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();dest.write_bytes(b)
  rec.update({'archive_path':str(dest.relative_to(ROOT)),'archive_sha256':sha(dest.read_bytes()),'status':'newly_archived_exact_preexisting_pin','source_review_credit_added':0,'execution_credit_added':0})
 except Exception as e:rec.update({'status':'retrieval_or_hash_gap_remains','error':str(e),'finished_utc':now(),'source_review_credit_added':0,'execution_credit_added':0})
 records.append(rec)
li=next(x for x in d['license_provenance']['peer_pins'] if x['language']=='go');b=(ROOT/li['retained_license']['snapshot']).read_bytes();assert sha(b)==li['retained_license']['sha256'];p=OUT/'upstream/go'/li['commit']/'LICENSE';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
license={'repository':li['repository'],'commit':li['commit'],'identification':li['identification'],'upstream_license_path':li['upstream_license_path'],'upstream_url':li['url'],'archive_path':str(p.relative_to(ROOT)),'sha256':sha(b),'copied_utc':now(),'copied_from_frozen_snapshot':li['retained_license'],'network_fetch':False,'full_notice_retained':True,'policy':'Unchanged upstream research bytes only, including copyright headers; no copied production or test implementation.'}
result={'schema':'minyar.peer_provenance_integration.raw.v1','sources':records,'license':license,'attempts':len(records),'verified_archives':sum(r['status']=='newly_archived_exact_preexisting_pin' for r in records),'alternate_routes_attempted':0}
(OUT/'go-retrieval.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
