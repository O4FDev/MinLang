# Isolated scalar List prefix bulk copy

**The bounded count/semantic experiment passed; the candidate remains isolated.**
No production source, capacity policy, allocation or cleanup hook was changed.
There is no timing, generated-language or adoption result for this candidate.
[Preregistration](runtime-list-bulk-preregister.json) predates the fixture,
baseline red and candidate. [Derived results](runtime-list-bulk-results.json)
retain exact separate cohorts; [durable sources and logs](evidence/runtime-list-bulk/)
survive `make clean`.

The [pinned peer implementation review](peer-implementation-review.md) suggested
copying an initialized scalar prefix after trusted reservation. This is an
original internal experiment, not a Rust source port or a new memory algorithm.
Minyar's compiler emits `minyar_list_appended` for `.appended(...)`; the previous
generated List fixture exercises that API. No `.appended` application call site
was found in the inspected compiler/examples source search, and no application
hot-path or prevalence claim is made.

## Source condition and patch

The baseline is the **already guarded** production reservation implementation,
not the earlier geometric/unconditional candidates. The isolated
[exact patch](evidence/runtime-list-bulk/run-cdthtzns/candidate.patch) captures
`!references && !rc_pending_count` after the common header, before reservation.
Any pending object/frame/chunk task keeps the full previous copy loop even if
reservation subsequently drains it. References also keep that loop, including
mortal, null and immortal elements. The original tail add/take remains unchanged.

After unchanged successful reservation, the fresh scalar destination has capacity
at least `n+1` and cannot overlap the protected source. The existing capacity and
header-inclusive size checks establish representability of `n*sizeof(long long)`.
The candidate copies that initialized prefix only when `n>0`, then publishes
length `n`. Zero length skips copying because source backing may be NULL.
The valid typed scalar, single-mutator, non-reentrant contract ensures no callback
observes intermediate result lengths. It gains no `restrict`, metadata, service,
layout or recovery policy. Invalid fabricated native headers are not certified.

## Red and paired controls

The first [adapter cohort](evidence/runtime-list-bulk/run-uy7vxriu/results.json)
failed to compile: the Darwin SDK had already defined a fortified `memcpy`
macro. No fixture ran there. The [recorded correction](runtime-list-bulk-adapter-correction.json)
undefines that macro before local observer interposition, without changing the
oracle or thresholds.

The [first successful baseline](evidence/runtime-list-bulk/run-034ic9tc/results.json)
then reproduces the declared work red at `n=2`: three observed scalar append
entries and no bulk copy fail the one-copy/one-tail requirement with exit 70,
**after semantic checks and exact recovery**. This is a missing count target,
not a runtime correctness defect. Its full semantic cohort passed before the
candidate was written.

| Configuration | Baseline / candidate durable run | Full observations per variant |
| --- | --- | ---: |
| system/K32/O2 | `run-034ic9tc` / `run-cdthtzns` | 34 |
| fixed2MiB/K1/O2 | `run-bqxj0dp4` / `run-fuml9dih` | 34 |
| system/K32/native C ASan+UBSan/O1 | `run-yj8cm18v` / `run-5olg8n6r` | 34 |

These are six builds/six full executions of 34 control shapes, plus three expected
baseline count reds and three candidate target passes. They are not 204 distinct
tests or ports. No generated LLVM was compiled, and LSan is disabled. The first
system pair uses the saved pre-format fixture; the later pairs use its pinned
ClangFormat 23.1.2 formatting. Executed fixture and runner versions remain
separately archived rather than relabeled as one final-source matrix.

Lengths are 0,1,2,3,7,15,31,32,1023,1024,4095,4096,8193 with both tail flags.
Every source/result slot is checked against independently initialized signed
endpoints, Boolean/Character/Float slot words and varying unsigned bit patterns.
A retained source alias remains unchanged after dropping the producer root.
The reference controls contain mortal/null/immortal members and a tail aliasing
an existing member, with exact retain/take counts and surviving bytes. Object,
frame and temporary-chunk debt must remain after common header service; all
retain the previous loop. Capacity uses a separate mathematical policy oracle.

| Idle scalar length | Baseline append entries, retained tail | Candidate append entries | Candidate prefix-copy bytes |
| --- | ---: | ---: | ---: |
| 0 | 1 | 1 | 0 |
| 2 | 3 | 1 | 16 |
| 1,024 | 1,025 | 1 | 8,192 |
| 8,193 | 8,194 | 1 | 65,544 |

The source-level observer counts entry executions even when the optimizer inlines
calls. Copy bytes are still linear; scalar element data is still written. This
does not establish fewer machine instructions, memory traffic or CPU cost.
The independent earlier performance audit confirms its own baseline binary
retained the scalar loop, not that this new candidate is faster. Tiny inputs and
already-optimized copies remain important prospective timing controls.

For every pair, ordered managed object/data/resize **request-entry** events,
helper events and all observed public poll offer/work/pending transitions match.
Nested helper/public work is not added twice. Capacity, retain/take, post-operation
objects/requested bytes and exact drained recovery also match. Debt/reference
rows, including their copy observer fields, are completely equal. Scalar idle
rows differ only in prefix append/copy work. This fixture does not log underlying
libc allocation addresses, continuous charged/RSS peaks or every possible public
poll input; it records all polls occurring in these controls.

Each case drains pending tasks and separately disposes cached frames, with zero
object/requested/tracked heap allocation or fixed-pool used bytes. Native commands
have CPU 30s/file 32MiB/30s timeout, Darwin taskpolicy memory pressure 128MiB and a
completed-process RSS check at 128MiB. The largest saved native peak is 11,272,192
bytes. This is not continuous RSS enforcement or a latency experiment; the paced
system soak remained active. Compile processes use the established normal-QoS
outer limits.

## Remaining gates

The basic trace argument is promising but admission/error and generated coverage
are still pending. A next narrow cohort can replay the existing tight object,
frame/chunk pressure fixtures against the guarded baseline and isolated candidate,
then compare deterministic follow-on requests after successful construction.
No new capacity/service policy is needed. Independent exact-patch review and
separately coordinated paired CPU observations must precede any adoption decision.
No production change is authorized by this report, and frozen cohorts still
validate the unchanged production sources.

Reproduce the basic pair with serial calls to
`python3 tests/memory-research-list-bulk.py`, then `--candidate --compare-baseline`
using the new baseline result. `--profile fixed --budget 1` selects the fixed pair;
`--sanitize` selects native C instrumentation. Installed Darwin Clang/SDK and the
repository helper are external prerequisites. Local successful binaries/dSYM were
hashed before selective removal; retained JSON, patches and source snapshots are
not deleted.
