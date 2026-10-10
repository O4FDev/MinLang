"""Serialize this manually authored documentary review; never imports or runs tests."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / 'evidence/peer-readonly/swift-round7'
R = ROOT / 'research/2026-10-memory'
PIN = '1ff1cc1170617ab23ab74aa8b741c8daca1903f6'

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')

def manifest(path, target):
    raw = (ROOT / path).read_bytes()
    dst = E / target / path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw)
    return dict(path=path, snapshot=str(dst.relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), physical_lines=len(raw.splitlines()))

coverage = {}
def cover(key, path, spans, proves, limit):
    rec = manifest(path, 'local')
    coverage[key] = dict(**rec, lines=spans, proves=proves, limit=limit,
                         verification='source_read_only; not_run; no_new_pass_claim')

cover('record-fields', 'tests/conformance/records/program.min', [[1,10]],
      'Explicit reordered record fields and nested named projections: Ada,36,language.',
      'Three-field Person and two-field Name; no Swift tuple, initializer, by-value copy or eight-field return oracle.')
cover('scalar-init', 'tests/scalar-record-initialization.py', [[8,36],[45,55]],
      'Returned scalar(37,true,z), mixed(41,mixed), nested(8,13), and effect order(x12,y11,state12); exact output and setter selection assertions.',
      'At most three fields on these returned shapes; no eight-Integer returned record with every position independently checked.')
cover('scalar-storage', 'tests/scalar-record-storage.py', [[59,75],[96,162],[164,182],[184,191]],
      'Reordered pair effects1110/11; managed alias/return/container escapes; swap21/12; mixed/direct projected constructors; budget64 one-field shapes plus2 fallbacks.',
      'Budget counts many small records, not fields in one wide returned record; first escape cases observe x only; no Swift initialization delegation or ARC endpoint.')
cover('scalar-mutation', 'tests/scalar-record-mutation.py', [[17,44],[86,105]],
      'Independent pair-field capture1110/11 and escaped managed pair9/4; explicit wrong-output/failure mutant oracles when invoked.',
      'Two-field shapes only in these cases; no execution or mutant detection claimed here.')
cover('scalar-production', 'tests/production-scalar-storage.py', [[50,74],[76,113]],
      'Boolean field effects/snapshots406/404; reordered Pair fields7/3/37; scalar record argument/return generations5/11/21/17.',
      'Four scalar fields in Flags, two in Pair, one in Cell; no eight-field end-to-end return retention.')
cover('parameters', 'tests/readonly-parameters.py', [[16,25],[40,54],[101,123],[139,146]],
      'Scalar same-input addition7+7=14; shared List mutation2/6/6; projected Pair parameters; recursive returned Text; earlier Text argument retained during later mutation.',
      'No exact double2/4 cases, generic/existential metadata, function values, varargs or Swift inout; later-argument control uses Text.')
cover('parameter-production', 'tests/production-readonly-parameters.py', [[9,41]],
      'Distinct same-type operands259/714/rightleft/2; retained List parameter after last external owner replacement42/99.',
      'No wide record with field permutation; shared List lifetime is not Swift value copying.')
cover('loops', 'tests/conformance/loops-and-assignment/program.min', [[17,24],[26,43],[53,64]],
      'Ordered words alpha/beta/gamma; Unicode iteration; shared Player mutationhealth15/99; nested List mutation7.',
      'Different exact iteration values; no slicing in the selected Swift file; shared mutation is not Swift array value semantics.')
cover('literal', 'tests/recursive-data.py', [[148,184]],
      'Ordered List initializer values1/2/3 and exact literal values7/seven/false/b/empty/é🙂; earlier Box retained across later replacementold!/new!/new!.',
      'No tuple label rearrangement, eight-field return or imported metadata; initializer capture already exists, so no duplicate generic literal-effects proposal.')
cover('adversarial', 'tests/adversarial.py', [[16,43],[83,103],[145,211]],
      'Borrowed parameters escape; receivers survive index/slice mutation; Boolean effect trace3/4/5/6/8; early returned Text pairs; retained shared diamond leaf!.',
      'Existing ownership and short-circuit controls are related; none specifies Swift ARC class deinit at each test boundary or every field of an eight-Integer return.')
cover('runtime-originals', 'tests/memory-research-peer-projections.py', [[62,276]],
      'Eight existing originals: Bytes copy/shared alias, row scalar snapshot, literal effects, once-only producers, NaN matrix, source underflow bits, middle Boolean literal barrier and2^53 binary64 arithmetic/bits.',
      'Initial run-7m86apqr36 and concurrently completed run-l5_218bk48 are separate runtime-lane evidence. Frozen local source already includes eight methods; no round7 run. No8-field return or Swift operator/tuple/metadata/ARC equivalence.')
cover('language-oracle', 'tests/regressions.py', [[54,65]],
      'Harness checks successful compile/link, requested O0/O2 process status and exact UTF-8 stdout when invoked.',
      'Not invoked in this lane; environmental link flags and actual argv matter, as historical optimization correction shows.')
cover('function-conformance', 'tests/conformance/programs-and-entry-points/program.min', [[1,14]],
      'Typed double via multiplication on0,1,2, checked only as total6 and top level output.',
      'Aggregate total is weaker than independent double(2)=4 and double(4)=8 assertions; x*2 differs from selected x+x lowering.')
cover('ownership-conformance', 'tests/conformance/memory-lifetime/program.min', [[1,12]],
      'Saved shared Node survives root replacement; values1,2,1.',
      'Related existing managed retention, no implicit value copy or wide returned record field-map proof.')

supplementary_local = []
for path in ['tests/conformance/records/expected.stdout','tests/conformance/loops-and-assignment/expected.stdout',
             'tests/conformance/programs-and-entry-points/expected.stdout','tests/conformance/memory-lifetime/expected.stdout',
             'docs/syntax-review.md','tests/fuzz.py']:
    supplementary_local.append(manifest(path, 'local'))
implementation = []
for path, spans, meaning in [
    ('compiler/compiler.min', [[1559,1626],[2593,2708],[3112,3141],[3275,3317],[4030,4071]],
     'Scalar proof excludes whole aliases/arguments/returns; field names resolve to declared positions while expressions parse in source order; call operands parse in order; borrowed returns retained before leaving frame.'),
    ('runtime/minyar_collections.h', [[229,320]],
     'Private scalar/mixed record allocation, bounds-checked field slots, scalar writes and reference retain-before-replacement. Pointer-based managed records; no Swift by-value aggregate ABI.')]:
    implementation.append(dict(**manifest(path, 'local'), reviewed_spans=spans, meaning=meaning,
                               verification='implementation_read_only; does_not_prove_correct_execution'))

selected = json.loads((E/'selection-checkpoint.json').read_text())['selected']
byname = {Path(f['path']).name:f for f in selected}
units = []
def unit(id, file, span, name, expected, disposition, mapping, excluded, local, sites, helpers=(), proposal=()):
    f=byname[file]; lines=(ROOT/f['snapshot']).read_text().splitlines()
    us = dict(id=id, language='swift', commit=PIN, path=f['path'], sha256=f['sha256'], lines=list(span),
              name=name, url=f['url']+f'#L{span[0]}-L{span[1]}', upstream_expected=expected,
              disposition=disposition, minyar_mapping=mapping, excluded_contracts=excluded,
              source_assertion_sites=[dict(line=n, source=lines[n-1], kind='expectEqual' if 'expectEqual' in lines[n-1] else 'FileCheck_CHECK') for n in sites],
              in_file_helper_spans=[list(s) for s in helpers], local_coverage_ids=local,
              local_source_test_coverage=[coverage[k] for k in local], proposal_ids=list(proposal),
              backend_skip_guards=[], driver_lines=[1,2],
              verification='whole_selected_file_and_in_file_helpers_read; documentary_only',
              port_status='not_implemented; not_executed')
    if file=='structs.swift':
        us['shared_harness_oracle']='H1: expectEqual(0,LifetimeTracked.instances) once after its owning registered test; attached, not a new unit/site per subcase.'
        us['harness_registered_test']= 'Interval' if id in ['S1','S2','S3'] else 'Big' if id=='S4' else 'Generic' if id=='S5' else 'InitStruct' if int(id[1:])<11 else 'InitStructAddrOnly'
    units.append(us)

interval_helpers=[(9,28),(30,32)]
for id,span,name,expected,sites in [
    ('S1',(35,39),'Interval unary negative','lo=-2,hi=-1 from -Interval(1,2)',[37,38]),
    ('S2',(40,44),'Interval addition','lo=4,hi=6 from (1,2)+(3,4)',[42,43]),
    ('S3',(45,49),'Interval subtraction','lo=1,hi=3 from (3,4)-(1,2); lo=a.lo-b.hi,hi=a.hi-b.lo',[47,48])]:
    unit(id,'structs.swift',span,name,expected,'adapt_pending',
         'Named Interval record with explicit fields and ordinary negate/add/subtract helpers can preserve each scalar result; no input mutation/copy assertion occurs.',
         ['operator overloading','Swift struct by-value argument/return ABI','TestSuite closure syntax','H1 Swift ARC endpoint check'],
         ['record-fields','scalar-init','scalar-storage'],sites,interval_helpers)
unit('S4','structs.swift',(60,71),'Big returned eight-field record',
     'a,b,c,d,e,f,g,h =1,6,1,8,0,3,4,0; every named field independently asserted.',
     'adapt_pending','Explicit eight-Integer record factory preserves all field values; managed Minyar return differs from Swift large aggregate value return.',
     ['Swift by-value aggregate ABI','H1 Swift ARC endpoint check'],['scalar-init','scalar-storage','scalar-production'],list(range(63,71)),[(52,58)],['P1'])
unit('S5','structs.swift',(82,86),'Generic phantom String instantiation','a=19,b=84; no String payload field.',
     'incompatible_as_written','Ordinary explicit Integer fields could hold19/84 but would remove GenStruct<String> metadata/specialization.',
     ['user generic struct','phantom type instantiation','H1 Swift ARC endpoint check'],['record-fields'],[84,85],[(73,80)])
for i,(start,call,vals,sites,helper,label) in enumerate([
    (128,129,(10,20),[130,131],(93,96),'default initializer'),
    (133,134,(69,420),[135,136],(98,101),'labeled initializer'),
    (138,139,(6,8),[140,141],(111,114),'init then self assignment'),
    (143,144,(6,8),[145,146],(116,119),'self assignment then init'),
    (148,149,(6,8),[150,151],(121,124),'init then init'),
    (196,197,(10,20),[198,199],(161,164),'address-only default initializer'),
    (201,202,(69,420),[203,204],(166,169),'address-only labeled initializer'),
    (206,207,(6,8),[208,209],(179,182),'address-only init then self assignment'),
    (211,212,(6,8),[213,214],(184,187),'address-only self assignment then init'),
    (216,217,(6,8),[218,219],(189,192),'address-only init then init')],6):
    addr=i>=11
    unit(f'S{i}','structs.swift',(start,sites[-1]+1),'InitStruct '+label,
         f'x={vals[0]},y={vals[1]}; H1 also requires no live LifetimeTracked after owning test.',
         'incompatible_as_written',
         'Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.',
         ['member default LifetimeTracked(0)','Swift class ARC/deinit endpoint','constructor overloading/delegation','self initialization']+(['Any existential address-only storage'] if addr else []),
         ['scalar-init','scalar-storage','adversarial'],sites,[(155,193) if addr else (88,125),helper])

for id,span,name,expected,site in [
    ('T1',(27,28),'positional tuple addition','(lo=4, hi=6)',27),
    ('T2',(29,30),'reordered labeled tuple addition','(lo=4, hi=6); first spelling hi:2,lo:1 still assigns lo1/hi2',29),
    ('T3',(31,32),'tuple interval subtraction','(lo=1, hi=3)',31),
    ('T4',(34,40),'inout tuple compound update','(lo=4, hi=6) after x(1,2) <+>= (3,4)',37)]:
    unit(id,'tuples.swift',span,name,expected,'adapt_pending',
         'Original named-record helper can preserve lo/hi values; labeled construction keeps field identity despite source order. Shared record helper mutation changes the one record; not Swift inout exclusivity/copy semantics.',
         ['tuple typealias','positional/labeled tuple coercion','custom operators']+(['inout exclusivity/value writeback'] if id=='T4' else []),
         ['record-fields','scalar-storage','loops'],[site],[(4,25)]+([(34,39)] if id=='T4' else []))
for id,span,name,expected,site in [
    ('T5',(50,51),'empty varargs','CHECK0 ints; print helper actually emits "0 ints: " then newline',50),
    ('T6',(52,53),'one vararg','CHECK1 ints: 1; helper emits trailing space before newline',52),
    ('T7',(54,55),'three varargs','CHECK3 ints: 1 2 3; helper emits trailing space before newline',54)]:
    unit(id,'tuples.swift',span,name,expected,'incompatible_as_written',
         'A List<Integer> helper could print length/elements but would not exercise variadic argument packing or empty varargs.',
         ['varargs Int...','print terminator named argument','string interpolation'],['loops','literal'],[site],[(42,48)])

for i,expected,name in [(1,'true','generic Bool projection true'),(2,'false','generic Bool projection false'),
                        (3,'true','existential/autoclosure RHS true'),(4,'false','existential/autoclosure RHS false')]:
    line=23+i
    unit(f'B{i}','bool_as_generic.swift',(line,line),name,expected,'incompatible_as_written',
         '!! here returns x.boolValue; it is not double negation. &&& accepts protocol existential and autoclosure. Both call-site LHS values are true; no false-LHS skipped effect/trap is asserted.',
         ['generic protocol constraint','Bool protocol extension','existential metadata','custom operator']+(['autoclosure','conditional expression'] if i>2 else []),
         ['parameters','adversarial','runtime-originals'],[line],[(6,22)])

for i,line,val in [(1,16,4),(2,18,8)]:
    unit(f'F{i}','functions.swift',(line,line+1),f'double scalar call {i}',str(val),'adopt_pending',
         'Ordinary typed Integer helper return x+x preserves the exact result; no generics/closure/lifetime contract involved in this unit.',
         [],['parameters','function-conformance'],[line],[(4,6)])
for id,span,name,expected,site,helper,excluded in [
    ('F3',(21,22),'curried captured subtraction','12',21,(8,10),['returned closure','captured scalar','function-valued return']),
    ('F4',(24,25),'twice named function value','20',24,(12,14),['function-valued parameter','indirect calls']),
    ('F5',(26,27),'twice implicit closure','7',26,(12,14),['closure parameter','implicit $0']),
    ('F6',(28,29),'twice named closure','3',28,(12,14),['closure parameter','closure-local parameter']),
    ('F7',(41,42),'subclass overload foo','Right',41,(31,36),['class inheritance','Any','overloads/default arguments']),
    ('F8',(43,44),'subclass overload bar','Right',43,(38,39),['class inheritance','Any varargs','overloads/default arguments']),
    ('F9',(53,54),'tuple existential return','("1", "2", "3", 42, 7)',53,(46,51),['tuple aggregate return','Number protocol existential','protocol extension','aggregate reflection printing'])]:
    unit(id,'functions.swift',span,name,expected,'incompatible_as_written',
         'Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.',
         excluded,['parameters','adversarial','literal'],[site],[helper])

unit('X1','slices.swift',(23,32),'bound array iteration','ordered6,0,2,2,1,4','adopt_pending',
     'Ordinary Integer List and for preserve all six visits/values; print(x) replaces Int.show only at the observation boundary.',
     ['Showable protocol method dispatch','Swift array storage/value-copy semantics not asserted'],['loops','literal','runtime-originals'],list(range(27,33)),[(4,12)])
unit('X2','slices.swift',(34,41),'temporary array iteration','ordered9,8,1,0,5','adopt_pending',
     'Ordinary for over Integer List literal preserves all five visits/values. No array slice, copy, offset or alias assertion exists.',
     ['Showable protocol method dispatch','Swift array storage/value-copy semantics not asserted'],['loops','literal','runtime-originals'],list(range(37,42)),[(4,12)])
unit('X3','slices.swift',(43,53),'varargs array iteration','ordered1,6,1,8','incompatible_as_written',
     'An explicit List helper reproduces values but erases Int... packing; not counted as variadic coverage.',
     ['Int... variadic packing','Showable protocol method dispatch'],['loops','literal'],list(range(50,54)),[(4,12),(43,47)])

proposal_source = '''record Wide { a: Integer; b: Integer; c: Integer; d: Integer; e: Integer; f: Integer; g: Integer; h: Integer }
function peerValues(): Wide {
    return Wide { a: 1; b: 6; c: 1; d: 8; e: 0; f: 3; g: 4; h: 0 }
}
function show(value: Wide) {
    print(value.a); print(value.b); print(value.c); print(value.d)
    print(value.e); print(value.f); print(value.g); print(value.h)
}
function mark(trace: List<Integer>, digit: Integer): Integer {
    trace[0] = trace[0] * 10 + digit
    return digit * 11
}
function make(trace: List<Integer>): Wide {
    return Wide {
        h: mark(trace, 8); g: mark(trace, 7); f: mark(trace, 6); e: mark(trace, 5)
        d: mark(trace, 4); c: mark(trace, 3); b: mark(trace, 2); a: mark(trace, 1)
    }
}
function echo(value: Wide): Wide { return value }
show(peerValues())
let trace = [0]
let holder = [make(trace)]
let kept = echo(holder[0])
let scalar = kept.a
show(kept)
print(trace[0])
holder[0].a = 111
print(kept.a)
print(scalar)
holder[0] = peerValues()
holder = []
for i in 0..8 { let temporary = peerValues(); print(temporary.h) }
show(kept)
'''
proposal_expected = '\n'.join(map(str,[1,6,1,8,0,3,4,0,11,22,33,44,55,66,77,88,87654321,111,11,*([0]*8),111,22,33,44,55,66,77,88]))+'\n'
proposals = [dict(id='P1', name='All fields of a wide returned record, reordered effects and retained alias',
                 source_units=['S4'], local_coverage_ids=['scalar-init','scalar-storage','scalar-production','parameters','literal'],
                 demonstrated_gap='Inspected returned-record fixtures have1–3 fields, four-field Flags is direct/scalar, and the64-proof budget fixture has66 distinct one-field objects. None of these checks all8 named positions across a returned/reordered8-field factory, ordinary echo, source-container replacement and retained alias. This is a bounded width/field-mapping combination, not a claim that all record returns lack tests.',
                 proposed_minyar_source=proposal_source, independent_expected_stdout=proposal_expected,
                 rationale='First assert the full pinned field vector. A second original vector uses distinct11..88 so each slot permutation is observable, with noncommutative source-order trace87654321. Mutation111 versus captured scalar11 distinguishes shared record from scalar value snapshot; subsequent replacement/drop plus allocations tests reachable retained alias content. No address, destructor-time or Swift struct copy assertion.',
                 status='proposal_only; not_implemented; not_compiled; not_executed',
                 tdd_handoff='Core owner may add this exact positive oracle through the existing candidate-aware O0/O2 harness and relevant ownership configuration. Retain a red only if one is actually observed; no defect, required change or fabricated red claimed. No surface syntax or memory policy change requested.')]

support = json.loads((E/'support-retrieval.json').read_text())
support_spans = {
    'stdlib/private/StdlibUnittest/StdlibUnittest.swift': [[1,50],[197,207],[327,358],[806,810],[928,947],[1361,1449],[1543,1612],[1740,1808],[1873,1912],[1953,1994],[2110,2177]],
    'stdlib/private/StdlibUnittest/LifetimeTracked.swift': [[1,78]],
    'stdlib/private/StdlibUnittest/CMakeLists.txt': [[1,95]],
    'test/lit.cfg': [[644,646],[911,980],[1438,1457],[1718,1734],[2682,2759],[2864,2879]],
}
for f in support:
    if 'snapshot' not in f: continue
    f['reviewed_spans']=support_spans[f['path']]
    # Exact complement, including unread helper infrastructure, remains explicit.
    read=set(n for a,b in f['reviewed_spans'] for n in range(a,b+1))
    pending=[]
    for n in range(1,f['physical_lines']+1):
        if n not in read:
            if pending and pending[-1][1]==n-1: pending[-1][1]=n
            else: pending.append([n,n])
    f['review_pending_spans']=pending
    f['status']='selective_support_contract_read; not_selected_test_file'

for f in selected:
    f['reviewed_spans']=[[1,f['physical_lines']]]
    f['review_pending_spans']=[]
    f['status']='complete_selected_file_semantically_reviewed'
    f['license_sha256']='770af8291f708538d8ff885a0bbc4e045cd700531741c4f99528d435c14d7f55'
    f['license_url']=f'https://github.com/swiftlang/swift/blob/{PIN}/LICENSE.txt'

ledger = dict(schema='minyar.peer_readonly_swift_round7.v1', mode='documentary_read_only_source_review',
    model='GPT-6.1 Sol high',
    scope=dict(selected=selected, selected_remaining_review_spans=[],
               selection='Five complete manageable pinned Interpreter files; not an entire directory/prefix sample.',
               excluded_candidate='constructor.swift complete56line screening retained;11 ordered class/generic overload initializer markers a,b,c,d,e,f,g,h,i,j,k. No destructor assertion despite final comment; not selected, zero comparison credit.'),
    counts=dict(complete_selected_files_reviewed=len(selected), selected_raw_physical_lines=sum(f['physical_lines'] for f in selected),
                authored_comparison_groups=len(units), group_dispositions=dict(Counter(u['disposition'] for u in units)),
                selected_expectEqual_source_sites=36, selected_FileCheck_CHECK_source_sites=35,
                registered_TestSuite_blocks=5, imported_lifetime_oracle_source_sites=1,
                imported_lifetime_oracle_attachments=5, proposed_original_regressions=len(proposals),
                ports_implemented=0, peer_or_local_test_executions=0, compilations=0, installations=0,
                production_test_build_edits=0, timing_measurements=0, commits=0, subagents=0),
    grouping_policy='One complete observed scalar scenario/call; one full loop groups its ordered CHECKs. Struct named tests contain15 subcase groups; helpers and the single shared lifecycle source site are attached, never extra ports/groups. All71 selected-file oracle source sites attributed once.',
    outcome_policy='Source expectations inferred, never observed. All files require executable_test and %target-run-simple-swift; four pipe to FileCheck with default CHECK directives. These annotations are ordered textual patterns, not exact whole stdout/status recordings. structs.swift uses StdlibUnittest assertions and runAllTests, not FileCheck. Configuration-dependent optimization flags are retained; no Swift backend/mode run claimed.',
    disposition_policy='adopt_pending preserves bounded ordinary value/iteration contract excluding harness/protocol observation syntax; adapt_pending explicitly replaces tuple/overloaded struct operations with named-record algorithms. incompatible_as_written retains unsupported core class/generic/closure/Any/initializer/ARC/variadic contracts. already_covered requires an exact credited unit; count0 despite related fixtures. No claim that a syntax projection preserves implicit copies or aggregate ABI.',
    local_coverage_policy='Every coverage claim binds to frozen bytes and exact inspected spans. Related tests do not imply exact inputs, supported Swift features or passing status; no exhaustive repository-gap assertion.',
    local_coverage_references=coverage, implementation_reviews=implementation, comparison_groups=units,
    support_helper_reviews=support,
    shared_helper_contracts=[dict(id='H1', path='stdlib/private/StdlibUnittest/StdlibUnittest.swift', lines=[1953,1994],
                                assertion_lines=[1991,1993], expected='LifetimeTracked.instances==0 after each registered synchronous test; reset before body; optional native leak tracking guarded SWIFT_RUNTIME_ENABLE_LEAK_CHECKER',
                                attachments=['Interval','Big','Generic','InitStruct','InitStructAddrOnly'],
                                disposition='incompatible_as_written; Swift immediate ARC endpoint cannot be presumed for Minyar deferred reclamation',
                                lifetime_source='LifetimeTracked.swiftL21–42; init increments, deinit asserts positive serial/decrements/negates',
                                dynamic_counts='Five ordinary registered test boundaries in unfiltered source; no executed assertion count.')],
    selected_file_nonassertion_review=[
        dict(path='test/Interpreter/structs.swift', reviewed_spans=[[1,223]],
             dormant_spans=[[30,32],[103,109],[171,177]],
             meaning='Interval print helper is unused; both init(b:) overloads have branches but are never called; no extra test/output or chosen branch credited. Field l is not directly inspected, but H1 tracks its destruction through the harness. Any field a containing "hi" is not directly asserted.'),
        dict(path='test/Interpreter/slices.swift', reviewed_spans=[[1,54]], dormant_spans=[[14,21]],
             meaning='FIXME show_slice generic helper is wholly commented out, not compiled; no slice operation anywhere. Protocol/Int.show only print values.'),
        dict(path='test/Interpreter/functions.swift', reviewed_spans=[[1,54]],
             meaning='Wrong overload bodies retained; CHECKRight means selected overload, not just a text literal test; closure/function-value units remain incompatible.'),
        dict(path='test/Interpreter/tuples.swift', reviewed_spans=[[1,55]],
             meaning='Label reordering is real; no tuple alias/copy discriminator. Variadic print includes trailing spaces omitted by shorter CHECK patterns.'),
        dict(path='test/Interpreter/bool_as_generic.swift', reviewed_spans=[[1,27]],
             meaning='!! is identity projection through a generic protocol, not logical double negation. &&& lazily calls y via autoclosure in definition; no false LHS call, ordered IDs or RHS suppression oracle in file.')],
    proposed_original_regressions=proposals,
    prior_runtime_evidence=dict(results='research/2026-10-memory/evidence/runtime-peer-projections/run-7m86apqr/results.json',
        status='passed_in_separate_lane; record_read_only_here', summary=dict(test_methods=6,configurations=3,generated_executions=36),
        optimization='Saved link argv have18 last-O0 and18 last-O2; native runtime C objectsO2, sanitized runtime C objectsO1. Generated ASan separate; no generated UBSan/LSan/full-suite claim.',
        historical_correction='runtime-peer-optimization-correction.json retains earlier18/24/36 archives effectivelyO1 sanitizer links; old ledgers immutable.',
        deduplication='Do not repropose Bytes/row/literal/producer/NaN/subnormal six originals or the separately completed round6 Boolean ordered-decisive and2^53 originals. Latest status has its own documentary evidence, preserving earlier snapshots.'),
    availability=dict(restricted_Rust='not_retried_or_bypassed', round5_directory_API='not_retried_or_bypassed',
        stopped_execution_lanes='untouched', new_restrictions=[],
        support_path_error='Guessed StdlibUnittest.swift.gyb raw path404 once, not retried. Correct named .swift file accessible; CMake pinned file confirms .swift and LifetimeTracked.swift. This is path correction for a missing source, not alternate access around a restriction.',
        LLVM_fallback='not_needed; no unpinned sources used'),
    handoff=dict(campaign_earliest_completion_utc='2026-10-04T06:54:29Z',campaign_completion_claim=False,
        source_review_complete=True, selected_unread_lines=0, central_ledgers_untouched=True,
        existing_dirty_work_preserved=True, active_core_native_work_disturbed=False,
        remaining='All12 adopt/adapt groups and P1 remain unimplemented/unexecuted;26 incompatible excluded. Unselected Interpreter files/other peers and exact support complements remain outside round7. Constructor screening carries no group credit.',
        owned_write_boundary=['research/2026-10-memory/peer-readonly-swift-round7.md','research/2026-10-memory/peer-readonly-swift-round7.json','evidence/peer-readonly/swift-round7/']))
ledger['counts']['group_dispositions']['already_covered']=0
ledger['latest_runtime_update']=dict(results='research/2026-10-memory/evidence/runtime-peer-projections/run-l5_218bk/results.json',
    provenance='research/2026-10-memory/evidence/runtime-peer-projections/run-l5_218bk/provenance.json',
    status='passed_record_in_separate_runtime_lane; documentary_read_only_here',
    summary=dict(test_methods=8,configurations=3,generated_executions=48),
    preserved_manifest='evidence/peer-readonly/swift-round7/latest-runtime-manifest.json',
    new_fixture_spans=[[226,253],[255,276]],
    new_methods=['test_middle_boolean_literal_preserves_all_prior_effects','test_binary64_halfway_even_addition_at_unit_spacing_boundary'],
    source_snapshot_note='After initial live fixture read and before frozen local capture, current fixture acquired eight methods; frozen hashc24645e4fb7b2908318c2e14cae5a750e59d830738427bd24fc0a736b17dd962. Final spans/review reflect those actual bytes; initial README/runtime-report/result snapshots remain separately unchanged.',
    limits='External saved48 statuses/argv/provenance checked; no round7 execution, whole-suite, timing, Swift semantics or generated UBSan/LSan claim. Round6 historical proposal ledgers unchanged.')
save(R/'peer-readonly-swift-round7.json', ledger)
save(E/'local-manifest.json', [dict(path=c['path'],snapshot=c['snapshot'],sha256=c['sha256'],bytes=c['bytes'],physical_lines=c['physical_lines']) for c in coverage.values()]+implementation+supplementary_local)
license_rec=manifest('evidence/peer-readonly/values-round5/upstream/swift/LICENSE.txt','references')
save(E/'source-manifest.json',dict(selected=selected,support=support,license=dict(path='LICENSE.txt',snapshot='evidence/peer-readonly/swift-round7/upstream/swift/LICENSE.txt',sha256=license_rec['sha256'],bytes=license_rec['bytes'],physical_lines=license_rec['physical_lines'],url=f'https://github.com/swiftlang/swift/blob/{PIN}/LICENSE.txt',identification='Apache-2.0 with Runtime Library Exception',provenance='Unchanged retained pinned round5 license; SHA matches peers.json; entire license/exception read. Selected files have no individual license header; pinned repository license retained. Support headers preserved.')))
print(json.dumps(ledger['counts'],indent=2))
