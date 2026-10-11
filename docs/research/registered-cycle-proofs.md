# Registered graph growth without repeated certified-cohort scans

This follow-up requires fbbb3b2 and remains confined to the opt-in cycle runtime.
Ordinary single-thread runtime and maintained compiler sources are unchanged.
The previously profiled real 20,000-gateway process ran frozen old613 code;
none of the synthetic results below proves its setup time or idle CPU fixed.

## Actual tests-first failures

Tests-only commit `8007a5b` independently models root→list→interior ownership and
growing registered branch→leaf graphs. On fbbb3b2, 256 take additions cost 135,884
collector units / 256 epochs, failing the strict `32*n + 256` bound. The callback shape
contains peer→callback→environment→peer, a captured old root, and a 16-field
details record. 256 additions cost 2,195,259 units / 521 epochs, failing `128*n + 512`.
Copied ownership and sustained streaming growth exercise distinct call orderings.

An initial partition candidate still failed the unchanged callback bound with
35,144 units / 1024 epochs. Interrupted local ROOTS also exposed invalid white
collection: a removed branch left 99 objects where 194 remained reachable. Both
failed schedules are preserved separately, rather than counted as green.

Independent review found another actual defect in that candidate: a primary
owning edge published to an ACTIVE local-MARK owner after field 0 was scanned
could promote the owner while its earlier child remained unknown. A later
unknown-only job cleared that child's leaf. Tests-only `80380fe` reproduces exact
live-object loss under native and ASan/UBSan; the real append API fails the
expected 9-object oracle. Separate evidence retains both barrier-prefix and
actual-API reds. The final adversary covers copy/take at fields 1 and 7, plus
repeated already-certified publication. A repeated-case fixture capacity error
was independently found and corrected by reserving 16 slots before any job.
The failing v4 fixture evidence is retained and excluded from final results.

## Safety invariants and actual ordering

The registry has two lists using its existing previous/next words. Unknown
nodes remain eligible for finite snapshot work. A node reached from the held
primary anchor moves to the known list in one survivor unit after its fields
were visited. RcCycle remains 32 bytes with eight-byte alignment.

A genuine additive store does not remove an old anchor→node path. Completed
primary certificates can therefore survive unknown additions while IDLE or a
local job is active. An active full proof build still invalidates conservatively.
Unknown self-insertion retains the original strict full ROOTS request rule.
Local SWEEP also invalidates for an uncertified, unprocessed old target.

For copying stores, retain occurs first. The incoming barrier expires the
temporary witness, registers a fresh source if needed, checks completed-primary
guards, shades, increments incoming, then rechecks the primary anchor's
external count. A take can consume the sole external anchor without decrementing
RC: that post-incoming check must invalidate before publication or polling.

Only after the owning slot is published does commit_insert certify its direct
child and request unknown work. It never certifies arbitrary descendants.
Descendants acquire a primary tag one actual owning field per collector unit.
A first tag transition on an ACTIVE MARK object restarts its index at 0 while
preserving the captured limit and pin; completed scans are requeued. Repeated
already-primary insertions do not restart. A local node may upgrade at most
conservative→temporary→primary within the unchanged cohort, so this introduces
at most two restarts; full proof propagation upgrades once.

Local ROOTS seeds published primary children and genuine external roots.
MARK excludes stable known nodes; its old rooted cohort does not get scanned
for each addition. Local epochs use a separate snapshot generation. A third
alignment tag bit distinguishes local snapshots from full snapshots; gray
links preserve all three bits. Full ROOTS clears opposite temporary tags before
entering the full proof namespace. Local ROOTS clears stale temporary tags
before rebuilding its own witness.

Constructor releases can otherwise repeatedly finish small unknown jobs before
the constructor is published. An unchanged unknown cohort may cache one
independently held temporary root only when every surviving unknown node was
reached from it. Its opposite certificate generation is never a primary
certificate and never moves a node to the known list. Every registry or owning
edge change expires this witness; root release, incoming transfer, pinning and
unregister are also checked before reuse. Two disconnected unknown roots cannot
inherit each other's certificates.

Every mutator removal/replacement and registered unregister joins known into unknown
in constant time and invalidates. A canceled local job omitted the old primary
roots, so it must retain its whites for the mandatory joined full rescan.
It cannot reclaim them using that incomplete snapshot. The captured cohort tail
bounds ROOTS and SWEEP even after cancellation joins or newborn prepends.
Pending debt remains until requested local/full work and rescan flags retire.
Collector-internal white cleanup keeps the existing inside-collector barrier
exemption: an actually white object cannot remove an owning path from a held
root to a certified survivor.

## Independent testing and limits

[CPython's collector callback regressions](https://github.com/python/cpython/blob/main/Lib/test/test_weakref.py)
exercise one-way reachability and object-content preservation during collection.
That motivates testing live child contents, not just absence of a crash.
[CPython's collector design](https://github.com/python/cpython/blob/main/InternalDocs/garbage_collector.md)
also documents the need to re-evaluate reachability when callback activity changes
ownership. These are test-methodology influences, not copied implementations:
this patch adds neither Python finalizers nor weak references.

The tests use explicit owning edges and externally owned roots to predict
objects and contents, rather than trusting collector marks. Per-call work
limits, original e2 ROOTS selection, witness/progress gates and final exact zero
objects/bytes/debt remain strict. Adversaries cover partial promotions in each
local phase, removal, sole-primary-anchor release/take, registry tail
unregister/re-register, generation flips, temporary-root copy/take/release,
disconnected roots, active captures, list expansion/removal and allocator
lifetimes. The extended empty check also requires both registry heads/tails
and temporary/primary anchor state gone.

The new 2048-peer callback fixture has four registered records per peer and
needs 4 MiB fixed-pool capacity; its live objects do not fit the old scalar
fixture's 1 MiB pool. Existing fixtures retain 1 MiB. This is fixture capacity, not
a loosened work, reclamation, memory-per-object or idle threshold.


The final strengthened growth fixture passes 30 native and 30 ASan/UBSan/LSan
runs: system, fixed pool, lazy pool and eager profiles; bounded budgets 1, 32
and 1024; graph sizes 32, 256 and 2048. At system budget 32:

| Registered additions | Take units | Copy units | Callback units | Streaming callback units |
| --- | ---: | ---: | ---: | ---: |
| 256 | 2,048 | 2,304 | 19,328 | 19,328 |
| 2,048 | 16,384 | 18,432 | 154,624 | 154,624 |

All unchanged runtime-source gates pass: additive 30 native + 30 sanitized;
witness 14 + 14; progress 21 + 21; full independent randomized graph oracle
160 cases across five seeds and budgets 1, 2, 7, 32 and 1024 where applicable.
Their opt-in header hashes match the final source exactly.

Eleven isolated wrong guard variants fail exact runtime assertions or sanitizer
diagnostics in 44 runs (native/SAN, budgets 1/32): missing active restart, forced
append rescans, missing post-incoming anchor check, canceled-local white
collection, omitted known-list join, temporary/full tag alias, stale temporary
paths, certifying all temporary roots, lost gray namespace, missing publication
proof and treating replacement as insertion. An initial lost-namespace mutant
survived at budget 32; an independent controlled constructor schedule closed
that coverage gap. It explicitly services one real collector unit at ownership
boundaries while preserving normal list-growth service, and now catches that
same wrong code at both budgets under native and sanitizer builds.

The ordinary runtime object is byte-identical to fbbb3b2, SHA256
effee3192380318446fa53efc9d223dfb98aa04a37bb0c236889bf1131ff306a. All 54 other tracked runtime/compiler files match bytes.
Cycle metadata remains 32 bytes. No ordinary runtime/compiler file is changed.

The residual self-cycle benchmark deliberately retains full request semantics:

| Fresh self-cycles | Collector units (native and SAN) | Epochs |
| --- | ---: | ---: |
| 32 | 3,660 | 32 |
| 256 | 201,676 | 256 |
| 2,048 | 12,623,820 | 2,048 |

An eightfold increase from 256 to 2048 nodes costs about 62.6 times the work,
so this remaining regime is approximately quadratic. Every residual run still
checks all live fields and exact objects before reclamation, then zero objects,
bytes, registry state and debt.


The intentionally conservative self-cycle fixture reports increasing total
work instead of asserting a general linear bound. Any self-insertion that
invalidates the primary witness, real removal/replacement, or persistent
unrelated unknown components can retain repeated whole-cohort work. Mixed
components beyond one temporary witness are conservative. Synthetic callback
shapes do not establish arbitrary graph complexity or real transport setup.

All execution is sequential j1 on CPU 7 of the existing included Boat box, with
a 75% aggregate CPU guard. It is reactive, not a hard every-sample cap:
the final mutant wrapper observed 83.33% and 78.26% shared-box samples and paused
its owned group until CPU fell below 60%; one inner mutant paused at 80%.
These excursions and pause/resume records are preserved. No local builds, Windows work, machines, provisioning,
new spend or push occurred. macOS/Windows, global CI and source-current real
20k setup/idle/soak acceptance remain owned by root/CI.

## Evidence

Evidence root: /home/user/minyar-overnight/memory-audit/.

| Artifact | SHA256 |
| --- | --- |
| registry-growth-red/manifest.json | bfde710bd4020a0309718ce7f9ca63b00a3527a322ed46830f75fdbd2a4c000d |
| registry-callback-red/manifest.json | 2d7b52f8a24bc280ef562092eb81d0492951e790e3d63921b333392a6fb35a42 |
| registry-active-publication-api-red/manifest.json | 5e6c04812fbc38354c216eafe73f7ebdd5dd8106bf039d959e0d8b22a03a9cd4 |
| registry-active-publication-sanitize-red/manifest.json | 62e814e64982c674fa3c0f21252d2fe3030cd098f3f983fd62bd978f894fb37d |
| registry-final-v5/manifest.json | a862787454655e67b9245135c7161e9c69007c0e1e0d8f1e83f93440042da76b |
| registry-final-v8/registered-native/manifest.json | 6d666b656ec961d67b271afe217e4d28bf7613d71b7e91826fa3bb9c3e6335ff |
| registry-final-v8/registered-sanitize/manifest.json | 8ff345d1ef3bf67e06a8b2eed9e7dc41eac009c008842fdb90ff2c5c41c07c50 |
| registry-mutants-final/manifest.json | 0c0993860a7697f11c83bc48e731e47ac4265f82a50f918b77485a2f7111b288 |
| registry-residual/manifest.json | 71e74356e238ff38ec7a74c628febb42851bed098dde1b2c1a99c10cdeb4a0db |
| registry-default-identity/objects.json | 16b64b5471e2ea8322fd2bab688402a52e79944345950d9429e8241f6264fcff |

Final runtime sources:

- runtime/minyar_cycles.h: b7c62517bc65a9ee7dbc1a6448c8c5e208d605afe5f778da6ff52c282459be22
- runtime/minyar_cycles_collect.h: d2e26d99a52449d4ee42ae76dfaa6a154c8c25b4ec31bba64232adf7027413a5
- runtime/minyar_cycle_collections.h: 18da5fe1b644377e9f5961b08186558f4afba2b8dfd3d27700b4b859b94e44f4


The source-only bundle requires/excludes commit
fbbb3b2ebda9beead3b8925cae61361e9a10d3a8. The source delta contains only
the three opt-in cycle headers, additive/growth/residual tests and this report.
