# Independent final data audit

Source/data-only audit of the 13:00 BST `reports/perfcs-codex.md` checkpoint,
`measurements/perfcs/current-self/{instructions,manifest}.json`,
`measurements/perfcs/current-products/{results,manifest}.json`, maintained helper
sources and current runtime. No builds, tests, workloads, bx/box access, tracked
source edits, report edits or additional landing conditions. Parent owns both
frozen gates and landing. Runtime checkout HEAD observed:
`b27249f482d5eb180fecacdfb716b4d3a206f054`.

Initial inspection: self has four profiles and seven retained observations plus
one warmup each; product results contain 272 observations, 14 workload summaries
and 12 full-codec oracle records. Both build manifests are ready; product results
are complete. Product clang identifies LLVM 23.1.3, with its exact compiler hash
matching the self manifest's selected clang hash. All claims below will be
independently recomputed from individual observations rather than accepting the
summary booleans or stored medians alone.

## Recomputed data

All 16 LLVM 23.1.3 table rows match independently recomputed medians from the
individual retained observations. Nonzero displayed percentages round correctly:
self default -3.8486286213%, JS default -2.7111857161%, jsmn16/1024/16384 default
-3.16082566%/-6.77057751%/-6.84245347%, instrumented JPEG default -1.44381478%.
Rows labelled unchanged have tiny measured changes, not bit-identical instruction
counts; their largest absolute percentage is JS eager, about 0.00024682%.

Self: exactly 32 observations, four groups of eight, each sample IDs -1,0..6
and one warmup. Every instruction count is positive, counter running time is
positive and exactly equals enabled time, counter_scaled is false, and exit is
zero. All stdout/stderr strings are empty. Every emitted LLVM observation has
17,171,630 bytes and the report's SHA-256
`0df92ae214e773ae0fdf8ae01ed7de3871b77c4f82c5aaf9a20de3c9045e64c9`.

Products: exactly 272 observations, 34 groups of eight, 34 warmups and 238
retained. There are 14 workloads with baseline/candidate and six extra jsmn
reference roles. Every group has sample IDs -1,0..6 and one warmup. All counters
are positive, continuously running and unscaled; every exit is zero and every
stderr hash is the empty-file hash. Recomputed medians, instruction arrays,
minimums and maximums match the stored summaries. All per-workload semantic
records agree across roles and samples; jsmn tokens/bytes/iterations/checksum
were independently recomputed from count/repeats. All 176 build/check commands
record zero exit.

There are 12 codec-oracle records (3 codecs x 2 profiles x 2 roles). All four
raw hashes agree within each codec. JPEG's independent reference tolerance is
3, but exact baseline/candidate output remains required by helper code; that
distinction is correctly reported. The four JS shipping/ownership proof records
all hash exactly `3980\n` in both links. Jsmn has all 48 qualification cells:
three client families x four parser modes x two profiles x two roles.

## Identity and accounting checks

The product results' manifest hash exactly matches the local archived product
manifest. Both campaigns use the same clang SHA-256 and selected LLVM23.1.3
path; product clang --version explicitly says 23.1.3. The maintained product
builder, measurement helper, self relinker and shared hardware-counter helper
hashes match the frozen copies recorded by the corresponding manifests. Self
instructions also record that exact shared counter-helper hash.

Every runtime-tree file in both manifests was compared by SHA-256 with the
declared Git commit's blob contents, without a checkout or execution: all 103
baseline files match repairpack `4ff252015ebc619a1b62f024326f73ecd9a48b73`, and
all 104 candidate files match `b7375a015`. No mismatch or missing file occurred
in either self or product campaign. Self baseline/candidate use the same frozen
LLVM hash within default and eager profiles, respectively. This corroborates
the report's runtime-only isolation and exclusion of cumulative compiler gains.

Accounting labels match every runtime-object record: measured JS/jsmn disabled;
separate JS/jsmn ownership objects enabled; safelibs measurements enabled. Self
runtime profiles all record accounting disabled. The maintained builder uses
exactly those prefixes, and proof destructors are guarded outside arena. Jsmn's
eager poll compatibility function is present symmetrically in both roles.

## Concrete wording finding (reported promptly)

The original report's unqualified three/four-unit fairness sentence needed the
existing general-dispatch qualification. `runtime/minyar_cycle_bounded_rc.h`
lines361-367 explicitly allow a cycle request created inside the pre-existing
object-only bounded batch to wait for its return; the inner List loop at
lines445-458 does not stop solely for a new cycle_pending flag. This does not
invalidate restricted owner batching or its prefix proof.

Parent accepted and corrected the coordination report, and prepared the matching
design-doc clarification for its later documentation commit while keeping the
gate sources frozen. This is a documentation precision finding, not a new runtime
issue, requested runtime change, or landing condition.

## Shared-object isolation and execution order

For all 14 product workloads, the baseline/candidate recorded link commands
are identical after replacing only the role runtime object and output path.
Their common program/native object hashes match the immutable manifest entries.
No product link command contains LTO flags. Both roles' runtime object/wrapper
hashes match their accounting records and immutable-file entries. Self links
have matching per-profile frozen program LLVM hashes and matching selected
`-flto=thin` flags, including the LLVM23.1.3 linker. These are runtime-only pairs;
they do not benchmark cumulative current compiler/product-HEAD changes.

The product observations' actual global interleaving exactly matches the
maintained helper: each workload, round0 warmup then seven retained rounds,
listed roles on even rounds and reversed roles on odd rounds. Self JSON stores
observations grouped by profile, so global interleaving is established by its
hash-matched maintained runner, not an independently timestamped sequence in
that JSON. Product metadata records CPU0 affinity and the helper sets affinity
before fork. Self's hardware event is pinned but that runner does not set CPU
affinity, exactly as the report now explicitly distinguishes.

The two lossless codec raw oracle hashes also equal their independently frozen
expected-file hashes. JPEG is intentionally compared with a tolerant independent
reference but requires exact same bytes across the runtime roles/profiles. The
shipping JS/jsmn proof destructor establishes no active frames/scopes, drained
debt and live object count equal to immortal count; it does not promise that
ordinary reusable frame caches are physically freed. Strict physical recovery
is separate focused-test evidence, not an invented property of shipping links.

## Activated owner batching proof and amortized accounting

The current cycle header enables the marked owner batching block only in the
`cycles==1` instantiation (`:474-495`), selected after sticky `rc_cycle_present`
activation (`:524-527`). It first excludes object tasks, cycle debt and the other
owner queue. Frame visits capture/clear/drop one indexed local and return, while
frame finalization decrements pending once without dropping an owner (`:323-346`).
Chunk units have the same visit-versus-finalization separation (`:349-358`).

`rc_drop` may add an object task (`:102-107,140-184`) and traced drops may add a
cycle task (`runtime/minyar_cycles.h:168-177`). It does not service an existing
object/cycle task. Removing a cycle job occurs in collector units
(`runtime/minyar_cycles_collect.h:25-35,203-209`), which the owner loop never calls.
Under the documented non-reentrant runtime/allocator-hook assumption, an owner
visit therefore cannot decrease pending, and owner finalization decreases it
once without creating competitors. `pending_after <= pending_before` is sound
for continuing this loop; new object/cycle debt forces exit immediately.

The candidate writes the same successor before each unit: frame ->2 and chunk
->3 in the activated four-queue path. If it remains the sole owner queue, generic
selection must choose the same next unit; if a competitor appears, control
returns to that unchanged selection. Induction preserves every per-poll unit
prefix, order, finalization, next-queue state and debt. The do-loop is entered
only under work<budget; budget is clamped to K at entry (`:368-370`), and each
visit/finalization increments work once. No new K-total cleanup violation follows.

The second original wording issue was calling X only "competing units" in the
selection-overhead formula. Sole-object work can remain in the general branch
after owner finalization, and still pays selection until poll return. Also,
sole-owner batches are split by poll/K boundaries. Parent accepted the exact
accounting: B=batched owner units, R=owner-batch invocations including those
splits, U=all other generic-dispatch units. Selection count changes B+U -> R+U;
cleanup units stay unchanged. The coordination report now contains this corrected
definition, and the matching post-gate design-doc patch is prepared. This remains
a constant-factor runtime dispatch argument, not an asymptotic graph-work or
product-speedup claim. Both wording fixes were independently reread in the report.

## Audited data identities and conclusion

| Archived input | SHA-256 |
| --- | --- |
| current-self/instructions.json | ea7b8da64e03165fab5465b2f3452cde67a3b15d1a9554887e7b289e4db4d783 |
| current-self/manifest.json | d25535a1eb32fa7bbbc1ffa80605499c01251198e1e4dd25e1a8353b15487f38 |
| current-products/results.json | c2b3cc7a81bc9aa68918cf4c1ea13984414c15cceba9356e7edc39edac794a66 |
| current-products/manifest.json | 2f5dca0aa451e75bfcafc225cf7ca0160428bdcf547ae97370cebb443f6ee1ff |

No numerical, sample-count, output/counter, accounting or runtime-isolation
inaccuracy was found in the current LLVM23.1.3 table and supporting campaigns.
The two concrete argument wording findings were promptly reported and accepted;
both are now corrected in the coordination report, with production/gate trees
unchanged. The amortized argument is sound under the corrected definitions.

This audit recomputed archived data and reviewed hash-matched maintained sources.
It did not rerun any workload, qualification suite or archive extraction, rehash
all measured ELF/native-library archive contents, independently establish the
reported CPU model/KVM identity from these four JSON files, or verify a gate/
landing receipt. Earlier campaigns and separate focused-test matrices were not
requalified here. These are scope limits, not new conditions for landing. No
production, test, maintained-helper or parent-report file was edited by this
audit. Scoped task complete; parent continues frozen gates and landing.
