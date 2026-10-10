"""Author comparison records from already-read source; never import or run tests."""
import json
import re
import hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

E = Path('evidence/peer-readonly/strings-round4')
R = Path('research/2026-10-memory/peer-readonly-strings-round4')
STAMP = datetime.now(timezone.utc).isoformat()
sources = json.loads((E / 'sources.json').read_text())
selected = [s for s in sources if s['path'].startswith('test/')]
lookup = {s['path']: s for s in selected}
units = []
coverage = {}

def cov(key, path, spans, meaning):
    coverage[key] = dict(path=path, lines=spans, extent=meaning,
                         verification='fixture_source_read_only; no_run_or_pass_claim')

cov('unicode', 'tests/regressions.py', [[96,112]], 'Scalar indexing, slice(ordinal,ordinal+1), Text(Character), length/byteLength; inputs A,é,界,🙂,Aé界🙂 and combining é. Different exact literals from this round.')
cov('invalid-utf8', 'tests/regressions.py', [[114,125]], 'File bytes C0 AF, ED A0 80, F4 90 80 80, E2 82 require exit1 and invalid UTF-8 diagnostic; no permissive replacement decoding.')
cov('scalar-boundary', 'tests/runtime-unit.c', [[359,367]], 'Native scalar roundtrip table includes zero and U+10FFFF; length1. Native ABI fixture, not compiler literal syntax or invalid Character traps.')
cov('byte-model', 'tests/runtime-bytes.c', [[33,99]], 'Native deterministic Bytes model: count/value oracle for mutation, clear/resize, self-append and sampled slice contents. Slice released before later source mutation, so copied-slice independence is not asserted.')
cov('byte-self', 'tests/runtime-bytes.c', [[61,65]], 'Native self-append doubles original bytes in the independent model. Does not establish in-place overlapping subrange copy or generated addBytes self-call.')
cov('byte-slice', 'tests/conformance/bytes/program.min', [[2,21]], 'Generated-syntax Bytes operations, slice(4,5) reads153 (expected.stdout L8), then byte iteration sum2759. No copy/source mutation contrast.')
cov('byte-empty', 'tests/conformance/bytes/program.min', [[32,38]], 'Clear length0, resize(3) zero at2, empty addBytes(loaded) length15. No explicit slice(length,length).')
cov('list-text', 'tests/conformance/text-and-lists/program.min', [[1,12]], 'Shared List additions/replacement, joinText Myar🙂, scalar length5 versus byteLength8, slice(1,4)=yar, typed nested empty List. Expected.stdout L1–6.')
cov('loops', 'tests/conformance/loops-and-assignment/program.min', [[9,24]], 'Range sum18 with break/continue; ordered Text List visits alpha,beta,gamma; Text héllo Character iteration skipping l. No effectful collection helper or loop growth assertion.')
cov('utf-loop', 'tests/peer-research-semantics.py', [[99,106]], 'abc日本語 scalar sequence/reconstruction and length6/byteLength12. Different literal; no once-evaluation counter.')
cov('empty-loop', 'tests/peer-research-semantics.py', [[108,117]], 'Empty Text loop visits0, leaves outer β code946; fresh binding, not Go assignment-form range semantics.')
cov('view-lifetime', 'tests/runtime-unit.c', [[162,192]], 'Native full slice identity, flattened nested immutable Text view root and surviving cd; retention guard copies one byte from8192-byte source. Public Text does not expose pointer identity.')
cov('text-self', 'tests/memory-research-text-join-index.min', [[31,47],[55,72]], 'Generated-syntax indexed Text self-join, empty join, retained immutable alias and view + suffix while root remains intact. Source expectations only.')
cov('receiver-order', 'tests/adversarial.py', [[83,103],[124,143]], 'Captured Text receiver survives effectful start/end helper replacement; output old!,new,last!. Indexed assignment events1 then2 and original!!. Different operation from Go parallel range assignment.')
cov('unicode-model', 'tests/adversarial.py', [[233,253]], 'Model-derived scalar lengths, byte lengths, every index and sampled slices, with alphabet containing zero, combining mark, Unicode maximum, quote/backslash. Not exact peer-case coverage or guaranteed sample at every endpoint.')
cov('text-abc', 'tests/regressions.py', [[77,90],[234,235]], 'Ordinary abc.slice(0,2)=ab and Text a+b=ab. Different exact nested ASCII substring sequence.')
cov('empty-list', 'tests/recursive-data.py', [[199,210]], 'Contextually typed empty List return/reassignment length0; no slice-pointer coercion/type machinery.')
cov('no-list-slice', 'tests/regressions.py', [[92,94]], 'Explicit diagnostic: List has no slice method; Text has no add method. No proposed writable List views.')

PENDING = 'runtime_projection_pending'
INCOMPATIBLE = 'incompatible_as_written'

def add(id, path, span, name, outcome, mapping, exclusions, local, gap, proposal=None, disposition=PENDING, helpers=None):
    s = lookup[path]
    lines = Path(s['evidence_path']).read_text().splitlines()
    units.append(dict(id=id, language=s['language'], path=path, lines=span, name=name,
        url=s['url']+f'#L{span[0]}-L{span[1]}', sha256=s['sha256'], disposition=disposition,
        upstream_expected=outcome, minyar_mapping=mapping, incompatible_or_excluded_contract=exclusions,
        current_local_coverage=local, pending_original_regression_or_gap=gap, proposal=proposal,
        helper_spans=helpers or [], source_assertion_sites=[],
        backend_skip_guards=[dict(line=i,source=lines[i-1].strip()) for i in range(span[0],span[1]+1) if 'return error.SkipZigTest' in lines[i-1]],
        verification='read_assertions_and_helpers; no_execution; no_port'))
    return units[-1]

# Go copy.go: all five families plus full [0:] array control. The nested driver
# domain is grouped rather than counted as hundreds of thousands of ports.
copy_common = 'For length0..39, in0..32, out0..32: n=min(length,40-in,40-out); returned count n, destination prefix/suffix unchanged, copied destination[out+j]=input[in+j] for0<=j<n. reset swaps two DISTINCT allocations; input/output do not overlap. Silent successful main.'
families = [
 ('C1','uint8 slice',109,110,[36,39],[131,160],'u8(i)=97+i%26; byte values97..122','byte-model','Bytes values fit directly; indexed writes into a destination using a separately copied source range.'),
 ('C2','string to uint8 slice',111,112,[36,39],[172,201],'ASCII inputS constructed from input8; same byte values','byte-slice','Use Text indexing plus Integer(Character) only for these ASCII scalars, or initialize matching Bytes; no Text-to-Bytes conversion API is claimed.'),
 ('C3','uint16 slice',113,114,[41,46],[213,242],'u16(i)=u8(i)*0x0101; values24929..31354','loops','A List<Integer> can hold these bounded values; explicit indexed destination writes preserve the value/count oracle.'),
 ('C4','distinct named uint32 slices',115,116,[48,54],[254,283],'u32(i)=u8(i)*0x01010101; values1633771873..2054847098','loops','A List<Integer> can hold these bounded values; named Go slice types have no Minyar counterpart.'),
 ('C5','uint64 slice',117,118,[56,63],[295,324],'u64(i)=u8(i)*0x0101010101010101, all top bytes<=0x7A and within signed64','loops','A List<Integer> can hold this particular value domain; full uint64 arithmetic/width is excluded.')]
for id,title,a,b,gen,verify,values,local,mapping in families:
    u=add(id,'test/copy.go',[a,b],title,copy_common+' '+values,mapping,
      'No copy intrinsic, writable slice/view, capacity, named slice types, parallel swap or unsigned element-width semantics. A helper implemented with ordinary indexing would test its own algorithm, not Go copy lowering.',[local],
      'Exact bounded prefix/copied/suffix/count matrix absent from inspected fixtures; propose a small independent matrix rather than claiming the full upstream driver.', 'P2',helpers=[gen,[65,87],[89,105],verify,[326,334]])
    u['source_assertion_sites']=[dict(line=i,kind='failure_predicate',source=Path(lookup['test/copy.go']['evidence_path']).read_text().splitlines()[i-1].strip()) for i in range(verify[0],verify[1]+1) if re.match(r'\s*if ',Path(lookup['test/copy.go']['evidence_path']).read_text().splitlines()[i-1])]
add('C6','test/copy.go',[336,346],'array [0:] roundtrip','Forty byte values u8(i) survive input->array[0:]->zeroed output; verify8(40,0,0,40) checks count40 and every value.',
    'Fresh Bytes initialized explicitly, full-range Bytes.slice followed by explicit destination writes can check content and copy independence.',
    'Go array-to-slice conversion, array storage and copy intrinsic excluded.', ['byte-model','byte-slice'],
    'Full-range snapshot followed by destination/source mutation remains a narrow original control relative to sampled native slices.', 'P1',helpers=[[36,39],[65,87],[96,105],[131,160]])

# Go literal assertions get one row each; unasserted mixed initial concatenation
# gets a separate compile/acceptance unit, explicitly not a result assertion.
add('L0','test/string_lit.go',[55,73],'unasserted mixed interpreted/raw concatenation',
    'All literal syntax/concatenation must be accepted; s is later overwritten. No assertion checks the value of this initial concatenation.',
    'Ordinary Text + accepts valid UTF-8 scalars; accepted syntax here is largely Go-specific.',
    'Raw backquoted strings, octal/hex/Unicode escape spellings, invalid-byte literals and Go constant concatenation are not inferred as Minyar support.', ['unicode','text-abc'],
    'No value oracle to preserve; do not invent one or count this as a passing runtime regression.', disposition=INCOMPATIBLE)
literal_specs = [
 (75,75,'empty interpreted/raw equality','Empty byte sequence.', 'An ordinary empty Text has length0 and byteLength0.', 'Raw backquote syntax excluded.', ['empty-loop'], 'P6',PENDING),
 (76,76,'blank equality','One ASCII space (32).','Ordinary single-space Text content equality.', 'Go assertion/diagnostic infrastructure excluded.', ['unicode-model'],'P5',PENDING),
 (77,77,'hex a equality','Byte61 hex equals ASCII a (97).','Use literal a or Text(Character(97)); hex escape parser contract excluded.','No Go hex-escape syntax claim.', ['unicode'],'P5',PENDING),
 (78,78,'hex a versus raw a','Same byte61 hex.','Same runtime content projection with ordinary Text.','Raw and hex escape spellings excluded.', ['unicode'],'P5',PENDING),
 (79,79,'Unicode ä escape','U+00E4 encoded C3 A4.','Literal ä equals Text(Character(228)); scalar length1, bytes2.','No Go Unicode-escape parser claim.', ['unicode','scalar-boundary'],'P5',PENDING),
 (80,80,'Unicode ä versus raw ä','U+00E4 encoded C3 A4.','Same scalar projection using ordinary UTF-8 literal.','Raw backquote and Unicode-escape spellings excluded.', ['unicode'],'P5',PENDING),
 (81,81,'Unicode 本 escape','U+672C encoded E6 9C AC.','Literal 本 equals Text(Character(26412)); scalar length1, bytes3.','No Go escape parser claim.', ['utf-loop'],'P5',PENDING),
 (82,82,'Unicode 本 versus raw 本','Same U+672C bytes.','Same runtime scalar/content projection.','Raw backquote and Unicode-escape spellings excluded.', ['utf-loop'],'P5',PENDING),
 (83,85,'control escape equality','Bytes07,08,0C,0A,0D,09,0B,5C,22 on both sides.','Build Text from valid Character values7,8,12,10,13,9,11,92,34 and observe every scalar; no unsupported escape required.','Escape spellings/diagnostic byte indexing excluded.', ['unicode-model'],'P5',PENDING),
 (86,88,'raw escape-looking text','Literal backslash-letter text, not controls; both sides have identical bytes.','Build literal backslash Character92 plus ordinary letters/quotes, assert exact scalar sequence.','Raw string grammar excluded.', ['unicode-model'],'P5',PENDING),
 (89,91,'octal/hex arbitrary byte escape equality','Bytes00,53,00,CA,FE,53 then two U+BABE scalars (몾); CA FE are invalid UTF-8.','Keep binary bytes in Bytes. Minyar Text must reject invalid UTF-8 rather than preserve this string.','Invalid UTF-8 Text, octal escapes and permissive byte-string contract incompatible.', ['invalid-utf8','byte-model'],None,INCOMPATIBLE),
 (92,94,'raw octal/Unicode escape-looking text','Ordinary ASCII backslashes and digits compare equal; no escape decoding on raw side.','Reconstruct ordinary Text through existing backslash Character and ASCII pieces.','Raw backquote parser and Go octal/Unicode escape syntax excluded.', ['unicode-model'],'P5',PENDING),
 (95,95,'raw trailing backslash','ASCII sequence backslash x, backslash u, backslash U, backslash.','Construct via Character92 and letters; content equality/length7.','Raw literal ending in backslash excluded.', ['unicode-model'],'P5',PENDING),
 (101,101,'maximum variable rune','U+10FFFF encoded F4 8F BF BF.','Text(Character(1114111)) has length1/byteLength4 and indexing returns1114111.','Go rune int32/string conversion syntax excluded.', ['scalar-boundary','unicode-model'],'P5',PENDING),
 (104,104,'variable too-large rune','U+110000 converts to replacement U+FFFD EF BF BD.','Character(1114112) must stop; no replacement value.','Scalar validation versus replacement is incompatible.', ['scalar-boundary'], 'P5',INCOMPATIBLE),
 (107,107,'variable minimum surrogate','U+D800 converts to U+FFFD.','Character(55296) must stop.','Surrogate replacement differs from scalar-only Character.', ['invalid-utf8'], 'P5',INCOMPATIBLE),
 (110,110,'variable maximum surrogate','U+DFFF converts to U+FFFD.','Character(57343) must stop.','Surrogate replacement differs from scalar-only Character.', ['invalid-utf8'], 'P5',INCOMPATIBLE),
 (113,113,'negative variable rune','-1 converts to U+FFFD.','Character(-1) must stop.','Negative replacement differs from scalar validation.', ['scalar-boundary'], 'P5',INCOMPATIBLE),
 (118,118,'maximum constant rune','U+10FFFF encoded F4 8F BF BF via Go compile-time conversion.','Same runtime Text(Character(1114111)) projection as L14; no compile-time conversion coverage.','Go compile-time constant conversion excluded.', ['scalar-boundary'],'P5',PENDING),
 (120,120,'too-large constant rune','U+110000 constant converts to U+FFFD.','Runtime Character(1114112) rejection control only.','Go compile-time acceptance/replacement unsupported.', ['scalar-boundary'],'P5',INCOMPATIBLE),
 (122,122,'minimum surrogate constant','U+D800 constant converts to U+FFFD.','Character(55296) rejection only.','Go constant acceptance/replacement unsupported.', ['invalid-utf8'],'P5',INCOMPATIBLE),
 (124,124,'maximum surrogate constant','U+DFFF constant converts to U+FFFD.','Character(57343) rejection only.','Go constant acceptance/replacement unsupported.', ['invalid-utf8'],'P5',INCOMPATIBLE),
 (126,126,'negative constant rune','-1 constant converts to U+FFFD.','Character(-1) rejection only.','Go constant acceptance/replacement unsupported.', ['scalar-boundary'],'P5',INCOMPATIBLE),
 (131,131,'mixed valid/invalid rune slice','One U+10FFFF followed by four U+FFFD;16 UTF-8 bytes total.','A List<Character> cannot contain invalid scalars; explicit Character construction stops at first invalid value.','No permissive rune-list to Text conversion; no full conversion API.', ['scalar-boundary','invalid-utf8'],None,INCOMPATIBLE),
 (133,133,'global valid rune roundtrip','gr1 -> string equals aä本☺; scalars97,228,26412,9786;9 UTF-8 bytes.','Iterate valid Text, reconstruct with Text(Character); scalar length4/byteLength9.','Go globals and []rune conversion APIs excluded.', ['utf-loop'],'P3',PENDING),
 (134,134,'global invalid rune roundtrip','gr2 replaces each FF with U+FFFD, equals aä��本☺;15 UTF-8 bytes.','Reject invalid input before a Text iteration can begin.','Go invalid-byte replacement decode incompatible.', ['invalid-utf8'],None,INCOMPATIBLE),
 (135,135,'global valid byte roundtrip','gb1 -> string equals original aä本☺ bytes.','Known byte sequence can be modeled in Bytes; valid Text content can be asserted separately.','No Text<->Bytes conversion API in inspected language contract; Byte indexing must not be replaced with Character indexing on Unicode.', ['unicode','byte-model'],None,INCOMPATIBLE),
 (136,136,'global invalid byte roundtrip','gb2 -> string preserves FF FF unchanged.','Bytes may preserve FF; Text rejects invalid UTF-8.','Permissive binary string and conversion API incompatible.', ['invalid-utf8','byte-model'],None,INCOMPATIBLE),
 (144,144,'local valid rune roundtrip','r1 -> string equals aä本☺.','Scalar iteration/reconstruction projection; length4/bytes9.','Go rune-slice conversion and globals are not implemented.', ['utf-loop'],'P3',PENDING),
 (145,145,'local invalid rune roundtrip','r2 conversion replaces each FF; aä��本☺.','Reject invalid Text.','Permissive replacement decode incompatible.', ['invalid-utf8'],None,INCOMPATIBLE),
 (146,146,'local valid byte roundtrip','b1 -> string preserves valid UTF-8 bytes.','Bytes and Text controls separately; no conversion port.','Missing Text<->Bytes conversion API; do not claim byte indexing through Text.', ['unicode','byte-model'],None,INCOMPATIBLE),
 (147,147,'local invalid byte roundtrip','b2 -> string preserves FF FF unchanged.','Binary preservation belongs in Bytes, invalid Text stops.','Permissive string conversion incompatible.', ['invalid-utf8','byte-model'],None,INCOMPATIBLE)]
for n,(a,b,title,outcome,mapping,exclusions,local,proposal,disposition) in enumerate(literal_specs,1):
    add('L'+str(n),'test/string_lit.go',[a,b],title,outcome+' Equality assert succeeds; main exits0.',mapping,exclusions,local,
        'Exact source assertion values pending where representable; related fixtures do not cover Go syntax/conversion. Invalid scalar controls must assert rejection, never U+FFFD replacement.',proposal,disposition,helpers=[[15,38],[40,51]])

# Go range.go units separate assertions about parallel assignment from ordinary
# collection iteration; unsupported pointer/map/channel features stay excluded.
range_specs = [
 ('R1',28,52,'blank ASCII Text visits','Three loop forms each visit26.', 'Use ordinary for character in alphabet and a counter; fresh unused name.', 'No blank identifiers, index/value tuple binding or assignment-form range.', ['loops','empty-loop'],'P4',PENDING,[]),
 ('R2',53,60,'ASCII byte-position sum','Index sum325 (0..25).','Explicit range0..text.length or counter yields325 for ASCII.','Minyar Text loop yields Characters, not byte offsets; equivalence only for ASCII.', ['loops'],'P3',PENDING,[]),
 ('R3',61,69,'ASCII rune sum','Rune sum2847.','Sum Integer(character) in ordinary Text loop.','Go rune arithmetic/type width excluded.', ['utf-loop'],'P4',PENDING,[]),
 ('R4',71,88,'channels','Channel sequence reconstructs alphabet; separate channel count26.','No channel or goroutine API. A List sum would not cover this test.','Channel close/receive and concurrent generator incompatible.', ['loops'],None,INCOMPATIBLE,[[13,24]]),
 ('R5',100,113,'slice expression evaluated once','nmake1, value sum15.','Helper with shared Integer state returns List<Integer>[1,2,3,4,5]; for visits its values once.','Go global state, index/value tuple syntax and fixed slice header length excluded.', ['loops'],'P4',PENDING,[[93,98]]),
 ('R6',115,125,'slice range parallel target assignment','i0,x[0]10,x[1]99.','Minyar has fresh loop binding and single-target assignment; explicit sequential code changes the contract.','Parallel target capture including x[old i] incompatible.', ['receiver-order'],None,INCOMPATIBLE,[]),
 ('R7',127,141,'slice index expression once','nmake1,index sum10.','Evaluate helper once into local List, explicit ordinal range/counter over values.', 'No index-yielding List loop; a range over stored length is a weaker runtime projection, not intrinsic range coverage.', ['loops'],'P4',PENDING,[[93,98]]),
 ('R8',143,157,'slice no bindings expression once','nmake1,count5.','Ordinary unused element binding and helper side-effect counter.','Go no-binding range syntax excluded; no growth case upstream.', ['loops'],'P4',PENDING,[[93,98]]),
 ('R9',167,181,'byte conversion expression once','makenumstring called1; byte sum15 for01..05.','Helper returns initialized Bytes01..05 and increments shared state once, then Bytes loop Integer sum15.','[]byte(Text) conversion and byte overflow width excluded; this changes helper representation and is explicitly a projection.', ['byte-slice','byte-model'],'P4',PENDING,[[162,165]]),
 ('R10',191,205,'array values once','nmake1,sum15.','Fresh List helper once with same values.','Array value copying/fixed size excluded; List shared semantics not an array implementation.', ['loops'],'P4',PENDING,[[186,189]]),
 ('R11',207,221,'array indices once','nmake1,sum10.','Fresh List helper evaluated once plus ordinary ordinal range.','Go index range, array value and length evaluation rules excluded.', ['loops'],'P4',PENDING,[[186,189]]),
 ('R12',223,237,'array no bindings once','nmake1,count5.','Fresh List helper and unused element binding.', 'Go fixed-array/no-binding semantics excluded.', ['loops'],'P4',PENDING,[[186,189]]),
 ('R13',244,270,'array pointer len/cap and values','Each len/cap call invokes helper once and yields5; range invokes once and sums15.','No pointer-to-array or capacity property.','Pointer len/cap evaluation and range contract incompatible; List helper similarity does not cover it.', ['loops'],None,INCOMPATIBLE,[[239,242]]),
 ('R14',272,287,'array pointer indices','nmake1,index sum10.','No pointer-to-array range.','Pointer representation/evaluation incompatible; no duplicate List projection credit.', ['loops'],None,INCOMPATIBLE,[[239,242]]),
 ('R15',288,302,'array pointer no bindings','nmake1,count5.','No pointer-to-array range.','Pointer/no-binding contract incompatible.', ['loops'],None,INCOMPATIBLE,[[239,242]]),
 ('R16',312,325,'Unicode Text values expression once','nmake1, scalar sum10180 for abcd☺ (97+98+99+100+9786).','Effectful Text helper once; Integer(Character) sum10180/count5 and byteLength7.', 'No global mutable state; no rune32 width arithmetic. Minyar valid UTF-8 domain preserved.', ['utf-loop'],'P4',PENDING,[[307,310]]),
 ('R17',327,336,'Text range parallel indexed target','i0,x[0]a,x[1]c.','No parallel range assignment.', 'Old-index lvalue capture and outer assignment incompatible.', ['receiver-order'],None,INCOMPATIBLE,[]),
 ('R18',337,346,'Text range parallel target depending on rune','r2,y[0]1,y[1]0,y[2]3.','No parallel range assignment.', 'Value/index assignment order and old-rune target capture incompatible.', ['receiver-order'],None,INCOMPATIBLE,[]),
 ('R19',348,362,'Unicode Text byte-position sum','nmake1, byte offsets0,1,2,3,4 sum10.','An explicit scalar ordinal counter also sums10 ONLY for this literal, whose sole multibyte scalar is last.','Minyar for Text produces Character, not byte positions. Original interior-multibyte discriminator required; same sum is not general byte-index coverage.', ['unicode','utf-loop'],'P3',PENDING,[[307,310]]),
 ('R20',364,378,'Unicode Text no bindings count','nmake1,count5, despite UTF-8 byteLength7.','Ordinary Text loop helper once yields five Characters.','Go no-binding syntax excluded.', ['utf-loop'],'P4',PENDING,[[307,310]]),
 ('R21',388,402,'map values expression once','nmake1,sum10180.','No Map type in inspected Minyar language.', 'Map range/construction and unspecified iteration order incompatible; equivalent List sum not coverage.', ['loops'],None,INCOMPATIBLE,[[383,386]]),
 ('R22',404,418,'map indices expression once','nmake1,key sum10.','No Map/key iteration.', 'Map key contract incompatible.', ['loops'],None,INCOMPATIBLE,[[383,386]]),
 ('R23',420,434,'map no bindings once','nmake1,count5.','No Map range.', 'Map/no-binding contract incompatible.', ['loops'],None,INCOMPATIBLE,[[383,386]]),
 ('R24',446,461,'effectful pointer range lvalues','getvar calls4; index sum1,value sum3.','Ordinary helper effects have related tests, but no pointer lvalues or parallel range targets.','Pointer dereference, range-assignment evaluation contract incompatible.', ['receiver-order'],None,INCOMPATIBLE,[[439,444]]),
 ('R25',463,472,'empty array skips lvalue evaluation','No iteration and ncalls0.','An empty Text/List/Bytes skips body effects as an original control, not pointer-target evaluation.','No effectful pointer range targets, no zero-sized Go array typing.', ['empty-loop','empty-list'],None,INCOMPATIBLE,[[439,444]])]
for id,a,b,title,outcome,mapping,exclusions,local,proposal,disposition,helpers in range_specs:
    add(id,'test/range.go',[a,b],title,outcome+' All failure checks stay false; main silent success.',mapping,exclusions,local,
        'Exact once-call counters/sums pending where representable; excluded contracts remain unsupported. Collection growth/element replacement is not tested upstream.',proposal,disposition,helpers=helpers)
add('S1','test/strcopy.go',[17,29],'substring conversion address inequality',
    '2048 zero bytes -> string -> sub[10:12] -> string([]byte(sub)); subh.Data != subcopyh.Data or panic. No distinct content oracle is asserted.',
    'Public immutable Text sharing is legal. Bytes.slice copies, but proving its mutation independence is a different original contract.',
    'reflect.StringHeader, unsafe.Pointer and forced string-byte-string allocation/address identity are incompatible. The2048-byte source is below Minyar documented >4KiB tiny-slice copy guard; do not claim it must copy.',
    ['view-lifetime','byte-slice'],'Only copied Bytes mutation independence and retained Text value/lifetime can be proposed. Never assert distinct public Text addresses.','P1',INCOMPATIBLE)

# One named Zig test is one explicit group, including every nested helper and
# all type/value assertions. Runtime projections never claim comptime/type parity.
zig_specs = [
 (1,'Lengths5/10 and first selected i32 value1234.', 'Initialize a List<Integer> of20 values; explicitly collect positions5..10 and10..20 into fresh Lists, or use bounded byte values in Bytes. No public List.slice.', 'Undefined array storage, pointer dereference, writable view and pointer-to-array type excluded.', ['loops','no-list-slice'],'P6',PENDING),
 (2,'Comptime ASCII source length10, slice length1, element2.', 'Runtime Text1234567890.slice(1,2) has length1 and Character2.', 'No compile-time slice execution/type coverage.', ['text-abc'],'P6',PENDING),
 (3,'Undefined many-pointer slices[0..0] and[100..100] each length0.', 'Initialized empty Bytes/Text boundaries only; cannot slice beyond an empty object.', 'Undefined/unbounded pointer has no Minyar counterpart; slice(100,100) on empty Bytes/Text must fail.', ['byte-empty','empty-loop'],'P6',INCOMPATIBLE),
 (4,'Zero-element u8 array coerced to slice; helper length0.', 'Bytes() or contextually typed empty Integer List length0.', 'Implicit array-to-slice pointer coercion excluded.', ['byte-empty','empty-list'],'P6',PENDING),
 (5,'hello sentinel slice length5, slice[5]0; runtime and comptime helper calls.', 'Text hello length5; index5 must stop, not yield zero.', 'Sentinel access at length and comptime execution incompatible.', ['unicode'],'P6',INCOMPATIBLE),
 (6,'Nested open slices of comptime buffer share mutation; nested indexed value1.', 'Plain Bytes alias observes writes; each Bytes.slice makes an independent copy instead.', 'Writable nested view and comptime variable identity incompatible.', ['byte-slice','list-text'],'P1',INCOMPATIBLE),
 (7,'Nested sentinel slices preserve [:0]const u8; lengths5/4, first h/e, sentinel0 at5/4.', 'Ordinary Text nested slices can assert content/length; endpoint reads must stop.', 'Sentinel propagation, pointer typing and endpoint zero access incompatible.', ['view-lifetime'],'P6',INCOMPATIBLE),
 (8,'End-index slices types *const[5]u8 and *const[5:0]u8; both length5, h/o values, sentinel0 for sentinel variant.', 'Runtime hello slice contents only; no sentinel/type claim.', 'Type-level sentinel and endpoint access incompatible.', ['text-abc'],'P6',INCOMPATIBLE),
 (9,'Both array and slice loops yield type values i32,f64,type in that order.', 'Minyar has no first-class type values or compile-time generic loop.', 'List<type>, reflection, comptime and inline type iteration incompatible.', ['loops'],None,INCOMPATIBLE),
 (10,'Generic memAlloc(u8,10) returns view into static100-byte buffer; memFree deliberately no-op; test has no value assertion.', 'Automatic Bytes ownership is not this allocator/free API.', 'Generic pointer cast, static storage and manual free protocol incompatible; no allocator leak/success claims.', ['byte-empty'],None,INCOMPATIBLE),
 (11,'Hardcoded pointer4 slice length2; type*[2]u8 and slice.ptr address4.', 'No public hardcoded-address/pointer conversion.', 'Address identity and pointer typing incompatible.', [],None,INCOMPATIBLE),
 (12,'Comptime pointer view assignment changes nested original buffer read to1.', 'Plain Bytes aliases observe1 but copied slice does not mutate source.', 'Pointer cast/comptime mutable view incompatible.', ['byte-slice'],'P1',INCOMPATIBLE),
 (13,'Both pointer-cast variants slice[1]2 from array1..8.', 'Runtime Bytes slice(0,2) returns second byte2 with original input initialized.', 'Pointer casts, const-pointer typing and comptime pointer provenance excluded.', ['byte-slice'],'P6',PENDING),
 (14,'Empty string and empty u32 array slices have length0 and content equality to empty.', 'Text empty.slice(0,0) and Bytes().slice(0,0) length0; typed empty List cannot call slice.', 'Array-to-slice/storage/type conversion excluded; Text counts scalars generally.', ['byte-empty','empty-list'],'P6',PENDING),
 (15,'Pointer shift by1 then first5 values gives length5 and elements2,3,4,5,6.', 'Bytes1..8.slice(1,6), check every selected byte.', 'Unbounded pointer arithmetic and missing-end syntax excluded.', ['byte-model'],'P6',PENDING),
 (16,'Hardcoded x address0x1000,len0x500; y shifted0x100 i32 items address0x1400,len0x400.', 'No pointer address or element-size layout property.', 'Raw address arithmetic and compile-time pointer construction incompatible.', [],None,INCOMPATIBLE),
 (17,'Literal full slice *const[4:0]u8; array full slice *const[4]i32; runtime-zero slices [:0]const u8 and []const i32.', 'Ordinary Text/Bytes content does not cover these exact static types.', 'Sentinel and runtime/comptime-dependent pointer types incompatible.', ['text-abc'],None,INCOMPATIBLE),
 (18,'Struct entries []u32 field initialized through empty array coercion length0.', 'Record with explicitly typed empty List<Integer> field length0.', 'Zero-sized array/slice implicit result-location coercion excluded.', ['empty-list'],'P6',PENDING),
 (19,'Helper runtime slice[3..3] of three bytes equals empty.', 'Bytes1,2,3.slice(3,3) length0; empty at end is legal.', 'Writable view, usize width and Zig safety-mode behavior excluded.', ['byte-model','byte-empty'],'P6',PENDING),
 (20,'C-pointer[0..10] equals kjdhfkjdhf.', 'Known Text literal slice(0,10) projects ASCII contents.', 'Core test exercises C pointer range/conversion; remains incompatible, no pointer coverage.', ['text-abc'],'P6',INCOMPATIBLE),
 (21,'C pointer runtime-zero slice type[]const u32 versus compile-time zero *const[1]u32; five pointed values42.', 'Initialize Integer List with42 values only as optional content control.', 'C pointer element addresses, type resolution, dereference iteration incompatible.', ['loops'],None,INCOMPATIBLE),
 (22,'Comptime helper sliceSum([1,2])3 and sliceSum([3,4])7.', 'Two ordinary Integer List sums3 and7 can be compared separately.', 'No comptime specialization identity, inline loop or generic helper coverage.', ['loops'],'P4',PENDING),
 (23,'Aligned32 record slice write of field anything42 is observed in array[1].', 'Shared List<Record> plain alias can observe scalar field42.', 'Alignment32 and array view aliasing not covered by List alias; no implicit copied-record semantics.', ['list-text'],None,INCOMPATIBLE),
 (24,'buf abc followed by zero; sentinel slices resolve [:0]u8 then *[2]u8 or []u8 depending on bound.', 'Ordinary Bytes abc0 can preserve zero, but no sentinel type.', 'Null-termination validation, pointer-to-array and runtime-bound type distinctions incompatible.', ['byte-model'],None,INCOMPATIBLE),
 (25,'Empty slice permits align1,align4,align16 coercions and asserts each reflected alignment.', 'No public alignment or pointer attributes.', 'Alignment coercion/type reflection incompatible; empty length alone would not cover assertions.', ['empty-list'],None,INCOMPATIBLE),
 (26,'Five FF bytes cast from aligned slice to *u16 dereference65535; runtime/comptime.', 'Bytes FF FF getUInt16(0)=65535 is an optional explicit little-endian scalar control.', 'Core alignment/pointer cast/native layout and comptime dereference incompatible.', ['byte-slice'],None,INCOMPATIBLE),
 (27,'Many-pointer open slices keep [*]u8 or [*:0]u8 types and first values2,3, runtime/comptime.', 'Ordinary initialized Bytes.slice(1,5) could read2,3; bounded owned copy differs.', 'Unbounded pointer/no-end/sentinel propagation/type assertions incompatible.', ['byte-slice'],'P6',INCOMPATIBLE),
 (28,'Twenty helper subcases assert pointer-to-array types, sentinels, alignments, optional coercion, runtime/comptime distinctions; content subcases read2,3,5,0,1 and concatenateab. All exact sites/helper spans retained in JSON.', 'Only initialized bounded Bytes slices and ordinary Text+ can project selected values. Main test remains incompatible; no20-helper port credit.', 'Pointer-to-array typing, sentinel propagation/access, u0, explicit alignment, optional slice coercion and comptime/runtime type differences incompatible.', ['byte-slice','text-abc','view-lifetime'],'P6',INCOMPATIBLE),
 (29,'Comptime sentinel source slices type*[2]u8,*[2:4]u8,*[4:0]u8; runtime open tail[:0]u8.', 'No public sentinel-dependent type.', 'Pointer-array/sentinel and phase-dependent typing incompatible.', [],None,INCOMPATIBLE),
 (30,'Zero ordinary/sentinel slice variants resolve different *[0] or *[0:0] types across phases; no content assertion.', 'No pointer-array type reflection; empty length not the tested oracle.', 'Zero-size/sentinel phase-dependent typing incompatible.', ['empty-list'],None,INCOMPATIBLE),
 (31,'Two coerced slice literals: length3 values42,56,54; length3 strings hello, comma-space,world!; runtime/comptime.', 'Explicit homogeneous List<Integer> and List<Text>, check lengths/every element.', 'Anonymous tuple pointer-to-slice coercion, unused union definition and comptime execution excluded; no tuple/generic support inferred.', ['list-text'],'P7',PENDING),
 (32,'Comptime array concat aoeu+asdf yields aoeuasdf and *const[8]u8.', 'Ordinary Text+ preserves aoeuasdf.', 'Compile-time concat/slice constant folding and pointer type excluded.', ['text-abc'],'P7',PENDING),
 (33,'Comptime slice multiplication aoeu**2 yields aoeuaoeu and *const[8]u8.', 'Ordinary Text aoeu+aoeu preserves content without a repeat operator.', 'Slice multiplication syntax, compile-time evaluation and pointer type excluded.', ['text-self'],'P7',PENDING),
 (34,'Comptime bs of dotted literal[8..9] is1; both empty++bs and bs++empty have length1 and contents1.', 'Runtime Text.slice(8,9), then both orders of +empty.', 'Compile-time block/concat/type behavior excluded.', ['text-self','text-abc'],'P7',PENDING),
 (35,'Both explicit sentinel array and123 literal slices length3,slice[length]0.', 'Text123 index3 must stop.', 'Sentinel length-index access incompatible.', ['unicode'],'P6',INCOMPATIBLE),
 (36,'Sentinel array1..4 slice[4..5] includes zero with length1,*[1]u8.', 'Bytes four elements slice(4,5) must stop; explicit appended zero is an ordinary fifth element.', 'Implicit sentinel participates beyond public length; incompatible.', ['byte-model'],'P6',INCOMPATIBLE),
 (37,'Sentinel slice1..4[4..5] includes zero length1,*[1]u8.', 'Bytes slice(4,5) on length4 must stop.', 'Sentinel end-index access incompatible.', ['byte-model'],'P6',INCOMPATIBLE),
 (38,'Comptime writable slice descriptor length0 +=2 exposes original0,1 and length2.', 'Bytes.resize(2) zero-initializes exposed bytes instead of reviving old contents; separate alias shares container length.', 'Direct slice.len descriptor mutation/comptime view metadata incompatible.', ['byte-empty'],None,INCOMPATIBLE),
 (39,'All four equality assertions compare exact const pointer/slice-field-pointer types.', 'No address-of or pointer attributes.', 'Const pointer type reflection incompatible.', [],None,INCOMPATIBLE),
 (40,'All four equality assertions compare mutable pointer-to-slice and pointer-to-ptr-field types.', 'No address-of/mutable pointer metadata.', 'Pointer/field mutability type reflection incompatible.', [],None,INCOMPATIBLE),
 (41,'Global slice ptr+=1,len-=2 transforms string totrin.', 'Text string.slice(1,5) yields trin as an optional content control.', 'Direct global writable descriptor/pointer arithmetic incompatible; resulting contents alone do not cover it.', ['text-abc'],'P6',INCOMPATIBLE),
 (42,'Slice of12 void items with runtime bound10 has length10.', 'Nothing cannot be stored in List; no zero-bit element type.', 'Slice<void>, zero-sized value storage and undefined array incompatible.', ['no-list-slice'],None,INCOMPATIBLE),
 (43,'Two block expressions use dereferenced runtime index0 on empty array; retained result length0.', 'Bytes().slice(ordinary Integer0,0) length0.', 'Pointer dereference and block-value break syntax excluded.', ['byte-empty'],'P6',PENDING),
 (44,'Two empty-slice pointer casts retain the same integer address after adding zero. Name says non-null; actual assertions only compare addresses.', 'No public pointer identity/null contract; length0 is not this oracle.', 'Pointer identity, cast and undefined storage assumptions incompatible; do not invent a non-null assertion.', ['empty-list'],None,INCOMPATIBLE),
 (45,'Sentinel many-pointer from abcdefg-zero scans via mem.span; equals seven-byte ordinary slice.', 'Text containing explicit zero preserves it as a scalar; public Text never implicitly scans to zero.', 'Sentinel decay, scanning pointer and pointer-length discovery incompatible.', ['unicode-model'],None,INCOMPATIBLE),
 (46,'Pointer to optional slice updated via bar/baz from null to text ok; string equalityok.', 'A return Text helper can yieldok; this alone does not cover pointer/optional mutation.', 'Optional types, pointer writes, error-union propagation incompatible.', ['text-abc'],None,INCOMPATIBLE),
 (47,'Comptime slice descriptor snapshots: a values[10],b[10,20] after separate len increments.', 'Explicit Bytes.slice copies of sizes1,2 or separate initialized Lists can retain those values.', 'Direct length modification, copied descriptor state and comptime semantics incompatible; mutable Minyar container alias has shared length.', ['byte-slice'],'P1',INCOMPATIBLE),
 (48,'Zero-size struct array field helper foo(0,0).len0.', 'Explicit record with Bytes() field; field.slice(0,0).length0.', 'Undefined struct, [0]usize fixed storage and self pointer excluded.', ['empty-list','byte-empty'],'P6',PENDING),
 (49,'Nested1234 slices equal1234,2,3,4,34.', 'Exactly the same ordinary Text slices with explicit bounds; held view remains valid after reassigning source.', 'Zig byte offsets coincide with scalar ordinals for ASCII only; no mutable view/type coverage.', ['text-abc','view-lifetime'],'P6',PENDING),
 (50,'Undefined []void slice index0 address passed to no-op destroy; no value assertion.', 'No Nothing List or address-of operation.', 'Zero-bit element pointer and undefined storage contract incompatible; no empty-bound safety coverage.', [],None,INCOMPATIBLE),
 (51,'Four sentinel zero-length slice/array variants index0 value2 despite length0.', 'Empty Bytes/Text/List index0 must stop.', 'Sentinel storage readable at zero-length endpoint incompatible.', ['byte-empty','empty-list'],'P6',INCOMPATIBLE),
 (52,'Runtime false peer choice between &[42]u32 and empty struct coerces to[]const u32,length0.', 'Ordinary if assigning an explicitly typed empty Integer List length0.', 'ABI alignment, peer-type inference, empty struct coercion excluded.', ['empty-list'],'P6',PENDING),
 (53,'Sentinel u16 max65535 inferred via @intCast; *const[2:sentinel]u16, endpoint65535,len2,values1,2.', 'Explicit Bytes UInt16 or Integer List can store65535, but no hidden endpoint.', 'Sentinel result-type inference and endpoint access incompatible.', ['byte-slice'],None,INCOMPATIBLE),
 (54,'foo(false,false-text) returns empty; foo(true,true-text) returns true-text.', 'Function(Boolean,Text):Text returning empty or borrowed argument keeps exact content; retain returned Text across caller reassignment.', 'Zig slice ABI, empty-array coercion excluded; Minyar automatic lifetime adds original control.', ['text-abc','view-lifetime'],'P7',PENDING)]
zig_path='test/behavior/slice.zig'
zlines=Path(lookup[zig_path]['evidence_path']).read_text().splitlines()
starts=[(i,re.match(r'test "(.*)" \{',line).group(1)) for i,line in enumerate(zlines,1) if re.match(r'test "(.*)" \{',line)]
add('Z0',zig_path,[11,29],'module comptime type search',
    'indexOfScalar(type,[c_uint,c_ulong,c_ulonglong],c_ulong) unwraps optional index1; otherwise compileError. Legal module-level comptime execution.',
    'An ordinary Integer List search is not type/generic/comptime coverage.',
    'First-class type values, optional result, generic slice parameters, comptime execution and compileError incompatible.', [], 'No runtime port proposed; preserve unsupported type contract.', disposition=INCOMPATIBLE,helpers=[[13,23]])
for (n,outcome,mapping,exclusions,local,proposal,disposition),(start,name) in zip(zig_specs,starts):
    end=next(i for i in range(start+1,len(zlines)+1) if zlines[i-1]=='}')
    u=add('Z'+str(n),zig_path,[start,end],name,outcome+' Every source expectation holds when backend guards permit; phase assertions retained separately.',mapping,exclusions,local,
        'Proposed runtime values/negative endpoint controls are unimplemented. Inspected fixtures cover related values or native lifetime only; none establishes Zig pointer/type/generic/comptime parity.',proposal,disposition)
    u['phases']=[dict(line=i,source=zlines[i-1].strip()) for i in range(start,end+1) if re.search(r'\bcomptime\b|@inComptime',zlines[i-1])]

# Documentary extraction only: preserve each assertion site, helper definition
# and guard after human whole-file review. Counts are source sites, not runs.
def definition_span(lines,start):
    depth=0
    for i in range(start,len(lines)+1):
        line=lines[i-1].split('//',1)[0]
        depth+=line.count('{')-line.count('}')
        if depth==0 and '{' in '\n'.join(lines[start-1:i]): return [start,i]
    raise ValueError('unclosed source definition')

definitions={}
for s in selected:
    lines=Path(s['evidence_path']).read_text().splitlines()
    defs=[]
    for i,line in enumerate(lines,1):
        if re.match(r'\s*(?:func|fn)\s+\w+',line):
            defs.append(dict(name=re.search(r'(?:func|fn)\s+(\w+)',line).group(1),lines=definition_span(lines,i)))
    definitions[s['path']]=defs
for u in units:
    lines=Path(lookup[u['path']]['evidence_path']).read_text().splitlines()
    a,b=u['lines']
    if u['language']=='zig':
        u['helper_spans'] += [d for d in definitions[u['path']] if a<=d['lines'][0]<=b]
        for i in range(a,b+1):
            line=lines[i-1]
            if re.search(r'\b(?:expect(?:EqualSlices|EqualStrings|Equal)?|assert)\(',line):
                u['source_assertion_sites'].append(dict(line=i,kind='expected_true_or_equal',source=line.strip()))
        ext={4:[[75,77]],10:[[167,173]],16:[[238,239]],19:[[285,287]],22:[[323,329]]}
        n=int(u['id'][1:])
        for span in ext.get(n,[]):
            u['helper_spans'].append(span)
            for i in range(span[0],span[1]+1):
                if re.search(r'\b(?:expect|assert)\(',lines[i-1]):
                    u['source_assertion_sites'].append(dict(line=i,kind='attached_helper_expectation',source=lines[i-1].strip()))
        if u['id']=='Z0':
            u['source_assertion_sites'].append(dict(line=28,kind='compile_error_guard',source=lines[27].strip()))
    elif u['path']=='test/string_lit.go' and u['id']!='L0':
        u['source_assertion_sites']=[dict(line=a,lines=[a,b],kind='string_equality',source='\n'.join(lines[a-1:b]).strip())]
    elif u['path']=='test/range.go':
        u['source_assertion_sites']=[dict(line=i,kind='failure_predicate',source=lines[i-1].strip()) for i in range(a,b+1) if re.match(r'\s*if ',lines[i-1])]
        if u['id']=='R25': u['source_assertion_sites'].append(dict(line=466,kind='unreachable_loop_body',source=lines[465].strip()))
    elif u['id']=='S1':
        u['source_assertion_sites']=[dict(line=26,kind='failure_predicate',source=lines[25].strip())]
    elif u['id']=='C6':
        u['source_assertion_sites']=[dict(line=345,kind='attached_verify8',source=lines[344].strip())]

monster = next(u for u in units if u['id']=='Z28')
monster_notes = {
 'testArray': 'Initialized array slice[1..3]: *[2]u8, values2,3.',
 'testArrayZ': 'Sentinel array slices preserve/drop sentinel according to known end: *[2]u8,*[4:0]u8,*[2:4]u8.',
 'testArray0': 'Ordinary empty gives *[0]u8; sentinel empty gives *[0:0]u8 and endpoint0.',
 'testArrayAlign': 'Aligned array offset4 yields *align(4)[1]u8,value5; offset0 length2 keeps alignment4.',
 'testPointer': 'Many-pointer slice[1..3] yields *[2]u8, values2,3.',
 'testPointerZ': 'Sentinel many-pointer slice types *[2]u8 and *[2:4]u8.',
 'testPointer0': 'Pointer to zero-bit u0 yields *const[1]u0 and value0; not a zero-length slice.',
 'testPointerAlign': 'Aligned many-pointer offset4 yields *align(4)[1]u8,value5; aligned length2 type.',
 'testSlice': 'Runtime mutable slice[1..3] with known bounds yields *[2]u8, values2,3.',
 'testSliceZ': 'Known bound gives pointer-to-array types; open tail is *[4:0]u8 in comptime, [:0]u8 at runtime.',
 'testSliceOpt': 'Peer type of optional slice and array pointer is ?[]u8 in both operand orders; unwrap then full slice *[2]u8.',
 'testSliceAlign': 'Aligned slice offset4 yields *align(4)[1]u8,value5; offset0 length2 keeps alignment4.',
 'testConcatStrLiterals': 'Both ordinary and explicit-sentinel literal slice concatenations equal byte sequenceab.',
 'testSliceLength': 'Nested shifted ordinary slice +known lengths yields *[2]u8,*[4]u8,*[2:4]u8.',
 'testSliceLengthZ': 'Nested sentinel source with both implicit/explicit sentinel shift gives *[2]u8 or *[2:4]u8.',
 'testArrayLength': 'Nested ordinary array slices yield *[2]u8,*[4]u8,*[2:4]u8.',
 'testArrayLengthZ': 'Nested sentinel array length4 reaches sentinel: *[4:0]u8; shorter length2 no sentinel or explicit4 sentinel.',
 'testMultiPointer': 'Nested shifted ordinary many-pointer slicing gives *[2]u8,*[4]u8,*[2:4]u8.',
 'testMultiPointerLengthZ': 'Both ordinary and sentinel many-pointer variants assert no implicit length4 sentinel after shifted unsized pointer; explicit length2 sentinel4 retained.',
 'testSingleItemPointer': 'Scalar pointer[0..1] yields *[1]u8,value1; empty[0..0] gives *[0]u8.'}
monster['uncounted_helper_subcases']=[]
for helper in monster['helper_spans']:
    if isinstance(helper,dict) and helper['name'] in monster_notes:
        a,b=helper['lines']
        monster['uncounted_helper_subcases'].append(dict(
            name=helper['name'],lines=helper['lines'],upstream_expected=monster_notes[helper['name']],
            source_assertion_sites=[site for site in monster['source_assertion_sites'] if a<=site['line']<=b],
            minyar_mapping='Only ordinary explicitly initialized values may be projected; no pointer/sentinel/type/comptime contract coverage.',
            disposition=INCOMPATIBLE,counted_separately=False,
            current_local_coverage=monster['current_local_coverage'],
            pending_original_control=monster['proposal']))

proposals=[
 dict(id='P1',name='Copied Bytes versus shared alias and immutable Text retention',design='Initialize Bytes11,22,33,44,55; keep plain alias and snapshot=slice(1,4). Mutate source[1]=99: alias sees99, snapshot[0]22. Mutate snapshot[1]=77: source[2]33. Clear source via alias; snapshot remains22,77,44. Independently retain Text substring of a2048-scalar root, reassign root, verify substring value; do not inspect or assert distinct addresses.',expected='Alias99; snapshot22,77,44; source length0 after clear, snapshot length3. Retained Text equals its original content.',local=['byte-model','byte-slice','view-lifetime'],gap='Native source reads sampled slice then releases it; exact generated copied-slice mutation independence missing from inspected fixtures. Text retention already covered natively; use public generated control only if it adds a demonstrated gap.'),
 dict(id='P2',name='Bounded copy oracle using explicit snapshots',design='Original helper accepts destination/source Bytes and offsets/count, clamps count explicitly to each remaining length, snapshots selected source with Bytes.slice before writes, returns count. Independent expected arrays check untouched prefix/suffix. Cover count0, unequal remaining lengths, exact end, forward/backward shared-input overlap and full self-copy. Explicit original algorithm; no copy intrinsic or view feature added.',expected='For11,22,33,44,55: src[0..4] -> dst[1..5] gives11,11,22,33,44; src[1..5] -> dst[0..4] gives22,33,44,55,55; full self-copy unchanged; count0 preserves all values; clamped count=min(requested,source remaining,destination remaining).',local=['byte-model','byte-self'],gap='Go copy.go covers distinct allocations only. Original overlap helper tests snapshot semantics, not upstream Go copy lowering or unsupported public memmove.'),
 dict(id='P3',name='Interior Unicode scalars distinguish byte positions',design='For aé🙂b assert every Character, length4,byteLength8, slice(1,3)=é🙂 and reconstructed Text equality. Explicit ordinal counter yields0,1,2,3; document Go byte offsets0,1,3,7 without pretending Minyar Text exposes bytes. Also reconstruct aä本☺ from Characters using current Text conversion.',expected='Codes97,233,128578,98; ordinal sum6 versus conceptual byte-offset sum11. For aä本☺:97,228,26412,9786,length4,byteLength9.',local=['unicode','utf-loop','unicode-model'],gap='Go range abcd☺ sum10 does not discriminate offset semantics; current fixtures have Unicode length/index controls but different exact discriminator sequence.'),
 dict(id='P4',name='Once-evaluated loop collection and original growth contrast',design='Three helpers mutate shared Integer state[0] then return List1..5, Bytes1..5 or Textabcd☺; each for evaluates helper once. Independent visit/value counters. Empty variants still invoke helper once then no body effects. Optional List control starts1,2 and appends3 on first element, with bounded guard; doc requires rereading List.length. No Go tuple or blank syntax.',expected='Each helper calls1; List/Bytes sum15,count5; Text sum10180,count5,byteLength7; empty call1/body0. Original growing List visits1,2,3,sum6.',local=['loops','utf-loop','empty-loop'],gap='Inspected local loops have no effectful collection helper count. Upstream does not mutate/grow ranged collections; growth contrast is Minyar-only original control, not a peer match.'),
 dict(id='P5',name='Valid literal content and invalid Character boundaries',design='Use ordinary Text literals and Text(Character) for ä,本,U+10FFFF and controls7,8,12,10,13,9,11,92,34. Construct escape-looking text through backslash Character, not raw/backquoted syntax. Independently reject Character1114112,55296,57343,-1 in isolated original programs; no replacement character success expectation or copied Go diagnostics.',expected='ä length1/bytes2/code228; 本 length1/bytes3/code26412; max length1/bytes4/code1114111. Controls preserve every code in order; trailing-backslash text length7. Invalid scalar construction stops.',local=['scalar-boundary','unicode','unicode-model','invalid-utf8'],gap='Native max/zero scalar roundtrip already exists. Compiler scalar-boundary rejection cases and exact content sequences are not present in inspected fixtures; do not add redundant native tests or unsupported escape spellings.'),
 dict(id='P6',name='Nested and empty slice endpoints with lifetime',design='Runtime Text1234 full slice then nested[1,2],[2,3],[3,4],[2,4] by slice(start,end); preserve nested34 across parent/root rebinding. Test Text empty and Bytes empty slice(0,0); three-byte Bytes.slice(3,3). Separate original failures: Text/Bytes indexlength, empty index0, slice(length,length+1), negative/reversed bounds. No sentinel, writable view or List.slice.',expected='1234,2,3,4,34; retained34. Every legal empty range length0. Endpoint/invalid-range accesses stop; no sentinel zero exposed.',local=['text-abc','view-lifetime','byte-empty','byte-model','unicode-model'],gap='Exact generated nested ASCII and Bytes end-to-end empty slices pending; existing native view lifetime and model slices are related. Reuse existing bounds fixtures if they already assert each proposed negative case.'),
 dict(id='P7',name='Ordinary Text concatenation and conditional borrowed return',design='Join aoeu+asdf, aoeu+aoeu, and both empty orders around slice8..9 of dotted Text. Function(Boolean,Text):Text returns empty or argument; caller reassigns argument after true return, retained result staystrue. Explicit Lists42,56,54 and hello,comma-space,world! assert every element. Runtime only.',expected='aoeuasdf; aoeuaoeu; each empty join result1,length1; false branch empty; true branchtrue surviving caller reassignment; both Lists length3 with exact values.',local=['text-self','text-abc','list-text','view-lifetime'],gap='Related empty/self joins and return/lifetime fixtures exist. Exact peer content inputs and conditional borrowed-return sequence are pending in inspected fixtures; no comptime concat/repeat or pointer coercion claim.')]
for p in proposals: p['status']='proposed_original_existing_syntax_only; unimplemented_unexecuted'

counts=dict(selected_source_entries=len(selected),complete_selected_files_reviewed=len(selected),
    selected_raw_physical_lines=sum(s['lines'] for s in selected),
    go_comparison_groups=sum(u['language']=='go' for u in units),
    zig_named_test_groups=len(starts),zig_module_comptime_groups=1,
    authored_comparison_groups=len(units),dispositions=dict(Counter(u['disposition'] for u in units)),
    go_literal_equality_assertion_groups=len(literal_specs),
    zig_assertion_source_sites=sum(len(u['source_assertion_sites']) for u in units if u['language']=='zig'),
    go_range_failure_predicate_sites=sum(sum(s['kind']=='failure_predicate' for s in u['source_assertion_sites']) for u in units if u['path']=='test/range.go'),
    proposed_regressions=len(proposals),ports_implemented=0,peer_or_local_test_executions=0,
    compilations=0,installations=0,production_build_test_edits=0,commits=0,subagents=0,timing_measurements=0)

snapshots=[]
snap_paths=sorted(set(c['path'] for c in coverage.values())|{'docs/language.md','docs/runtime-memory.md','research/2026-10-memory/README.md','tests/conformance/bytes/expected.stdout','tests/conformance/text-and-lists/expected.stdout'})
for path in snap_paths:
    b=Path(path).read_bytes(); dest=E/('local-'+path.replace('/','-')+'.txt');dest.write_bytes(b)
    snapshots.append(dict(path=path,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),lines=len(b.splitlines()),evidence_path=str(dest),snapshot_utc=STAMP,meaning='source_snapshot_only; no_execution'))

record=dict(schema='minyar.peer_readonly_strings.review.v1',created_utc=STAMP,
    mode='read_only_semantic_review; author_owned_comparison_evidence_only',
    scope={'selected':[{k:s[k] for k in ['language','commit','path','sha256','lines','url']}|{'reviewed_lines':[1,s['lines']],'extent':'whole_file'} for s in selected],
           'support':'Selected assertion-helper bodies reused from pinned round3 sources after exact SHA256 check; support files/tests/transitive utilities not exhaustive and not peer credits.',
           'excluded_previous_reviews':['Go test/utf.go','Go test/stringrange.go','Go test/append.go','Go test/divmod.go','Go test/for.go','Go test/simassign.go','Go test/assign.go','Go test/if.go','Zig test/behavior/array.zig','Zig test/behavior/string_literals.zig'],
           'remaining':'No unread selected-file lines. All ports/proposals pending. Other unselected peer files remain unreviewed; restricted Rust resource excluded.'},
    counts=counts,
    grouping_policy='One Go copy element-family matrix (all length/in/out combinations), full-array control, one Go literal assertion, one Go unasserted syntax initializer, one explicit range semantic group, one Go address test, one Zig named test with ALL nested helpers, and one module comptime unit. Nested assertions/helpers never count as ports or extra units.',
    upstream_outcome_policy='Expected from immutable //run directives, failure predicates and Zig test assertions/guarded helpers only. Never executed. Runtime/comptime clauses and backend skip guards retained as source constraints, not validation coverage.',
    local_coverage_policy='Inspected fixture source/hashes only. Related does not mean exact or passing. Pending denotes absent exact control in this bounded fixture review, not an exhaustive absence claim. Native ABI fixture is not compiler/language syntax coverage.',
    semantic_contract='No new memory syntax, writable view, pointer, generic, sentinel, tuple or conversion API. Text scalar indexing/strict UTF-8 and immutable value behavior, Bytes copied slicing and shared whole-object aliases, List shared reference/fresh loop binding semantics preserved.',
    evidence=str(E/'provenance.json'),local_coverage_references=coverage,
    comparison_groups=units,proposed_original_regressions=proposals,
    read_auxiliary_definitions=definitions,
    selected_file_nonassertion_review={
        'test/copy.go':'Read globals/aliases, all value generators, reset distinct-buffer swaps, count clamp, all bad/verify bodies, nested driver and main. Diagnostic print helpers are not independent semantic units.',
        'test/string_lit.go':'Read global valid/invalid literal initialization and rune/byte conversions, assert diagnostic helper, unasserted concatenation, conversion operands preceding each assertion and os.Exit. All32 equality calls assigned exactly once.',
        'test/range.go':'Read channel generator, all once-call helpers, map/pointer helpers/global counters, and main dispatch of19 test functions. No assertion is inferred for bare declarations; sums are exact source expectations.',
        'test/strcopy.go':'Read unsafe/reflect imports, conversion chain and the sole address failure predicate. Content equality is not asserted.',
        'test/behavior/slice.zig':'Read imports, module comptime search,54 named tests, all nested and standalone helpers, hardcoded pointer globals x/y, all phase/type assertions and backend guards. No prefix-only credit.'})

R.with_suffix('.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
md=['# Read-only Text/Bytes/List peer comparison — round 4','',
    f'Five complete previously unreviewed files, {counts["selected_raw_physical_lines"]} raw physical lines, {counts["authored_comparison_groups"]} explicitly grouped comparisons: {counts["go_comparison_groups"]} Go groups and54 named Zig tests plus one module comptime group. {counts["dispositions"].get(PENDING,0)} pending runtime projections, {counts["dispositions"].get(INCOMPATIBLE,0)} incompatible-as-written groups. Seven original proposals; zero ports, executions, compilations, installations, code/test edits, commits, subagents or timing measurements. Quantities are derived from the saved JSON ledger, not estimates.','',
    'This is a new independent read-only lane. The prior restricted Rust resource was not retried or bypassed; stopped integration/literature/tooling lanes were not resumed. No content/service restriction or upstream unavailability occurred on these accessible official Go/Zig reads. Parent campaign completion remains its responsibility, with earliest completion06:54:29UTC; this record makes no elapsed-time or campaign-completion claim.','',
    '## Scope and immutable provenance','',
    '| File | Commit | Whole-file raw lines | SHA256 | License |','| --- | --- | --- | --- | --- |']
for s in selected:
    md.append(f'| [{s["path"]}]({s["url"]}) | `{s["commit"]}` | 1–{s["lines"]} | `{s["sha256"]}` | {s["license"]} |')
md += ['', 'Complete raw bytes and pinned licenses are retained under `evidence/peer-readonly/strings-round4`. Use one-based physical raw-source line numbers; web rendering collapses blank lines and has different line totals. Supporting std assertions have selective body review only, no library-test credit. Exact source/helper spans, guards, local snapshots, prior record hashes, ownership boundary and documentary checks are in the structured provenance.','',
    'The pre-existing peer inventories mark all five selected files unreviewed. Existing utf.go/stringrange.go/append.go/divmod.go and string_literals.zig are excluded, together with rounds2/3 files. Prior rounds2+3 retain98 grouped comparisons across five files; this round adds no duplicate file credit. Inventories/central campaign records were not edited.','',
    '## Findings and limits','',
    '- Go copy.go swaps two separate input/output arrays. Its copy-up/copy-down comment does not establish same-buffer overlap; no overlap oracle is asserted. Count and prefix/copied/suffix checks span a grouped matrix, not individually executed ports.',
    '- Go range.go abcd☺ byte positions0,1,2,3,4 sum10, which also matches scalar ordinals because the multi-byte scalar is last. P3 places multibyte scalars inside aé🙂b, distinguishing conceptual byte offsets0,1,3,7 from scalar ordinals0,1,2,3.',
    '- Go string_lit.go accepts arbitrary invalid-byte strings, replaces invalid runes/surrogates with U+FFFD and preserves invalid byte roundtrips. Minyar Text rejects invalid UTF-8 and Character accepts only scalars. Binary preservation belongs to Bytes; no Text/Bytes conversion API is invented.',
    '- Go strcopy.go asserts raw address inequality after a substring conversion. Minyar immutable Text may share its backing legitimately; Bytes copied-slice mutation independence is a separate contract. Minyar tiny-view copy guard applies only to sources larger than4KiB, not this2048-byte input.',
    '- Zig writable slice views, descriptor len/ptr mutation, hidden sentinels readable at length, pointer/type/generic/comptime/ABI alignment contracts remain excluded. Ordinary Text/Bytes content projections do not cover them. In particular, Zig zero-length sentinel index0 reads2; Minyar empty index0 must stop.',
    '- Selected Go loops assert once-evaluation for unchanged inputs. They do not establish fixed-versus-live length behavior during growth. Minyar List iteration rereads length; P4 adds an original bounded growth control without claiming peer equivalence.',
    '- Existing native Bytes self-append and Text immutable-view lifetime/consuming-join fixtures are related source coverage. This lane ran none of them and makes no final-source or whole-campaign validation claim.','',
    '## Local fixture references','']
for key,c in coverage.items():
    md.append(f'**{key} — `{c["path"]}` L'+', '.join(f'{a}–{b}' for a,b in c['lines'])+f'.** {c["extent"]} Source only; not run.\n')
md += ['## One-to-one grouped comparisons','',
    'Each row below is an explicit grouped semantic unit with every attached assertion/helper retained in JSON. Upstream outcomes mean expected values inferred from pinned source, never observations. A pending runtime projection preserves only stated ordinary value behavior; listed exclusions remain unsupported. Pure incompatibilities can reference original contrast proposals without changing their disposition.','']
for u in units:
    a,b=u['lines']; label='Pending runtime projection' if u['disposition']==PENDING else 'Incompatible as written'
    md += [f'**{u["id"]} — [{u["path"]}:L{a}–{b}]({u["url"]}) — {u["name"]}. {label}.**','',
        'Upstream: '+u['upstream_expected'],'', 'Minyar: '+u['minyar_mapping'],'',
        'Excluded/incompatible: '+u['incompatible_or_excluded_contract'],'',
        'Inspected local references: '+(', '.join(u['current_local_coverage']) or 'No relevant fixture reference for this unsupported contract')+'. '+u['pending_original_regression_or_gap']+(' Original proposal: '+u['proposal']+'.' if u['proposal'] else ''),'']
    if u['backend_skip_guards']:
        md += ['Backend guard source: '+ '; '.join(f'L{x["line"]}: `{x["source"]}`' for x in u['backend_skip_guards'])+' No backend was run.','']
md += ['## Original regression proposals — all pending','']
for p in proposals:
    md += [f'**{p["id"]} — {p["name"]}.**','',p['design'],'','Expected independently: '+p['expected'],'','Coverage/gap: '+p['gap']+' Related source references: '+', '.join(p['local'])+'.','']
md += ['## Remaining scope and handoff','',
    'All selected-file source review is complete. No selected assertion/helper is knowingly left pending; retained support implementations outside the listed helper spans remain unreviewed and uncounted. Go copy1.go, other range/slice files and other unselected Zig behavior/std text files remain outside this round. Accessible sources were independently read; no unavailable resource needed alternate access.','',
    'All runtime projections and original regressions remain unimplemented/unexecuted. Full upstream compile-time/generic/pointer/capacity/conversion contracts are not covered. Exact local gaps are relative to the inspected snapshots; an implementer should deduplicate against other existing fixtures before adding tests. Parent retains prior98 comparisons plus this ledger’s new group count, with unlike group sizes and no new ports.','',
    'Only `research/2026-10-memory/peer-readonly-strings-round4.md/.json` and `evidence/peer-readonly/strings-round4` were authored. Existing dirty work and concurrent soak/application work were preserved. Parent scope/progress messages were sent using stable round4 request IDs; final handoff uses counts from this saved ledger.']
R.with_suffix('.md').write_text('\n'.join(md)+'\n')

provenance=dict(schema='minyar.peer_readonly_strings.provenance.v1',recorded_utc=STAMP,
    selected_sources_and_licenses=sources,local_initial_snapshot=json.loads((E/'local-initial-snapshot.json').read_text()),
    local_coverage_snapshot=snapshots,workspace_status_snapshot=str(E/'workspace-initial-status.txt'),
    overlap_check='peers.json, peers-inventory.json, peers-review-ledger.json and expanded inventory read/query; all five selected paths listed but no authored reviews; bounded research md/json path search found inventory mentions only. Prior round2/round3 records read including provenance.',
    ag_instruction='User supplied Conventional Commit AGENTS instruction honored; no filesystem AGENTS.md at workspace or /Users/luke/Projects or /Users/luke ancestors. No commits authorized/made.',
    source_retention='Full immutable official source/license bytes retained as .txt; support sources reused only after checking prior pinned hash/provenance. Full local referenced docs/fixtures copied as source-only snapshots. No peer or local executable code executed.',
    line_policy='One-based physical lines of retained raw bytes including blank lines; web renderer totals differ.',
    restrictions='Read-only primary/local docs/tests; only assigned new research/evidence records; no code-copy ports, compiler/tests/installation/build/production edits, commits, subagents, timing or stopped-lane continuation.',
    prohibited_actions_executed=[],content_or_service_restriction_this_round=None,new_unavailable_upstream_resources=[],
    resource_dispositions=[dict(resource='prior restricted Rust URL/resource',status='excluded_not_retried_or_bypassed'),dict(resource='stopped integration/literature and optional tooling execution lanes',status='excluded_not_resumed')],
    support_semantic_limits='Assertion decisions, relevant type equality/scalar comparisons, slice element equality and sentinel span/scan bodies read. Diagnostic formatting, transitive architecture/type utilities and remaining std tests not exhaustive; no support-test credit.',
    parent_checkpoint=dict(parent_thread_id='f1059e32-7dfe-4169-b483-13c846782181',scope_client_request_id='round4-strings-research-scope',progress_client_request_id='round4-strings-research-progress1',delivery='steered'),
    document_checks=str(E/'document-checks.json'),handoff=str(E/'handoff.json'))
(E/'provenance.json').write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(counts,indent=2))
