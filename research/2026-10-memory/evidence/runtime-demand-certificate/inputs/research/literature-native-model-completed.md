# Completed native ownership-model cohorts

The actual C runtime passed the completed native and sanitizer cohorts against an independently generated immediate logical ownership oracle. Sources, deterministic operation tapes, tooling, exact commands and compressed per-step logical-live/physically-retained journals are durable under `evidence/native-model`.

| Cohort | Distinct seeds | Builds / replays | Events in seed tapes, counted once per seed | Actual replay executions | Constructed / destroyed generations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native O2 | 24 | 10 / 240 | 98,309 | 983,090 | 174,520 / 174,520 |
| ASan+UBSan O1 | 8 | 9 / 72 | 24,768 | 222,912 | 40,140 / 40,140 |
| Combined | 32 | 19 / 312 | 123,077 | 1,206,002 | 214,660 / 214,660 |

“Events in seed tapes” includes the repeated boundary prefix and repeated operation tuples. It distinguishes input event volume from configuration-weighted replay executions; it is not a uniqueness count of operation tuples. Native profiles are eager (K1 control), system, fixed pool and lazy pool (K1/K8/K32). Sanitizers cover system/fixed/lazy at K1/K8/K32. Seeds are101–124 and501–508 respectively. Every seed includes all fourteen public ownership transitions.

The native cohort observed90,727 managed-address reuses; sanitizer runs observed12,244. All replays checked logically live payload generation identity plus an independent64-bit digest, rejected observed live frees, bounded explicit poll work/destructions, made positive final draining progress and recovered every managed allocation after releasing permitted frame caches. Source hashes remained unchanged. The exact formatted runtime SHA is `c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4`.

Native peaks across configurations were331 logically live and319 retained objects;26,234/24,814 requested bytes and30,752/29,376 charged bytes. Sanitizer peaks were291/275 objects;22,136/21,531 requested and26,176/25,440 charged bytes. These partitions include managed records and List backing buffers, excluding frames, temporary chunks and cache storage. System/eager “charged” means requested allocation bytes, not libc or OS footprint.

Resource observations use POSIX `getrusage`. Native wall time158.53s, runner user/system CPU120.86/0.94s and67.19MB peak RSS; children27.49/2.67s CPU and76.17MB peak RSS. Sanitizer wall46.96s, runner23.61/0.25s CPU and49.87MB RSS; children16.15/3.38s CPU and114.02MB RSS. Child RSS is the maximum over completed direct campaign children, including compilers; it is not a per-replay heap estimate. Observation and journals change elapsed time, so these figures are campaign costs rather than runtime latency benchmarks.

Coverage has specific limits. The boundary prefix crosses129 mixed-record edges,65 repeated List owners, sparse local slot8 in a nine-slot frame, and17 temporary aliases. Random continuation adds nested frame sizes0/1/2/8/9/16, external alias/drop, local copy/take/move, temporary borrow/keep/step, mutable DAG replacement/append, and zero/oversized polls. Old parents can point to newly allocated children when independent graph-path checking rules out a cycle. Exact maximum graph depth, fan-in and root-lifetime distributions were not measured. Current mixed records reserve scalar field0, so reference-only unary records and their scheduler specialization remain uncovered by this cohort. The payload digest is a finite checksum, not a mathematical collision-free direct comparison of every field.

Calibration sensitivity is preserved separately: `archived-run-4zv0y9or` detects four compiled semantic changes through a live-free observer, live-payload error, final recovery failure and oversized-poll violation. Its prior invalid linker-path attempt and unclassified diagnostic attempt remain archived. The initial three-seed four-profile pilot is `archived-run-fpsry2d1`; it is not folded into the large-cohort counts above.

The planned reference-only unary/late-arrival and257-temporary-owner distributions, detailed shape/lifetime census, and direct per-field expected descriptors remain **unexecuted**. A recurring service-side interruption was reported after the completed cohorts; this lane documents only completed evidence and claims no follow-on execution. This is bounded single-threaded acyclic C-ABI verification, not exhaustive correctness, compiler ownership inference, cycle collection, OOM admission or production HFT latency certification.
