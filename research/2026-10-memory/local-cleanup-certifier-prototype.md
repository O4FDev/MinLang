# Standalone local cleanup certifier research prototype

**Current-source validation:** all **131 assertion groups pass: 20 positive and
111 rejection cases**, with 118 distinct input hashes. After the coordinator
released the CPU window, the independent reviewer confirmed three false
acceptances on checker `e149d4e6…`: identical branch targets lost the getter’s
bounds condition, numeric SSA spellings `%0`/`%00` were treated as different
identities, and the Float token `1.5` was accepted as a block label. The expanded
red-first gate retained exactly four failing groups before minimal conservative
repairs. Checker `d2607ac5…` now passes those groups and all retained positives.
Independent repaired-source static review and unchanged **5/5 probe replay**
now give [narrow research-only approval](local-cleanup-certifier-implementation-review.md)
of this exact checker/test checkpoint under the stated P/O premises. The earlier
126-case checkpoint and later 127-case/12-failure self-review remain separate
historical evidence.

The current validated Python prototype infers the archived texture function’s conditional local
cleanup total from its saved LLVM: **V=2, F=2, W=4 after full service**. It parses
and analyses all 13 selected definitions, comprising 225 instructions in 29
blocks. It infers the actual counted-loop bound of two. Caller Bytes protection
remains **required_not_discharged**. This is a static inference under the reviewed
runtime and valid-execution premises. This bounded task is complete; the campaign
remains active, with earliest finish 06:54:29 UTC.

The [checker](../../tests/cleanup-certificate-research.py),
[independent fixture expectations](../../tests/cleanup-certificate-research-tests.py),
[bounded serial runner](../../tests/cleanup-certificate-research-run.py), and
[fault controls](../../tests/cleanup-certificate-research-faults.py) are standalone
research files. They use Python’s standard library. Input is never evaluated or
executed. No compiler, runtime, language, native LLVM execution, build,
installation, benchmark, commit, subagent or stopped execution lane was used.
All writes belong to the authorized new tests, this report/JSON and its evidence
directory. Existing design, approval and campaign artifacts are preserved.

Reproduce the inference and test gate from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/cleanup-certificate-research.py \
  research/2026-10-memory/evidence/local-cleanup-certifier-design/inputs/application/application.ll \
  .minyar.fn.minyar_module_1_snow
PYTHONDONTWRITEBYTECODE=1 python3 tests/cleanup-certificate-research-run.py reproduce-current-green
```

The API is `analyze(saved_ir_text, arbitrary_entry_symbol, **context_options)`.
It returns a conditional component certificate or a located rejection with no
numeric work certificate. Profile/catalog/source mismatches and requests for
context or process closure reject. `external_protection` and `outside_debt` are
recorded context requests; they cannot discharge requirements. CLI exit status
is zero for a conditional certificate and one for rejection. This interface has
no compiler integration or product acceptance claim.

The [current certificate](evidence/local-cleanup-certifier-prototype/actual-certificate-current.json)
contains input/body digests and spans, exact runtime premises and source hashes,
body-derived effects, finite dataflow observations, loop witness, generations,
producer intervals, ordered chunk slots, frame activation, discovered boundary,
external requirements, assumptions, O1–O8 statuses and nonclaims. The
[machine report](local-cleanup-certifier-prototype.json) and
[current control coverage](evidence/local-cleanup-certifier-prototype/control-coverage-current.json)
derive counts from actual fixture records.
The historical certificate remains at `actual-certificate.json`; it does not
validate the current source. The fresh CLI capture has separate raw output,
source provenance and a bounded resource gate.

| Inferred case | Owner visits V | Finalizers F | Full-service W | Active chunk occupancies |
| --- | ---: | ---: | ---: | --- |
| Archived real function | 2 | 2 | 4 | [2] |
| Independent three owners | 3 | 2 | 5 | [3] |
| Independent eight owners | 8 | 2 | 10 | [8] |
| Independent nine owners | 9 | 3 | 12 | [8, 1] |
| Independent zero owners | 0 | 1 | 1 | [] |

For the archived case, constructor/keep intervals are IR1044→1048 and
IR1049→1054. The inferred lengths/capacities are 3/4 and 2/2. Before IR1057, each
generation has one token in an active, unqueued chunk; the heap activation has
zero written locals. Scalar backing and elements contribute no extra managed
visits under P6. The algorithm computes W from occupancy, chunk count and one
activation; it contains no archived answer, application whitelist or application
hash acceptance rule. Renaming, comments, spacing, a single-line layout, changed
payloads/lengths and a new owner are tested. The expected-derivation file is never
read by the checker.

The lexer preserves byte locations in the ASCII saved dialect. Module indexing
balances all definition bodies, indexes signatures and opaque unreferenced
globals, and rejects aliases and catalog-symbol shadow definitions. Every
selected instruction is parsed with complete operands and types. Resolution
checks direct calls, signatures, duplicates, SSA dominance, targets and
terminators. Recursive application call graphs and unknown zero-argument calls
reject. Unselected bodies have framing and signatures checked; their instruction
semantics are outside this analysis.

Borrower analysis derives singleton pointer provenance, ScalarList/Bytes roles,
reads/writes/protection requirements and guard effects from every selected body.
It substitutes roles and loop obligations through calls, including a wrapper
that swaps parameter order. Private cells use a finite forward fixed point:
initialization joins by intersection, differing scalar tags become OtherScalar,
and incoming guard depths must agree. Final facts validate loads and returns.
Effects are conservatively unioned over every syntactically reachable block;
constant conditions do not remove an effect. Pointer conversions, aliases,
stores, returns, lens/cell escapes and unsupported effects reject. Getter slot
loads require exact layout/width, the same List generation, immutable backing
and a dominating true unsigned index-versus-Length edge.

The K witness is structural, rather than an unrolling or scalar-value solver.
Dominators identify exactly one header/latch backedge; removing it must leave an
acyclic graph. There is one preheader, a counter initialized to zero, a separate
immutable Length cell, an exact signed header comparison and a sole unit latch
increment/store. All writes to the counter/limit are counted across the whole
body. Private index copies have one permitted store. The header true edge
dominates the cycle. Both continuing blocks and returning arms are checked for
read-only effects; the actual scalar-return guard leave is allowed immediately
before return. Nested loop calls are conservatively rejected in an iteration.

Under `0 <= limit <= LLONG_MAX-1`, initialization establishes
`0 <= counter <= limit`. The only continuing backedge increments once after
`counter < limit`, stays representable and decreases `limit-counter` by one.
Every other path exits through an acyclic returning tail. Normal returns balance
the guard, and callees preserve the current ownership frame and List backing.
The root discharges this loop requirement using its sealed fresh List length
two. An external List bound would remain a caller requirement. These statements
are an independently inspected implementation proof argument, rather than a
mechanized LLVM/C proof or a proof inferred from tests alone.

For ownership, successful construction creates one fresh producer token. Scalar
append changes checked length/capacity without adding an edge. Keep consumes
that producer once and publishes it in an active eight-slot chunk. The eighth
owner leaves a full active chunk; the ninth creates a second chunk before its
publication. Freshness and producer/active-chunk protection prevent prefix
service from consuming this component, under the frozen summaries. The terminal
typed suffix `rc_step?; rc_leave; stack_leave; ret void` supplies the boundary.
No earlier local service or later use is accepted. Detachment and retirement
conserve the initial V+F tickets, while automatic service consumes an unknown
subset. Thus W is the component-attributed total including any suffix service
and eventual later service; it gives no exact remaining-at-return or process
poll count, and supplies no byte/admission/deadline conclusion.

A proposed narrowing was recorded before green acceptance in
[proposed-narrowing.json](evidence/local-cleanup-certifier-prototype/proposed-narrowing.json):
all unreachable selected blocks reject, including harmless detached code. The
design allowed classification of some such blocks. The actual archived module
also contains unselected native `zeroext` declarations; indexing retains their
signature details without supplying effects. Selected grammar was not widened
to make the positive pass. Other conservative constraints include signed i64
literals, entry-only guard enter, immediately-pre-return guard leave, exact
canonical loop blocks, and rejection of nested loop calls in an iteration.

The later [review repair narrowing](evidence/local-cleanup-certifier-prototype/review-subset-narrowing.json)
was recorded before acceptance: identical conditional successor labels reject
during CFG validation, numeric identifiers are excluded from the saved named
dialect, and selected block labels must satisfy the unquoted named grammar.
Some valid LLVM with parallel branch edges or unnamed numeric identifiers is
therefore outside this subset. The repaired checker keeps the existing CFG
representation and makes no broader LLVM verifier claim. The reviewer’s exact
executed inputs and hashes are copied separately; preliminary numeric/label
fixture hashes are distinguished from the corrected executed versions.

The [current green record](evidence/local-cleanup-certifier-prototype/independent-review-current-green.log)
has **131 passed fixture assertion groups: 20 positive and 111 rejection
cases**, with 118 distinct input hashes. It covers all 29 preregistered record
IDs through 110 expanded cases and adds 21 parser/dataflow/caller cases. Record
IDs, programs, contexts and assertion groups are separate counts. Compound
alternatives have individual rows, including keep protocols, unknown calls with
and without pointers, four owner/service operations, reference classification
and append, both pointer stores, four laundering forms, six loop-effect cases,
nine rank/alias cases, guard/suffix alternatives, getter bounds/layout variants,
profile/catalog/source mismatch, representability, parser limits and malformed
or trailing constructs. Resource-infeasible capacity/work-overflow states are
not manufactured by changing limits; checked arithmetic remains an explicit
implementation argument, with out-of-range literals and actual limits tested.

The original red-first record has 99 failed expectations against the unimplemented
API. Later retained semantic reds expose accepted wrong-width loads, dropped
wrapper loop requirements, improper guard placement, an exception on nested
types, a hidden write in a returning loop arm, and whitespace-dependent framing.
Two fixture defects are recorded separately: shortening a trailing comment did
not truncate a body, and a signature replacement initially matched twice. Their
corrections changed fixture construction, not independent work expectations.
The original failures and red checker/test snapshots remain in evidence.
The later 127-case self-review had 115 passes and 12 failures for explicit
`may_terminate` metadata and a duplicate named declaration parameter. Its static
repairs pass in the expanded 131-case red run; that run independently exposes
both direct/trampoline bounds failures and the two parser failures. The
[validation history](evidence/local-cleanup-certifier-prototype/validation-history-current.json)
retains the distinct gate commands, source hashes, counts, resource observations,
fixture corrections and interrupted coordinator history.

Seven separate checker fault families were calibrated against unchanged checkpoint
expectations. Each intended semantic target fails, not merely an internal
serialization assertion: assumed application purity accepts a poisoned callee;
duplicate transfer accepts double keep; ignored backedge effects accept a latch
detachment; omitted finalizers produce eight rather than ten; element charging
produces twelve rather than four; poll subtraction produces zero rather than
four; and original-name bypass accepts premature local service. The
[final fault records](evidence/local-cleanup-certifier-prototype/fault-calibrations.json)
retain mutations, source hashes, targets, logs and resource gates. An earlier
aggregate coordinator was interrupted and its incomplete fifth worker preserved;
subsequent calibration uses one bounded invocation per fault. The aggregate
coordinator’s total duration was not instrumented, so no 30-second compliance
claim is made for that interrupted orchestration attempt.

The [current affected calibrations](evidence/local-cleanup-certifier-prototype/fault-calibrations-current.json)
rerun only the aligned purity family and add three separate mutants disabling
the new parser checks. The poisoned-callee target and each new rejection target
falsely certify under their intended mutant, with unchanged 131-case semantic
expectations. All four calibrate within the original worker limits; the six
unchanged historical families were not rerun. The inherited harness initially
reused the historical purity mutant path; the executed current bytes were
retained separately and the old matching snapshot restored. The
[path retention record](evidence/local-cleanup-certifier-prototype/fault-path-retention.json)
preserves actual argv and digest identities. Future fault outputs use a separate
directory for each label prefix.

Analysis limits remain 8 MiB input, 128 selected definitions, 256 blocks per
definition and 20,000 selected instructions, with 500,000 tokens and 200,000
dataflow iterations as additional safeguards. Exceedance rejects the input and
never emits a partial certificate. Serial final test workers enforce 30 seconds
and 256 MiB RSS. The current green worker observed 9.183 seconds, sampled peak
181,911,552 bytes and measured child peak 185,663,488 bytes, below both limits.
The checkpoint fault workers also stayed below both limits. RSS sampling has gaps;
the exit-time child peak supplements samples and includes the runner’s small
`ps` children. These are resource observations under shared host conditions,
not performance measurements or a universal analyser resource theorem.

Actual `build`, `drawTile` and `main` contexts reject with located reasons:
pointer return at IR4152, unsupported instruction at IR1551 and unsupported
value at IR6638 respectively. The preserved
[unsupported corpus record](evidence/local-cleanup-certifier-prototype/unsupported-corpus.json)
reports those exclusions. The manual archived caller witness from the design
review does not discharge the certificate’s Bytes requirement. An unprotected
context cannot acquire a context-closed conclusion; arbitrary outside debt
leaves the conditional full-service component total intact.

Provenance is pinned to IR `b7e797c2…`, reviewed catalog `f9c729a5…`, and the
six frozen runtime source hashes including C `c4e78f59…`. The checker compares
frozen bytes with embedded approved hashes, rather than mutable review contents
or live production. Historical compiler/source/object identities remain
documentary provenance, with no new compilation or binary execution. Tests
check independently computed input and selected-body digests. The
[checkpoint input manifest](evidence/local-cleanup-certifier-prototype/input-manifest.json)
preserves historical identities. The
[current manifest](evidence/local-cleanup-certifier-prototype/input-manifest-current.json)
and current source handoff distinguish checker `d2607ac5…`, tests `74ca4a33…`,
unchanged runner `f269c931…`, and fault harness `3aa396d9…`; exact full hashes
are recorded in JSON. Frozen C `c4e78f59…` and collections `01ae1e88…` remain
unchanged premises; no live production changes are silently adopted.

The [final review disposition](evidence/local-cleanup-certifier-prototype/final-review-disposition.json)
pins reviewer Markdown SHA `720e14a4…` and JSON SHA `98cc20c5…`, inspected checker
`d2607ac5…` and unchanged five-input replay. Its narrow approval resolves the
three immediate implementation blockers. The raw certificate was captured
before that approval; its generic O3 “review pending” string is preserved as
capture-time output, with the later disposition recorded separately.

O1/O3/O4/O5 have implemented subset checks, tested controls and independent static
approval under the stated premises; no mechanized proof follows. O2/O6 rely on reviewed source summaries
and cost correspondence. O7 requires truthful external representations, a
continuously live outside owner and eventual fair full service. O8 lacks a full
compiler/build/link/optimizer refinement proof. Allocation, scalar arithmetic,
bounds and guard success remain valid-execution premises. No novelty, production
optimization, general memory automation or whole-campaign readiness is claimed;
the generic inference and continuation ideas remain covered by the inherited
prior-art review.
