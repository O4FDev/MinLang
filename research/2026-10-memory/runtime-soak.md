# Sustained mixed payload soak

Preregistered on 4 October 2026 before the long run. Production runtime sources remain unchanged. This complements the short frame/ownership models and completed public-operation replay corpus with sustained native C ABI Text/List/Bytes/record payload churn in one process. It does not certify generated code, cycles, GPU behavior or real-time latency.

The first fixed 16 MiB/K1 cohort completed successfully: native elapsed
7,200.008299 seconds, final drain passed, exit 0 and all captured source hashes
unchanged. It recorded 64,326,144 epochs, 62,819 exact quiescent recoveries and
9,550,532,069 explicitly counted public API calls. End-of-epoch requested/charged
sample maxima were 290,853/362,656 bytes; periodically sampled RSS reached
18,939,904 bytes. These are sampled scopes, not continuous transient caps.
[Final result](evidence/runtime-soak/run-h2hs4wqq/results.json) and
[durable archive inventory](evidence/runtime-soak/run-h2hs4wqq/archive-index.json)
retain the source snapshots, summaries, monitor and successful final recovery.
Its own scratch executables/symbols were removed after success, with hashes
retained. Native elapsed and the observer's 7,199.983764-second clock duration
are distinct recorded measurements; the preregistered completion criterion uses
the native monotonic duration.

The default system/K32 cohort passed its oracle corruption and ten-second
sanitizer/native pilots and started the approved two-hour run at
2026-10-04 03:45:22 UTC, seed 335671. Native monotonic origin is
760370.913484 seconds and target 767570.913484; observer clock values are recorded
separately. [Final result](evidence/runtime-soak/run-s9b7q1ep/results.json) and
[minute summaries](evidence/runtime-soak/run-s9b7q1ep/system-two-hour-summaries.jsonl)
record a passing cohort: 7,200.027850 native monotonic seconds, normal exit, final verified drain and unchanged source hashes. Its
[driver](runtime-system-soak.py) makes only summary-origin/initial-output changes
to the copied C fixture; payload, epoch, recovery and pacing code remain
byte-identical. Production stayed frozen through this cohort.

The approved long cohort is a two-hour fixed 16 MiB heap at K1, seed `0x20261004` (539365380). Before it, a deliberately corrupted independent Bytes oracle must fail at epoch 512 in a system/K32 ASan+UBSan build. Then ten-second pilots run system/K32 with ASan+UBSan, fixed/K1 native, and lazy/K32 native. Leak detection is disabled. No threshold will be increased after a failure without preserving the result and defining a new cohort.

There are 32 logical live slots. Each holds an owning Text, mutable Bytes, a 64-member scalar List, a one-member reference List and a two-field mixed scalar/reference record. Payload lengths are capped 4096 bytes. Text operations include known/unknown ASCII, accented/non-BMP Unicode, borrowed and consuming joins, self joins, full-range flattened views and protected old aliases. Mutable List/Bytes/record aliases observe updates; reference edges replace old Texts while frames/borrowed expression roots churn. Independent bounded byte/scalar arrays define expected payloads. They are compared after every mutated slot operation, with exact Text length/scalar checks including breadcrumb boundaries. At each 1024-epoch checkpoint every slot is verified, all roots are dropped and pending cleanup is polled to quiescence. Object count and requested bytes must reach zero; after explicit test-only frame-cache draining, system allocations or finite-pool charges must also reach zero. This deliberately removes cache retention at checkpoints; production cache plateau behavior is not separately certified by this cohort.

The declared logical live set is distinct from reclamation debt, which may temporarily grow. After each completed epoch, sampled requested runtime bytes must stay at most 4 MiB and finite-pool charges at most 8 MiB. These samples do not measure allocation-by-allocation transient peaks. The drain must finish within 1,000,000 explicit polls. Each explicit poll must consume at most its budget and destroy at most one object per consumed unit. Hidden service hooks and their compound aggregate are not instrumented in this soak. Any OOM requires premise analysis before labeling a runtime defect.

The runner monitors RSS every 30 seconds, aborting above 256 MiB native or 1 GiB sanitizer. It applies a 9000-second CPU limit and 256 MiB output-file limit, nice 15, a 120-second progress watchdog and an absolute 7800-second watchdog. Minute summaries report exact seed, monotonic elapsed duration, epochs, explicitly counted public API calls (including oracle queries; excluding internal calls), assertions, explicit poll units, full recoveries, end-of-epoch requested/charged peaks and sparsely sampled maximum epoch wall time. The last 64 operation descriptors form a bounded failure trace; there is no per-operation journal. Source snapshots and hashes, commands, stderr, monitor samples and summaries are written directly under `evidence/runtime-soak`, surviving `make clean`.

The fixture paces 256-epoch batches using process CPU consumption toward 8% CPU. This is a host-responsiveness policy, not throughput evidence. Sparse wall samples run under host load and pacing; they cannot establish tail latency or hard bounds. The process may pass the requested duration by one batch/pacing interval before final verified drain.

Commands:

```
python3 tests/memory-research-soak.py --pilot-only
python3 tests/memory-research-soak.py --duration 7200
```

Initial fixture compilation failed because a POSIX feature macro hid Darwin stack-query declarations, plus const/sign mismatches. That adapter result is preserved in `evidence/runtime-soak/run-r0sh37q4/results.json`; it is not a runtime failure.


A second approved cohort is preregistered in
[runtime-soak-system-preregister.json](runtime-soak-system-preregister.json):
two hours on the default system heap/K32 with seed `0x51f37`, after the fixed
cohort succeeds or a preserved failure is resolved. It keeps the same 256 MiB
native RSS ceiling and payload/recovery thresholds. The added coverage is libc
allocation/reuse/retention and the default cleanup budget; operation families
intentionally overlap. Requested/object and tracked system allocation counts
must recover exactly, while allocator/OS RSS retention may plateau rather than
return to zero. There is no additional lazy duration without a distinct VM
pressure premise. The new driver snapshot will persist its absolute monotonic
origin; current active cohort sources stay unchanged.

Active soak executables are temporary scratch beside the current cohort, with separately saved hashes. They will be removed when each cohort is finished; executable bytes are not part of the curated durable evidence. Each cohort has `metric-scope.json` distinguishing end-of-epoch memory samples, periodic RSS observations, exact recovery and its elapsed-time/origin scope.


Measurement wording correction: the original preregistration said, "Requested
runtime bytes must stay at most 4 MiB and finite-pool charges at most 8 MiB."
That wording could imply a continuously checked cap. The immutable fixture has
always checked those values after each completed epoch, so a continuous
within-epoch cap is **not established** by a passing cohort. The corrected claim
is passing sampled epoch thresholds plus exact quiescent recovery. The raw
results retain their original threshold/peak field names, with added
`metric-scope.json` explaining this limitation. No ongoing check, threshold,
seed, workload or source was changed after discovering the wording issue.
The second cohort will preserve this same sampled scope for comparison; any
allocation-by-allocation calibration will be a separate identified experiment.

## Completed default-system cohort

The default system/K32 cohort completed 62,875,392 epochs and 61,402 full recoveries, with 9,331,688,557 explicitly counted public API calls (oracle queries included, internal calls excluded). Maximum end-of-epoch requested sample was 278,052 bytes; maximum periodic RSS sample was 3,555,328 bytes. These are sampled maxima, not continuous transients. Native elapsed 7,200.027850 seconds and observer elapsed 7,199.949118 seconds use separate clocks; completion uses the native clock. The final verified drain and frame-cache disposal assert zero managed objects/requested bytes/tracked system allocations. No diagnostic occurred. Both long cohorts validate runtime c4e78f59 and collections01ae1e88, excluding the pending aggregate and scalar bulk candidates. [Archive inventory](evidence/runtime-soak/run-s9b7q1ep/archive-index.json) retains exact sources, commands and hashes.
