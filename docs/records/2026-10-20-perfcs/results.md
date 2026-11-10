# Matched runtime measurements

Historical campaigns below use Linux x86_64/LLVM 23.1.2 user-space hardware
instructions; the final section records a separate LLVM 23.1.3 repeat. All use
seven retained observations and one warmup per role. Counters run
continuously without scaling. Product and native studies pin one allowed CPU;
the self runner pins its hardware event rather than CPU affinity. No wall-time,
RSS, universal speedup or target-platform latency claim follows from these counts.

The first runtime candidate is 7b36666d8, with its exact parent 7dae54f14 as
control. Every pair shares identical generated program LLVM; product pairs also
share native/generated objects, linked to separate O2 runtimes without LTO.
Self pairs use matched ThinLTO. Eager uses separate scope-owner LLVM for both
roles and acts as a negative control for bounded-only changes.

## Compiler self-compilation

| Pair | Default control | Default candidate | Change | Eager control | Eager candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Chunk cache and restricted cycle batching | 15,276,598,895 | 14,804,071,799 | -3.093% | 4,556,210,894 | 4,556,212,003 |
| Same frozen control, plus frame initialization and empty Map paths | 15,276,600,213 | 14,688,582,024 | -3.849% | 4,556,211,720 | 4,556,211,642 |

The second pair adds only the documented five-header frame/Map delta to the
frozen first candidate. It is a controlled runtime experiment on the same
self-compiler LLVM/input, rather than attribution of unrelated later branch
changes. All 40 first-pair executions (including arena) and 32 combined executions
emit identical 17,171,630-byte LLVM:
`0df92ae214e773ae0fdf8ae01ed7de3871b77c4f82c5aaf9a20de3c9045e64c9`.
The matching first-pair arena median is 2,409,033,972. Default remains over 6x that
arena control; the 1.2x target is unmet. Eager is unchanged within measurement
variation. The isolated frame screen saves 0.780% beyond the first candidate.
Raw observations and identities are in [first-self.json](../../../experiments/perfcs/results/first-self.json),
[combined-self.json](../../../experiments/perfcs/results/combined-self.json) and
[frame-screen.json](../../../experiments/perfcs/results/frame-screen.json).

## Complete first-candidate product campaign

Measured JS/jsmn runtime accounting is disabled. Separate links using the same
objects enable accounting and prove normal-exit ownership recovery. Safelibs
**requires instrumented runtime accounting** for its frozen live-object API;
its results below carry that limitation. These are focused frozen probes, not
qualification of current product HEADs or complete product sanitizer suites.

| Workload/profile | Control | Candidate | Change |
| --- | ---: | ---: | ---: |
| js-create-default | 169,402,727 | 167,404,976 | -1.17929% |
| js-create-eager | 95,580,175 | 95,579,681 | -0.00052% |
| jsmn-1024-default | 6,459,141,622 | 6,104,090,124 | -5.49688% |
| jsmn-1024-eager | 2,957,318,803 | 2,957,318,344 | -0.00002% |
| jsmn-16-default | 11,149,279,777 | 10,939,274,251 | -1.88358% |
| jsmn-16-eager | 5,419,818,842 | 5,419,818,147 | -0.00001% |
| jsmn-16384-default | 10,535,612,307 | 9,949,082,237 | -5.56712% |
| jsmn-16384-eager | 4,776,857,850 | 4,776,856,846 | -0.00002% |
| safelibs-jpeg-default | 12,707,537,265 | 12,529,527,950 | -1.40082% |
| safelibs-jpeg-eager | 8,126,381,954 | 8,126,380,972 | -0.00001% |
| safelibs-png-default | 7,132,489,331 | 7,132,488,232 | -0.00002% |
| safelibs-png-eager | 6,270,843,070 | 6,270,842,949 | -0.00000% |
| safelibs-zlib-default | 5,310,823,321 | 5,310,820,756 | -0.00005% |
| safelibs-zlib-eager | 4,747,509,570 | 4,747,510,636 | +0.00002% |

All 288 hardware executions pass semantic checks. Twelve separate codec oracles
save and compare complete decoded bytes across roles/profiles; JPEG's C-reference
tolerance does not weaken exact candidate/control equality. Jsmn additionally
passes unchanged upstream, compatibility and thread clients in all four parser
modes for each runtime/profile. JS requires shipping and instrumented checksum
stdout to agree. [first-products.json](../../../experiments/perfcs/results/first-products.json)
retains every observation and oracle hash; full raw decoded bytes, objects,
manifests and source snapshots are in the coordination archive.

JS default ablations are 169,402,727 baseline, 167,404,883 cache-only,
169,402,737 cycle-only and 167,404,976 combined. Thus the measured JS gain comes
from caching. The earlier instrumented/broader batching screen is not a shipping
JS gain; both ordinary batching implementations regressed self-compilation
about 2.5% and were removed. Their unfavorable raw reports are retained here.

## Combined frame and Map follow-up

A fresh paired campaign uses the same frozen compiler, library and product
inputs, adding the measured five-header delta to the first candidate. Each
profile still emits its program LLVM/object once for both roles. These counts
compare within this campaign; percentages from separate studies are not added.
Accounting labels and exact-byte oracles above remain unchanged.

| Workload/profile | Control | Combined candidate | Change |
| --- | ---: | ---: | ---: |
| js-create-default | 169,402,400 | 164,810,750 | -2.71050% |
| js-create-eager | 95,579,778 | 95,579,942 | +0.00017% |
| jsmn-1024-default | 6,459,141,859 | 6,021,821,263 | -6.77057% |
| jsmn-1024-eager | 2,957,318,285 | 2,957,318,401 | +0.00000% |
| jsmn-16-default | 11,149,279,273 | 10,796,870,600 | -3.16082% |
| jsmn-16-eager | 5,419,818,723 | 5,419,818,753 | +0.00000% |
| jsmn-16384-default | 10,535,612,325 | 9,814,717,836 | -6.84245% |
| jsmn-16384-eager | 4,776,857,270 | 4,776,857,065 | -0.00000% |
| safelibs-jpeg-default | 12,707,539,481 | 12,524,064,415 | -1.44383% |
| safelibs-jpeg-eager | 8,126,381,305 | 8,126,382,415 | +0.00001% |
| safelibs-png-default | 7,132,489,881 | 7,132,484,272 | -0.00008% |
| safelibs-png-eager | 6,270,841,196 | 6,270,843,752 | +0.00004% |
| safelibs-zlib-default | 5,310,822,630 | 5,310,811,202 | -0.00022% |
| safelibs-zlib-eager | 4,747,509,752 | 4,747,509,947 | +0.00000% |

All 272 executions and 12 complete codec-byte oracles pass. Eager, zlib and PNG
remain unchanged within measurement variation. Default JS improves 2.710%,
JPEG 1.444% (instrumented), and the three jsmn sizes 3.161%, 6.771%, 6.842%.
[combined-products.json](../../../experiments/perfcs/results/combined-products.json)
retains every observation. This follows the directly measured 3.849% default
self-compiler improvement above; no arena-target or general 2x claim is made.

## Activated-cycle batching

A separate shipping native workload constructs, releases and collects a genuine
self-cycle before its active cases. Inactive controls never allocate traced
objects. Both runtime roles share one O2 workload object; the control removes
only the marked batching block while retaining the chunk cache. For 200,000
frames of eight scalar owners:

| Case | Generic scheduler | Restricted batching | Change |
| --- | ---: | ---: | ---: |
| Activated local owners | 615,178,543 | 506,578,747 | -17.653% |
| Activated temporary owners | 535,578,177 | 432,178,329 | -19.306% |
| Inactive local owners | 574,376,655 | 574,376,757 | +0.00002% |
| Inactive temporary owners | 485,576,384 | 485,576,248 | -0.00003% |

All 64 executions emit checksum 1279999200000; separate 32-frame same-object
instrumented links require 32640 and zero ownership/tasks/caches/backing.
These microbenchmarks justify the restricted path, without product inference.
[cycle-owner data](../../../experiments/perfcs/results/cycle-owners.json) and the
`experiments/perfcs/cycle-owners/` sources preserve its method. The exact
K-unit/queue equivalence proof is in [bounded-ownership.md](bounded-ownership.md).

## Collection audit and Map follow-up

[collections.md](collections.md) records source complexity arguments and the
320-run, ten-kernel O0/O2/sanitizer-checked scaling study. Unicode append followed
by length on every prefix approaches4x instructions per doubled input; plain
unique append and List growth approach linear scaling. Aliased List copying is
quadratic in byte volume even when optimized memcpy gives approximately linear
retired instructions. The larger alias study records both observations.

The two empty-Map early paths preserve List allocation/kind/reserve and equality
read-guard retain/releases. At 2048 historic entries the complete empty workload
falls 28,713,066→1,414,227 instructions (-95.075%); nonempty sparse control changes
28,919,525→28,922,068 (+2543 instructions). This includes unchanged population,
removal and cleanup; sparse nonempty traversal remains capacity-linear. Raw
[empty-map.json](../../../experiments/perfcs/results/empty-map.json) and
[large-alias.json](../../../experiments/perfcs/results/large-alias.json) retain samples.

## Qualification and reproduction

All builds/tests/counters run through the lane's existing Boat boxes. Designs
precede implementation. Independent review found no production ownership,
K-budget, fairness or growth defect. Focused matrices preserve exact owner and
finalization charges, queue turns, old/recent parity, cycle barriers, cap bytes,
physical zero recovery and intended mutant assertions. Frame tests reconstruct
the old behavior fail-closed, model ownership independently, and require complete
cached capacity NULL; growth includes discard/lower-buddy/poison boundaries.
The original full 200-pair model and 60 activated-cycle pairs passed.

The required portable/ownership/cycle/sanitizer/recovery/stack gates remain the
landing authority. Their exact stamp/log/landed SHAs are recorded in the active
coordination report and resume note, rather than inferred from these screens.

The current safelibs transaction wrapper manually resets private runtime roots.
Its adoption needs three guarded hooks: clear finalized cache on normal success,
null its root after raw rollback, and reject a residual cache at admission.
The patch is `experiments/perfcs/safelibs-cache-compat.patch`. An isolated frozen
actual-wrapper proof passes K1/2/7/32/1024, O0/O2, native/ASan/UBSan/LSan,
every calibrated allocation refusal/retry, output ownership and three omission
mutants. The product checkout was not edited; its complete product adoption
qualification remains separate.

See [the reproduction guide](../../../experiments/perfcs/README.md). Complete frozen
inputs, executables, LLVM, raw logs/counters and failed preparations are retained
under the 2026-10-20 perfcs coordination archive. JSON paths identify the original
remote artifacts; they are not executable laptop instructions.

## LLVM 23.1.3 matched runtime repeat

Control runtime is repairpack `4ff252015`; candidate runtime is `b7375a015`.
The same frozen compiler LLVM/input/library and product inputs isolate runtime
changes. This does not attribute unrelated current compiler or product-HEAD
improvements. The subsequently landed `ce0775824` seven explicit NaN casts are
a separate strict-warning baseline repair; these measurements precede that
source-only spelling repair, while the final landing gates include it.

| Workload/profile | Control | Candidate | Change |
| --- | ---: | ---: | ---: |
| Self default | 15,278,643,768 | 14,690,625,511 | -3.84863% |
| Self eager | 4,559,017,837 | 4,559,017,595 | unchanged |
| JS create default | 169,368,995 | 164,777,087 | -2.71119% |
| JS create eager | 95,615,231 | 95,614,995 | unchanged |
| jsmn16 default | 11,149,279,356 | 10,796,870,073 | -3.16083% |
| jsmn16 eager | 5,419,818,598 | 5,419,818,241 | unchanged |
| jsmn1024 default | 6,459,142,551 | 6,021,821,298 | -6.77058% |
| jsmn1024 eager | 2,957,318,187 | 2,957,318,123 | unchanged |
| jsmn16384 default | 10,535,612,055 | 9,814,717,702 | -6.84245% |
| jsmn16384 eager | 4,776,857,625 | 4,776,857,632 | unchanged |
| JPEG default, instrumented | 12,707,538,137 | 12,524,064,823 | -1.44381% |
| JPEG eager, instrumented | 8,126,381,400 | 8,126,380,459 | unchanged |
| PNG default, instrumented | 7,132,490,626 | 7,132,480,734 | unchanged |
| PNG eager, instrumented | 6,270,840,512 | 6,270,841,329 | unchanged |
| zlib default, instrumented | 5,310,822,211 | 5,310,811,023 | unchanged |
| zlib eager, instrumented | 4,747,509,973 | 4,747,509,147 | unchanged |

All 32 self executions emit the same 17,171,630-byte LLVM/hash recorded above.
All 272 product counters and 12 complete codec-byte comparisons pass. Shipping
JS/jsmn accounting remains disabled, separate same-object ownership links pass,
and safelibs still requires instrumented accounting. Eager/PNG/zlib changes are
small measurement variation, not exact instruction equality or claimed gains.
Raw reports and complete build manifests are
[current-self.json](../../../experiments/perfcs/results/current-self.json),
[current-self-manifest.json](../../../experiments/perfcs/results/current-self-manifest.json),
[current-products.json](../../../experiments/perfcs/results/current-products.json) and
[current-products-manifest.json](../../../experiments/perfcs/results/current-products-manifest.json).

A separate [source/data audit](current-data-audit.md) independently recomputes
all 16 rows, all 304 counters, sample/order/output/accounting assertions, shared
link objects and exact runtime-tree Git identities. It found no numerical or
accounting error; accepted selection-count/general-dispatch wording refinements
are reflected in the design. It did not rerun workloads or qualify the final
gates. The parent separately verified all 773 immutable manifest files against
the downloaded measured-artifact archive; its
[coverage receipt](../../../experiments/perfcs/results/current-archive-coverage.json)
and coordination archive index identify that byte audit. Measured binaries,
LLVM, inputs and raw output are retained offbox; proof-source/log archives
explicitly omit reproducible ELF/object files.

## Final-source repeat after the NaN baseline repair

This separate final campaign compares exact control runtime `ce0775824` with
frozen candidate runtime `b7e605a81`; both include all seven explicit NaN casts.
It shares the earlier frozen compiler LLVM/input/library and all product inputs.
It isolates this lane's runtime changes rather than cumulative compiler changes
or later composition into tonight. All 32 self executions emit identical
17,171,630-byte LLVM with the hash above. All 272 product counters and 12 complete
codec-byte oracles pass, with seven retained observations plus one warmup.
Shipping JS/jsmn accounting is disabled; separate same-object ownership links
pass. Safelibs remains instrumented for its frozen live-object API.

| Workload/profile | Control | Candidate | Change |
| --- | ---: | ---: | ---: |
| Self default | 15,278,646,435 | 14,690,629,119 | -3.84862% |
| Self eager | 4,559,020,146 | 4,559,018,219 | unchanged |
| JS create default | 169,369,200 | 164,776,858 | -2.71144% |
| JS create eager | 95,614,966 | 95,615,220 | unchanged |
| jsmn16 default | 11,149,279,269 | 10,796,870,639 | -3.16082% |
| jsmn16 eager | 5,419,818,692 | 5,419,818,483 | unchanged |
| jsmn1024 default | 6,459,141,996 | 6,021,821,391 | -6.77057% |
| jsmn1024 eager | 2,957,318,637 | 2,957,318,557 | unchanged |
| jsmn16384 default | 10,535,613,370 | 9,814,721,247 | -6.84243% |
| jsmn16384 eager | 4,776,857,528 | 4,776,857,101 | unchanged |
| JPEG default, instrumented | 12,707,542,102 | 12,524,071,846 | -1.44379% |
| JPEG eager, instrumented | 8,126,381,639 | 8,126,385,883 | unchanged |
| PNG default, instrumented | 7,132,489,688 | 7,132,484,003 | unchanged |
| PNG eager, instrumented | 6,270,842,479 | 6,270,844,403 | unchanged |
| zlib default, instrumented | 5,310,824,019 | 5,310,812,869 | unchanged |
| zlib eager, instrumented | 4,747,509,798 | 4,747,510,164 | unchanged |

Raw data/build manifests: [self](../../../experiments/perfcs/results/postfix-self.json),
[self manifest](../../../experiments/perfcs/results/postfix-self-manifest.json),
[products](../../../experiments/perfcs/results/postfix-products.json) and
[product manifest](../../../experiments/perfcs/results/postfix-products-manifest.json).
The [independent final-source audit](postfix-data-audit.md) recomputes all 304
counters/16 medians and checks sample/output/accounting/link/helper identities,
every runtime Git blob, and unchanged frozen compiler, 103 product input files
and 78 library files. No discrepancy was found; it does not certify a landing.
The parent separately verifies all 773 immutable files plus 12 complete decoded
codec files against the downloaded archive, with a
[byte receipt](../../../experiments/perfcs/results/postfix-archive-coverage.json).
Full ELF/LLVM/input/raw artifacts are retained in the coordination archive
`postfix-artifacts.tar.gz`, 58,335,565 bytes, SHA-256
`502e2a9a81d984f63800b2ea5f2c9165992ef80100902c2825d12e0837f22458`.
No universal throughput/RSS gain or 1.2x-arena target claim follows.
