# Queue-empty List reservation and buddy placement

The debt guard preserves the original cleanup-service opportunities whenever
debt remains after result-header allocation. That reasoning does not prove
identical allocation histories or universal later allocation admission on the
queue-empty reservation path. This bounded differential tests that separate
boundary; production sources remain unchanged.

The fixture constructs the same scalar source List in each retained original or
final guarded runtime, then allocates unrelated raw pool blocks, shuffles their
indices using an exact xorshift32 seed, and frees half in that order. Initial
allocation-map/free-list-head fingerprints and source lengths match across
variants. Append runs only when separate smaller header space and a final-sized
free block exist. Pending task count must be zero before and after append.
The result must have identical contents and geometric capacity. Six subsequent
raw allocation attempts are made in the same order, retaining successes until
all attempts finish. Every cohort then frees all objects/backing and asserts
exact object, requested-byte, and pool-charge recovery.

| Cohort | Pool | Seeds | Admitted appends | Placement differences | Follow-on admission differences |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial pilot | 8 KiB | 2,048 | 2,048 | 0 | 0 |
| Broadened source-hashed cohort | 64 KiB | 16,384 | 15,653 | 0 | 0 |

The broadened cohort varies scalar append source lengths 3, 7, 15, 31, 63, 127,
255, and 511; source capacities follow the bounded policy. Random live filler
requests range from 32 through 8,192 bytes. Follow-on requests are 32, 128, 512,
2,048, 8,192, and 16,384 bytes. Both binaries use O2 and fixed/K32. Cleanup budget
does no queued work in these cohorts. The 731 histories without the stated
append-space precondition are skipped explicitly, not classified as passes.
For those skipped pairs, the runner compares seed, source length, initial
fingerprint and the precondition decision, and each binary still asserts complete
recovery. It performs neither append-content/placement nor follow-on admission
comparisons for them. The 15,653 admitted pairs perform all those additional
comparisons.

Run against a retained complete pre-reservation runtime snapshot:

```sh
python3 tests/memory-research-list-fragmentation.py \
  --before-runtime PATH_TO_RETAINED_RUNTIME --seeds 16384
```

No counterexample was found in this bounded history family. This is not a proof
for arbitrary fragmentation, allocator free-list order, other allocators,
intervening allocation/reclamation, reference members, huge Lists, allocation
failure, or lazy VM commitment. The raw `try_allocate` probes observe buddy
admission without fatal process termination; they do not claim recoverability
from failed managed allocations. Fingerprints are comparison aids, not a formal
state-equivalence proof. There is no timing or universal monotonic-memory claim.

The [final formatted broadened evidence](evidence/runtime-fragmentation/run-q8c_86fq/results.json)
retains original/guarded source hashes, immutable snapshots, commands, every seed
row and exact summary. An [earlier identical-count broad run](evidence/runtime-fragmentation/run-4tbkb1ky/results.json)
preceded fixture formatting; it is retained separately and not added to the final
seed count. The [pilot](evidence/runtime-fragmentation/run-2moldtha/results.json)
retains its handwritten-run output and fixture; it lacked an at-launch source
hash manifest, so it does not carry the broadened cohort's provenance strength.
