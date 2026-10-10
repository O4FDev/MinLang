# Standalone local cleanup certifier research prototype

**CPU-window hold:** the 126-case validated checkpoint is preserved. A later
127-case self-review run produced 12 failures: missing explicit helper
`may_terminate` fields and a duplicate declaration parameter accepted by the
indexer. The bounded worker completed and all Python workers are idle. Static
repairs have been prepared; their validation and certificate refresh await the
coordinator’s explicit release. The checkpoint evidence below is not a pass for
these later changes.

The validated Python prototype checkpoint infers the archived texture function’s conditional local
cleanup total from its saved LLVM: **V=2, F=2, W=4 after full service**. It parses
and analyses all 13 selected definitions, comprising 225 instructions in 29
blocks. It infers the actual counted-loop bound of two. Caller Bytes protection
remains **required_not_discharged**. This is a static inference under the reviewed
runtime and valid-execution premises; independent implementation review is
pending. The campaign remains active, with earliest finish 06:54:29 UTC.

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
PYTHONDONTWRITEBYTECODE=1 python3 tests/cleanup-certificate-research-run.py review-green
```

The API is `analyze(saved_ir_text, arbitrary_entry_symbol, **context_options)`.
It returns a conditional component certificate or a located rejection with no
numeric work certificate. Profile/catalog/source mismatches and requests for
context or process closure reject. `external_protection` and `outside_debt` are
recorded context requests; they cannot discharge requirements. CLI exit status
is zero for a conditional certificate and one for rejection. This interface has
no compiler integration or product acceptance claim.

The [actual certificate](evidence/local-cleanup-certifier-prototype/actual-certificate.json)
contains input/body digests and spans, exact runtime premises and source hashes,
body-derived effects, finite dataflow observations, loop witness, generations,
producer intervals, ordered chunk slots, frame activation, discovered boundary,
external requirements, assumptions, O1–O8 statuses and nonclaims. The
[machine report](local-cleanup-certifier-prototype.json) and
[control coverage](evidence/local-cleanup-certifier-prototype/control-coverage.json)
derive counts from actual fixture records.

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
are an implementation proof argument awaiting independent review, rather than a
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

The checkpoint [green record](evidence/local-cleanup-certifier-prototype/provenance-green.log)
has **126 passed fixture assertion groups: 20 positive and 106 rejection
cases**, with 113 distinct input hashes. It covers all 29 preregistered record
IDs through 105 expanded cases and adds 21 parser/dataflow/caller cases. Record
IDs, programs, contexts and assertion groups are separate counts. Compound
alternatives have individual rows, including keep protocols, unknown calls with
and without pointers, four owner/service operations, reference classification
and append, both pointer stores, four laundering forms, six loop-effect cases,
nine rank/alias cases, guard/suffix alternatives, getter bounds/layout variants,
profile/catalog/source mismatch, representability, parser limits and malformed
or trailing constructs. Resource-infeasible capacity/work-overflow states are
not manufactured by changing limits; checked arithmetic remains an explicit
implementation argument, with out-of-range literals and actual limits tested.

The actual red-first record has 99 failed expectations against the unimplemented
API. Later retained semantic reds expose accepted wrong-width loads, dropped
wrapper loop requirements, improper guard placement, an exception on nested
types, a hidden write in a returning loop arm, and whitespace-dependent framing.
Two fixture defects are recorded separately: shortening a trailing comment did
not truncate a body, and a signature replacement initially matched twice. Their
corrections changed fixture construction, not independent work expectations.
The original failures and red checker/test snapshots remain in evidence.

Seven separate checker fault families were calibrated against unchanged final
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

Analysis limits remain 8 MiB input, 128 selected definitions, 256 blocks per
definition and 20,000 selected instructions, with 500,000 tokens and 200,000
dataflow iterations as additional safeguards. Exceedance rejects the input and
never emits a partial certificate. Serial final test workers enforce 30 seconds
and 256 MiB RSS. The last green worker observed 8.505 seconds, sampled peak
186,286,080 bytes and measured child peak 192,118,784 bytes, below both limits.
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
[input manifest](evidence/local-cleanup-certifier-prototype/input-manifest.json)
and final evidence hashes enumerate exact paths and identities.

O1/O3/O4/O5 have implemented subset checks and tested controls; their soundness
still needs the fresh independent review. O2/O6 rely on reviewed source summaries
and cost correspondence. O7 requires truthful external representations, a
continuously live outside owner and eventual fair full service. O8 lacks a full
compiler/build/link/optimizer refinement proof. Allocation, scalar arithmetic,
bounds and guard success remain valid-execution premises. No novelty, production
optimization, general memory automation or whole-campaign readiness is claimed;
the generic inference and continuation ideas remain covered by the inherited
prior-art review.
