# Deferred owners and consuming Text joins

Selected raw results, source diffs and hashes survive `make clean` in the
[durable runtime index](evidence/runtime/index.json); original acquisition paths
remain recorded there.

## Falsifiable hypothesis

A runtime owner in an unreachable retired frame or container can keep physical
reference count above one after its last observable alias dies. A consuming Text
join then copies even when a semantic owner model has one live owner. Bounded
service might reconcile that count before the reuse decision, at the cost of
additional work and potentially retaining a larger buffer. This is a known class
of interaction between deferred counting and reuse; no novelty is claimed.

No extra-service or reuse policy has been adopted. The separate Unicode
representation repair in `runtime-unicode-join.md` is now production, and
`runtime/minyar_collections.h` contains the guarded List reservation. Every early-service
comparison here is test-only and must not be mistaken for an accepted runtime
policy.

## Isolated pilot

`tests/memory-research-deferred-reuse.c` keeps a 32,768-byte Text with an explicitly
131,072-byte backing. That deliberate spare capacity isolates prefix copying
from byte-buffer reallocation. A frame first owns this Text, then owns unrelated
leaf Texts. The frame's reverse sparse-owner retirement leaves the selected Text
last. A separate caller owner protects the consuming join throughout.

The pilot at K1 with two written slots produced:

| Scenario | Logical live owners | Physical owners before join | Header reused | Prefix copy |
| --- | ---: | ---: | --- | ---: |
| Retired alias, ordinary join | 1 | 2 | No | 32,768 B |
| Retired alias, extra poll(1) | 1 | 1 after poll | Yes | 0 B |
| Live alias, extra poll(1) | 2 | 2 after poll | No | 32,768 B |
| Live slice view, extra poll(1) | 2 | 2 after poll | No | 32,768 B |
| Borrowed self operand, extra poll(1) | 1 | 1 after poll | Yes | 0 B |
| Deeper three-slot frame, extra poll(1) | 1 | 2 after poll | No | 32,768 B |

This is a pilot recorded in the tool transcript, not a completed matrix. The
current fixture accepts an explicit frame width so it can be replayed with width
2 at K1, or compared on the identical width-33 program at K1/K8/K32. It counts
logical owners independently, checks every byte, preserves live aliases/views,
checks actual object destructions against explicit poll units, and drains/reclaims
all objects, data, chunks and cached frames at the end of each case.

At K32/width33, explicit service uses two units (the retained slot plus frame
finalization), after which a logically unique Text is physically unique. A
width65 backlog consumes all 32 extra units and still prevents reuse. This
contrasts reaching a nearby dead owner with generic debt draining; one fixed
budget is not a guarantee of successful reconciliation.

## Retention tradeoff

The compact-copy pilot ends with 32,884 requested runtime bytes including the
fresh result and suffix. Reusing the deliberately oversized buffer ends with
131,186 bytes. Eliminating a copy therefore retains roughly four times the
post-join requested storage in this stress setup. Root headers, suffix storage
and all other managed data are included in these `rc_bytes` observations; cached
frame storage is separately outside that object/data counter.

For finite pools the fixture also records rounded pool charge and the high-water
mark over the join. Requested byte accounting, pool block charge, actual live
Text payload, and pending **task** count are different quantities. No RSS, peak
requested-byte or allocator-internal copy claim follows from the requested-byte
snapshots. No timing has been measured for this experiment.

## Generated-language check prepared before a candidate

`tests/memory-research-deferred-generated.min` uses ordinary syntax. A synchronous
function builds a temporary Text batch and places its caller's Text last. The
caller then reassigns its Text through a consuming join. Live aliases, a retained
slice view and self-join cases check ordinary language semantics. The source is
compiled once, then linked against eager/system/fixed/lazy runtime profiles at
K1/K8/K32, natively and with ASan+UBSan.

The C observer wraps only the four final consuming joins. Earlier construction
keeps the normal policy. It distinguishes **header reuse** from **backing-buffer
reuse**, since a successful uniqueness check can still require realloc and copy.
It records physical counts before/after optional service, actual extra units,
pending task count, requested bytes and the result's buffer capacity. The
generated program's borrowed-argument and temporary owners may differ from the
isolated C setup, so no reuse outcome is hard-coded for its retired-alias case.
Live aliases and views must always preserve their bytes and block in-place
mutation.

Both matrices completed after the integration suite released its reservation:

```sh
python3 tests/memory-research-deferred-reuse.py
python3 tests/memory-research-deferred-generated.py
```

Isolated evidence: [run-7_ql4lfc/results.json](evidence/runtime/results/deferred-isolated.json)
(20 configurations, 61 recorded commands/checks, 200 case observations).
Generated evidence: [run-7r05rn2u/results.json](evidence/runtime/results/deferred-generated.json)
(20 configurations, 62 recorded commands/checks, 160 join observations).
Both cover eager32 and system/fixed/lazy K1/K8/K32 natively and with ASan+UBSan.
The generated sanitizer variant additionally annotates generated LLVM definitions
with `sanitize_address`; UBSan coverage is the C runtime layer. LeakSanitizer
is disabled, and complete isolated object/data/frame/chunk recovery is explicit.

The generated result is a substantive negative control. At every incremental
budget, the eligible retired-alias and self-join cases still have physical count
two at the selected join. An extra K units of service also fails to reach the
last owner in the 65-element retired List; no incremental final join reuses its
header under either action. At K32, ordinary allocation service subsequently
finishes enough debt that the copied retired-alias result leaves 32,826 requested
bytes, but uniqueness was already tested before that service. Eager retirement
allows eligible header reuse. Genuine aliases/views prevent reuse and preserve
all expected program output in every profile/action.

Thus the favorable nearby-frame result does not transfer to this unchanged
generated program. Adding a pre-poll cannot be justified as a general reuse
improvement from this experiment. No runtime pre-poll/reuse mechanism was added.

## Evidence and failures retained

The first isolated matrix attempt failed to compile because a fixture-only helper
was unused under the eager profile with `-Werror`; the helper was then scoped to
incremental profiles. Its evidence is
[run-x7agg8z1/results.json](evidence/runtime/results/deferred-starvation-b.json).

The second attempt ran under a background QoS limiter during the integration
suite. Parent orchestration stopped only this matrix with SIGINT to release the
exclusive compiler reservation. It is marked interrupted, with no correctness
conclusion: [run-sgfu6jfx/results.json](evidence/runtime/results/deferred-starvation-a.json).
No system daemon or peer process was stopped by this lane.

## Acceptance criteria for any future mechanism

- Compare an identical generated program across eager and K1/K8/K32; separate
  logical live owners from queued edges and temporary caller protections.
- Preserve live aliases, flattened view roots, self-RHS lifetime, evaluation
  order and failure diagnostics. A reference count above one alone cannot prove
  all excess owners are unobservable.
- Account for total extra cleanup work at the public operation boundary. Adding
  an early poll must not silently double a claimed per-operation bound.
- Measure header and byte-buffer reuse, bytes copied, requested storage, rounded
  retained storage, allocation admission, and quiescent drain separately.
- Prefer a bounded policy with explicit invariants; do not scan arbitrary queued
  graphs to seek uniqueness or discard deferred owners without proving ownership.
- Recheck short/large inputs, genuine live aliases, large spare capacity and long
  unobservable-owner backlogs. A faster isolated join is insufficient if retention
  or pressure behavior worsens.

Retired List prefixes form a related adversary: an immortal-only List retires in
one unit, but its first mortal insertion promotes the whole prior prefix to
future field work. `tests/memory-research-immortal-prefix.c` passed selected
systemK1/native, systemK5/sanitized, fixedK32/native and lazyK3/sanitized probes
in [run-bv0yq7a7/results.json](evidence/runtime/results/accounting-probes.json).
At a 65,534-element prefix, the unpromoted List costs one unit and leaves no
retained requested storage. Appending one mortal Text creates one queued task
requiring 65,536 total units; after initial release it retains 557,153 requested
bytes on system and 557,145 on pools. All profiles eventually drain completely.
The same artifact records private chunk/view tasks 1→2→1→0, sparse moved-owner
and cached-capacity9→2→9 controls, and mixed record cursor127/128 checks.
These are selected kernel/native probes, not a proof of all public ABI traces.
No ownership bitmap, sparse map or new metadata policy has been added.
