Round2 native/application validation is **passed**. The final frozen matrix passed 108/108 contracts in 12 configurations; 11/11 deliberately broken source controls were detected.

This lane added tests and research evidence only. No production edits, core runtime/compiler/launcher/build changes, commits or resets were made. The three lane production source hashes match the prior round and the saved entry snapshot. Exact entry dirty patches and status are retained alongside every matrix snapshot.

Each configuration tests three distinct PNG staging allocation failures, six deferred zero frames followed by a successful 8x8 PNG retry, four seeded mesh traces with valid uploads/draws/clear/refill and fragmented handle churn, and one real terrain edit/remesh/upload trace. PNG failures report the exact memory diagnostic, leave the screenshot request pending, and perform no pixel reads or file open/write. Other successful staging allocations remain live until fatal process exit; this is explicitly not recoverability or leak evidence.

The matrix executed 49,152 mixed mesh iterations over 48 executions and 175,872 actual mesh API calls including the directed prefix and drains. The independent occupied bitmap searches from slot zero. Typed GL seams separately validate layout, object association, upload length/hash and draw vertex count. Clear/refill never leaves a pointer retained by the seam. Registry growth is bounded at 256 slots/4096 requested bytes/three reallocations, with 512 mock GL objects maximum and zero after drain. Restoring the first handle then creating beyond a dense 128-slot prefix still checks 127 occupied slots; the optimization retains linear worst-case scans.

One terrain replay has 192 edits (143 changes, 43 unchanged writes, 6 outside controls), 21,354 solid and 8,910 water vertices. Every event compares all 65536 block bytes, 4096 column tops, 1024 dirty slots and exact distinct torch membership against an independent byte/set/rectangle model. The mesh oracle checks complete rectangle-face multisets, outward triangle winding, cube/water/torch bounds, atlas endpoints and four-corner UV coverage, exact ambient/directional RGB, sky light and distance-based glow. It allows either diagonal and does not certify exact UV-to-corner orientation. The matrix checked 2,304 actual event snapshots and 363,168 vertex rows. All configuration snapshot hashes match.

Calibrations restore the original minimized-frame and repeated-placement behavior, bypass PNG OOM checks, remove mesh deletion hint maintenance, corrupt upload size/draw count, corrupt column tops/torch dirty reach, omit bottom faces, alter ambient brightness and alter atlas inset. Native assertion/trap exits and exact independent terrain mismatch diagnostics are saved. The first fixture compile failure is retained separately at pilot1; its GL stub naming collision and Darwin resource-header visibility were fixed only in the new fixture.

Separate saved output controls detected 10/10 corruptions of block contents, column tops, dirty membership, duplicate torches, vertex positions, atlas UVs, ambient RGB, sky, glow and triangle winding. These are distinct oracle calibration cases and are not added to source-mutation or matrix execution counts. The supplemental native run passed 12/12 exact PNG file-open failure controls across the same configurations without rebuilding. Each creates no file, emits the exact creation-error diagnostic, records one read and one failed open, and no writes/closes. As with OOM, staged memory remains live only until fatal process exit. Pinned ClangFormat 23.1.2, owned Python syntax and Git whitespace checks passed, and all matrix source hashes still match.

The sustained run uses the saved preregistered resource thresholds and abort rules. O2 and native ASan+UBSan cohorts run serially for the requested duration, with active verified batches paced toward five percent of one CPU. Real generated terrain replays at scheduled checkpoints run while the native worker is suspended. The native process and its borrowed buffer/registry remain alive across batches; the application replay starts a fresh bounded world each time.

| Cohort | Status | Actual wall s | Native CPU s | Mixed iterations | Mesh API calls | Native peak RSS bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| system-o2 | passed | 900.050 | 45.002 | 7,654,400 | 18,676,158 | 7,110,656 |
| system-sanitize | passed | 900.025 | 45.001 | 5,163,008 | 12,597,880 | 19,152,896 |

The saved sustained records currently contain 8 passed application replays, 1,536 independently checked events and 242,112 vertex rows. Source checks performed: 34; changed-source reports: 0.

`ASAN_OPTIONS=detect_leaks=0:abort_on_error=1`; `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`. ASan default quarantine is untouched. Every sanitizer configuration has 96/96 generated ASan-attributed definitions. Generated UBSan and LSan are not claimed. RSS sampling supports the explicit input/storage bounds and does not prove all runtime live objects.

Headless CPU evidence does not establish real GPU ownership, rendering/shader correctness, frame times or whole-game performance. Large PNG arithmetic/chunk ceilings, other materials, world generation and save/load remain outside this evidence. External host load persists and all CPU/wall values are resource observations, with no accepted timing comparison.

Explicit remaining gaps for distinct follow-up:

- PNG dimension/size arithmetic and encoded chunk limits (`graphics.c`, `png_chunk`/`write_screenshot`).
- Actual GPU/display/shader/driver behavior, including translucent state and real readback.
- GL namespace hypothesis: both fake generators start at1, so arrays/buffers get coincident values. `bound_buffer == expected[slot].buffer` and `buffers[name].used` may miss an array-valued bind. The smallest independent control uses one array1/buffer513,120-byte triangle upload/draw/delete plus a saved-copy wrong-field mutation. [The prepared proposal](native-application-round2-gl-namespace-proposal.json) is explicitly unexecuted and outside this cohort.
- Other source-grounded computations: general matrix math; overlay/glyph/line buffers; terrain generation/other materials; physics collisions/movement/water/flight/aim ties; texture/icon and atmosphere cloud generation.
- Continuous terrain/application lifetime, public save/load and full runtime owner/deferred cleanup accounting: terrain checkpoint processes restart their prepared world, while only native registry/borrowed buffer state persists across the soak.

Reproduce a new matrix in an unused label:

```sh
python3 tests/native-research-round2.py --label replay-round2 --profiles eager system fixed lazy --modes o0 o2 sanitize --calibrate
```

Prepare and review a new resource proposal before starting a new sustained run; the soak tool requires an exact matching passing matrix. Binaries, large application output snapshots and LLVM stay disposable in build/native-research-round2. Durable evidence retains frozen sources, compiler/source/instrumentation hashes, exact commands/errors, small binary/JSON input trace, mutation anchors/hashes, native checkpoint NDJSON and all derived summaries.

Native worker pacing is separate from monitoring/application overhead. Saved child CPU is 150.268s (workers, terrain replays and ps sampling), coordinator CPU 10.337s, over 1804.228s wall; their combined resource average is 8.90% of one core. This is resource accounting, not a latency or throughput measurement. All completed native NDJSON rows parse completely, increase monotonically and match the final saved cohort records. [Process lifecycle evidence](evidence/native-application-round2/sustained/process-lifecycle.json) retains the actual sanitizer transition start at one-second ps resolution.

[Machine counts and provenance](native-application-round2-results.json), [matrix](evidence/native-application-round2/final-matrix/results.json), [sustained records](evidence/native-application-round2/sustained/results.json), [resource proposal](native-application-round2-soak-preregistered.json).
