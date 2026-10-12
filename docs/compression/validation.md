# Compression qualification

Branch `ws5/compression`, based on `bf9c0e9`. Implementation and Boat testing
are released; merge into v2 remains the integrator's task. No push, v2 merge,
base mutation, other workstream edits, box lifecycle or paid spend occurred.
No local privileged/security/keychain/trust/privacy operations occurred.

Test-first RED was observed for the missing `zstd.min` module and missing
native compression header before implementation. Exact commands/diagnostics
are in `docs/evidence/compression/test-first.json`.

Final Linux commands on **bx_ev9fa25q**, **/home/user/ws5-compression**:

```sh
python3 tests/compression.py --mode native --artifacts evidence/native-final3
python3 tests/compression.py --mode sanitize --artifacts evidence/sanitize-final2
python3 benchmarks/compression.py --artifacts evidence/bench-primary --prepare-only
```

Both test modes passed (Boat `cmd_9qpxslsy6qte`, 14:28:06.889–14:28:28.797 UTC).
The terminal stdout is retained in
`docs/evidence/compression/qualification.stdout.json`; exact captured argv,
statuses and source/provider manifests are the `native-*` and `sanitize-*`
JSON files beside it. These passing cohorts were preserved on resumption;
all 47 repository source/header hashes in each manifest still match.
Each passed 31 captured commands including manual custom compilation/link,
normal `clang-driver.py` dispatch and the actual `./minyar` launcher. Both
normal and seven-byte codec chunks qualify exact caps/trailers, empty gzip
members, guards, mutation/truncation, optional gzip header CRC, zlib FDICT,
zstd checksum/skippable/concatenation/dictionary-ID diagnostics, explicit RAW
magic-prefix by-copy mutation, error recovery and dictionary-close after an
incomplete operation. Native C runs 4,000 deterministic mutation cases per
chunk; Python oracle tests compare 400 zstd and 800 gzip/zlib mutations per
chunk, with accepted outputs checked independently. Minyar tests include safe
copied-owner close, repeated raw DCtx use, invalid ranges/levels, complete
buffer APIs and partial Into writes.

Sanitizer mode annotates actual generated IR, then builds binding and runtime
with ASan/UBSan, and runs all three Minyar link routes. The separately identified
ctypes oracle cohort and distribution codec archives are unsanitized. Source
hashes for 47 files match the retained manifests; the compiler and selected
static archives are bound in those manifests. This is Linux qualification;
Windows UCRT64/CLANG64 qualification and full platform/global regression gates
remain with WS7/integrator. A small macOS contract/guard smoke also passed using
the existing `/Users/luke/Projects/Minyar-Lang/build/minyarc` and manual linking;
no compiler rebuild or local benchmark was run.

Static providers in the Linux evidence:

- `/usr/include/zstd.h` (zstd 1.5.5), actual
  `/usr/lib/x86_64-linux-gnu/libzstd.a`, SHA-256
  `3b002d21b06091605db4a98c3739b479bd1126bac91b389a9e4a9e75612848ab`.
- `/usr/include/zlib.h` (zlib 1.3), actual
  `/usr/lib/x86_64-linux-gnu/libz.a`, SHA-256
  `d9f5f6208214a493583f305c40c9879bfad2cada1ef2753a45e3b0bf8a4c7be2`.

Provider tests reject missing absolute archives and deliberately mismatched
header/library versions. The normal native object cache includes the provider
header/archive fingerprint. Advanced zstd dictionaries use static APIs; the
C reference explicitly uses RAW/byCopy CDict/DDict with usingCDict/usingDDict.

The first quiet prebuilt benchmark used five alternating samples of 128 full
operations at 64 KiB. Parent admission followed SHA/tar quiescence ACKs; full
prestart process inventory at 14:32:27.023 UTC found no live WS5 builds/tests.
`cmd_thtlo1wqd9to`/PID33422 passed 14:33:01.679–14:33:03.817 UTC. Shell bounds
are 14:33:01.710820445–14:33:03.816805738 UTC. The command was:

```sh
flock /tmp/ws5-benchmark.lock python3 benchmarks/compression.py \
  --artifacts evidence/bench-primary --run-only --samples 5 --rounds 128
```

All paired result counts matched. Binding/C median ratios ranged 0.739–1.101;
dictionary reuse compression/decompression was 0.977/1.015 and separate
construction 0.856. Raw samples showed CV 3–27%, so these short intervals do
not support percent-scale speed claims or the project's 1% regression gate.
The native selection does not rely on an invented pure-code timing: there is
no pure compression candidate. Benchmark source/provider/corpus hashes and
every ns sample/argv are retained in `docs/evidence/compression/bench-primary.json`.

The longer quiet run used the same verified preparation, 64 KiB corpus and
five alternating samples, with **4,096 operations per sample** for all 21
cases. The 128-operation JSON was preserved before the Boat results path was
reused. All 29 prepared source/compiler/provider/executable/corpus hashes
matched immediately before the run; the full 15:07:33.532839 UTC process
inventory showed no workstream build/test/benchmark jobs. Parent admission
followed tar's terminal/quiescent acknowledgment and the reviewer's no-Boat
acknowledgment. No compilation or provider discovery occurred during timing.

```sh
flock -n /tmp/ws5-benchmark.lock python3 benchmarks/compression.py \
  --artifacts evidence/bench-primary --run-only --samples 5 --rounds 4096
```

Boat `cmd_255yip8x7hze`/PID 43754 exited 0, 15:08:00.178–15:08:37.531 UTC;
shell bounds were 15:08:00.198105999–15:08:37.530808115 UTC. All **105 pairs**
had identical result counts. Binding/C median ratios ranged **0.953–1.085**;
dictionary reuse compression/decompression was **0.953/0.981**, and separate
dictionary construction was **1.085**. Sample CVs ranged 0.40–17.19%; the
largest was Minyar dictionary construction. These measurements quantify
binding/allocation overhead on this corpus. They still do not establish
percent-scale speed differences, the project's 1% regression gate, or a
pure-code preference comparison. No further benchmark was started.

`docs/evidence/compression/bench-long.json` retains every raw ns sample/argv
and the unchanged preparation manifest. The sibling `bench-long.log`,
`bench-long.bounds.log`, `bench-long.prestart.json`,
`bench-long.processes.before.txt` and `bench-long.boat.json` retain stdout,
UTC bounds, input verification, process inventory and terminal job status.
The quiet slot was released to the parent only after terminal status.

The parent owns the shared driver helper, `build-support/formats.mk`, progress,
dogfooding gap updates, shim migration note and all merge requests. This branch
only adds the codec driver dispatch and matched-provider selector needed by
these modules. The parent will reconcile its SHA/tar driver hunks. A fresh
independent implementation review is required before a merge offer; none is
claimed by these test results.
