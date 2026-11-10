# Runtime collection costs

Source audit and measurements, October 20, 2026. The runtime snapshot is
`7b36666d8`; no collection implementation change is included in this study.
The harness is `experiments/perfcs/collections.c` and `collections-study.py`.

The included C runtime uses system heap, K32 ownership, testing accounting and
disabled Integer-to-Text caching. All ten kernels pass independent value,
alias, full byte/scalar and complete ownership recovery checks at O0/O2 and
ASan/UBSan with leak detection. Small alias checks inspect every old prefix;
measurement checks inspect its endpoints and the complete final List. This
avoids adding a quadratic checker to the copying experiment.

Seven retained hardware instruction samples plus one warmup cover four sizes
per kernel: 320 executions in total. Every counter runs continuously, without
scaling, on one allowed CPU. Counts include setup, allocation, validation and
complete cleanup. They describe these native API workloads, not generated
application performance or isolated kernel costs.

| Kernel | Sizes | Median instructions, smallest to largest | Last doubling |
| --- | --- | --- | --- |
| Map lookup, Text key bytes | 256..2048 | 3,077,899; 5,187,065; 9,405,607; 17,842,138 | 1.897x |
| Set lookup, Text element bytes | 256..2048 | 3,086,138; 5,195,301; 9,413,844; 17,850,379 | 1.896x |
| Map keys/equality, one remaining entry | 256..2048 initial entries | 4,109,302; 7,652,774; 14,744,079; 28,919,525 | 1.961x |
| Map keys/equality, empty after removal | 256..2048 initial entries | 3,902,857; 7,446,299; 14,537,586; 28,713,066 | 1.975x |
| List add | 2048..16384 elements | 2,484,688; 4,655,060; 8,988,173; 17,638,981 | 1.962x |
| Unique consuming List appended | 2048..16384 elements | 3,796,835; 7,278,057; 14,232,739; 28,126,436 | 1.976x |
| Aliased consuming List appended | 256..2048 elements | 1,694,141; 3,310,687; 6,573,628; 13,236,906 | 2.014x |
| Unicode Text append | 128..1024 pieces | 547,438; 909,296; 1,625,987; 3,057,102 | 1.880x |
| Unicode append and length after every piece | 128..1024 pieces | 9,513,041; 36,754,807; 145,512,630; 578,052,420 | 3.973x |
| Unicode joinText | 128..1024 pieces | 561,184; 929,624; 1,660,937; 3,122,728 | 1.880x |

Map/Set queries repeat 4096 times on the same Text value. Sparse/empty Map
traversals repeat 512 times. Ordinary/unique List construction repeats 32,
aliased construction 8, and Text construction 4. A Unicode piece is `é🙂`:
six UTF-8 bytes and two scalars. Ratios from small cases include substantial
fixed process and verification overhead; no time threshold is used.

## Map and Set

Maps use linear probing, cached per-bucket 64-bit hashes and a 75% growth
threshold. Growth reuses the stored hashes and transfers bucket ownership;
hash caching during resize is already implemented. With suitable hash
distribution, scalar lookup is expected O(1), Text lookup O(m) for m key bytes,
and record lookup includes user hash/equality cost. Deliberately colliding
record callbacks still give Theta(n) probes and potentially Theta(n²) rebuild
work. The deterministic hash is not an adversarial constant-time guarantee.

The Text bytes are hashed again on every lookup, including pointer-identical
keys: q queries require Omega(qm) byte work. The first two rows support this
source-derived bound at fixed q. An immutable Text hash cache could reduce
reuse to O(m+q), but must handle unique internal append, views and address
reuse. A new Text field would also affect compiler literals and native layouts.

Three bucket Lists use 24C backing bytes for capacity C, before headers. Sets
reuse this Map and retain a full dummy value array: one third of bucket bytes
stores scalar 1. Specialized Set storage needs a deliberate ABI/ownership design.

Removal never shrinks capacity. Enumeration and equality scan C buckets even
at live length 0 or 1; a reference-bearing bucket List also retires C slots.
The sparse/empty observations include their population/removal costs but agree
with the capacity traversal bound. Empty traversal has a small independent
optimization described in `empty-map-traversal.md`. Nonempty sparse traversal
needs shrinking with hysteresis or a dense occupied-entry representation.
Neither may bypass existing snapshot callbacks, mutation guards, cycle barriers
or bounded cleanup. Existing bulk growth itself is not a bounded-latency call.

## List

System capacities grow geometrically, first doubling then quadrupling above
the large-List threshold. Pool capacities follow 3,7,15,... to fit backing plus
header in buddy classes. There are O(log n) growth allocations and O(n) total
slots moved over n adds, even when every realloc moves. Reserve already makes
one allocation for a known target. Unique consuming append reuses the backing.
The observed ordinary/unique instruction curves approach linear scaling.

An aliased append copies its old prefix to preserve immutability. Repeating it
copies n(n-1)/2 slots, Theta(n²) bytes, even when only the previous snapshot is
retained briefly. The small instruction curve above is approximately linear:
it does **not** refute that byte-volume proof or demonstrate quadratic measured
instructions. Optimized memcpy can transfer many bytes per retired instruction;
fixed allocation, checking and process costs also matter at these sizes. No
bytes-copied or realloc counter was instrumented in this campaign.

Scalar bulk-copy shortcuts deliberately yield to pending ownership debt.
Removing those service points changes finite-pool progress and successful
allocation, rather than merely removing overhead. Capacity-preserving clear
and alias behavior are existing contracts.

## Text

Unique consuming append doubles byte capacity, giving O(B) total copying for
B produced bytes. Aliases and slice backing correctly force copying. joinText
uses a size pass and a copy pass, O(parts+B), with one final allocation.

Unicode append invalidates the lazy character index/count. A following length
query rebuilds it over the entire current prefix, so n constant-size appends
with length observed each time require Theta(n²) UTF-8 scan work. The observed
doubling ratios 3.864, 3.959, 3.973 closely follow that bound. At 1024 pieces the
whole-process count is 578M versus 3.06M for append without intermediate length
queries; this is a synthetic workload contrast, not a product speedup.

Keeping a Unicode count while clearing offsets is currently invalid: known
count plus no offsets denotes ASCII in indexing/slicing. A future change needs
separate count/index validity or incremental breadcrumbs. It must preserve
invalid-UTF8 diagnostic timing, aliases, self-append, views and every 64-scalar
boundary. Eagerly decoding appended operands would change lazy validation and
therefore requires a separate semantic decision. No Text representation change
is proposed here.

Complete raw counter/command/semantic artifacts and frozen source identities
are retained in the perfcs coordination archive. Checked-in result JSON
and reproduction instructions are linked from [results.md](results.md).
