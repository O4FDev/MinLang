"""Check document/source attribution and hashes only; no peer or local test runs."""
from pathlib import Path
import json
import re
import hashlib
from collections import Counter
from datetime import datetime, timezone

E=Path('evidence/peer-readonly/strings-round4')
R=Path('research/2026-10-memory/peer-readonly-strings-round4')
d=json.loads(R.with_suffix('.json').read_text())
p=json.loads((E/'provenance.json').read_text())
groups=d['comparison_groups']
sources={s['path']:s for s in p['selected_sources_and_licenses'] if s['path'].startswith('test/')}
problems=[]
def check(ok,message):
    if not ok: problems.append(message)

check(len({g['id'] for g in groups})==len(groups),'duplicate group id')
check(d['counts']['authored_comparison_groups']==len(groups),'group count mismatch')
check(d['counts']['dispositions']==dict(Counter(g['disposition'] for g in groups)),'disposition counts')
check(d['counts']['selected_raw_physical_lines']==sum(s['lines'] for s in sources.values()),'line total')
check(len(d['proposed_original_regressions'])==d['counts']['proposed_regressions'],'proposal count')
for s in p['selected_sources_and_licenses']+p['local_coverage_snapshot']:
    b=Path(s['evidence_path']).read_bytes()
    check(hashlib.sha256(b).hexdigest()==s['sha256'],'hash '+s['evidence_path'])
    check(len(b)==s['bytes'] and len(b.splitlines())==s['lines'],'bytes/lines '+s['evidence_path'])
for g in groups:
    s=sources[g['path']]; lines=Path(s['evidence_path']).read_text().splitlines()
    a,b=g['lines'];check(1<=a<=b<=len(lines),'group span '+g['id'])
    check(g['sha256']==s['sha256'],'group hash '+g['id'])
    check(bool(g['upstream_expected']) and bool(g['minyar_mapping']) and bool(g['incompatible_or_excluded_contract']),'empty semantics '+g['id'])
    for site in g['source_assertion_sites']+g['backend_skip_guards']:
        i=site['line'];check(1<=i<=len(lines),'site span '+g['id'])
        if 'lines' in site: a0,b0=site['lines']; actual='\n'.join(lines[a0-1:b0]).strip()
        else: actual=lines[i-1].strip()
        check(actual==site['source'],'site source '+g['id']+' '+str(i))
    for key in g['current_local_coverage']:check(key in d['local_coverage_references'],'coverage key '+key)
    if g['proposal']: check(g['proposal'] in {v['id'] for v in d['proposed_original_regressions']},'proposal id '+g['id'])

literal=sources['test/string_lit.go']
ll=Path(literal['evidence_path']).read_text().splitlines()
expected_literal={i for i,l in enumerate(ll,1) if re.match(r'\s*assert\(',l)}
actual_literal=[site['line'] for g in groups if g['path']=='test/string_lit.go' for site in g['source_assertion_sites']]
check(set(actual_literal)==expected_literal and len(actual_literal)==len(expected_literal),'literal assertion attribution')

z=Path(sources['test/behavior/slice.zig']['evidence_path']).read_text().splitlines()
named=[(i,re.match(r'test "(.*)" \{',l).group(1)) for i,l in enumerate(z,1) if re.match(r'test "(.*)" \{',l)]
actual_named=[(g['lines'][0],g['name']) for g in groups if g['language']=='zig' and g['id']!='Z0']
check(named==actual_named,'all Zig names/spans attribution')
expected_z={i for i,l in enumerate(z,1) if re.search(r'\b(?:expect(?:EqualSlices|EqualStrings|Equal)?|assert)\(',l)}|{28}
actual_z=[s['line'] for g in groups if g['language']=='zig' for s in g['source_assertion_sites']]
check(set(actual_z)==expected_z and len(actual_z)==len(expected_z),'Zig assertion attribution including module compileError/standalone helper')
guards={i for i,l in enumerate(z,1) if 'return error.SkipZigTest' in l}
actual_guards=[s['line'] for g in groups if g['language']=='zig' for s in g['backend_skip_guards']]
check(set(actual_guards)==guards and len(actual_guards)==len(guards),'Zig guard attribution')

rg=Path(sources['test/range.go']['evidence_path']).read_text().splitlines()
range_expected={i for i,l in enumerate(rg,1) if re.match(r'\s*if ',l)}
range_actual=[s['line'] for g in groups if g['path']=='test/range.go' for s in g['source_assertion_sites'] if s['kind']=='failure_predicate']
check(set(range_actual)==range_expected and len(range_actual)==len(range_expected),'Go range all failure predicates')

monster=next(g for g in groups if g['id']=='Z28')
monster_helpers=[h for h in monster['helper_spans'] if isinstance(h,dict)]
check(len(monster_helpers)==21,'Z28 dispatcher plus20 helper subcases')
locals={s['path']:s for s in p['local_coverage_snapshot']}
for c in d['local_coverage_references'].values():
    check(c['path'] in locals,'local snapshot missing '+c['path'])
    for a,b in c['lines']:check(1<=a<=b<=locals[c['path']]['lines'],'local span '+c['path'])
md=R.with_suffix('.md').read_text()
for g in groups:check(md.count('**'+g['id']+' — ')==1,'markdown group attribution '+g['id'])
for prop in d['proposed_original_regressions']:check(md.count('**'+prop['id']+' — ')==1,'markdown proposal attribution '+prop['id'])

result=dict(schema='minyar.peer_readonly_strings.document_checks.v1',checked_utc=datetime.now(timezone.utc).isoformat(),
    meaning='record_source_attribution_and_hash_consistency_only; no_compilation_or_test_execution',
    status='consistent' if not problems else 'needs_correction',problems=problems,
    counts=d['counts'],go_literal_assertion_lines=sorted(expected_literal),go_range_failure_predicate_lines=sorted(range_expected),
    zig_named_tests=len(named),zig_assertion_sites_including_compile_error=len(expected_z),zig_backend_skip_guard_sites=len(guards),
    zig_large_group_helper_subcases=len(monster_helpers)-1,
    source_hashes_verified=len(p['selected_sources_and_licenses']),local_snapshot_hashes_verified=len(p['local_coverage_snapshot']))
(E/'document-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['counts','go_literal_assertion_lines','go_range_failure_predicate_lines']},indent=2))
if problems: raise SystemExit(1)
