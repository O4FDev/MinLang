# Text and List.clear verification

Implementation: `13d9e9a`, LLVM 22 on owned Linux Boat `bx_ez43hrrp`, under
the WS3 serial build lock. `provenance.json` records the source and built
artifact hashes and confirms the remote source matches that commit.

The native independent Python model checks 581 cases across ordinary/traced
heap profiles, including malformed UTF8, signed parsing bounds, KMP prefix
inputs, aliases, exact managed ownership and progressive cyclic List.clear.
Frontend tests and four fixed points passed, together with the four frozen
exact-LLVM cases. Verification logs preserve failed intermediate attempts as
well as the corrected final run.

`text-basics-benchmark.json` and `benchmark-r1.log` preserve the failed
compiler diagnostic, ratio 1.014865715. After the narrow compiler call-path
optimization, `text-basics-benchmark-r2.json` records 31 alternating paired
batches of 16 identical-source compilations after warmup, ratio 0.995569069
against the unchanged 1.01 gate. Every generated LLVM result is checked for
byte equality. The retained fixture checksum is 11,200,000; the separate
repeated-prefix fixture checksum is -64. The raw samples include scheduling
outliers without filtering.

These diagnostics and new API workloads do not discharge the parent integrated
five-workload performance gate. Native macOS/Windows remain pending admitted
platform routes. The native Atacama GUI gate additionally needs an existing
permitted WindowServer/AX environment.

Generated executables and LLVM artifacts listed in `ARTIFACTS.sha256` were
captured in the owning worktree and Boat evidence directory; the repository
keeps the small textual logs, raw receipts and hashes rather than generated
binaries.
