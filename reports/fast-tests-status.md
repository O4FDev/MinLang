# Fast tests: status

Goal: the full gate (`check-portable` + the benchmark checks: the 8 targets of the single-box gate queue, 340
checks) in ≤ 300 s wall with the same pass/fail as a single-box gate. Command: `tools/fast-gate.sh TREE`.

## 2026-10-31 20:45 UTC

### Done
- **Shard image** `252387913` (`shard-image-20261031a`): the gate boxes' provisioning (LLVM 23.1.3 + FileCheck,
  Rust, the apt set), user `agent`, no apt timers, base tree 160ab1d42 for delta syncs. Boot to SSH: 65 s.
- **Parity of the image:** a single-box gate of int14 (160ab1d42) on a shard from the image agrees with box M's
  recorded int14 gate on all 340 checks (both red only on the box-environment `check-determinism-runtime` and its
  aggregate `check-portable`), 24.6 min.
- **`tools/fast-gate.sh`** (`tools/fast-gate/`): creates `shard-*` droplets tagged `test-shard`, sends the tree as a
  delta against the image's base, runs the tree's own `make check-in-parallel` over the full check list on every
  shard with a PATH `make` shim that finishes the checks and shared builds packed onto other shards at once
  (`plan.py` reproduces check-in-parallel's plan: 340 checks; `pack.py` longest-first by int14's times), merges the
  verdicts (an aggregate passes when its own recipe and every check under it passed) and deletes every droplet of the
  run on any exit. Multi-tree runs reuse one set of shards. Tested end to end on one box; 2-shard skip/merge test
  correct.
- **Recorded gates preserved** (the `loop-*` boxes go at 21:30): 30 runs' times.tsv/status, each tree matched to its
  commit by file hashes; manifest `~/Projects/minyar-fast-tests/recorded/manifest.tsv`. Proof trees as worktrees in
  `~/Projects/minyar-fast-tests/trees/`.
- **Where the CPU goes** (process accounting over the full gate): clang 72%, linkers 12%, make 3%, minyarc 0.6%
  (10,204 compiles at ~5 ms each). The Minyar compiler is not the bottleneck; LLVM is.
- **Compiler build:** two serial single-module ThinLTO links (~45 s each). Linking the bootstrap stage1 unoptimised
  (cde8375a9) emits byte-identical stage2 IR and cuts the cold build from 92 s to ~50 s. llvm-split + parallel
  ThinLTO did not help (one partition holds the big functions).

### Numbers
| measurement | value |
| --- | --- |
| single-box gate, 8 vCPU | 24.6 min (probe), 26 min (box M) |
| check CPU sum | 9,192 s; shared builds 533 s; compiler build 92 s → ~50 s |
| shard boot (snapshot) to SSH | 65 s |
| tree delta sync laptop → shard | 10 s |

### In progress
- 4 Wafer agents split the 19 checks above ~90 s CPU into ≤ 60 s pieces (reports in
  `~/Projects/minyar-fast-tests/reports/split-*.md`), dev box shard-probe-1.
- `fgcc` (tools/fast-gate/fgcc): content-addressed cache in front of clang (log / cache / verify modes); goes into
  the next image so every box has the same toolchain identity.
- Cache box `shard-cache`: builds and plans at t=0 while shards boot (written, not yet run).

### Blockers / asks for Luke
- **Droplet limit 10** (account): at most 8 shards + shard-cache. A higher limit would let a cold gate fit 300 s
  without depending on cache hits.
- **Guard accounting:** test-shard-guard charges every shard a full hour (8 shards = $1.33 per gate, so ~6 gates a
  day inside $10 with shard-cache), while DigitalOcean bills per second since 2026-01-01 (a 6-min 8-shard gate costs
  ~$0.13). Counting per second (60 s minimum) would allow ~60 gates a day for the same money. Luke's call.
