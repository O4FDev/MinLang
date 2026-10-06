# Independent runtime transformation review

This lane is a new independent GPT-6.1 Sol high static review. It owns this
document, its JSON companion and `evidence/runtime-transformation-review/` only.
Source/evidence reading, SHA-256 verification and mathematical reasoning are the
entire method. No tests, compilers, native models, installations, commits,
subagents or timing observations were run. No production, test or build files
were changed. The active source-frozen core cohorts and separate paired CPU job
remain outside this lane. This is no campaign-completion claim; the campaign's
earliest completion remains 2026-10-04 06:54:29 UTC.

## First delivery: aggregate Text ASCII propagation

**Disposition: conditional static approval of the exact isolated patch; keep it
UNAPPLIED.** I found no semantic or allocation/service-order blocker for supported
well-formed Text objects. At first delivery, no-query CPU cost was unresolved;
the subsequently available saved timing archive is reviewed below. The coordinator
must retain the source freeze through both active core cohorts (approximately
05:44 UTC in the brief) and arrange the appropriate final integration checks
before production acceptance. Neither
elapsed time nor this static approval authorizes application during the freeze.

### Exact identity and evidence

All 22 entries in baseline `run-soga_9x2/archive-index.json` and all 23 entries in
candidate `run-i0thmm8l/archive-index.json` were independently rehashed; every
entry matched. Comparing their instrumented runtime files produces exactly the
same three substantive hunks as `candidate.patch`: local boolean, certificate
comparison in the sizing pass, conditional result count. The pristine candidate
archive runtime is byte-identical to the currently frozen production runtime,
so the patch is demonstrably unapplied at this reading checkpoint.

| Artifact | SHA-256 |
| --- | --- |
| Candidate patch | `87b8c3a0ec59b2b9bb526ef4f1a60d6f3c2e82c00788690780d77c922e72390a` |
| Pristine/frozen `minyar_runtime.c` | `c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4` |
| Baseline instrumented runtime | `b0066034c1d780d0d07536ad940182d0e9069b7bd17a3fbcd574cf4d4fc3b3e4` |
| Candidate instrumented runtime | `2d091b9fea993260862cf7470f0c58cd03658905eb9129d37611ac9590df1b83` |
| Common instrumented ownership fragment | `2f5a1ab0e31fac30babbb005cfcf786c54f834e304767ba94be2197d30a61fc8` |
| Baseline saved results | `57c7b4b98e808e8ed9977d5bf2c2e21ef7f48b113de4f1b1a55d0786a777e755` |
| Candidate saved results | `7e8edda6ed46c2d9a7e2cc0746be65c6016a85608554f9cd1062225e822d7b44` |
| Recorded compiler executable identity | `995dd6e61def8f84cd9a8d3419156621b6a5e2a772b26723149ae6bd8a2ad190` |

The compiler executable hash is inherited from the saved results, not a newly
executed or reconstructed compiler. The archived tests/patches and other source
identities are in the original manifests and the companion review register.
The declared compiler call-pattern source, `compiler/compiler.min`, rehashes to
`994d457a3728806942541df5f567e332a6594ea508c3bc61cc2d4ac5c485eadc`.
Its escaped-literal fragments at lines 280–338 call aggregate join at line 333.
That source reading supports the projection; it supplies no full compiler timing.

The retained red, `run-0e5yjkpm/results.json`, records normal exit/output followed
by `Certified ASCII aggregate still requires a cold scan`. This is an
avoidable-scan requirement failure, not a UTF-8 or ownership defect. Both final
variants record 18 generated controls and eight native controls/traps: six
successful debt cases and two expected error exits. Generated configurations
are system/K32 O2, compiler-arena O2, and C ASan+UBSan with generated ASan O1.
The 13 generated ASan definitions, disabled leak checking, and absence of
generated UBSan claims remain explicit (`tests/memory-research-aggregate-join.py`
in the candidate archive, lines 187–207).

### Representation lemma and preservation audit

For a **Text**, let `b >= 0` be byte length, `c` character length, `o` offsets and
`p[0..b)` the initialized immutable byte range. The supported states are:

* `c = -1, o = NULL`: unknown, possibly malformed, validated lazily on character
  operations. Unknown is not an ASCII certificate even when the bytes happen to
  be ASCII or the length is zero.
* `c = b, o = NULL`: certified ASCII, every visible byte below 128, including NUL;
  empty Text has the vacuous certificate.
* `0 <= c < b, o != NULL`: validated UTF-8, exact scalar count, valid breadcrumb
  index/cursor belonging to this header and byte range.

Valid UTF-8 contains scalars of widths 1–4; width one is exactly ASCII. Thus
`c = b` in a truthful known-count state implies all widths are one. The predicate
does **not** validate arbitrary memory or a forged count. `new_text` merely
initializes fields (pristine `runtime/minyar_runtime.c:304–312`); its callers
must establish the invariant.

| Constructor or mutation | Preservation argument and pristine source lines |
| --- | --- |
| Generated literals | Self-hosted emitter asks `literal.length == literal.byteLength` before emitting a certified constant; other literals have `-1` and null offsets (`compiler/compiler.min:4539–4567`). Stage zero emits only unknown counts (`bootstrap/stage0.c:1853–1862`); its compiler-arena/bootstrap representation is not an ordinary runtime ABI proof. |
| External/C/Boolean/argument/file Text | `copy_c_text` uses `-1` (349–354); Boolean delegates to it (945–946); platform arguments remain unknown even after Windows conversion (978–994); file reads remain unknown (1019–1044). Malformed input is therefore not certified by construction. |
| Integer and Float formatting | Integer bytes are digits and optional minus, with count equal to byte length (840–858). Float output is ASCII punctuation/digits/special strings (`minyar_numbers.h:77–169,179–184`). Integer cache changes ownership, not bytes/count (867–882). |
| Character cache and encoding | All 128 cached values, including zero, write one ASCII byte with count one (924–942). Other Unicode scalars encode to 2–4 bytes and start unknown (885–921); invalid scalars trap before construction. |
| Lazy index construction | The high-bit scan and decoder validate the full visible range. Equality returns ASCII without allocating offsets; non-ASCII installs the index and exact count (610–674). The decoder rejects overlong, surrogate, truncated and out-of-range encodings (556–584). |
| Ordinary copied binary joins | Both certificates are required; otherwise the output stays unknown (449–459). No index pointer is inherited. |
| Consuming binary join | Unique owner/non-view check protects aliases. Growth uses saved lengths, including self RHS; old offsets are freed, and a known count survives only if both old counts equal their saved byte lengths (484–522). Non-ASCII becomes unknown. |
| Ordinary slices/views | Index validation and scalar endpoints establish exact byte/scalar extents. Partial copy/view gets a known count only when the two extents are equal; views retain a flattened root. Full-range slice retains the original header (772–835). Root retention precludes unique-root mutation while views survive. |
| Arena slices and joins | Arena extension preserves the original visible byte range and returns conservative unknown metadata (462–477). Slices of indexed Unicode remain unknown even when their bytes are ASCII (785–810). Cache hits compare exact bytes, so a previously established certificate remains valid; no forced recertification is required. Arena storage survives cache eviction and ownership hooks are no-ops (`minyar_rc.h:15–25`). |
| Aggregate candidate | Sizing-pass conjunction of already valid certificates implies concatenated ASCII. Sum uses the unchanged overflow check; `new_text` supplies null offsets/backing and exact summed count. Any uncertified fragment preserves `-1` (`candidate.patch`, pristine anchor 526–545). |

`MinyarBytes` deliberately reuses the layout with **capacity**, not a character
certificate, in `character_length` (`minyar_bytes.h:3–11,41–48,55–88`). The lemma
therefore quantifies over typed Text, not every object with the leaf RC kind.
Passing arbitrary Bytes as Text or native-forged/mutated metadata violates the
preexisting typed/native contract. The candidate introduces no new ABI field or
runtime kind capable of enforcing that boundary. This is an explicit premise,
not an assertion that the equality predicate makes unchecked native input safe.

### Edge cases and observable work

The saved rows below hold in all three generated configurations. Baseline cold
builds are one except no-query; candidate cold builds are as shown. Warm builds
are zero throughout.

| Control | Fragments / output bytes | Uncertified ordinary / arena | Candidate cold builds / scan bytes |
| --- | --- | --- | --- |
| Known ASCII | 5 / 15 | 0 / 0 | 0 / 0 |
| Unicode (accent/nonBMP) | 5 / 12 | 3 / 4 | 1 / 12 |
| Persistent unknown ASCII | 6 / 19 | 1 / 1 | 1 / 19 |
| No-query ASCII | 5 / 15 | 0 / 0 | 0 / 0 |
| Empty parts List | 0 / 0 | 0 / 0 | 0 / 0 |
| Single known ASCII | 1 / 3 | 0 / 0 | 0 / 0 |

Empty parts keep the allocation of a one-byte terminator and a fresh Text;
only a zero-input cold build disappears. Single known ASCII still copies and
creates a fresh result, preserving identity/ownership behavior. A single
unknown/Unicode fragment would remain unknown by the conjunction rule; that
specific generated shape is source-derived, not another recorded execution.
An unknown empty fragment also keeps the conservative sentinel. With one native
`0xff` fragment, both variants record null offsets and count `-1`, construct the
result, then trap on query with exit 1 and `Text contained invalid UTF-8.` in both
native and sanitizer configurations. Normal-exit recovery is not claimed for
those traps (archived C fixture:82–125,170–192).

The generated alias control retains `sourceAlias`, appends `!` to the source,
and checks both the result and original source alias against the independent
Python escape decoder (`.min:29–35,53–62`; `.py:209–211`). The candidate never
mutates a fragment/header/index, retains the same copying pass, and reads its
certificate before either allocation hook. Single-mutator, non-reentrant service
cannot mutate a live protected fragment between sizing and copying. The saved
alias case is concrete coverage, not every ownership-lowering proof.

I independently compared the saved observation arrays (not merely the report's
pass string): all 18 configuration/mode pairs, every recorded phase including
final, and all eight native pairs have identical ordered `events`, object/data
request counts, payload sizes, hook counts, offered and actual queued units.
There is no timing observation in this comparison.

The public function orders **data request/service → fragment copies → Text
header request/service**, not header first (`minyar_runtime.c:538–545`;
`minyar_rc.h:109–131`). Data payload is `b+1`; actual ordinary requests include
eight-byte RcData and RcObject prefixes, then allocator rounding. A Text payload
is 40 bytes, so its ordinary header request is 48 bytes. The generated statement
adds a third hook: 3×K32 offered, zero executed queued units. Arena hooks are
absent. Native debt controls isolate the two allocation hooks: object/frame
counts stay 1 while each hook executes 32 units; chunk counts are 13→10→6.
Equal cardinality is not equal remaining work or retained bytes. These are
system-allocator debt controls, not a recorded fixed/lazy admission matrix.

The removed ASCII build itself allocates no offsets and invokes no managed
allocation service (`minyar_runtime.c:634–636`); after it, baseline and candidate
have the same count/null-index representation. Consequently the added metadata
load/conjunction and omitted scan do not alter the abstract allocation/service
sequence under the stated invariant. Unknown/Unicode still run the same lazy
validation/index allocation. This local argument complements the saved traces;
the traces alone cannot certify every possible debt state.

**Approval conditions and limits.** Retain exactly this patch and source
identity, truthful typed Text metadata, protection of live operands, and the
existing overflow/error/copy/allocation order. Keep unknown/malformed cases lazy
and arena proof states conservative. Preserve the avoidable-scan red as count
evidence. Do not infer CPU benefit from a 15-byte scan becoming five predicates:
the unknown case adds six predicates and still scans 19 bytes; no-query adds five
predicates without saving a later scan. The separate paired CPU job must resolve
those costs under its own protocol; its now-available evidence is assessed below.
Final integration and any additional
allocator/profile coverage are coordinator-owned, after the freeze, and are not
reported as done by this review.

### Subsequent saved timing review

The timing archive became available during this review. I read the actual
`evidence/runtime-aggregate-timing/run-rrkuiyad/results.json`, its archived
preregistration, C observer, generated-source fixture and complete Python runner.
All 37 archive entries independently rehash correctly. Results SHA-256 is
`d1000f83b4ce9789e287e5a217266feac7f426e9ad519724ee5e42074c7f8523`.
The uninstrumented candidate runtime is
`d919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51`;
its actual diff from the frozen baseline is exactly the previously reviewed
patch `87b8c3a0ec59b2b9bb526ef4f1a60d6f3c2e82c00788690780d77c922e72390a`.

The raw result has 139 successful process records: toolchain/compiler/two links,
five pilots, ten warmups and 120 paired processes. Each mode has blocks 0–11
once, two warmups and its retained calibration row. I independently recalculated
each geometric mean from the twelve raw CPU ratios; all five exactly match the
saved means. I read the bootstrap implementation (archived `.py:25–33`) but did
not execute or independently regenerate the 10,000 resamples. Its published
intervals below remain the saved bootstrap results, not new measurements.

| Mode | Loops | Baseline/candidate CPU geometric mean | Saved 95% interval |
| --- | ---: | ---: | --- |
| Known ASCII, 4096 bytes | 590627 | 2.480824 | 2.464376–2.498152 |
| Known ASCII, 15 bytes | 1000000 | 1.086539 | 1.081053–1.091888 |
| Persistent unknown ASCII, 4096 bytes | 576495 | 0.989337 | 0.982164–0.995961 |
| Unicode, 4096 bytes | 24453 | 1.002061 | 0.999359–1.004938 |
| No-query ASCII, 4096 bytes | 1000000 | 0.995274 | 0.989519–0.999394 |

I also compared all 135 saved pilot/warmup/paired stdout records against an
independent reconstruction from the archived raw inputs: decoded escapes, exact
joined bytes, byte/scalar checksum and alias-equality line all match. This is
read-only comparison of existing output, not a replay of the program.

The rejection rule uses **candidate/baseline**, so its lower bound is the
reciprocal of the displayed upper bound. Unknown's inverse geometric mean is
approximately 1.0108 (about 1.08% slower) and no-query's is approximately 1.0047
(about 0.47% slower). Both
intervals indicate a retained small slowdown, and neither reaches its specified
5%/3% rejection threshold. Known-large exceeds 1.03 with lower bound above one;
the other controls do not trigger rejection. The runner checks exactly those
directions and thresholds (`.py:178–191`). This supports the preregistered
**workload tradeoff**, not a claim of zero regression or universally faster join.
No-query cost is therefore now observed for this workload, while generalization
to other call mixes/hardware remains unresolved.

Short and no-query pilots hit the one-million-loop cap. Their raw mean baseline
CPU durations are respectively 0.070907 and 0.122508 seconds, below the intended
0.15–0.30-second target. All pairs remain present; the cap reduces resolution and
does not justify treating narrow bootstrap intervals as cross-host robustness.
Recorded load1 changes from about 10.04 to 9.34; the paced core soak continued.
The preregistration explicitly allows that disclosed contamination, with other
deliberate jobs coordinated idle. This lane does not independently establish
host quietness from those load numbers.

Both saved link commands specify O2/system/K32 and the same generated LLVM.
The C observer clocks from a constructor to a destructor (`.c:19–39`), so the
measured CPU includes process setup, fragment construction, repeated joins,
cleanup and output. Fragment assembly precedes the loop (`.min:24–41`), but
it is not excluded from the clocks. The oracle checks all final output bytes,
scalar/byte checksum and `alias == source` (`.py:131–138`). This alias equality
does not add a consuming-mutation test; the earlier count fixture provides that
separate coverage. There is no compiler-arena timing or full compiler/HFT claim.

The runner records compiler/binary hashes before and after and reports equality
(`.py:151–155,192–194`). Those binaries/LLVM are omitted from the durable archive;
I verified retained source/patch/results, not omitted executable bytes. The
archive also preserves the resource-description correction: outer CPU240s/
output256MiB/taskpolicy768MiB/nice15 and subprocess timeout30s were enforced;
the preregistered separate child CPU60s limit was not installed. This is a
documented protocol deviation, not silently corrected compliance. No child
approached 30 seconds, and the observed timing thresholds are unchanged.

**Updated disposition:** no static/evidence blocker to the exact candidate's
declared engineering tradeoff. It remains UNAPPLIED pending completion of both
frozen core cohorts and coordinator-owned final integration. The observed
slowdowns, capped durations, source/clock scope and protocol deviation must
accompany any acceptance claim.

## Second delivery: queue-empty buddy admission analysis

**Disposition:** literal equality of complete C allocator state is false, even
for a three-element scalar source. A narrower theorem does establish equality
of the complete **allocator decision state**, including every free-list link in
order, for this fresh-buffer transformation in a canonical fixed buddy pool.
Its proof below covers arbitrary buddy depth and both in-place and moving
growth. This is a mathematical result for the explicitly specified transition
system, with a source correspondence audit; it is not mechanically verified C,
an executable model result, or a whole-compiler ownership theorem.

### Empirical record and the debt boundary

I read `runtime-list-reservation.md`, the accepted core patch inventory, the
actual current allocator/collections/heap/RC fragments, the saved baseline
collection fragment and final fragmentation fixture/runner/results. The final
`run-q8c_86fq/results.json` rehashes to
`f4a20cfe36e7420463895469f189cd40397080b95fa0eecb4c899a14b1cfaf04`.
Its summary records 16384 seeded histories, 15653 admitted appends and no observed
placement/admission differences. The remaining 731 are explicit skips, not
successful appends. The tested lengths are 3,7,15,31,63,127,255,511; the six
follow-on requests are 32,128,512,2048,8192,16384 bytes. Fixed/K32/O2 only.
The pilot and pre-format cohort are not added to these totals.

I independently read the retained before/guarded JSONL rows: each has 16384 rows,
15653 admissions, 731 skips and seed range 1–16384. The two complete files are
byte-identical and rehash to
`aef91ddd890ed06387a5e188644c108268bfe70419f974c73c37e48f6c1ce49f`.
This checks saved cohort arithmetic/observations, not a new history enumeration.

The fixture hashes the full map and free-list **heads** before append, not all
links (`.c:51–58`). A finite hash plus heads does not prove complete state
equality. It checks result location/content and a six-request admission bitmask,
then exact declared recovery (`.c:69–96`). Those observations neither establish
the theorem nor refute telemetry differences. The admission gate requires a
separate free class below the target and a free class at least the target before
the common result header (`.c:59–65`). For its selected lengths, target
`16*(n+1)` is the exact header-inclusive final backing block size. A smaller
free class ensures that the 32-byte header request does not consume that final
class; the proof below uses the cleaner condition **after** common header service.

The accepted production guard is at `minyar_collections.h:203–216`, after
`minyar_list_new` and its object-allocation service. It tests **any** pending
task through `rc_pending_count`, not just object queues. Enqueue increments,
object completion decrements, frame completion decrements and chunk completion
decrements appear at `minyar_bounded_rc.h:69–74,132–190,219–250`; task kinds and
poll selection are explicit at 253–264. The fused unary loop carries pending
ownership inside the non-reentrant poll, then publishes ordinary queue/count
state before return (269–315). The reasoning starts at that return boundary,
not inside its temporary carried state. Matched initial queues and header
service give matched post-header queues and allocator state.

If any task remains, the old repeated growth schedule is retained. This is
necessary: saved K1/K32 unconditional and object-only counterexamples fail when
later growth services free an upper buddy (`runtime-list-reservation.md:185–221,
267–294`). The theorem does not excuse those failures or weaken the guard.
With zero tasks, scalar construction neither drops owners nor creates tasks;
idle `rc_service_pending` returns zero (`minyar_rc.h:94–100`), and scalar stores
return without polling (`minyar_collections.h:104–111,129–136`). No omitted
service can produce a new free block in this case.

### State model: metadata remains visible

Let the fixed pool have minimum block `m=32`, capacity `P=m*2^D`, and a fixed
base address. A block `(a,k)` is the aligned interval `[a,a+m*2^k)`. All addresses
below are offsets from that same base. A valid canonical state has a disjoint
cover of the pool by allocated and free blocks, with no two free same-order
buddies. The complete map has an order+1 start byte (allocated flag 0x80) and
zero interior entries. For each order, an ordered doubly linked list contains
**every** free block of that order exactly once; both `previous` and `next`
links and the head agree. The mask has a bit exactly for nonempty lists; `used`
is the sum of allocated block charges. This is stronger than equal total free
bytes, equal heads, equal result address, or equal fingerprints.

Define full C state `S=(A,T,V,Q,C)`, where:

* `A` contains P,D,base, the complete map, all ordered free-list links, mask, used,
  and allocated block boundaries. Allocation has no separate hidden block
  header: free blocks overlay a 16-byte `PoolLink` in their own storage.
* `T` contains high-water charge, testing allocation count and step statistics,
  and any instrumentation history. These are real fields, but the source does
  not consult them for admission.
* `V` contains runtime object/data headers, initialized semantic payloads, and
  the remaining spare/free bytes. Initialized field equality is required;
  spare/free bytes are not assumed byte-identical or observable language data.
* `Q` contains all RC object/frame/chunk queues, cursors, selection/parity state,
  frames/cache and ownership counts; the phase starts at a valid quiescent
  service-return boundary with pending count zero.
* `C` contains configuration and arithmetic/request bounds. There are no
  concurrent mutators, reentrant allocators, user finalizers, injected faults,
  intervening calls, or request decisions based on telemetry/uninitialized data.

The relation `S ≈adm S'` requires exact A and C, equal Q and initialized V at
phase boundaries, and the same logical object identities at the **same addresses**.
It permits differing T, unused bytes and transient histories. This explicitly
projects a complete state; it does not redefine a fingerprint as full equality.
It also excludes OS residency/touch history and wall time. The theorem is about
the fixed buddy admission algorithm, not lazy physical commitment or libc.

Every header/request is included. The ordinary List header is
`RcObject(8)+MinyarList(24)=32` bytes; fields are values pointer, length and
capacity (`minyar_runtime.c:63–74`, `minyar_rc.h:27–30`). A scalar backing request
is `RcData(8)+8*c` bytes (`minyar_rc.h:122–157`). No per-slot reference map exists
for scalar Lists. Pool metadata is a separate fixed `P/32`-byte map established
at startup, not a suppressed per-growth request (`minyar_pool.h:45–49,119–147`).
The result header is allocated identically **before** the diverging phase; any
source header/backing, active frame/chunk and cache storage remains part of A/Q.

For a source of length n, let t=n+1 and require all capacity arithmetic to be
representable. The bounded List schedule is `c0=3`, `c(i+1)=2*c(i)+1`, hence
`ci=2^(i+2)-1`. Its exact requests including RcData are
`bi=8*(ci+1)=32*2^i`. Let f be the least i with `ci >= t` and F=`32*2^f <= P`.
The direct phase requests F once. The geometric phase starts with NULL backing
and requests b0,b1,...,bf; the result remains length zero during this entire
growth phase. Both then perform the same scalar copy/store loop. The saved
baseline grows before copying (`before/minyar_collections.h:183–198`); current
planning/growth/copy are at 29–87 and 201–223. This is **fresh empty result**
construction, not bypassing growth of an already live source buffer.

### Exact allocator transitions

Allocation for order r chooses the least nonempty order j>=r, removes its head
B, and retains B's lower base while inserting each upper half at the head of
orders j-1,...,r. It marks the lower block allocated and updates used. This is
`minyar_pool.h:89–115,152–185`.

Growing an allocated block first requires base alignment to the target order
and exact free upper buddies at each intermediate order. It validates the
entire path before removing any links; failure leaves A unchanged
(`minyar_pool.h:246–286`). If that fails, it allocates a replacement **while the
old block is still allocated**, copies the header-inclusive old requested
prefix and then deallocates the old block (290–317). Deallocation coalesces
exact same-order buddies and inserts the coalesced block at the head (205–223).
List growth calls this preserving resize, not frame `resize_discard`; the
latter's lower-buddy relocation path (323–395) is outside this theorem.

### Lemma 1: one original free block is a closed growth region

Fix the canonical post-header free partition Π. Suppose a fresh allocation
chooses original free block B=(a,j) and currently occupies its lower block
(a,k), k<=j. Inside B, the only free blocks are its upper-half chain at orders
k,k+1,...,j-1; outside B the partition remains Π. For any next target r with
k<r<=j, a is aligned to order r, and each required upper buddy is exactly one
member of that chain. The validation therefore succeeds and removes precisely
the orders k,...,r-1. It leaves the lower block (a,r) and the remaining upper
chain. Neither allocation elsewhere nor moving growth occurs.

For a target r>j, growth cannot stay within B. If the alignment check fails,
the source returns NULL immediately. If alignment holds, its scan ultimately
requires B's same-order upper buddy (a+32*2^j,j). That cannot be a free block
of order j in Π: canonicality would already have merged it with B. It cannot
be a larger free block covering that buddy and excluding B either: dyadic
alignment makes B's same-order sibling an entire half of their parent, so a
larger dyadic cover of the sibling contains B. A split subtree is not an exact
order-j free map entry. No external block was freed. Thus the scan fails,
without mutating A. This covers an upper-half origin as well as a lower one;
the alignment failure is not an omitted growth case.

### Lemma 2: leaving a region restores its exact list position

At a moving step r>j, the old region contains only free orders <j and one
temporary allocated subblock. Consequently allocation of the replacement
chooses a head from the original outside partition at some order h>=r>j.
It inserts split halves only at orders >=r, which cannot change any list at
orders <=j. B was originally the head of its order-j list, because allocation
always chooses a head. Since selection of B, operations inside it only inserted
and removed its upper-chain nodes at orders <j; no outside operation has changed
the order-j list. Its original tail therefore remains in exactly the same order.

Deallocating B's lower subblock removes each remaining upper-chain node and
coalesces to B. Canonicality of Π prevents any merge past order j. Inserting B
at the head restores precisely its original position, head, predecessor and
successor links. At lower orders, removing the chain nodes restores the
previous lists and all their links; other initial nodes retain their relative
order even if a chain node was once their head. The replacement's higher-order
removal/splits are exactly the modifications that allocating directly from its
own original region would make. Thus the old region is restored completely in A,
not merely as a set of free bytes.

### Theorem: fresh scalar reservation preserves future raw admission

**Premises.** Matched valid complete initial states; identical protected scalar
source and appended value; successful common header allocation/service; zero
pending object/frame/chunk tasks at return; fixed canonical buddy state as
above; fresh NULL result backing; representable capacities/requests; no
intervening operation or reentrancy. After common header service, at least one
original free block has order >=f. No premise substitutes summed free bytes for
that exact contiguous block.

**Conclusion.** Both transformations succeed, finish with the same result
header and backing addresses, final capacity cf, initialized source/result
fields and contents, full map, ordered free lists/links, mask, current pool
charge, RC requested-byte count and ownership/queue state. Their completed
states satisfy `≈adm`; literal S equality and allocation/service trace equality
are not asserted. Every finite legal continuation of raw allocation/resize/free
requests, with request choices depending only on common initialized data,
addresses and success responses, has the same admission responses and returned
addresses in the two states.

**Proof by induction over the growth schedule and visited regions.** Initially
there is no temporary backing. The first allocation selects the least original
free class >=0 and its head B. The state is Π except for B's lower allocated
subblock and head-inserted upper chain, so Lemma 1's invariant holds. If the
next request remains within B's order, Lemma 1 proves the same invariant at the
larger target without any outside mutation. If it exceeds B's order, Lemma 1
proves unchanged-state validation failure. The unchanged original block of
order >=f is still available outside B, since B's order is < the next target
<=f. The replacement therefore succeeds before the old buffer is released.
Lemma 2 restores B exactly and establishes the invariant with the replacement's
new original region. The visited-region order increases strictly at every move;
thus this step applies at any finite D without an enumeration assumption.

Inductively, every departed original region is restored, and the current region
was chosen from the least available original class >= the current target. The
first current region with order >=f is exactly the head in the least original
class >=f: all earlier visited classes were <f and restored, and no step changed
the original lists at orders >=f before this selection. That is exactly the
region a direct F allocation chooses. No further move is possible before f.
Lemma 1 consumes the current region's lower-order chain up to f, leaving the
same upper-half free blocks as direct splitting from that region to f. Every
other map entry and list/link is restored. Current charge and backing address
are therefore equal to direct allocation, establishing exact A equality.

`rc_reallocate_data` writes final RcData.size=`8*cf`, and both callers write the
same pointer/capacity. The identical scalar loop fills the same n+1 slots and
length, without ownership operations or additional growth. The source stays
protected and unchanged. Header kinds/counts and post-header queue/cache state
are the same, and final requested-byte accounting includes precisely the same
RcObject/RcData sizes. This establishes the initialized V/Q relation. The proof
does not equate uninitialized spare slots: baseline's preserving memcpy can
copy old spare bytes even though result length is zero.

Finally each raw allocator transition reads A/C, never the high-water/statistics
or unused payload bytes to decide admission. Equal A/C gives the same selected
class/head, validation, split/unlink/coalescence and response, including a failed
try-allocation. Resize copies have no allocator side effect, and later request
choices see common initialized inputs/responses. Induction on continuation
length therefore preserves A/C equality and success/address responses. This
proves the stated raw-continuation property, not merely success during append.

The final-block premise is sufficient, not a result of byte summation. Without
it, no successful-transform post-state is claimed. In the model, canonicality
also prevents temporary-only growth from manufacturing a larger original free
region across an unchanged live blocker. Failures can occur at different
intermediate steps, retaining different transient storage before fatal exit.
The proof deliberately does not promise equivalent recoverable failed states.

### Smallest full-state counterexample, derived by hand and unexecuted

Use a 4096-byte fixed pool and an ordinary scalar source with length=capacity=3,
values `[0,37,74]`. From the empty initialized pool, construct that source without
other owners: its RcObject/List request 32 takes offset 0; its RcData+three slots
request 32 takes offset 32. Its payload pointer is 8 and values pointer is 40.
The common result-header request 32 takes offset 64, payload pointer 72.
At this boundary both variants have used=high_water=96, pending_count=0,
source RcData.size=24, and result `(values=NULL,length=0,capacity=0)`.

| Offset | Size | Post-header state |
| ---: | ---: | --- |
| 0 | 32 | Source RcObject + List |
| 32 | 32 | Source RcData + three scalar slots |
| 64 | 32 | Result RcObject + empty List |
| 96 | 32 | Free, sole order-0 node |
| 128 | 128 | Free, sole order-2 node |
| 256 | 256 | Free, sole order-3 node |
| 512 | 512 | Free, sole order-4 node |
| 1024 | 1024 | Free, sole order-5 node |
| 2048 | 2048 | Free, sole order-6 node |

This is a complete canonical partition; all listed free links are `(NULL,NULL)`,
other lists are empty, D=7, mask=125, and every interior map entry is zero.
Source/result starts have byte 0x81; free starts have order+1. The separate
128-byte metadata map is initialized and external to the charged pool.

Append scalar 919, requiring capacity 7 and exact backing request `8+7*8=64`.
Direct reservation splits the original 128-byte free region: allocated 64 at
128 and free 64 at 192. Used/high_water become 160.

Geometric growth first allocates 32 at 96, making used=128. At request 64,
`96 & (64-1) = 32`, so same-base growth fails without mutation. Moving resize
allocates 64 at 128 **before** freeing offset 96, so used and high_water reach
192. It copies the 32-byte old requested prefix, frees the 32-byte old block and
finishes with used=160 and high_water=192. Under testing, backing allocation
count increments twice versus once; including the common three initial
allocations, counts are 5 versus 4. Those metrics never control admission.

Both final A states have allocated starts 0,32,64 (0x81) and 128 (0x82), free
starts 96 (1),192 (2),256 (4),512 (5),1024 (6),2048 (7), zero interior entries,
mask=123 and sole-node lists at orders 0,1,3,4,5,6. Both result values pointers
are 136, capacity 7, length 4 and prefix `[0,37,74,919]`; RcData.size is 56.
This is an exact high-water/full-state counterexample, **not** a
baseline-success/candidate-OOM continuation. All subsequent legal raw request
responses still agree by the theorem. Source lengths 0–2 require only the
initial 32-byte backing class, so length 3 is the smallest scalar append length
that distinguishes this moving-growth high-water history.

An unrestricted C context allowed to read the private high-water field could
distinguish the variants and choose different later requests (for example,
request P+1 when high_water=160, otherwise request 32). Baseline would admit
the latter and direct reservation would reject the former. This is a deliberate
telemetry-dependent continuation, not unequal admission for the same request
schedule, and not a public Minyar observation. It explains why the theorem's
continuation domain must be stated rather than silently called all C contexts.

### Remaining obligations and smallest useful falsification target

The mathematical induction above has no remaining arbitrary-depth canonical
state case: alignment failure, all in-region upper-buddy steps, moving overlap,
coalescing only to the original region, and ordered head restoration are all
covered. Its first vulnerable lemma is exact restoration of an original region
and its class-list position. An actual full-map/**all-link** mismatch in a valid
post-header zero-debt replay would refute the source correspondence; a result
address match or digest is not an adequate oracle.

No executable replay is authorized in this lane. For a later separately
coordinated check, the length-3 layout above is the smallest case testing one
move plus a split, exact addresses and the telemetry distinction. A next hand
state that exercises **two** moving boundaries uses source length/capacity 7,
source header at 0 (32), unrelated live block at 32 (32), result header at 64
(32), source RcData at 192 (64), and free regions 96 (32),128 (64),256 (256),
512 (512),1024 (1024),2048 (2048). It is canonical and fully covers the pool.
Targets 32→64→128 move 96→128→256; the live source at 192 obstructs the second
in-place growth. Direct allocation of 128 also chooses 256. Both finish with
original free nodes 96/128 restored and the split free 128-byte node at 384.
The later oracle should compare every map entry, every ordered list and both
links, all live headers/initialized values, current charge and identical raw
continuations; high-water and allocation counts must be compared separately.
This is a proposed falsification case, not a recorded passing test.

End-to-end obligations remain explicit: checked arithmetic and representation
assumptions at all C callers, valid protected native operands, mapping every C
allocator mutation to the modeled transition, and compiler ownership preservation.
This source audit supplies line-by-line algorithm correspondence but no formal
C/LLVM proof or new execution. Extending the theorem to noncanonical injected
states, already-live buffer resizing, telemetry-driven continuations, intervening
allocations/releases, reference elements, pending owners, lower-buddy discard
resize, libc, or lazy physical admission would require new premises/proofs.
Literal complete state equality fails as shown; publishing a stronger claim
would have to retain rather than conceal that failed equality obligation.

### Prior art, scope and reading extent

The literature premises are inherited from `literature-claims-round2.md`, read
in full here; no paper was newly fetched or counted as independently reread.
That report's P1 2026 allocator preprint was inspected only at pp 1–7,12–13 and
selected p27 references and concerns a different unbounded-address model.
CTRC's lazy reuse/variable-size boundary (P3 pp 2–4,8–10 and §3.1 opening), Poss
LRC synchronization before getrc (P4 p5 §4.2–4.3), Beans parent-edge obstruction
(P5 pp2–3), and inherited Joisha LIFO bounded cleanup/Free-Me allocator-specific
negatives are established context, not this review's new priority claims.
The possible contribution is this **transformation-specific** admission relation
and its exact preconditions. No absence of a counterexample establishes novelty.
Rejected same-credit reuse and Bytes slack retain their earlier
baseline-success/candidate-OOM dispositions; this fresh monotone-buffer theorem
does not cover their changed retention/service histories.

Repository README, architecture, campaign README and both runtime-contract
documents were read; hardening notes and the historical notes logs
`ownership-after-layout.log`, `unicode-cursor-green.log`, `runtime-traps-green.log`
were consulted for their distinct earlier scope. Current aggregate/count/timing,
reservation, fragmentation and patch-inventory reports were read; large prior
literature registers were consulted selectively in addition to the full round-two
report. The excluded Rust resource and rejected university source were not
accessed, retried or bypassed. Stopped integration/native-model/tooling lanes
remain untouched. No new restriction occurred in this static lane.

`evidence/runtime-transformation-review/inputs.sha256` pins the inspected source
and report checkpoint. The JSON companion records dispositions; the evidence
directory separates archived-output/hash verification from the unexecuted hand
cases. Later central-report updates do not alter the archived identities above.
