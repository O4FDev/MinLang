"""Document authoring only: no imports or execution of repository/peer tests."""
from pathlib import Path
import json,re,hashlib,datetime,collections
BASE=Path('evidence/peer-readonly/values-round5')
REPORT=Path('research/2026-10-memory/peer-readonly-values-round5')
manifest=json.loads((BASE/'source-manifest.json').read_text())
selected=[s for s in manifest if s['kind']=='selected_test']
by_path={s['path']:s for s in manifest}
def lines(path): return Path(by_path[path]['snapshot']).read_text().splitlines()
local_refs={
 'nan-equality':{'path':'tests/conformance/floats-and-bits/program.min','lines':[[22,23]],'expected_path':'tests/conformance/floats-and-bits/expected.stdout','expected_lines':[[15,16]],'proves':'Direct generated Float NaN equality false and inequality true. No relational, negated or helper-returned Boolean matrix.'},
 'finite-floats':{'path':'tests/conformance/floats-and-bits/program.min','lines':[[7,23]],'expected_path':'tests/conformance/floats-and-bits/expected.stdout','expected_lines':[[2,16]],'proves':'Finite decimal arithmetic, exponent extremes, Float conversion, negative zero formatting and one finite ordering. Different literal values from selected Go file.'},
 'literal-normalization':{'path':'tests/compiler-hardening.py','lines':[[118,149]],'proves':'64 model-derived decimal normalization comparisons, negative zero, enormous zero exponent, huge mantissa and exact overflow boundary. No explicit half-minimum-subnormal source literals or named Go cases.'},
 'float-bits-formatter':{'path':'tests/runtime-numeric.py','lines':[[34,62],[123,161]],'proves':'Native formatter receives binary64 bits, including minimum subnormal and maximum finite; generated lane uses separate numeric-formatting.min. Native inputs bypass source literal parser.'},
 'formatter-native-driver':{'path':'tests/runtime-numeric.c','lines':[[34,38],[119,134]],'proves':'Reads hexadecimal bit patterns, reconstructs native double with memcpy, then formats. Does not parse Minyar source.'},
 'scalar-boundaries':{'path':'tests/checked-scalars.py','lines':[[12,46],[95,163]],'proves':'Signed64 bit shifts, Character bounds, truncating Float-to-Integer and exact conversion traps. Does not introduce small-width Integer types or casts.'},
 'nan-clamp':{'path':'tests/checked-scalars.py','lines':[[48,62]],'proves':'Bytes-backed NaN payload and negative-zero clamp behavior. Clamp selects negative zero in this case; it is not a direct NaN comparison matrix.'},
 'small-mask':{'path':'tests/conformance/floats-and-bits/program.min','lines':[[29,38]],'expected_path':'tests/conformance/floats-and-bits/expected.stdout','expected_lines':[[22,29]],'proves':'Small 0xFF & 0x0F, shifts, OR/XOR, complement and wrapping. No 21/10/7-bit projection of a 64-bit input spanning its 32-bit boundary.'},
 'bytes-endian':{'path':'tests/conformance/bytes/program.min','lines':[[2,16]],'expected_path':'tests/conformance/bytes/expected.stdout','expected_lines':[[1,7]],'proves':'Unaligned Int32 -2, UInt16 65535 and Float storage. Does not implement Zig arbitrary-width integer casts or packed enum layout.'},
 'list-and-record-literals':{'path':'tests/recursive-data.py','lines':[[148,184]],'proves':'Homogeneous ordinary Lists and named records; managed captured projection survives replacement. No Optional, enum, inheritance, dynamic class casts or packed layout.'},
 'existing-projections':{'path':'tests/memory-research-peer-projections.py','lines':[[41,100]],'proves':'Previously implemented original Bytes independent-copy, row-alias versus explicit snapshot and unused-literal effect/order controls. Not new round5 coverage; do not propose duplicates.'},
 'local-oracle':{'path':'tests/regressions.py','lines':[[49,62]],'proves':'CompilerTestCase.executes checks process status and exact stdout at O0/O2 when actually invoked. This research round invokes none of it.'},
}
for ref in local_refs.values(): ref['verification']='fixture_source_read_only; not_run_this_round'
contracts=[
 {'path':'docs/language.md','lines':[[19,67],[106,110],[149,160],[250,284]],'meaning':'signed64 Integer, binary64 Float, explicit same-type comparison, initialized homogeneous reference Lists/records; record equality absent'},
 {'path':'compiler/compiler.min','lines':[[249,268],[1693,1720],[2160,2189]],'meaning':'Float digits required around point; no unary plus; ordered NaN comparisons, unordered !=; logical ! XOR Boolean'},
 {'path':'docs/runtime-memory.md','lines':[[69,113]],'meaning':'automatic ownership and protected borrows; matching values alone prove no alias/copy/lifetime property'},
]
units=[]
def unit(id,path,span,name,disposition,expected,mapping,excluded,coverage,gap='',proposal=None,helpers=(),sites=(),guards=()):
 s=by_path[path]
 u={'id':id,'language':s['language'],'commit':s['commit'],'path':path,'sha256':s['sha256'],'lines':list(span),'url':s['url']+f'#L{span[0]}-L{span[1]}','name':name,'disposition':disposition,'upstream_expected':expected,'minyar_mapping':mapping,'incompatible_or_excluded_contract':excluded,'current_local_coverage':coverage,'coverage_gap':gap,'proposal':proposal,'helper_spans':[list(x) for x in helpers],'source_assertion_sites':list(sites),'backend_skip_guards':list(guards),'verification':'manually_read_complete_selected_file_and_helpers; no_peer_or_local_execution; no_port'}
 units.append(u);return u
# Swift: output directives are ordered subsequence checks, not exact-output assertions.
p='test/Interpreter/array_of_optional.swift'
unit('S1',p,(12,25),'optional-array present/absent iteration and final progress','incompatible_as_written',
 'Printed sequence 10, none, 20, none, 30, hello world. Six ordered CHECK directives L6-11; normal main call. No mutation, destructor or ownership-count assertion.',
 'Minyar has initialized homogeneous Lists but no Optional or sum/enum payload. A Boolean-tagged record algorithm would implement another protocol; no such substitute proposed.',
 'Int?, .none/.some payload pattern and switch are absent; no optional lifetime or allocation proof from value output.', ['list-and-record-literals'],
 sites=[{'line':i,'kind':'FileCheck_CHECK','source':lines(p)[i-1]} for i in range(6,12)],helpers=[(12,23)])
for id,span,name,expect,mapping,exclude,helper,site in [
 ('S2',(8,9),'derived-to-base inherited method call','foo','Named Minyar records have no subtyping or inherited methods.','class inheritance and derived-to-base conversion',(4,6),8),
 ('S3',(10,11),'forced base-to-derived cast','bar','There is no dynamic class identity or forced downcast; ordinary helper print is not cast coverage.','as! and runtime class casting',(4,6),10),
 ('S4',(12,13),'forced cast to generic subclass','bas','No generic class factory, runtime specialization identity or forced downcast.','G<T>, G<Int>, inheritance and as!',(4,6),12)]:
 u=unit(id,'test/Interpreter/conversions.swift',span,name,'incompatible_as_written',f'Ordered output CHECK {expect}; associated call at L{int(id[1:])+13}. No failing cast is asserted.',mapping,exclude,[],helpers=[helper],sites=[{'line':site,'kind':'FileCheck_CHECK','source':lines('test/Interpreter/conversions.swift')[site-1]}])
 u['call_spans']=[[int(id[1:])+13,int(id[1:])+13]]
# Go: each explicit matrix entry is one reviewed semantic unit, all 54 retained.
p='test/floatcmp.go'
rows=[]
for n,line in enumerate(lines(p),1):
 m=re.search(r'floatTest\{"([^\"]+)", (.+), (true|false)\}',line)
 if m: rows.append((n,m.group(1),m.group(2),m.group(3)))
for i,(n,name,expr,want) in enumerate(rows,1):
 u=unit(f'N{i}',p,(n,n),name,'already_covered' if i<=2 else 'adopt_pending',
 f'{expr} is {want}; main compares the stored expr with want at L82, reports mismatches and panics if any mismatch. Successful source expectation: no diagnostics.',
 'Use Float nan=0.0/0.0 and Float f=1.0 with the exact comparison/Boolean ! expression. Alternative Bytes-backed quiet NaN may supply the same comparison domain; no payload-identity assertion required.',
 'Go math.NaN construction, globals, named array-table type, range tuple binding and diagnostic strings are outside this projection. Minyar does not coerce Integer 1 to Float.',
 ['nan-equality','nan-clamp','finite-floats'],
 'Direct NaN equality/inequality property already asserted in conformance; this does not establish variable/helper lowering.' if i<=2 else 'Inspected fixtures lack this exact ordered/negated operand combination; clamp/conversion rejection does not prove comparisons.',
 'P1',helpers=[(13,20),(79,93)],sites=[{'line':n,'kind':'explicit_table_oracle','source':lines(p)[n-1],'expression':expr,'expected_boolean':want=='true'}])
 u['assertion_driver_spans']=[[81,92]]
 u['support_helper_ids']=['go-nan','go-frombits']
# Go float lexical forms: core grammar coverage remains incompatible if spelling cannot be accepted.
p='test/float_lit.go'
for i,(n,line) in enumerate([(n,l) for n,l in enumerate(lines(p),1) if 'if !close(' in l],1):
 m=re.search(r'close\(([^,]+), (-?\d+), (\d+), (-?\d+)\)',line)
 lex,ia,ib,power=m.groups()
 compatible=not lex.startswith('+') and bool(re.fullmatch(r'-?\d+\.\d+(?:[Ee][+-]?\d+)?',lex))
 canonical=lex.lstrip('+')
 if canonical.startswith('-.'):canonical='-0'+canonical[1:]
 elif canonical.startswith('.'):canonical='0'+canonical
 if not re.search(r'\.\d',canonical):
  if '.' in canonical:canonical=canonical.replace('.','.0',1)
  else:canonical=re.sub(r'([Ee])',r'.0\1',canonical) if re.search('[Ee]',canonical) else canonical+'.0'
 u=unit(f'L{i}',p,(n,n+2),lex,'adopt_pending' if compatible else 'incompatible_as_written',
 f'close({lex},{ia},{ib},{power}) expects true. Reference db=(Float({ia})/Float({ib}))*10^{power}; both zeros compare equal, otherwise abs((da-db)/da)<1e-14. This is approximate agreement, not decimal-bit equality.',
 f'Existing-syntax value analogue {canonical}; explicit Float(Integer) conversions in a separate rational/reference helper. '+('Source lexeme itself fits current grammar.' if compatible else 'Rewriting spelling drops the lexical contract; value analogue is uncredited, not a compatible syntax port.'),
 'Go accepts leading/trailing-point floats, exponent-only forms and unary +. Minyar requires digits on both sides of a point and has no unary +. Float tolerance, constant-folding and print spelling are distinct contracts.',
 ['literal-normalization','finite-floats','float-bits-formatter'],
 'Related normalization/formatting fixtures use different operands. No supported syntax expansion requested. Underflow-bit discriminator P2 is an original boundary extension, not an assertion in this Go file.',
 'P2' if compatible else None,helpers=[(13,21),(23,47),(200,203)],sites=[{'line':n,'kind':'close_oracle_call','source':line,'literal':lex,'reference_integer_numerator':int(ia),'reference_integer_denominator':int(ib),'reference_decimal_power':int(power),'expected_close':True}])
 u['existing_syntax_value_analogue']=canonical
 u['oracle_limit']='The zero-mismatch branch L27-32 returns false without setting global bad; it prints from the caller but does not alone force the final panic. Nonzero tolerance failures set bad. Success output expected empty; no test-runner enforcement of stdout was inspected.'
 if n==173:u['diagnostic_mismatch']='Checked exponent is +23; failure output at L174 prints literal +10.e+234. The diagnostic is not the numeric oracle.'
# Zig: six complete named tests, fifteen meaningful subcases, every expect site included.
p='test/behavior/cast_int.zig'; src=lines(p)
named=[(7,18),(20,33),(35,137),(167,181),(183,215),(217,247)]
def guards(span):return [{'line':n,'source':src[n-1]} for n in range(span[0],span[1]+1) if 'return error.SkipZigTest' in src[n-1]]
def sites(span):return [{'line':n,'kind':'expectEqual' if 'expectEqual(' in src[n-1] else 'expect','source':src[n-1]} for n in range(span[0],span[1]+1) if re.search(r'\btry expect(?:Equal)?\(',src[n-1])]
def zig(id,span,test,name,disp,expected,mapping,exclude,coverage,proposal=None,helpers=()):
 u=unit(id,p,span,name,disp,expected,mapping,exclude,coverage,
 'Inspected scalar masks/shifts are related only; no Zig width/layout/optional test is executed or implemented.',proposal,helpers=helpers,sites=sites(span),guards=guards(test))
 u['named_test_span']=list(test);u['named_test_name']=src[test[0]-1];u['support_helper_ids']=['zig-expect','zig-expect-equal']
 return u
u=zig('Z1',(7,18),named[0],'u128 max shifted by checked u7 count120','incompatible_as_written','maxInt(u128)=2^128-1; >>120 yields255. Expect call L17.',
 'Integer is signed64; maxInt(u128) and count120 cannot be represented as this operation. A shift120 must stop.',
 'u128, u7 result typing, @intCast and unsigned logical shifting; -1 >>120 is not a substitute.', ['scalar-boundaries'])
u['support_helper_ids'].append('zig-maxint')
zig('Z2',(20,33),named[1],'signed -5 widen and checked narrow','incompatible_as_written','L27 i32 y equals i8 x, both -5; L32 checked i32 x2 to i8 equals i8 y2 -5. Both assertions true.',
 'Ordinary Integer -5 copies preserve value, but do not perform widening/narrowing; an existing Bytes Int16 check is a separate storage conversion.',
 'Minyar has one Integer type; implicit cross-width equality/coercion and i8 checked cast are absent.', ['scalar-boundaries','bytes-endian'])
unsigned=[((38,53),'u21',6417,'0x145678',1332856,'0x1FFFFF'),((55,70),'u10',234,'0x278',632,'0x3FF'),((71,86),'u7',11,'0x78',120,'0x7F')]
for j,(span,width,value,hexout,decimal,mask) in enumerate(unsigned,3):
 u=zig(f'Z{j}',span,named[2],f'{width} widen then truncate u64 to {width}','adapt_pending',
 f'All five expectEqual calls: a,b,c={value}; d,e={hexout} ({decimal}). w=0x1234567812345678; truncation discards all high bits above {width}.',
 f'Use Integer w & {mask} for the explicit low-bit algorithm and compare {decimal}; ordinary Integer aliases preserve {value}. This tests bitwise extraction, not a typed cast.',
 'u21/u10/u7/u32/u64/u60, implicit widening, @truncate and result typing absent. Replacing only widths with Integer would omit truncation.', ['small-mask','scalar-boundaries'],'P3')
 u['original_mask']=mask;u['independent_low_bits_expected']=decimal
for j,(span,width,initial,narrow) in enumerate([((88,103),'i21',-6417,-12345),((105,120),'i10',-234,-456),((121,136),'i7',-11,-42)],6):
 zig(f'Z{j}',span,named[2],f'{width} sign-preserving widening and checked narrowing','incompatible_as_written',
 f'All five expectEqual calls: a,b,c={initial}; d,e={narrow}. Negative narrow input fits {width}; no overflow/rejection case in this source block.',
 'Integer scalar assignment preserves both bounded negatives. Signed64 shift/mask controls may separately test sign extraction; assignment alone is not this cross-width contract.',
 f'{width}/i32/i64/i60 signed width coercion and checked @intCast absent. The test does not assert invalid casts.', ['scalar-boundaries'])
packed=[
 ('Z9',(173,175),named[3],'optional Piece payload','L174-175 optional unwrapped type PAWN and color BLACK after charToPiece(p).', 'optional payload, non-byte enum load, error-union return'),
 ('Z10',(177,180),named[3],'raw-byte Piece payload','L179-180 raw byte251 loaded into Piece has type PAWN, color BLACK.', 'packed layout, pointer cast/write and undefined initial object'),
 ('Z11',(192,198),named[4],'Piece field inside ordinary struct','L197-198 raw byte251 into struct0.p gives PAWN,BLACK; struct0.int is unobserved.', 'packed Piece load within ordinary struct and pointer cast'),
 ('Z12',(200,214),named[4],'three Piece fields inside packed struct','L209-214 every p0,p1,p2 gives PAWN,BLACK; p0 byte-written, p1/p2 helper-written. pad is unobserved.', 'non-byte-aligned packed fields, byte overwrite and little-endian guard'),
 ('Z13',(227,233),named[5],'packed union interpretation','L232-233 union0 int=251 interpreted as Piece gives PAWN,BLACK.', 'packed union type punning'),
 ('Z14',(235,241),named[5],'ordinary union overwritten Piece','L240-241 initial WHITE/KING Piece overwritten with byte251 gives PAWN,BLACK.', 'untagged union and raw partial-storage write'),
 ('Z15',(243,246),named[5],'middle packed Piece array element','L245-246 pieces[1] byte251 gives PAWN,BLACK; other elements unobserved.', 'array layout, packed enum load, pointer cast and undefined siblings')]
for id,span,test,name,expected,exclude in packed:
 zig(id,span,test,name,'incompatible_as_written',expected,
 'Named Minyar records can contain explicit Integer fields, but have no enum/packed bit layout, optional payload or pointer overwrite. An arithmetic 251 &1 / (251 >>1)&7 discriminator is an original bit algorithm only.',
 exclude+'; direct == is significant upstream: comments say expectEqual would hide the reported bug. No destructor, alias, reference-count or retained-result assertion.', ['list-and-record-literals','small-mask'],helpers=[(139,164)])
# Selective supporting oracle contracts, with exact unreviewed complements derived separately.
support=[
 {'id':'go-nan','path':'src/math/bits.go','read_spans':[[7,17],[30,31]],'meaning':'uvnan=0x7FF8000000000001; NaN constructs that binary64 via Float64frombits. No math library test credit.'},
 {'id':'go-frombits','path':'src/math/unsafe.go','read_spans':[[36,41]],'meaning':'Float64frombits reinterprets the uint64 bit representation. Minyar NaN construction need not preserve this payload.'},
 {'id':'zig-expect','path':'lib/std/testing.zig','read_spans':[[604,608]],'meaning':'expect false returns TestUnexpectedResult; true succeeds.'},
 {'id':'zig-expect-equal','path':'lib/std/testing.zig','read_spans':[[69,112]],'meaning':'Peer type resolution forms common T; scalar int/bool/enum equality uses != then TestExpectedEqual. Only scalar branch needed here, no structural equality credited.'},
 {'id':'zig-maxint','path':'lib/std/math.zig','read_spans':[[1440,1446]],'meaning':'For integer bits B, maximum=(1<<(B-isSigned))-1. u128 value has no Minyar equivalent.'},
 {'id':'zig-ascii','path':'lib/std/ascii.zig','read_spans':[[163,169],[190,194]],'meaning':'isUpper checks A..Z; toLower ORs bit5 only for uppercase. Input p is unchanged and BLACK.'}]
for u in units:
 if u['id'].startswith('Z') and int(u['id'][1:])>=9:u['support_helper_ids'].append('zig-ascii')
def complement(total,spans):
 seen=set(n for a,b in spans for n in range(a,b+1)); out=[]; start=None
 for n in range(1,total+2):
  if n<=total and n not in seen:
   if start is None:start=n
  elif start is not None:out.append([start,n-1]);start=None
 return out
for s in support:
 support_source=by_path[s['path']];s.update({k:support_source[k] for k in ['language','commit','url','sha256','snapshot']});s['review_pending_spans']=complement(support_source['physical_lines'],s['read_spans']);s['status']='selective_oracle_contract_review; not_complete_support_file'
proposals=[
 {'id':'P1','name':'NaN ordered and negated comparisons through direct values and helper returns',
 'design':'Use Float nan=0.0/0.0 and Float one=1.0. Check all 18 operand/operator combinations (nan,nan; one,nan; nan,one; ==,!=,<,>,<=,>=) directly, negated, and double-negated, with explicit expected Boolean rows. Also return each comparison from a typed Boolean helper before negation, and include finite-order controls (1.0<2.0 true, !(1.0<2.0) false). A small original two-call control compares effectful Float helpers returning nan/one and records trace12 regardless of comparison result.',
 'expected':'For each of the three operand pairs, base row [false,true,false,false,false,false]; ! row [true,false,true,true,true,true]; !! row repeats base. Helper-return rows identical; finite controls true,false; effectful ordered comparison false and decimal trace12.',
 'why_current_fixtures_do_not_prove_it':'Conformance L22-23 only exercises ==/!=; finite < is not unordered <; nan-clamp and NaN-to-Integer failure never observe Boolean ordering/negation. The emitter currently declares correct fcmp predicates but reading implementation is not regression evidence.',
 'coverage':['nan-equality','nan-clamp','scalar-boundaries','finite-floats'],'source_units':[f'N{i}' for i in range(1,55)],'duplicate_check':'No repetition of the already implemented Bytes-copy/row-snapshot/literal-effects projections; direct ==/!= are controls, not new coverage claims.','status':'original_proposal_existing_syntax_only; not_implemented_or_executed'},
 {'id':'P2','name':'Source literal underflow and signed-zero bit discriminators',
 'design':'In a generated Minyar program use 2.4703282292062327e-324, 2.4703282292062328e-324, and their negatives, plus 0.0e123 and -0.0e123. Append each Float to Bytes with addFloat64; print getInt64 at each offset. Repeat through a function returning Float. These decimal values straddle half the least positive binary64 subnormal; read signed64 bits rather than using a relative-error helper or formatting as the sole oracle.',
 'expected':'Bits in order: 0,1,-9223372036854775808,-9223372036854775807,0,-9223372036854775808. Function-return version identical. The two nearby decimal magnitudes are respectively below and above 2^-1075; positive zero and minimum subnormal compare differently at the bit level.',
 'why_current_fixtures_do_not_prove_it':'The Go file selected here tests normal nonzero values and tolerant decimal agreement, never half-minimum subnormal. Existing random source normalization has no guaranteed exact neighboring half-minimum values. Runtime formatter minimum-subnormal input is already binary bits and bypasses the source parser; existing overflow threshold tests concern the opposite end.',
 'coverage':['literal-normalization','float-bits-formatter','formatter-native-driver','finite-floats'],'source_units':[f'L{i}' for i in range(1,46)],'duplicate_check':'Generated source normalization boundary, not another native formatter or negative-zero-formatting test. No leading/trailing-point forms, unary plus or exponent-only syntax.','status':'original_boundary_proposal_existing_syntax_only; not_implemented_or_executed'},
 {'id':'P3','name':'Explicit low-bit extraction across the 32-bit boundary',
 'design':'Use Integer w=0x1234567812345678. Compare w &0x1FFFFF, w &0x3FF, w &0x7F with independently listed expected Integers. Pass the same value through typed Integer helpers and a List<Integer> slot, then repeat the masks. Add signed control -5 &0xFF=251 and (-5 &0xFF)<<56>>56=-5 using explicit grouping. Optional value-only packed-byte contrast checks 251 &1=1 and (251>>1)&7=5; do not construct an enum or packed record.',
 'expected':'All three paths yield1332856,632,120. Signed controls251,-5; optional scalar extraction1,5. No @truncate, small-width implicit conversion or packed-storage claim.',
 'why_current_fixtures_do_not_prove_it':'Conformance checks only 0xFF &0x0F and small bitwise values. Random full-width shift fixtures do not independently assert these cross-boundary low-bit masks or stored/helper projections. Typed Bytes tests have fixed native widths and are not arbitrary-width casts.',
 'coverage':['small-mask','scalar-boundaries','bytes-endian'],'source_units':['Z3','Z4','Z5'],'duplicate_check':'Original bitwise algorithm, not Zig cast implementation. Scalar equality on masks does not count as ownership proof.','status':'original_projection_proposal_existing_syntax_only; not_implemented_or_executed'}]
counts={'selected_source_entries':len(selected),'complete_selected_files_reviewed':len(selected),'selected_raw_physical_lines':sum(s['physical_lines'] for s in selected),'authored_comparison_groups':len(units),'swift_comparison_groups':sum(u['language']=='swift' for u in units),'go_nan_table_groups':len(rows),'go_float_literal_groups':sum(u['id'].startswith('L') for u in units),'zig_named_tests':len(named),'zig_semantic_subcase_groups':sum(u['language']=='zig' for u in units),'zig_assertion_source_sites':len(sites((1,len(src)))) if False else sum(len(u['source_assertion_sites']) for u in units if u['language']=='zig'),'zig_skip_guard_source_sites':len(guards((1,len(lines(p))))) if False else len(guards((1,247))),'swift_output_check_source_sites':9,'proposed_original_regressions':len(proposals),'dispositions':dict(collections.Counter(u['disposition'] for u in units)),'ports_implemented':0,'peer_or_local_test_executions':0,'compilations':0,'installations':0,'production_build_test_edits':0,'commits':0,'subagents':0,'timing_measurements':0}
# Helpers capture src/p in closures; reset Zig before count integrity.
p='test/behavior/cast_int.zig';src=lines(p)
counts['zig_assertion_source_sites']=len(sites((1,len(src))))
counts['zig_skip_guard_source_sites']=len(guards((1,len(src))))
for s in selected:s['reviewed_spans']=[[1,s['physical_lines']]];s['status']='complete_file_source_semantically_reviewed';s['review_pending_spans']=[]
ledger={'schema':'minyar.peer_readonly_values.round5.v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'new_distinct_read_only_source_review','scope':{'selected':selected,'selection_reason':'Complete bounded value/conversion/equality files; broadened Swift language-level Interpreter cases, Go binary64 assertions and Zig cast/packed-load behavior. No LLVM optimization IR equivalence claimed.','prior_round2_3_4_comparisons':218,'prior_round2_3_4_complete_selected_files':10,'central_ledgers_changed':False,'remaining_selected_source_review':[]},'counts':counts,'grouping_policy':'One explicit Go table row/literal call; one Swift output-producing conversion or complete optional sequence; Zig split into fifteen semantic subcases over six whole named tests. Different granularity from prior groups; not counts of ports, all language tests or campaign validations.','outcome_policy':'Expected values inferred from pinned assertions. No upstream/backend/compiler/test run. Swift CHECK is an ordered textual-subsequence contract, not whole stdout equality; executable_test required. Zig assertions only reached when recorded skip guards allow.','local_coverage_policy':'Inspected frozen local fixture source only, no current execution/passing claim. already_covered denotes an existing assertion of the semantic property, not an exact peer-code port. All gap claims relative to inspected fixtures.','ownership_policy':'No value comparison counts as copy/alias/retirement proof. Optional/packed/class results do not demonstrate lifetimes. Existing independent-copy, row-snapshot, unused-literal-order controls read and excluded from new proposals.','contract_references':contracts,'local_coverage_references':local_refs,'comparison_groups':units,'support_helper_reviews':support,'proposed_original_regressions':proposals,'source_nonassertion_review':{'swift':'Read entire two Interpreter files, class/helper declarations, main loops/calls and every RUN/REQUIRES/CHECK. No imports or backend-specific guards.','go':'Read all global initializers, every table/call oracle, all pow10/close/main helpers, diagnostic and panic branches. Mismatched exponent diagnostic and zero bad-flag weakness retained.','zig':'Read all imports, six named tests, all six width blocks, Piece enum and conversion/helper bodies, raw writes, unobserved fields, every backend/endian guard. Direct == bug note preserved.'},'availability':{'unavailable':[{'resource':'https://api.github.com/repos/swiftlang/swift/contents/test/Interpreter?ref=1ff1cc1170617ab23ab74aa8b741c8daca1903f6','status':'web_tool_internal_error_url_not_accessible','action':'No retry or alternative fetch of this directory API. Existing pinned local inventory supplied discovery; individual selected raw source resources independently accessible.'}],'prior_restricted_rust':'Excluded, not retried or bypassed; exact prior failed URL not supplied. Prior round1 semantic review count0 remains unchanged.','content_or_service_restriction_on_selected_sources':None,'new_unavailable_selected_sources':[],'unselected_discovery_candidates':[{'language':'zig','path':'test/behavior/eval.zig','commit':'3db960767d12b6214bcf43f1966a037c7a586a12','status':'unselected; web preview only, no authored semantic units; entire raw extent review_pending; normalized display length1642 is not authoritative raw physical length'},{'language':'go','path':'test/convert.go','commit':'56ebf80e57db9f61981fc0636fc6419dc6f68eda','status':'unselected; web body seen only, no authored review record; entire file remains review_pending; no file-credit'}]},'handoff':{'owned_writes':[str(REPORT)+'.md',str(REPORT)+'.json',str(BASE)+'/'],'prohibited_actions_executed':[],'parent_campaign_earliest_completion_utc':'2026-10-04T06:54:29Z','campaign_completion_claim':False,'pending_projection_ids':[u['id'] for u in units if u['disposition'] in ['adopt_pending','adapt_pending']],'incompatible_ids':[u['id'] for u in units if u['disposition']=='incompatible_as_written'],'already_covered_ids':[u['id'] for u in units if u['disposition']=='already_covered'],'proposals_unimplemented':['P1','P2','P3'],'unselected_peer_scope':'Outside this bounded selection, no exhaustive file/directory/campaign claim.'}}
(REPORT.with_suffix('.json')).write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+'\n')
# Concise report with complete per-unit tables; the JSON carries all exact attached sites.
md=['# Read-only peer value semantics — round 5','',f"Five complete new files, **{counts['selected_raw_physical_lines']} raw physical lines**, **{len(units)} heterogeneous comparison groups**: {counts['swift_comparison_groups']} Swift, {len(rows)} Go NaN rows, {counts['go_float_literal_groups']} Go literal calls, and {counts['zig_semantic_subcase_groups']} Zig subcases across six named tests. **60 pending adoptions, 3 pending adaptations, 53 incompatible units, 2 already-covered properties**. Three original proposals; zero ports or test executions.",'','This is a distinct documentary review, using GPT-6.1 Sol high. Only the two round5 research files and `evidence/peer-readonly/values-round5/` were authored. Core/native sources, dirty work, central ledgers, frozen soaks and stopped execution lanes were left alone. Earliest campaign completion remains 2026-10-04 06:54:29 UTC; this bounded round makes no campaign-completion claim.','', '## Complete source selection','', '| Source | Commit | Raw extent | SHA256 |','| --- | --- | --- | --- |']
for s in selected:md.append(f"| [{s['language']} {s['path']}]({s['url']}) | `{s['commit']}` | 1–{s['physical_lines']} | `{s['sha256']}` |")
md += ['', 'Sources and pinned licenses are retained unchanged under the evidence directory (Swift Apache-2.0 with Runtime Library Exception, Go BSD-3-Clause, Zig MIT). Physical lines come from raw bytes, including blanks; web line normalization differs. [Structured ledger](peer-readonly-values-round5.json) retains each exact assertion/helper/guard span. [Source manifest](../../evidence/peer-readonly/values-round5/source-manifest.json) and [document checks](../../evidence/peer-readonly/values-round5/document-checks.json) contain retrieval provenance and independent counts/hashes.','', 'The existing deduplicated ledger and rounds2/3/4 were read before selection. None of these five paths appears in their authored reviews. Prior rounds2–4 retain218 groups/10 complete files. Adding this round yields336 groups/15 files across those selected read-only rounds only; grouping differs, so this is not a whole-campaign denominator or a port count. Existing runtime projections were read at their durable run-ki_43p1a evidence and are not proposed again.','', '## Findings and interpretation','', '- **NaN ordering is a Boolean contract.** Existing conformance asserts direct == false and != true. The other52 exact operand/negation combinations are adoptable with existing Float/Boolean syntax; no special NaN syntax is needed. The current emitter declares ordered comparisons and unordered !=, but implementation reading does not replace an executable regression.','- **Literal grammar and numeric value are separate.** Eight of45 checked Go lexemes fit current Minyar grammar;37 test unsupported leading/trailing-point forms, exponent-only forms or unary plus. They remain incompatible as written. Rewriting to an ordinary decimal value does not cover Go grammar or require a Minyar syntax addition.','- **Go close is approximate.** For nonzero values it accepts relative error below1e-14; zero mismatches return false without setting global bad. Callers print failures; only nonzero error sets the final panic flag. L173 checks +10.e+23, while L174 prints +10.e+234 on failure. No exact decimal-bit, signed-zero or underflow result is inferred from that diagnostic.','- **Zig casts cannot be erased.** Unsigned21/10/7-bit truncation has a useful original mask projection; mixed signed widths and checked casts remain incompatible. A plain Integer assignment of -5 performs no narrowing. u128 max shifted120 cannot become signed64 -1 shifted120.','- **Optional/class/packed results supply no lifetime proof.** Swift optional iteration and inherited/forced generic class casts are incompatible. Zig packed enum/optional/union loads exercise layout, direct == and raw byte writes; Integer record fields would erase the tested bug. Source notes explicitly warn expectEqual hides it. No destructor or retained-owner assertion occurs.','- **Source and oracle execution stay distinct.** Swift CHECK accepts ordered textual matches, not necessarily exact stdout. Both Swift files require executable_test. Zig has19 skip-guard sites, including a little-endian guard in the packed-struct test; none was run. Go main expectations and all numeric results here are inferred.','', '## Local coverage mapping','']
for key,r in local_refs.items():
 span=', '.join(f'L{a}–{b}' for a,b in r['lines']);md += [f"**{key} — `{r['path']}` {span}.** {r['proves']} Source inspected only; no run/pass claim.",'']
md += ['', '## Per-unit comparisons','', 'The following tables cover every selected semantic unit without a within-file cap. JSON preserves attached driver/helpers and all51 Zig assertion calls; helpers and repeated guards are not extra comparisons. `adopt_pending` preserves the supported expression contract; `adapt_pending` is an explicitly weaker original algorithm. Incompatible rows can document a value analogue while retaining their incompatible disposition.','', '### Swift complete units','']
for u in units:
 if u['language']=='swift':md += [f"**{u['id']} — [{u['name']}]({u['url']}), {u['disposition']}.** {u['upstream_expected']} {u['minyar_mapping']} Excluded: {u['incompatible_or_excluded_contract']}",'']
md += ['### Go NaN matrix','', 'Every row uses Float operands with nan/one; directly preserve comparison and ! nesting. Local references: nan-equality, finite-floats, nan-clamp. N1/N2 have existing direct-property assertions; P1 adds the missing operand/operator/negation/helper combinations. All rows share the table initializer L19–77 and driver L79–93, plus pinned math.NaN/Float64frombits support. No globals/tuple-loop or payload-identity port.','', '| Unit / exact source | Expression | Expected Boolean | Disposition |','| --- | --- | --- | --- |']
for u in units:
 if u['id'].startswith('N'):
  a=u['source_assertion_sites'][0];md.append(f"| [{u['id']} L{a['line']}]({u['url']}) | `{a['expression']}` | `{str(a['expected_boolean']).lower()}` | {u['disposition']} |")
md += ['', '### Go complete literal call matrix','', 'All calls use pow10 L13–21 and close L23–47. Reference is (Float(ia)/Float(ib))*10^power; expected close=true, with the tolerance and zero limitation above. Local normalization/exponent/formatter tests are related but not exact peer-case or grammar coverage. The ordinary value column is a documentary analogue only for incompatible rows; no such ports were written. P2 is an original source-parser boundary discriminator rather than a Go assertion.','', '| Unit / physical source | Checked lexeme | Reference ia/ib ×10^power | Existing-syntax value analogue | Disposition |','| --- | --- | --- | --- | --- |']
for u in units:
 if u['id'].startswith('L'):
  a=u['source_assertion_sites'][0];md.append(f"| [{u['id']} L{u['lines'][0]}–{u['lines'][1]}]({u['url']}) | `{a['literal']}` | {a['reference_integer_numerator']}/{a['reference_integer_denominator']} ×10^{a['reference_decimal_power']} | `{u['existing_syntax_value_analogue']}` | {u['disposition']} |")
md += ['', '### Zig complete subcase comparison','']
for u in units:
 if u['language']=='zig':
  md += [f"**{u['id']} — [{u['name']}]({u['url']}), {u['disposition']}.** {u['upstream_expected']}",'',f"Minyar: {u['minyar_mapping']} Excluded: {u['incompatible_or_excluded_contract']}",'',f"Inspected local references: {', '.join(u['current_local_coverage'])}. "+('Original proposal '+u['proposal']+'. ' if u['proposal'] else '')+'Source only, no execution or ownership/copy proof.','', 'Guards for owning named test: '+('; '.join(f"L{g['line']}: `{g['source'].strip()}`" for g in u['backend_skip_guards']) or 'none')+'.','']
md += ['## Original missing-test proposals','', 'All three are original, precise, existing-syntax designs. No code was ported, compiled or executed. Recheck cited snapshot gaps against concurrent fixture changes before implementation.','']
for q in proposals:md += [f"**{q['id']} — {q['name']}.** {q['design']}",'',f"Expected independently: {q['expected']}",'',f"Gap: {q['why_current_fixtures_do_not_prove_it']} {q['duplicate_check']}",'']
md += ['## Availability, scope and handoff','', 'One Swift directory API request returned a web-tool Internal Error / URL not accessible; that API was neither retried nor routed around. The already retained inventory supplied candidate discovery. The distinct selected raw files and licenses were accessible. The prior restricted Rust resource remains excluded, with zero new review credit; stopped integration/literature/tooling execution lanes were not revived.','', 'Zig eval.zig and Go convert.go were discovery candidates only and remain unselected/review-pending. The retained unselected extents are Go convert.go L1–46 and Zig eval.zig L1–1759, entirely semantic-review pending. Full supporting raw files are retained but only the six listed oracle contracts receive selective-body review. Their exact pending complements are in JSON. Other peer files/directories are unreviewed by this round. No broad all-tests or all-papers claim is made.','', 'Selected-file review is complete: zero selected pending lines. All63 adopt/adapt projections and all3 original proposals remain unimplemented/unexecuted;53 incompatible groups remain excluded;2 existing direct NaN properties are documented. No runtime correctness result is inferred. Central ledgers remain untouched. The handoff derives counts from the saved record and independent documentary checks.']

# Retained unselected candidate extents receive no semantic-review credit.
ledger['availability']['unselected_discovery_candidates']=[{k:s[k] for k in ['language','commit','path','url','sha256','snapshot','physical_lines','status','reviewed_spans','review_pending_spans']} for s in manifest if s['kind']=='unselected_candidate']
REPORT.with_suffix('.json').write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+'\n')
REPORT.with_suffix('.md').write_text('\n'.join(md)+'\n')
print(json.dumps(counts,indent=2))
