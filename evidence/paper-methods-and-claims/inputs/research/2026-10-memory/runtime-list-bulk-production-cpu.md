# Production-config scalar List CPU observation

This separate cohort completed after the system soak stopped. External host load remained; there is no quiet-host claim. It does not causally compare old test-accounted and new production configurations. Production runtime files stayed unchanged during this acquisition. The exact patch was subsequently applied under the joint release, after independent review.

[Exact durable record](evidence/runtime-list-bulk-production-cpu/run-x3798c1e/results.json) retains 204 baseline pilots, 192 randomized adjacent pairs (384 measured children), every output/checksum, input/order, source/object/binary hash, actual preprocessing macros/body, sanitizer feature checks, linked symbols and machine code. All actual measured builds omit testing and research observers, sanitizers and LTO; semantic asserts remain enabled. Ordinary production fixed-heap bookkeeping remains.

| Profile/case | Baseline/candidate geometric ratio | Pointwise paired 95% interval |
| --- | ---: | --- |
| system, length 0, idle scalar | 1.003091 | [0.981573, 1.022939] |
| system, length 2, idle scalar | 1.038092 | [1.029316, 1.046941] |
| system, length 31, idle scalar | 1.555841 | [1.543300, 1.568142] |
| system, length 32, idle scalar | 1.556572 | [1.546935, 1.566316] |
| system, length 1024, idle scalar | 2.402822 | [2.376933, 2.425258] |
| system, length 8193, idle scalar | 2.341794 | [2.322704, 2.361235] |
| system, length 31, queued debt | 1.003934 | [0.992736, 1.016339] |
| system, length 31, reference | 1.004758 | [0.999351, 1.009868] |
| fixed, length 0, idle scalar | 0.990421 | [0.986641, 0.994298] |
| fixed, length 2, idle scalar | 1.031186 | [1.024090, 1.038617] |
| fixed, length 31, idle scalar | 2.080391 | [2.069307, 2.091312] |
| fixed, length 32, idle scalar | 2.035948 | [2.025392, 2.045225] |
| fixed, length 1024, idle scalar | 2.455413 | [2.447300, 2.463290] |
| fixed, length 8193, idle scalar | 2.452366 | [2.443528, 2.461404] |
| fixed, length 31, queued debt | 1.000274 | [0.997106, 1.003185] |
| fixed, length 31, reference | 0.989756 | [0.984903, 0.995125] |

All numerical criteria pass. The separate mandatory all-case adverse review flag is false: worst adverse pair was 8.9541% in system empty. Fixed empty retains ratio 0.990421 (about 0.967% higher candidate CPU), and fixed reference retains 0.989756 (about 1.035% higher candidate CPU); both intervals exclude parity under the declared estimator. These adverse controls were not discarded. Point-estimate control gates are not formal noninferiority guarantees. All pointwise intervals use the predeclared paired resampling, without multiplicity correction.

Observed aggregate child CPU was 72.070498s and runner wall 83.726859s. Every child completed under its 5-second CPU, remaining-wall/10-second timeout and 128MiB completed-RSS threshold; maximum recorded child RSS was 18,661,376 bytes. Aggregate 180s CPU/600s wall limits are checked between children, rather than enforced continuously. No overshoot, configuration, checksum or identity failure occurred. No repeat ceiling was increased for this cohort.

The measured CLOCK_PROCESS_CPUTIME_ID interval is append + separate opaque full-value checksum + release/quiescent drain; queued-debt construction is inside that control. Source setup and final complete-value/mutation checks/output are outside. All copied values affect the checksum; saved machine code retains the opaque call and loads. Full-value checksum cost dilutes isolated copying cost. Native system recovery here asserts quiescence and absence of frames, not an independently counted physical allocation balance; fixed pool charge reaches zero.

[The prior audited test-accounted cohort](runtime-scalar-bulk-performance-audit.md) and its calibration amendments remain preserved. [This production proposal](runtime-list-bulk-production-cpu-proposal.json), [configuration/resource validation](runtime-list-bulk-production-validation.md), and [joint final-source plan](runtime-joint-adoption-preregister.md) have separate scopes. [Independent production review](runtime-scalar-production-performance-review.md) is complete with no unresolved performance blocker. The exact scalar patch is applied, and [focused combined-source gates](runtime-joint-final-results.json) passed; dedicated final-source endurance and terminal acceptance remain pending. These primitive results do not establish application prevalence, whole compiler speed, general wall latency or HFT readiness.
