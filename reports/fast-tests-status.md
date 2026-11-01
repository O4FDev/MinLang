# Fast tests: status

Goal: the full gate (`check-portable` + the benchmark checks: the 8 targets of the single-box gate queue, 340
checks) in ≤ 300 s wall with the same pass/fail as a single-box gate. Command: `tools/fast-gate.sh TREE`.

## 2026-11-01 03:00 UTC

### Timing (the full 8-shard plan run in waves on 2 boxes, projected to one box per shard)
`tools/fast-gate.sh --shards 8 --boxes 2 TREE` runs the same 8-shard plan two shards at a time; `estimate.py RUN`
projects it: max(box ready 64 s, cache box done) + the slowest shard (pull → done) + 5 s.
| run | change | slowest shard | projected | verdict |
| --- | --- | --- | --- | --- |
| waves1 (14dd401cf) | first 8-shard plan, critical-path order (cache box done at 83 s) | 317 s | 405 s | green |
| waves2 (e0debc410) | heavy shared builds beside the checks (cache 89 s) | 252 s | 346 s | green |
| waves3 (7ef381401) | aggregate tails, 4-module compiler link | 247 s | 316 s | `check-net-loop` flake (4/4 green alone; REQUESTS.md row) |
| waves4 (d035852f0) | parallel deferred chains, ssh multiplexing | 214 s | 283 s | green: 440 checks, 0 failed |
| waves5 (7d9f971ca) | check-portable children kept apart (wrong model, see below) | 264 s | 333 s | green |
| waves6 (23997f4c3) | drain model, rebalancing passes, median times | 222 s | 291 s | green |
| waves7 (4cb66bb14) | `check-portable-core`, a 9th shard on the cache box | 203 s | **272 s** | green: 441 checks, 0 failed |
- Cache box (s-4vcpu): synced at 6 s, compiler + plan done at 48–54 s, before the shards are up (64–72 s to SSH).
- **check-portable waits for its whole shard.** It sits above 436 of the 440 checks, including the runner's
  exclusive `check-net-udp-offload`, which starts only once no other check runs on the shard, even where the shim
  skips it. So check-portable's own 48–57 s single-threaded recipe always ran last on its shard (waves5: 216 → 264 s),
  and the runner's priority propagation pushed the 3 checks outside it (ablation-switches, benchmarks) to the end of
  every shard. Fixed in the product (5f12d1ee3): the recipe is now its own check, `check-portable-core` (same command;
  check-portable fails if it fails). The plan grows to 441 checks.
- **The cache box runs a 9th shard** (4cb66bb14) once it has built and planned: 4 jobs at 0.70 of a shard core
  (measured), only short checks with known times, nothing that measures time or budgets or uses a sanitizer build,
  in its own copy of the tree (the copy it serves is untouched). waves7: its 16 checks done at 224 s.
- Shard boxes are shared-CPU: the same checks cost 9,386–10,163 CPU-s from run to run (±4%). The packing table now
  takes each check's median over runs, less the time the shim held it for deferred builds.
- Product change on this branch: `tools/compiler-link.sh` links minyarc and scope-compiler as 4 ThinLTO modules in
  parallel (identical stage3 output; cold compiler build 49 → 29 s on 4 vCPU).

### Since 03:00
- Rehearsal on the new machinery (8-shard plan in waves + the cache-box shard): batch 9 (10 reds incl.
  check-last-use-sinks) and int13 (5 reds incl. check-statement-nesting out of memory) **agree check for check**.
- **A fully green single-box gate recorded**: 5af3d8643, one s-8vcpu shard box, the loop's gate-queue.sh recipe
  (CHECK_JOBS=7): 441 checks, GATE-EXIT 0, 26 min. Added to recorded.tsv as tip-5af3d8643 (the earlier recorded
  gates are all red on check-determinism-runtime, fixed after them).
- Rebase rehearsal: goal/fast-tests onto goal/2026-10-30 f939afb71 applies cleanly (67 commits); its fast gate is
  green, 442 checks, projected 281 s (new goal-branch checks had no times yet; refreshed in e226fc1b6).

### Next
- Capacity is still 3 free droplets (account limit 10) until the run-2 boxes go at Sun 1 Nov 21:45 UTC, or until
  Luke raises the limit. Then: freeze, `time tools/fast-gate.sh TIP` on 8 shards (the verdict prints the time since the
  command started), the recorded trees on the same code, `agree.py`, and the rollout.
- Guard spend today: about $4 of $10 at 05:00; the proof and the merge gate need about $2–3.

## 2026-10-31 22:35 UTC

### Agreement so far (2 shards, image 252387913, compile cache off)
`tools/fast-gate.sh --shards 2 TREES…` then `tools/fast-gate/agree.py RUN` (records in `tools/fast-gate/recorded/`):
| recorded gate | commit | checks | red (fast = recorded) | wall on 2 shards |
| --- | --- | --- | --- | --- |
| int14 (box M) | 160ab1d42 | 340 = 340 | determinism-runtime, portable | 951 s |
| int13 (box M), c8 uncapped | 9c5e3b10d | 340 = 340 | + statement-nesting ("ran out of memory"), peer-regressions(-python-swift-ruby-lua) | 915 s |
| one-c1 (box N) | 724d3b883 | 340 = 340 | + memory-regressions | 910 s |
| c7 (box L, cake-base set) | 8631b46f5 | 337 = 337 | + last-use-sinks, quic-official-adapter, quic-rfc, record-reconstruction-reuse, structured-tasks | 877 s |
4 of 4 agree check for check. Batch 2 (image 252406632, real clang, cache off):
| batch 9 (box H, text record) | 2c2dd076b | 339 = 339 | + last-use-sinks, choice, choice-set-niche, ownership-name-proofs, quic-*, record-reconstruction-reuse, structured-tasks | 820 s |
| int12 (box K), c8 uncapped | 4b03b4fab | 340 = 340 | + statement-nesting, memory-regressions, peer-regressions(-python…) | — |
| one-c4 (box O) | 526b2f18f | 340 = 340 | + empty-map-traversal, scalar-record-reuse, public-release | — |
| one-c2 (box N) | 565a2528e | 340 = 340 | determinism-runtime, portable | 806 s |
8 of 8 recorded commits agree check for check. The integrated tip (ft-725b49172: all splits, stage1 -O0, rebased on
the determinism fix) is **green: 440 checks (all 340 reference checks + 100 pieces), 0 failed**, 854 s on 2 shards.

### Plan to the proof (capacity: 3 droplets until the run-2 boxes go, Sun 1 Nov 21:45 UTC)
1. Freeze the code; snapshot the tip.
2. As soon as 8 shards fit (limit raised, or Sun 21:45): `tools/fast-gate.sh TIP` with shard-cache → ≤ 300 s.
3. Then, same command and code, the recorded trees on 8 shards (~5 min each) + `agree.py` → ≥ 6 agree.
4. Merge into goal/2026-10-30 with that green gate; docs/dev-check.md, the playbook, REQUESTS.md rows.

### Since 20:45
- Rebased on goal/2026-10-30 518e2b500 (determinism fix). Integrated the Wafer splits: frame-initialization (6 pieces,
  longest 46 s), temporary-owner-cache, empty-map-traversal, owner-queue-batching, errors-*-bounded, quic-rfc(-sanitize)
  (6 each, longest 68 s; harness self-test kept once per variant), library-documentation (4, 76 s), last-use-sinks,
  record-reconstruction-reuse, scope-ownership, sequences, simulation-cli (6, 81 s), managed-graphs(-launcher),
  cycle-registration-exposure-sanitize, parallel-signatures, cycle-private-retirement-sanitize. Not taken:
  osdev-seeds-host (5 pieces cost +52 s CPU; 97 s unsplit fits). unicode-installed, installed-cli, cold-bootstrap stay
  whole (one dependent chain each).
- Shard timeline (shim start stamps): 6–8 cores busy in the main phase, but a 4–5 min tail because a fresh tree's
  runner starts its long checks last. Each shard now seeds `build/tooling/check-durations` (ordering only) so the
  longest checks start first.
- Image 252406055: same toolchain + fgcc (C) as the clang driver, off unless a run sets it.
- **Caught by the agreement runs:** with fgcc installed as `/opt/llvm-23.1.3/bin/clang` (image 252406055), batch 9
  disagreed on `check-native-cache` ("Clang fixture must exercise more than one retention chunk": the check retains the
  compiler binary itself as link provenance and requires it to be > 64 KiB; the 40 KB wrapper is not). Any wrapper at
  the toolchain's own path changes what checks observe, in every mode. Fixed: the image keeps the real driver there;
  fgcc sits at `/opt/fgcc/bin/clang` and a run that asks for it (`--cc-cache`) uses it only as the fixture Clang
  (`TEST_CLANG`, with `MINYAR_TEST_REAL_CLANG` real), the same route as the tree's own `MINYAR_TEST_CLANG_CACHE`. Batch
  2 rerun on the corrected image, cache off.
- fgcc test (5 checks, 3 passes): within one run 32 of 312 compiles were repeats, saving 74 of 306 compile-seconds
  (24%); every verified hit byte-identical. Across runs almost no hits: harnesses compile copies in random scratch
  directories, whose paths reach the outputs (so a cross-run hit would not be byte-identical, and the key rightly misses).

## 2026-10-31 20:45 UTC

### Done
- **Shard image** `252387913` (`shard-image-20261031a`): the gate boxes' provisioning (LLVM 23.1.3 + FileCheck,
  Rust, the apt set), user `agent`, no apt timers, base tree 160ab1d42 for delta syncs. Boot to SSH: 65 s.
- **Parity of the image:** a single-box gate of int14 (160ab1d42) on a shard from the image agrees with box M's
  recorded int14 gate on all 340 checks (both red only on `check-determinism-runtime` and its aggregate
  `check-portable`), 24.6 min. That red was real, not the box: three runtime helpers were missing from the determinism
  audit (fixed on the goal branch in 01a0bfe46, which goal/fast-tests is rebased on).
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

### For the Minyar loop's compiler-speed lane (run 2)
- In the full gate, `minyarc` itself is 0.6% of CPU (10,204 compiles, ~5 ms each); clang compiling and linking the
  IR it emits is 72% + 12% linkers. Cutting gate (and user build) time means emitting IR that is cheaper for LLVM,
  not a faster front end.
- The compiler's own cold build is two ~45 s single-module ThinLTO links. `clang -O2 -c build/compiler-stage2.ll`
  (no LTO) takes 20.8 s; with ThinLTO the post-link backend alone is 46.7 s. No single huge function (largest
  ~5,000 IR lines of 444k): the cost is spread over ISel (20%), RA, InstCombine.
- Fast-tests already takes the bootstrap stage1 off the critical path (cde8375a9: linked -O0, identical stage2 IR).

### In progress
- 4 Wafer agents split the 19 checks above ~90 s CPU into ≤ 60 s pieces (reports in
  `~/Projects/minyar-fast-tests/reports/split-*.md`), dev box shard-probe-1.
- `fgcc` (tools/fast-gate/fgcc): content-addressed cache in front of clang (log / cache / verify modes); goes into
  the next image so every box has the same toolchain identity.
- Cache box `shard-cache`: builds and plans at t=0 while shards boot (written, not yet run).

### Blockers / asks for Luke
- **Capacity until Sun 1 Nov 21:45 UTC: 3 droplets.** The account limit is 10; brief-crawl-1 and the six
  `goal-run2` boxes use 7. The ≤ 300 s run needs about 8 × s-8vcpu shards (64 vCPU: the gate is ~9,800 CPU-s), so
  it waits for the droplet-limit increase to ~20 (already on the list) or for the run-2 boxes to go at Sun 21:45
  (the account offers no CPU droplet above 8 vCPU, so fewer, bigger shards are not possible).
  Meanwhile: agreement proofs on 2 shards (same machinery, same verdict logic), the dev box for check splits, the
  compile-cache image.
- **Guard accounting:** test-shard-guard charges every shard a full hour (8 shards = $1.33 per gate, so ~6 gates a
  day inside $10 with shard-cache), while DigitalOcean bills per second since 2026-01-01 (a 6-min 8-shard gate costs
  ~$0.13). Counting per second (60 s minimum) would allow ~60 gates a day for the same money. Luke's call.
