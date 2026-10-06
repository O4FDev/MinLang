"""Author bounded documentary evidence; never compile or run reviewed programs."""
import collections
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path('/Users/luke/Projects/Minyar-Lang')
BASE = ROOT / 'evidence/peer-readonly/values-round9'
REPORT = ROOT / 'research/2026-10-memory/peer-readonly-values-round9'


def read_json(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def digest(b):
    return hashlib.sha256(b).hexdigest()


sources = read_json(BASE / 'sources.json')
selected = [x for x in sources if x['status'] == 'selected_complete_review']
by_path = {x['path']: x for x in sources}
texts = {x['path']: (ROOT / x['evidence_path']).read_text().splitlines() for x in sources}
refs = read_json(BASE / 'reference-snapshots.json')
by_ref = {x['path']: x for x in refs if 'snapshot' in x}
GCD = 'libcxx/test/std/numerics/numeric.ops/numeric.ops.gcd/gcd.pass.cpp'
MM = 'libcxx/test/std/algorithms/alg.sorting/alg.min.max/minmax.pass.cpp'
ARRAY = 'test/ken/array.go'
SHIFT = 'test/ken/shift.go'
groups = []


def group(id, path, name, spans, disposition, expected, mapping, local, oracle_lines=(), helpers=(), phase='runtime', **extra):
    src = by_path[path]
    a, b = min(x[0] for x in spans), max(x[1] for x in spans)
    item = dict(id=id, language=src['language'], repository=src['repository'], commit=src['commit'],
                path=path, sha256=src['sha256'], name=name, source_spans=spans,
                url=f"https://github.com/{src['repository']}/blob/{src['commit']}/{path}#L{a}-L{b}",
                disposition=disposition, upstream_expected=expected, minyar_mapping=mapping,
                local_coverage_ids=local, oracle_lines=list(oracle_lines), helper_spans=list(helpers),
                phase=phase, backend_guards=[], status='whole_selected_source_semantically_reviewed',
                port_status='not_implemented; not_compiled; not_executed',
                coverage_status='related_fixture_source_only; no_exact_peer_group_already_covered_claim')
    item.update(extra)
    groups.append(item)
    return item


# One group per explicit Cases row, retaining all 18 template-call subcases.
subcalls = []
for line in range(139, 166):
    s = texts[GCD][line - 1]
    m = re.search(r'test0<(.+)>\((.+), TC.expect\)', s)
    if m:
        subcalls.append(dict(line=line, types=m[1], operands=m[2], source=s.strip(),
                             expected='the row expect field, after conversion to Output'))
assert len(subcalls) == 18
for n, line in enumerate(range(31, 43), 1):
    m = re.search(r'\{(\d+), (\d+), (\d+)\}', texts[GCD][line - 1])
    x, y, expected = map(int, m.groups())
    group(f'G{n}', GCD, f'Cases row ({x}, {y}) -> {expected}', [[line, line]], 'adapt_pending',
          f'Every signed/sign-reversed, unsigned, mixed-sign and type-order instantiation of this row expects gcd magnitude {expected}. '
          'Both result-type checks must succeed. 18 test0 call forms per row, across the separately recorded type/phase drivers.',
          'An original Integer Euclidean loop can preserve the bounded magnitudes and all four sign combinations. '
          'Minyar has no gcd builtin, generics, unsigned Integer or constexpr execution; this is an arithmetic value projection, not std::gcd parity.',
          ['number-contract', 'division-model', 'checked-abs'], [51], [[44, 70], [128, 169]],
          phase='runtime_and_constexpr_in_upstream', table_values=[x, y, expected],
          assertion_subcases=subcalls, excluded_contracts=['C++ common_type and integral promotions', 'constexpr', 'std::gcd API'])

# Each paired compile-time/runtime driver is its own type/phase contract group.
driver_pairs = list(zip(range(175, 180), range(181, 186))) + list(zip(range(187, 191), range(192, 196))) + list(zip(range(197, 205), range(206, 214)))
for n, (static, runtime) in enumerate(driver_pairs, 1):
    args = re.search(r'do_test<(.+)>', texts[GCD][static - 1]).group(1)
    group(f'T{n}', GCD, f'do_test<{args}> type/phase driver', [[static, static], [runtime, runtime]],
          'incompatible_as_written',
          'Compile-time static_assert(do_test()) succeeds and runtime assert(do_test(non_cce)) succeeds. '
          'For all 12 rows, each of 18 call forms verifies the expected value and common result type in both operand-type orders. '
          'The unused do_test parameter receives argc in the runtime driver; it does not alter any expected value.',
          'Minyar has one signed Integer and no template/common_type/constexpr contract. G1–G12 separately retain the small mathematical values; '
          'a successful Integer loop cannot satisfy this driver type matrix or its compile-time phase.',
          ['number-contract'], [49, 50, static, runtime], [[44, 53], [128, 169]],
          phase='paired_constexpr_and_runtime', input_template_args=args,
          shared_value_group_ids=[f'G{i}' for i in range(1, 13)],
          phase_guard='file UNSUPPORTED c++03,c++11,c++14 at L9; runtime assert bodies require enabled cassert')

widths = [8, 16, 32, 64, 8, 16, 32, 64]
for n, (line, width) in enumerate(zip(range(222, 230), widths), 1):
    unsigned = n > 4
    typ = f'std::{"u" if unsigned else ""}int{width}_t'
    group(f'F{n}', GCD, f'seeded fuzzy {typ}', [[line, line]], 'incompatible_as_written',
          f'10000 generated pairs in [0, {2**width-1 if unsigned else 2**(width-1)-1}] compare std::gcd with basic_gcd. '
          'mt19937 is seeded 1938. One-byte types use int as distribution result type. '
          'The source supplies no explicit per-pair answer table; an identical seed alone does not establish an identical distribution sequence across implementations.',
          'No Minyar std::gcd, mt19937, distribution API or integral type instantiation exists. '
          'Use explicit independent operands/answers if deriving a new arithmetic regression; do not invent a copied seeded stream or credit 10000 Minyar checks.',
          ['division-model'], [83], [[55, 85]], input_type=typ, phase='runtime_loop; comparison_only_if_assert_enabled',
          input_domain=[0, 2**width-1 if unsigned else 2**(width-1)-1], designed_loop_iterations=10000,
          expected_oracle='recursive Euclidean algorithm after safe signed normalization and unsigned conversion')

for n, (line, width) in enumerate(zip(range(231, 239), widths), 1):
    unsigned = n > 4
    typ = f'std::{"u" if unsigned else ""}int{width}_t'
    minimum = 0 if unsigned else -(2**(width-1))
    maximum = 2**width-1 if unsigned else 2**(width-1)-1
    inputs = [minimum + (0 if unsigned else 3), minimum+1, minimum+2, maximum, maximum-1, maximum-2] + list(range(11)) + [(-i) % (2**width) if unsigned else -i for i in range(1,11)]
    group(f'L{n}', GCD, f'limit Cartesian table {typ}', [[line, line]],
          'incompatible_as_written' if unsigned and width == 64 else 'adapt_pending',
          'Each ordered pair in the 27-entry table must equal the independent basic_gcd helper. '
          'Duplicate entries remain present; design is 27×27=729 comparisons for this invocation. '
          'Signed minimum itself is deliberately excluded because its absolute value is unrepresentable. '
          'Unsigned negative spellings convert modulo the type width, rather than retaining a negative magnitude.',
          ('uint64 maximum and converted negative values exceed Minyar Integer; no lossless whole-domain projection. '
           if unsigned and width == 64 else
           'The listed mathematical values fit Integer. Explicit Integer constants and a new loop may preserve their gcd values, but not C++ widths, unsigned casts, common types or the std::gcd implementation. ')
          + 'No signed-minimum UB case is made into a Minyar success expectation.',
          ['number-contract', 'division-model', 'checked-abs'], [123], [[55, 70], [87, 126]],
          input_type=typ, exact_expanded_input_table=inputs, source_input_entries=list(range(92,119)),
          designed_ordered_pairs=729, expected_oracle='basic_gcd; nonnegative magnitude, gcd(0,0)=0',
          phase='runtime_only_if_assert_enabled')

group('W1', GCD, 'LWG2837 widened signed magnitude', [[215, 220]], 'adapt_pending',
      'gcd(int64(1234), INT32_MIN) yields 2, and result type is int64_t.',
      'Explicit Integer 1234 and -2147483648 preserve result 2 in an original Euclidean loop. '
      'This is within signed 64-bit range and does not validate C++ common_type or a narrower-type abs implementation.',
      ['number-contract', 'division-model', 'checked-abs'], [218, 219], proposal_ids=['P1'])

# Reference identity is the runtime oracle, not merely scalar equality.
mm_cases = [(35, 0, 0, 'x', 'y'), (36, 0, 0, 'y', 'x'), (41, 0, 1, 'x', 'y'),
            (42, 0, 1, 'x', 'y'), (47, 1, 0, 'y', 'x'), (48, 1, 0, 'y', 'x')]
for n, (line, x, y, first, second) in enumerate(mm_cases, 1):
    group(f'M{n}', MM, f'runtime reference selection at L{line}', [[line, line]], 'incompatible_as_written',
          f'In block x={x}, y={y}, returned first aliases {first} and second aliases {second}. '
          'Both pointer-address assertions must succeed. Equal values in M1/M2 specifically select first argument as minimum and second as maximum.',
          'Minyar min/max return scalar values; Integer bindings cannot expose C++ address/reference identity. '
          '0/1 value checks alone would erase the equal-value tie discriminator. P2 deliberately tests scalar snapshots under List mutation, not reference parity.',
          ['finite-extrema', 'list-alias'], [26, 27], [[21, 28]],
          in_block_values={'x': x, 'y': y}, expected_referents={'first': first, 'second': second}, proposal_ids=['P2'])
for n, (span, call) in enumerate([([56, 58], 'std::minmax(x,y)'), ([59, 61], 'std::minmax(y,x)')], 7):
    group(f'M{n}', MM, f'C++14 constexpr value pair {call}', [span], 'adapt_pending',
          'With constexpr static x=1,y=0, p.first equals 0 and p.second equals 1 at compile time. '
          'This branch checks values, not addresses.',
          'Ordinary Integer min(1,0)/max(1,0), and reversed order, preserve 0/1 at runtime. '
          'No Minyar constexpr declaration or standard-library pair API is promised.',
          ['finite-extrema'], list(range(span[0]+1,span[1]+1)), [[54, 55]], phase='constexpr_only',
          phase_guard='TEST_STD_VER>=14 at L50; no configured language mode or execution observed', proposal_ids=['P2'])

group('A0', ARRAY, 'length/capacity conjunction guard', [[59, 63]], 'incompatible_as_written',
      'make([]int,10,100) has length10 and capacity100. Exact guard is len!=10 && cap!=100: '
      'it panics only if BOTH are wrong, so a silent pass alone does not independently assert both properties.',
      'Minyar List exposes length, not Go capacity or zero-initialized make/reslicing. Do not strengthen the peer guard while claiming its oracle is unchanged.',
      ['list-alias'], [60], [[58, 76]])
array_cases = [(69, 0,10,45, 'after [0:100] initialization and [0:10]'),
               (72,5,25,290,'after reslice [5:25] from length10 but capacity100'),
               (75,35,100,4355,'after nested [30:95] from root offset5'),
               (83,0,20,190,'pointer to fixed [20]int'),
               (90,0,40,780,'new fixed [40]int exposed as a slice'),
               (93,5,30,425,'slice [5:30] of the initialized 40-element array'),
               (101,0,80,3160,'stack fixed [80]int exposed as a slice')]
for n, (line, low, high, value, context) in enumerate(array_cases, 1):
    group(f'A{n}', ARRAY, context, [[line,line]], 'adapt_pending',
          f'Helper res expects sum {value}, from half-open original indices [{low},{high}) via (hb-lb)*(hb+lb-1)/2. '
          'Failure prints operands/sum and panics. Mutation in setpd/setpf is visible to callers.',
          'An initialized List<Integer>, indexed helper mutation and an explicit range-sum loop can preserve this arithmetic result. '
          'No public List.slice, capacity extension, fixed-array pointer, Go slice-header/value ABI or implicit zero initialization is mapped. '
          'A3 needs explicit root offset35; replaying slice syntax against Minyar would be invalid.',
          ['list-alias', 'list-bounds', 'existing-row-projection'], [47], [[11,55]],
          original_root_bounds=[low,high], expected_sum=value, driver_call_line={69:132,72:132,75:132,83:133,90:134,93:134,101:135}[line])
for n, (span, write, size, comments, prints) in enumerate([([105,115],113,100,136,[108,112,114]),([118,129],127,80,137,[121,125,128])], 8):
    group(f'A{n}', ARRAY, f'dormant index-at-length fault size{size}', [span], 'adapt_pending',
          f'If called: good and should fault observations precede an index-at-length write ({size}); '
          'bounds failure should prevent bad. The main call is commented out, so these bodies do NOT execute in this selected //run test.',
          'Current List index-at-length failure is related and already has source fixtures for lengths0/2. '
          'An original length80/100 setup could preserve only the invalid-index relation; it would add little beyond those controls. No new redundant regression proposed.',
          ['list-bounds'], [write], phase='dormant_not_called', commented_driver_line=comments,
          print_observation_lines=prints, expected_success_output='no output from this uncalled body')

# Shift: one row for each constant invocation, and one for each dynamic (type,count,direction).
answer_rows = {}
for line in range(101,121):
    m = re.search(r'(ians|uans)\[index\((\d),(\d),(\d)\)\] =\s*(-?\d+)', texts[SHIFT][line-1])
    if m:
        table, t1, t2, t3, answer = m.groups()
        answer_rows[(int(t1),int(t2),int(t3))] = (int(answer),line,table)
constant_lines = [48,49,50,51,53,54,55,56,58,59,60,61]
for n, line in enumerate(constant_lines, 1):
    m = re.search(r'(testi|testu)\(.+, (\d),(\d),(\d)\)', texts[SHIFT][line-1])
    helper,t1,t2,t3=m.groups();key=(int(t1),int(t2),int(t3));value,answer_line,table=answer_rows[key]
    group(f'C{n}', SHIFT, f'constant shift tuple {key}', [[line,line],[answer_line,answer_line]],
          'adopt_pending' if helper=='testi' else 'adapt_pending',
          f'Expected {value} from explicit {table} answer cell. A mismatch prints a diagnostic; helper does not panic or change exit status. '
          'The //run harness compares merged stdout/stderr with expected output, so a diagnostic is observable failure under its empty-output expectation.',
          ('These signed small values and counts0/5 fit the existing Integer shift contract.' if helper=='testi' else
           '5678 and the results fit Integer, so only positive numeric values transfer; Go uint and unsigned shift semantics are omitted.')
          + ' Minyar uses x = x << count rather than unsupported <<= syntax. No compile-time evaluator equivalence is inferred.',
          ['shift-model', 'shift-boundaries'], [18 if helper=='testi' else 32], [[15,36],[95,121]],
          phase='upstream_constant_expression_in_runtime_call', case_tuple=list(key), expected_value=value,
          expression=texts[SHIFT][line-1].strip(), answer_source_line=answer_line)
for n, key in enumerate(sorted(answer_rows),1):
    t1,t2,t3=key;value,line,table=answer_rows[key];count=[0,5,1025][t2];operand=[1234,-1234,5678][t1]
    incompatible=count==1025
    group(f'D{n}', SHIFT, f'dynamic shift tuple {key}', [[68,92],[line,line]],
          'incompatible_as_written' if incompatible else 'adopt_pending' if t1<2 else 'adapt_pending',
          f'Fresh selected operand {operand}, count{count}, operator {"<<" if t3==0 else ">>"}, expected {value} '
          f'from {table}. Nonselected i/u variables also shift each iteration, but only the selected type branch is checked. '
          'Mismatch prints without panic; output harness supplies failure detection.',
          ('Count1025 stops in Minyar; it must not succeed with Go saturation/sign-extension values or be masked to1.' if incompatible else
           'Count0/5 and the explicit value are representable by existing Integer shifts; rewrite switch/compound shifts as ordinary branches/assignments. '
           + ('Go unsigned width/type remains excluded.' if t1==2 else 'No width-dependent overflow is needed for these values.')),
          ['shift-model','shift-boundaries','shift-failures'], [18 if t1<2 else 32], [[15,36],[95,121]],
          phase='runtime_variable', case_tuple=list(key), selected_operand=operand, count=count,
          expected_value=value, answer_source_line=line, operator='<<' if t3==0 else '>>',
          shift_source_line=82 if t3==0 else 83, helper_call_line=86+t1)


def local(id, path, spans, meaning, limit):
    src=by_ref[path]
    return dict(id=id,path=path,snapshot=src['snapshot'],sha256=src['sha256'],bytes=src['bytes'],
                physical_lines=src['physical_lines'],reviewed_spans=spans,meaning=meaning,limit=limit,
                status='source_inspected; no_execution_this_round')


coverage = [
    local('number-contract','docs/language.md',[[14,61],[94,112],[134,174],[230,277]],
          'Signed64 Integer, checked arithmetic, abs/min/max, shift count0..63, ordinary loops; shared List/records.',
          'No unsigned Integer, templates, constexpr, capacity or List.slice API.'),
    local('finite-extrema','tests/conformance/floats-and-bits/program.min',[[24,32]],
          'Small Integer min(3,-2), Float max(1.5,2.5), clamp/abs and elementary bitwise/shift controls.',
          'No C++ reference identity, equal-input extrema snapshot or full signed endpoint ordering.'),
    local('finite-extrema-output','tests/conformance/floats-and-bits/expected.stdout',[[1,36]],
          'Retained exact stdout for conformance values.', 'Expected output source only; no execution here.'),
    local('shift-model','tests/checked-scalars.py',[[12,46]],
          '48 seeded full-width signed values/counts; left shift truncation and arithmetic right independent Python models; abs/clamp.',
          'Source generation exists; exact 1234/-1234/5678 answer table and count1025 are not forced by inspected generation.'),
    local('shift-boundaries','tests/checked-scalars.py',[[95,120]],
          'Count63, signed minimum shifted by0, negative arithmetic right, scalar boundaries.',
          'No Go unsigned contract or oversized-shift success.'),
    local('shift-failures','tests/checked-scalars.py',[[57,93],[122,131]],
          'Both shift operators reject minimum/-1/64/maximum counts with left-to-right prints11,22 and exact diagnostic.',
          'Count1025 is not an explicit fixture in these spans; it is not proposed as a new high-value redundant test.'),
    local('checked-abs','tests/checked-scalars.py',[[165,186]],
          'Signed minimum abs failure and invalid clamp bounds have exact diagnostics.',
          'Rejects signed minimum; does not cover a complete Euclidean composition or import C++ undefined behavior.'),
    local('division-model','tests/peer-research-semantics.py',[[119,133],[161,190]],
          'Signed quotient/remainder compared with a separate sparse-bit subtract model; signed remainder projection.',
          'No gcd loop/test0/common_type or Euclidean fixed expected near-boundary composition in inspected spans.'),
    local('list-alias','tests/conformance/text-and-lists/program.min',[[1,12]],
          'Aliases see additions/index replacements; nested homogeneous values.',
          'No capacity/reslicing/fixed-array zero initialization or root-offset35 sum.'),
    local('list-bounds','tests/list-access.py',[[47,100]],
          'Length0/2 invalid getters/setters, growth during index/RHS, captured receiver replacement.',
          'Different sizes and active standalone traps; does not run Go dormant bodies or assert pointer identity.'),
    local('existing-row-projection','tests/memory-research-peer-projections.py',[[84,101]],
          'Retained shared row versus explicit copy, outer replacement, length/values after dropping owners.',
          'Managed row/reference control; no builtin min/max returned scalar snapshot or Euclidean arithmetic.'),
]
for item in groups:
    item['local_source_coverage']=[dict(coverage_id=c['id'],snapshot=c['snapshot'],sha256=c['sha256'],reviewed_spans=c['reviewed_spans'],meaning=c['meaning'],limit=c['limit']) for c in coverage if c['id'] in item['local_coverage_ids']]

implementation = [
    local('integer-emission','compiler/compiler.min',[[1836,1884]],
          'sdiv/srem share checked division; shift emits checked count then shl/ashr.',
          'Implementation reading only, not a generated-IR or executable observation.'),
    local('extrema-emission','compiler/compiler.min',[[3053,3073],[3100,3112]],
          'Integer extrema use signed compare/select and return scalar operands; Float uses minnum/maxnum.',
          'Integer equality selects right scalar but exposes no address; no Float tie-bit rule proposed.'),
    local('numeric-runtime','runtime/minyar_numbers.h',[[1,31],[201,220]],
          'Overflow/division failures, abs minimum failure and shift count check.',
          'Numeric helper ABI/source only; no runtime execution or platform representation claim.'),
]

helpers = [
    dict(path=GCD, name='test0', reviewed_spans=[[44,53]], meaning='Converts operands, two result-type static assertions, value assertion, returns true; assertion-disabled builds can remove value comparison.'),
    dict(path=GCD, name='basic_gcd_ and basic_gcd', reviewed_spans=[[55,70]], meaning='Recursive n==0 base else m%n; signed negatives normalized except minimum, then convert to unsigned. Selected signed-limit inputs avoid minimum. Unsigned converted negatives remain large positive values.'),
    dict(path=GCD, name='do_fuzzy_tests', reviewed_spans=[[72,85]], meaning='Seed1938, distribution0..type max, one-byte distribution uses int, 10000 model comparisons; no saved stream/answers or actual executions.'),
    dict(path=GCD, name='do_limit_tests', reviewed_spans=[[87,126]], meaning='27 ordered entries, duplicates kept; all729 ordered pairs compared to Euclidean helper; magnitude representability precondition explicitly documented.'),
    dict(path=GCD, name='do_test', reviewed_spans=[[128,169]], meaning='12 table rows,18 call forms each, signed/type-order/unsigned/mixed forms; accumulate &= evaluates each test0 call, does not short-circuit. Dummy int parameter unused.'),
    dict(path=GCD, name='main', reviewed_spans=[[171,241]], meaning='17 paired constexpr/runtime drivers; widened result example; eight fuzzy/eight limit calls; returns0. Runtime drivers wrapped in assert can disappear with NDEBUG; direct fuzzy/limit loops remain but their comparison assert can disappear.'),
    dict(path=MM, name='test', reviewed_spans=[[21,28]], meaning='Two reference-address assertions; equal scalar values cannot discriminate alias selection.'),
    dict(path=MM, name='main', reviewed_spans=[[30,66]], meaning='Six runtime calls, four constexpr value assertions under TEST_STD_VER>=14, returns0; no mutation/lifetime assertion.'),
    dict(path=ARRAY, name='setpd/sumpd/setpf/sumpf/res', reviewed_spans=[[11,55]], meaning='Each helper complete: shared backing stores set index values, sums selected lengths; res compares against arithmetic progression formula and prints/panics on mismatch. Debug print comments inactive.'),
    dict(path=ARRAY, name='scenario bodies and main', reviewed_spans=[[58,138]], meaning='All four active functions and two dormant fault functions fully read; main calls only active functions. Capacity conjunction not strengthened; nested slice root offsets tracked.'),
    dict(path=SHIFT, name='testi/index/testu', reviewed_spans=[[15,36]], meaning='Exact index ((t1*3)+t2)*2+t3; scalar mismatch prints only; no panic/fail/exit.'),
    dict(path=SHIFT, name='main/init', reviewed_spans=[[38,121]], meaning='12 constant calls;18 dynamic selected cases. Nonselected variables also shifted. Initialization writes18 exact answer cells before main; semicolons/formatting retained.'),
]
support = []
for path, spans, meaning in [
    ('libcxx/test/support/test_macros.h',[[88,105]],'TEST_STD_VER derived from __cplusplus unless already defined; C++14 minmax branch guard. No cassert/NDEBUG configuration or library ABI inspected.'),
    ('src/cmd/internal/testdir/testdir_test.go',[[608,615],[657,668],[1016,1054],[1133,1157]],'Command stdout/stderr share one buffer; //run verifies exit and output; missing optional .out means expected empty output, CRLF normalized. Timeout/build mechanisms and transitive tools remain outside review.'),
]:
    src=by_path[path];lines=texts[path]
    covered={i for a,b in spans for i in range(a,b+1)}
    missing=[i for i in range(1,len(lines)+1) if i not in covered]
    complements=[]
    for i in missing:
        if not complements or i!=complements[-1][1]+1:complements.append([i,i])
        else:complements[-1][1]=i
    support.append(dict(**src,reviewed_spans=spans,meaning=meaning,unreviewed_complement=complements,
                        reviewed_span_sha256=[dict(lines=[a,b],sha256=digest(b''.join((ROOT/src['evidence_path']).read_bytes().splitlines(keepends=True)[a-1:b]))) for a,b in spans]))

# Each lexical source oracle occurs once in this index, even if a helper attaches to many groups.
oracle_sites=[]
for src in selected:
    path=src['path']
    for line,text in enumerate(texts[path],1):
        kind=None
        if re.search(r'\bstatic_assert\s*\(',text):kind='static_assert'
        elif re.search(r'\bassert\s*\(',text):kind='assert'
        elif path==ARRAY and line in [47,60]:kind='failure_predicate'
        elif path==ARRAY and line in [113,127]:kind='dormant_bounds_fault_site'
        elif path==SHIFT and line in [18,32]:kind='print_mismatch_predicate'
        if kind:
            attached=[g['id'] for g in groups if g['path']==path and line in g['oracle_lines']]
            assert attached,(path,line,kind)
            oracle_sites.append(dict(path=path,line=line,text=text,kind=kind,group_ids=attached,
                                     failure_semantics='compile-time condition' if kind=='static_assert' else
                                     'assert enabled required; NDEBUG may remove expression' if kind=='assert' else
                                     'prints mismatch without panic; merged-output harness observes it' if kind=='print_mismatch_predicate' else
                                     'not called by main; no active upstream failure execution' if kind=='dormant_bounds_fault_site' else
                                     'prints and panics when exact predicate is true'))

proposals=[
    dict(id='P1',name='Signed Euclidean remainder composition with explicit boundary answers',
         source_group_ids=['G1','G2','G3','G10','L4','W1'],local_coverage_ids=['division-model','checked-abs'],
         gap='Inspected division-model/checked-abs sources cover primitives and traps but not repeated Euclidean remainder with explicit large signed operands and fixed answers. No gcd proposal occurs in retained round2–8 proposal lists. This is a selective gap, not repository-wide absence or exhaustive novelty.',
         excluded_contracts=['std::gcd API','unsigned arithmetic','templates/common_type','constexpr','signed minimum absolute-value success'],
         expected_reasoning='gcd(0,0)=0; zero with ±17 gives17; gcd(±25,±30)=5; consecutive maximum/maximum-1 are coprime; 9223372036854775806 is twice4611686018427387903; -2147483648 and1234 share exactly factor2. All abs inputs are representable; divisor-zero is avoided by the loop guard.',
         proposed_minyar_source='''function euclid(left: Integer, right: Integer): Integer {
    let a = abs(left)
    let b = abs(right)
    while b != 0 {
        let next = a % b
        a = b
        b = next
    }
    return a
}
print(euclid(0, 0))
print(euclid(0, -17))
print(euclid(-17, 0))
print(euclid(25, 30))
print(euclid(-25, 30))
print(euclid(25, -30))
print(euclid(-25, -30))
print(euclid(9223372036854775807, 9223372036854775806))
print(euclid(9223372036854775806, 4611686018427387903))
print(euclid(1234, -2147483648))
print(euclid(-2147483648, 1234))
''', independent_expected_stdout='0\n17\n17\n5\n5\n5\n5\n1\n4611686018427387903\n2\n2\n',
         status='original_proposal; unimplemented_uncompiled_unexecuted',
         validation_handoff='Core owner may first add exact-output regression, preserve any red, then choose its existing source-frozen optimization/profile checks. No defect, speed gain or peer API parity inferred.'),
    dict(id='P2',name='Integer extrema return scalar snapshots across shared List mutation',
         source_group_ids=[f'M{i}' for i in range(1,9)],local_coverage_ids=['finite-extrema','list-alias','existing-row-projection'],
         gap='Inspected conformance checks one small min and one Float max; row projection retains managed rows. No cited fixture returns both Integer extrema then mutates both source slots through an alias and checks the saved scalars across equal/reversed/signed-endpoint inputs. Prior swap/row/wide-record proposals do not perform this extrema composition.',
         excluded_contracts=['C++ pair/reference identity','scalar addresses','constexpr','Float NaN/signed-zero tie policy','implicit copies'],
         expected_reasoning='Equal0 yields0/0; both orders of0/1 yield0/1; either order of signed endpoints yields minimum/maximum. Returned Integer fields retain captured numbers while the shared source and its alias become100/200. Fresh Limits records are explicit; no record equality is used.',
         proposed_minyar_source='''record Limits { low: Integer; high: Integer }
function limits(values: List<Integer>): Limits {
    return Limits { low: min(values[0], values[1]); high: max(values[0], values[1]) }
}
function inspect(first: Integer, second: Integer) {
    let values = [first, second]
    let alias = values
    let saved = limits(values)
    alias[0] = 100
    alias[1] = 200
    print(saved.low)
    print(saved.high)
    print(values[0])
    print(values[1])
}
inspect(0, 0)
inspect(0, 1)
inspect(1, 0)
inspect(-9223372036854775808, 9223372036854775807)
inspect(9223372036854775807, -9223372036854775808)
''', independent_expected_stdout='0\n0\n100\n200\n0\n1\n100\n200\n0\n1\n100\n200\n-9223372036854775808\n9223372036854775807\n100\n200\n-9223372036854775808\n9223372036854775807\n100\n200\n',
         status='original_proposal; unimplemented_uncompiled_unexecuted',
         validation_handoff='Core owner may add exact-output red-first fixture and apply its existing final-source checks. Values do not prove address identity, unique ownership, allocation elimination or speed.')
]

# Union derives only authored selected groups, never screening/helper inventories.
prior=[]
prior_paths=set()
for record in refs:
    name=pathlib.Path(record['path']).name
    if name.startswith('peer-readonly-') and name.endswith('.json'):
        d=read_json(ROOT/record['snapshot']);units=d.get('comparison_groups',d.get('units',[]))
        paths={g['path'] for g in units}
        prior_paths.update(paths)
        prior.append(dict(manifest=record['path'],snapshot=record['snapshot'],sha256=record['sha256'],
                          groups=len(units),selected_paths=sorted(paths)))
central=read_json(ROOT/by_ref['research/2026-10-memory/peers-review-ledger.json']['snapshot'])
central_paths={x['path'] for x in central['reviewed_source_entries']}
assert not {x['path'] for x in selected}&(prior_paths|central_paths)
union=dict(prior_round2_through8_authored_groups=sum(x['groups'] for x in prior),
           prior_deduplicated_selected_complete_files=len(prior_paths),new_groups=len(groups),new_complete_files=len(selected),
           resulting_groups=sum(x['groups'] for x in prior)+len(groups),resulting_deduplicated_complete_files=len(prior_paths)+len(selected),
           meaning='Heterogeneous authored source-selection groups; array prefix/remainder deduplicated as one complete file and round5 retrieval-only candidates credited at round6. Not ports, dynamic assertions, passing tests, language-suite denominator or campaign coverage.')

counts=dict(complete_selected_files_reviewed=len(selected),selected_raw_physical_lines=sum(x['lines'] for x in selected),
            authored_comparison_groups=len(groups),group_dispositions=dict(collections.Counter(g['disposition'] for g in groups)),
            groups_by_file=dict(collections.Counter(g['path'] for g in groups)),
            lexical_oracle_sites=len(oracle_sites),oracle_sites_by_kind=dict(collections.Counter(x['kind'] for x in oracle_sites)),
            gcd_table_rows=12,gcd_table_subcall_source_sites=len(subcalls),gcd_paired_type_phase_drivers=len(driver_pairs),
            gcd_fuzzy_instantiations=8,gcd_limit_instantiations=8,minmax_runtime_reference_calls=6,minmax_constexpr_value_pairs=2,
            go_array_active_sum_calls=7,go_array_dormant_fault_bodies=2,go_shift_constant_call_groups=12,go_shift_dynamic_case_groups=18,
            selected_cpp_phase_guard_sites=2,selected_backend_skip_sites=0,proposed_original_regressions=len(proposals),
            ports_implemented=0,peer_or_local_test_executions=0,compilations=0,installations=0,production_test_build_edits=0,
            central_manifest_edits=0,timing_measurements=0,commits=0,subagents=0)

for src in selected:
    src['read_extent']=[[1,src['lines']]]
    src['read_status']='whole_file_through_EOF_including_helpers_comments_guards_and_dormant_bodies'
    src['selected_unread_lines']=0
    src['url']=f"https://github.com/{src['repository']}/blob/{src['commit']}/{src['path']}"
    src['license_paths']=['LICENSE'] if src['language']=='go' else ['LICENSE.TXT','libcxx/LICENSE.TXT']
    src['test_kind']='compiler_language_run_test' if src['language']=='go' else 'C++_standard_library_test_not_compiler_IR_test'

nonassertion=[
    dict(path=GCD,spans=[[1,48],[52,82],[84,122],[124,174],[180,180],[186,186],[191,191],[196,196],[205,205],[214,217],[220,241]],
         meaning='All header/include/declaration/table/normalization/random/limits/type-driver/return lines read, including complete helper bodies. L9 excludes pre17; both shared helper and parent assert expressions can disappear under NDEBUG. Table constants and signed minimum exclusion retained.'),
    dict(path=MM,spans=[[1,25],[28,56],[59,59],[62,66]],
         meaning='Header, includes, generic reference signature, block-local x/y declarations, all runtime calls, C++14 guard/static storage and return read. No mutation or ownership oracle hidden in driver.'),
    dict(path=ARRAY,spans=[[1,46],[48,59],[61,138]],
         meaning='Comments/directive/importless helpers, formulas, scenario construction/mutation, reslicing and drivers fully read; commented prints and both fault calls do not run.'),
    dict(path=SHIFT,spans=[[1,17],[19,31],[33,121]],
         meaning='Globals, init table, helper indices, pass strings, all constant/dynamic operations and nonselected-variable mutations fully read; print-only predicates are observations checked by harness.'),
]

handoff=dict(source_review_complete=True,selected_unread_lines=0,
             owned_write_boundary=['research/2026-10-memory/peer-readonly-values-round9.md','research/2026-10-memory/peer-readonly-values-round9.json','evidence/peer-readonly/values-round9/'],
             campaign_earliest_completion_utc='2026-10-04T06:54:29Z',campaign_completion_claim=False,
             pending_group_ids=[g['id'] for g in groups if g['disposition'].endswith('_pending')],
             incompatible_group_ids=[g['id'] for g in groups if g['disposition']=='incompatible_as_written'],already_covered_group_ids=[],
             unimplemented_proposal_ids=[x['id'] for x in proposals],selected_report_union=union,
             central_ledgers_untouched=True,restricted_resources_retried=False,
             remaining='Executable work remains with root/core. Other peer files and support complements remain outside review. '
             'No compilation/execution/ports/installation/commits/subagents/timings or production/test/build edits. '
             'Stopped native-model/compiler integration/AFL lanes and restricted Rust, university allocator and Joisha sources were not resumed/retried/bypassed.')

data=dict(schema=1,mode='read_only_peer_source_review',model='GPT-6.1 Sol high',round=9,
          scope='Four complete pinned previously unreviewed value/numeric/collection tests; source outcomes inferred, not observed. Local fixtures bound to frozen snapshots.',
          counts=counts,grouping_policy='One fixed gcd Cases row with all18 subcalls, one paired type/phase driver, one fuzzy/limit instantiation, one widened case; one minmax runtime call or constexpr pair; one Go array predicate/sum/dormant fault; one Go constant/dynamic shift tuple. Shared lexical helpers are indexed once and attached to all relevant groups. These units are heterogeneous and not port counts.',
          outcome_policy='C++ cassert must be enabled; static_assert always represents compile-time checks in supported modes. Go //run checks merged output and exit. Optional .out URLs returned404, supporting empty-output inference but no full tree absence proof. No upstream or Minyar backend ran.',
          local_coverage_policy='Source fixtures inspected at retained hashes and exact spans. Related tests are not exact upstream equivalence; zero already-covered exact peer groups. Selective gaps only, no repository-wide absence or exhaustive novelty.',
          selected_sources=selected,licenses=[x for x in sources if x['status']=='license_read'],
          local_coverage_references=coverage,implementation_reviews=implementation,comparison_groups=groups,
          oracle_source_index=oracle_sites,in_file_helper_reviews=helpers,support_helper_reviews=support,
          selected_file_nonassertion_review=nonassertion,phase_guards=[dict(path=GCD,line=9,kind='lit_unsupported',text=texts[GCD][8]),dict(path=MM,line=50,kind='preprocessor_phase_guard',text=texts[MM][49])],
          proposed_original_regressions=proposals,prior_selection=prior,selected_report_union=union,
          prior_runtime_evidence=read_json(BASE/'prior-runtime-document-checks.json'),
          availability=dict(records=read_json(BASE/'screening.json'),web_observation='web raw Go array display normalized138 physical lines to133. Raw saved bytes/physical lines authoritative. Initial libc++ clamp fetch404; saved failures retained; no service/content restriction.',
                            screened_unselected_complete_file='minmax_comp.pass.cpp: screening only, no credited semantic groups. Comparator/reference contract would largely duplicate minmax selected discriminators.',
                            restricted_resources_not_retried=['prior Rust restricted resource','2010 university allocator source','Joisha publisher'],no_bypass=True),
          documentary_reading_references=refs,handoff=handoff)
save(REPORT.with_suffix('.json'),data)
save(BASE/'handoff.json',handoff)
save(BASE/'provenance.json',dict(selected_sources=selected,licenses=data['licenses'],support_sources=support,
                               local_references=refs,scope='Raw byte hashes; only explicit semantic extents carry review credit.'))

parts=['# Read-only numeric and value peer review — round 9', '',
       f"Reviewed **{counts['complete_selected_files_reviewed']} complete new pinned files**, **{counts['selected_raw_physical_lines']} raw physical lines** and **{len(groups)} heterogeneous groups**. "
       f"Dispositions: **{counts['group_dispositions']['adopt_pending']} adopt pending, {counts['group_dispositions']['adapt_pending']} adapt pending, {counts['group_dispositions']['incompatible_as_written']} incompatible**; zero exact groups credited already covered. "
       'All selected lines through EOF, helpers, phase guards and dormant bodies were read.', '',
       'Two original regression proposals remain unimplemented, uncompiled and unexecuted. No maintained source/test/build edits, compilation, execution, ports, installs, timings, commits, subagents or central-manifest edits occurred. '
       'GPT-6.1 Sol high documentary research only. Root/core owns active executable projections and soak. Campaign earliest completion remains **2026-10-04 06:54:29 UTC**; this report does not claim campaign completion.', '',
       '## Complete selection and immutable evidence', '',
       '| Pinned source | Kind | Complete raw extent | Groups | SHA256 |', '| --- | --- | --- | ---: | --- |']
for src in selected:
    parts.append(f"| [{src['path']}]({src['url']}) | {src['test_kind']} | L1–{src['lines']} | {counts['groups_by_file'][src['path']]} | `{src['sha256']}` |")
parts += ['', 'Pins: Go `56ebf80e57db9f61981fc0636fc6419dc6f68eda`; LLVM `b708aea0bc7127adf4ec643660699c8bcdde1273`. '
          'Swift pin from peers.json was checked (`1ff1cc1170617ab23ab74aa8b741c8daca1903f6`), with no Swift file selected. '
          'No central/prior selected source overlaps. These are compiler-language Go tests and C++ standard-library tests, not LLVM IR optimizer tests.', '',
          'Raw bytes and notices are retained under [upstream evidence](../../evidence/peer-readonly/values-round9/upstream/). '
          '[Provenance](../../evidence/peer-readonly/values-round9/provenance.json) retains URLs, byte hashes, licenses and exact read extents. '
          '[Screening](../../evidence/peer-readonly/values-round9/screening.json) preserves three candidate404 paths and two optional output-sidecar404 paths; no retry followed a retained raw failure. '
          'minmax_comp.pass.cpp is retained as an unselected screening candidate, with no review-group credit. '
          'The web display normalized Go array blank lines (133 displayed versus138 raw physical lines); all attribution uses saved physical bytes.', '',
          '| License | Identification | SHA256 |', '| --- | --- | --- |']
for lic in data['licenses']:
    identification='BSD-3-Clause' if lic['language']=='go' else 'Apache-2.0 WITH LLVM-exception; full legacy/third-party sections also retained'
    parts.append(f"| [{lic['language']}/{lic['path']}](https://github.com/{lic['repository']}/blob/{lic['commit']}/{lic['path']}) | {identification} | `{lic['sha256']}` |")
parts += ['', 'All selected headers and retained full licenses were read. Evidence contains unchanged upstream bytes; no upstream implementation is imported into maintained tests.', '',
          '## Findings and contract boundaries', '',
          'The gcd table supplies12 independent expected magnitudes. Every row has18 signed/type-order/unsigned/mixed call forms. '
          'The17 paired drivers additionally require C++ common result types and compile-time execution; an Integer loop cannot prove those contracts. '
          'The random tests use a separate recursive Euclidean oracle but supply no fixed generated stream or per-pair expected values; no10000-check Minyar credit is claimed. '
          'Limit tests each retain27 input entries including duplicates and729 designed ordered pairs. Signed minimum is excluded by the source representability precondition; unsigned converted negatives remain unsigned magnitudes. '
          'The widened1234/INT32_MIN case fits signed64 and expects2. C++ assertions can be disabled with NDEBUG, including entire runtime do_test calls; no assertion-enabled configuration was run.', '',
          'Runtime minmax asserts addresses. Its equal-zero cases distinguish input identity despite equal values. Minyar min/max return scalar values and expose no scalar address, so these six runtime units are incompatible as written. '
          'The guarded constexpr pairs check0/1 values; those values can be projected at runtime, while the phase remains excluded. No C++ reference lifetime or Minyar allocation-elimination claim follows.', '',
          'Go array uses `len !=10 && cap !=100`; a pass alone does not separately assert both. '
          'It reslices beyond current length using retained capacity. The final nested reslice begins at original root index35, so its independent sum is4355. '
          'Minyar has neither public List.slice nor capacity: initialized Lists and explicit ranges can preserve sums and helper-visible mutation only. '
          'The two bounds-fault bodies are fully read but commented out in main; they are dormant source probes, not executed tests.', '',
          'Go shift helpers print mismatches without panicking. The pinned harness merges stdout/stderr and compares output; missing optional .out means empty expected output. '
          'The optional sidecar URLs returned404, supporting that bounded inference rather than a directory-wide absence proof. '
          'Twelve constant and18 dynamic tuples retain explicit answer cells. Nonselected i/u variables also shift, but only the selected branch is checked. '
          'Counts0/5 and small signed/positive values fit Minyar; count1025 must stop in Minyar, rather than adopting Go oversized-shift saturation/sign extension. '
          'Existing local sources already model full-width valid shifts and invalid counts; no redundant shift proposal is included.', '',
          '## Frozen local source coverage', '',
          '| ID / exact saved span | Source evidence | Limit | SHA256 |', '| --- | --- | --- | --- |']
for c in coverage:
    spans=', '.join(f'L{a}–{b}' for a,b in c['reviewed_spans'])
    parts.append(f"| {c['id']} / {spans} | [{c['path']}](../../{c['snapshot']}) — {c['meaning']} | {c['limit']} | `{c['sha256']}` |")
parts += ['', 'Implementation reads are separate from test coverage:', '']
for c in implementation:
    parts.append(f"- [{c['path']}](../../{c['snapshot']}) {c['reviewed_spans']}, SHA256 `{c['sha256']}`: {c['meaning']} {c['limit']}")
parts += ['', 'All mappings bind to retained bytes. Source reading and expected.stdout files are documentary, not observed pass evidence. '
          'Searches for gcd/min/max were limited to inspected fixtures and prior proposals; no whole-repository coverage or exhaustive novelty is asserted.', '',
          '## Complete per-group ledger', '',
          'The [JSON ledger](peer-readonly-values-round9.json) records every group, exact oracle line/helper span, subcall/limit expansion, source hash and local coverage reference. '
          'The lexical oracle index attributes each source site once and attaches reusable helper sites to every relevant group; template/loop multiplicity is never a port count.', '']
for g in groups:
    spans=', '.join(f'L{a}–{b}' for a,b in g['source_spans'])
    parts += [f"### {g['id']} — {g['name']}", '', f"[{g['path']} {spans}]({g['url']}) — **{g['disposition']}**; phase: {g['phase']}. ", '',
              f"Expected from source: {g['upstream_expected']}", '', f"Minyar: {g['minyar_mapping']}", '',
              f"Oracle source lines: {g['oracle_lines']}; complete helper spans: {g['helper_spans']}; related frozen coverage: {', '.join(g['local_coverage_ids'])}.", '']
parts += ['## Helpers, guards and remaining support extents', '',
          f"Machine-indexed lexical sites: **{counts['lexical_oracle_sites']}**, by kind `{json.dumps(counts['oracle_sites_by_kind'],sort_keys=True)}`. "
          'There are18 gcd test0 subcall source forms, two selected C++ phase guard sites and zero selected backend skips. '
          'No dynamic assertion total or configured backend execution is inferred.', '',
          '| In-file helper/driver | Complete read spans | Meaning |', '| --- | --- | --- |']
for h in helpers:parts.append(f"| {h['path']}::{h['name']} | {h['reviewed_spans']} | {h['meaning']} |")
parts += ['', '| Imported support | Exact reviewed spans | Contract and unreviewed remainder |', '| --- | --- | --- |']
for h in support:parts.append(f"| [{h['path']}](https://github.com/{h['repository']}/blob/{h['commit']}/{h['path']}) | {h['reviewed_spans']} | {h['meaning']} Unreviewed complement: {h['unreviewed_complement']}. |")
parts += ['', 'Platform cassert expansion, actual NDEBUG configuration, <algorithm>/<numeric> implementations, random distribution internals, integral ABI widths, transitive Go tool invocation and other harness sections are outside this semantic audit. '
          'Full-byte support retrieval is not whole-support review. The complete selected nonassertion extents remain explicit in JSON.', '',
          '## Original regressions — proposals only', '']
for p in proposals:
    parts += [f"### {p['id']} — {p['name']}", '', p['gap'], '',
              'Independent expectation: '+p['expected_reasoning'], '', '```minyar',p['proposed_minyar_source'].rstrip(),'```', '',
              'Exact expected stdout:', '', '```text',p['independent_expected_stdout'].rstrip(),'```','',
              'Excluded peer contracts: '+', '.join(p['excluded_contracts'])+'.', '',
              p['validation_handoff']+' Status: '+p['status']+'.','']
parts += ['## Prior evidence and bounded handoff', '',
          'Saved original runtime projections remain separate: run-l5_218bk has eight methods and48 generated executions with24 final O0/24 O2 link flags; '
          'run-1a2ft1yr separately has one wide-record method and6 executions with3 O0/3 O2. '
          'These pre-existing saved results were read, not rerun. No full nine-method final-source matrix or literal peer ports are claimed. '
          'The historical sanitizer optimization correction remains authoritative. [Saved documentary evidence](../../evidence/peer-readonly/values-round9/prior-runtime-document-checks.json).', '',
          f"Prior selected rounds2–8 derive **{union['prior_round2_through8_authored_groups']} groups / {union['prior_deduplicated_selected_complete_files']} complete files**. "
          f"This round gives the selected-report union **{union['resulting_groups']} groups / {union['resulting_deduplicated_complete_files']} complete files**. "
          'The central ledger is a separate earlier manifest and was inspected for overlap, not rewritten. Quantities remain heterogeneous source-review selections, not global/all-peer coverage, ports or passing tests.', '',
          f"**{len(handoff['pending_group_ids'])} adopt/adapt groups** and P1/P2 await root/core executable decisions; **{len(handoff['incompatible_group_ids'])} incompatible groups** stay excluded. "
          'Zero selected lines remain unread. Other peer files, the unselected comparator candidate and exact support complements remain outside credited review. '
          'All new failures are retained; restricted Rust/university-allocator/Joisha sources and stopped compiler/native-model/AFL lanes were not retried, bypassed or resumed. '
          'Only the two round9 reports and values-round9 evidence tree were authored. [Handoff](../../evidence/peer-readonly/values-round9/handoff.json).', '',
          'Documentary hashes/spans/counts/attributions are checked by the retained [document checks](../../evidence/peer-readonly/values-round9/document-checks.json); no test or compilation is run by those checks. '
          'The [evidence index](../../evidence/peer-readonly/values-round9/evidence-index.json) is machine-derived and excludes itself to avoid recursive hashing.', '']
REPORT.with_suffix('.md').write_text('\n'.join(parts))
print(json.dumps(dict(counts=counts,union=union,pending=len(handoff['pending_group_ids'])),indent=2))
