require 'json'
require 'digest'
require 'time'
base = 'research/2026-10-memory/evidence/local-cleanup-certifier-implementation-review'
read = ->(f) { JSON.parse(File.read(base + '/' + f)) }
probe = read.call('probe-output.json')
findings = [
  {id: 'F1', severity: 'high', baseline_gate: 'blocking', title: 'Parallel conditional successors falsely prove getter true-edge dominance', checkpoint_lines: [[390,397],[705,714]], fixture: 'same-target-getter', obligation: 'O3 guarded slot read'},
  {id: 'F2', severity: 'medium', baseline_gate: 'blocking', title: 'Unnamed numeric identifiers treated as independent string identities', checkpoint_lines: [[74,74],[403,406],[425,428]], fixture: 'numeric-ssa-alias', obligation: 'O1 LLVM subset membership and duplicate identity'},
  {id: 'F3', severity: 'medium', baseline_gate: 'blocking', title: 'Float token accepted as unquoted block label', checkpoint_lines: [[408,414]], fixture: 'float-block-label', obligation: 'O1 label grammar'}
]
findings.each do |f|
  r = probe['results'].find { |x| x['name'] == f[:fixture] }
  f[:baseline] = {input_path:r['path'], input_sha256:r['sha256'], expected:r['expected_status'], observed:r['actual']['status'], work:r['actual']['work'], full_output: base + '/probe-output.json', cost_undercharge_claim:false}
end
counts = File.readlines(base + '/independent-counts.jsonl').map { |l| JSON.parse(l) }
initial = Dir[base + '/inputs/*'].select { |f| File.file?(f) }.map { |f| {path:f,sha256:Digest::SHA256.file(f).hexdigest} }
live = %w[tests/cleanup-certificate-research.py tests/cleanup-certificate-research-tests.py tests/cleanup-certificate-research-run.py tests/cleanup-certificate-research-faults.py research/2026-10-memory/local-cleanup-certifier-prototype.md research/2026-10-memory/local-cleanup-certifier-prototype.json].map do |f|
  pinned = base + '/inputs/' + File.basename(f)
  before = Digest::SHA256.file(pinned).hexdigest
  after = Digest::SHA256.file(f).hexdigest
  {path:f,checkpoint_sha256:before,observed_sha256:after,changed:before != after}
end
File.write(base + '/observed-drift.json', JSON.pretty_generate({observed_utc:Time.now.utc.iso8601,paths:live}) + "\n")
record = {
 schema_version:1, status:'baseline rejected; repaired checkpoint static rereview completed, independent replay pending root release',
 reviewed_at_utc:Time.now.utc.iso8601, campaign_complete:false, campaign_earliest_finish_utc:'2026-10-04T06:54:29Z',
 role:'independent implementation reviewer; standalone Python research only',
 baseline:{disposition:'reject',checker_sha256:probe['checker_sha256'],tests_sha256:'bf51aa9ae8ffdaf8f72f1ca4e7a449dcf653a79d7cc731330cbbb629cac195fc',findings:findings},
 repaired:{checker_sha256:'d2607ac5c8d638b1d25dcd157be7aa459e021d94f7f51dded5fbf736194f96d5',tests_sha256:'74ca4a338be1c39677ec9fa658d5cff90323d0e6a23c65bc3e30a534d3a63929',static_rereview:'only three conservative grammar exclusions; no algorithm cost, runtime premise, thresholds or expectation changes',independent_replay:'pending root serial worker completion',production_approval:false},
 actual_body_inspection:read.call('independent-actual-extents.json'),
 baseline_probe_resource:read.call('probe-resource.json'),
 independent_counts:counts,
 historical_fault_counts:read.call('independent-fault-counts.json'),
 evidence_categories:{reviewer_executed:'five retained small analyses in one serial bounded Python worker after explicit release',owner_executed:'frozen red-first, parser/dataflow/returning-arm/whitespace reds,126 green,127 later red, seven fault worker records inspected',inherited:'design approval, C runtime ABI and cost premises, compiler/caller provenance, demand audit and Text/native observations',not_executed:'full unchanged suite by reviewer; any LLVM/native code; compilation; benchmark; installation; production change; remote retrieval'},
 loop_parallel_edge_control:probe['results'].find{|r|r['name']=='same-target-loop'}.slice('sha256','expected_status','expectation_met','actual'),
 actual_control:probe['results'].find{|r|r['name']=='actual-control'}['actual'].slice('work','loops','external_requirements','runtime_source_sha256','assumptions','obligations'),
 source_drift:live, input_hashes:initial,
 trusted_premises:['frozen P0-P11 runtime summaries and exact 64-bit system incremental K32 profile','valid successful allocation/arithmetic/shift/division/bounds/guard execution','single mutator, non-reentrancy, truthful representable heap/queue/cache state','fresh generation separation and protected borrows','continuously live external Bytes outside owner throughout invocation including hidden service','eventual fair positive full service'],
 unresolved:['full C-to-object/runtime refinement','exact linkage/interposition and optimizer preservation','LLVM library/intrinsic scalar semantics/refinement','compiler/source-to-binary build-chain correctness','automatic external caller protection discharge and whole-process closure','universal analyzer time/space proof; interrupted aggregate coordinator total <=30s unproven'],
 nonclaims:['verified compiler or production certifier','contextual/whole-process closure','completion at return','exact remaining-at-return or process poll count','allocation/byte/RSS/time/HFT guarantee','general novelty','campaign completion'],
 owned_files:['research/2026-10-memory/local-cleanup-certifier-implementation-review.md','research/2026-10-memory/local-cleanup-certifier-implementation-review.json',base+'/'],
 no_commits_resets_installations_production_changes_subagents:true
}
if File.exist?(base + '/repaired-probe-output.json')
 repaired = read.call('repaired-probe-output.json')
 raise 'repaired probe expectation failure' unless repaired['results'].all?{|r|r['expectation_met']}
 raise 'repaired resource failure' unless read.call('repaired-probe-resource.json')['violation'].nil?
 record[:repaired][:owner_evidence] = read.call('repaired-owner-counts.json')
 record[:historical_source_identity_checks] = read.call('historical-source-identity-checks.json')
 record[:independent_design_coverage] = read.call('independent-design-coverage.json')
 record[:repaired][:independent_replay] = repaired['results'].map {|r| r.slice('name','sha256','expected_status','expectation_met','actual')}
 record[:repaired][:resource] = read.call('repaired-probe-resource.json')
 record[:repaired][:disposition] = 'narrow research-only approval of exact repaired checkpoint under stated premises; not verified compiler or production certifier'
 record[:status] = 'independent review complete; baseline rejected; repaired d260 checkpoint narrowly approved'
end
File.write('research/2026-10-memory/local-cleanup-certifier-implementation-review.json',JSON.pretty_generate(record)+"\n")
