"""Retain documentary inputs only; never import tests or run compilers."""
import hashlib,json,pathlib,shutil
R=pathlib.Path('.'); E=R/'evidence/peer-readonly/evaluation-round6'
def retain(source,target,kind,extra=None):
 b=(R/source).read_bytes();p=E/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 return dict(path=source,snapshot=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),physical_lines=len(b.splitlines()),kind=kind,**(extra or {}))
prior=json.loads((R/'evidence/peer-readonly/values-round5/source-manifest.json').read_text());m=[]
for src in ['go/test/convert.go','zig/test/behavior/eval.zig','go/LICENSE','zig/LICENSE','zig/lib/std/testing.zig']:
 source='evidence/peer-readonly/values-round5/upstream/'+src
 entry=next(x for x in prior if x['snapshot']==source)
 assert hashlib.sha256((R/source).read_bytes()).hexdigest()==entry['sha256']
 m.append(retain(source,'upstream/'+src,'selected_test' if src.endswith(('convert.go','eval.zig')) else 'license' if 'LICENSE' in src else 'support',{'upstream_path':entry['path'],'commit':entry['commit'],'url':entry['url'],'raw_url':entry['raw_url'],'retrieval_record':'evidence/peer-readonly/values-round5/source-manifest.json','retrieved_utc':entry['retrieved_utc']}))
prior3=json.loads((R/'evidence/peer-readonly/go-zig-round3/sources.json').read_text())
for name in ['debug','mem','meta']:
 source=f'evidence/peer-readonly/go-zig-round3/{name}.zig.txt'
 # Provenance layout read below; byte hash kept regardless of layout.
 m.append(retain(source,f'upstream/zig/lib/std/{name}.zig','support',{'upstream_path':f'lib/std/{name}.zig','commit':'3db960767d12b6214bcf43f1966a037c7a586a12','url':f'https://github.com/ziglang/zig/blob/3db960767d12b6214bcf43f1966a037c7a586a12/lib/std/{name}.zig','retrieval_record':'evidence/peer-readonly/go-zig-round3/sources.json'}))
(E/'source-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
local=['README.md','docs/architecture.md','docs/language.md','docs/runtime-memory.md','docs/syntax-review.md','docs/testing.md','docs/bounded-runtime-contract.md','tests/regressions.py','tests/recursive-data.py','tests/list-access.py','tests/compiler-hardening.py','tests/peer-research-semantics.py','tests/adversarial.py','tests/memory-research-peer-projections.py']
for n in ['floats-and-bits','records','loops-and-assignment','numbers-and-comparisons','bytes','text-and-lists']:
 local += [f'tests/conformance/{n}/program.min',f'tests/conformance/{n}/expected.stdout']
refs=['research/2026-10-memory/README.md','research/2026-10-memory/peers.json','research/2026-10-memory/peers-review-ledger.json','research/2026-10-memory/runtime-peer-projections.md','research/2026-10-memory/evidence/runtime-peer-projections/run-crettoqb/results.json','research/2026-10-memory/evidence/runtime-peer-projections/run-crettoqb/provenance.json','evidence/peer-readonly/values-round5/source-manifest.json','evidence/peer-readonly/go-zig-round3/sources.json']
for n in ['go-zig-round2','go-zig-round3','strings-round4','values-round5']:
 refs += [f'research/2026-10-memory/peer-readonly-{n}.md',f'research/2026-10-memory/peer-readonly-{n}.json',f'evidence/peer-readonly/{n}/handoff.json']
# round2 has no standalone handoff: ledger_handoff is retained in its ledger.
refs=[p for p in refs if (R/p).is_file()]
(E/'local-manifest.json').write_text(json.dumps([retain(p,'local/'+p,'local_source_fixture_or_contract') for p in local],indent=2)+'\n')
(E/'reference-manifest.json').write_text(json.dumps([retain(p,'references/'+p,'prior_documentary_reference') for p in refs],indent=2)+'\n')
print('Retained',len(m),'upstream records,',len(local),'local fixtures/contracts,',len(refs),'prior references.')
print('round3 source manifest shape',str(prior3)[:1500])
