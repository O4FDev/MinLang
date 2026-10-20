# FBIP reconstruction reuse — isolated measurements

The implemented optimization eliminates 10,000 scalar-record allocations in a uniquely owned reconstruction loop. **It produces zero eligible reuse sites in the frozen compiler, c2min or safelibs workloads, and no meaningful workload speedup.** The tiny instruction changes below are reported rather than attributed to record reuse. Primary BX lease was explicitly returned after every build, counter, timing, synthetic and archive command terminated successfully. No slot 2 or local builds/tests.

## Isolation and correctness

- Candidate: `99640be776ba2d05a06bad9e01f33e9b7d36cb7e`; qualified compiler SHA256 `95d73795963a7e2700aafc15636d83c1e88dc0ba27e4ac685c508d8b9beeb22a`, bundle `11a9992fdac7518831db90e65feae2a0acbc484451d25c96129e5ad07a1ca15f`.
- Control: `4810a4399924e18c3b607a2f901416a006da771e`; freshly rebuilt compiler SHA256 `4406677e56d519b73b37401dc4d5ee0b82afaf5cc316d8685fcfb0dc8e0fb9f1`, bundle `826746e9c2173e3336e9c1a23eac52a7c49884d268e693c3bbeb95f634a3d080`. It restores only the five frontend files changed by the FBIP commit. The shared scalar-reuse runtime helper is present in both arms.
- Both compilers passed independent stage-2→stage-3 LLVM fixed points. Parent's qualified candidate feature matrix is separate; both arms additionally rebuilt and passed full frozen c2min O2 native qualifications and safelibs' 1,515 guarded checks, incumbent-header/four-thread ABI and range checks. No baseline executable was silently substituted for the freshly qualified control.
- Runtime/header tree, bundle-contained scope pass, canonical source/library, exact compiler/runtime/link flags, native operation counts, environment and codec output hashes matched across arms. The comparator rejects mismatches. Scope-pass SHA256: `7e63951c2de3ff60308bafbfc5875b6e6713f81168a56fa7d74c0a45ba2840ea`.
- Snapshots precede the independent contracts/local-`match` correctness repair. Parent later source edits never entered these artifacts. No peer coalescer/runtime improvement is attributed to FBIP.

## Compiler self-compile

All arms compile the same frozen 909,894-byte source `826746e9…` and library, using O2 + ThinLTO with LLD threads=1. True eager runtime has **no heap defines** and explicit `--scope-owners`; arena uses `MINYAR_COMPILER_ARENA`; the additional scoped bounded profile uses `MINYAR_SYSTEM_HEAP=1`. Runtime target-CPU/features attributes are normalized as in the maintained release runtime recipe.

One warmup and five retained hardware samples per profile, alternating profile order. Direct pinned user-space `perf_event_open` counters exclude Python/hash/link/kernel work; all 156 observations across both full campaigns have enabled time exactly equal to running time, with no scaling. No competing build or benchmark ran on the box during counters.

| Profile | Control retired instructions | FBIP retired instructions | Change |
| --- | ---: | ---: | ---: |
| Arena | 1,364,876,535 | 1,364,592,825 | -0.02079% |
| True scoped eager | 3,258,832,047 | 3,258,892,625 | +0.00186% |
| Scoped SYSTEM_HEAP/bounded | 3,907,104,329 | 3,907,174,860 | +0.00181% |

True eager/arena is 2.38764× control and 2.38818× candidate. There are **zero actual `minyar_record_reuse_scalar_take` call sites** in both compiled compiler graphs and both canonical self-compile outputs. The arena difference reflects frontend/code-layout work, not runtime record reuse; eager has a tiny measured overhead rather than a gain.

All three profiles within an arm emit identical LLVM: control `9999f24f295f243be34134af70d516c03a3d6fa69405724f5b064f120c19c455`; candidate `f919dd3cefae10584ef48be4fbbebe6557050e2320241499d671bd53bfc5ff75`. Different arms may intentionally emit different declarations/lowering. Independent compiler fixed points and semantic/native qualifications establish correctness; raw hash identity across arms is not falsely asserted.

Historical **171M arena** is retained as reference only. Its earlier Apple-era source/machine differs; frames' earlier approximately 1.188B arena also uses a smaller compiler input. Neither is the denominator for these newer matched counts. The earlier setup report's 3,907,102,953 was mislabeled eager: it was scoped SYSTEM_HEAP/bounded. That report has a visible correction; original raw evidence remains unchanged.

## Frozen byte-heavy products

Frozen c2min `53bdcf2890ee1a0f9b6d53f80f9108f83ff1e9e0` and safelibs `a9472dd7285f8464ed9471eaaa842eb45a9512d2`, unchanged API adapters and O2/noLTO default bounded runtime settings. Product sources/library/fixtures do not follow moving product heads. Both product generated graphs contain **zero eligible reconstruction sites**.

Hardware numbers below cover the full native child, including setup/preflight/output validation. Every same-arm workload has one warmup and five retained observations. Fixed operation counts are identical across arms; do not read whole-child totals as pure decoder-loop instructions.

| Workload | Operations / child | Control instructions | FBIP instructions | Change |
| --- | ---: | ---: | ---: | ---: |
| Tokenizer 1,024 tokens | 2,000 | 8,986,211,921 | 8,986,641,308 | +0.00478% |
| Tokenizer 16,384 tokens | 200 | 14,411,792,302 | 14,411,700,002 | -0.00064% |
| Inflate 1 MiB | 29 | 4,368,971,119 | 4,368,987,443 | +0.00037% |
| PNG 512² RGBA | 16 | 4,798,752,129 | 4,798,783,444 | +0.00065% |
| JPEG 512² RGB444 | 4 | 6,616,102,249 | 6,616,096,023 | -0.00009% |

Native timing was measured separately after PMU collection: one warmup then nine seeded-random alternating control/candidate pairs, one available CPU, exact same fixed operation counts and native warmed in-process loops. No noisy single-call measurement or timing acceptance threshold. Complete byte/checksum validation and zero-live-object checks passed. Median times and median paired ratios are distinct statistics:

| Workload | Control ms / operation | FBIP ms / operation | Median paired FBIP/control |
| --- | ---: | ---: | ---: |
| Tokenizer 1,024 | 0.216963 | 0.214002 | 0.98359 |
| Tokenizer 16,384 | 3.622058 | 3.615051 | 0.99942 |
| Inflate 1 MiB | 7.966888 | 7.910360 | 1.02781 |
| PNG 512² | 13.556146 | 13.479202 | 0.99609 |
| JPEG 512² | 57.461985 | 57.092145 | 0.99430 |

The inflate paired ratio can exceed 1 even when the ratio of independent medians is below 1; raw pairs retain that variation. Given zero eligible sites and effectively unchanged retired work, these timings do **not** establish a FBIP product improvement.

## Actual generated-code allocation and RC counts

Ten-thousand-iteration programs compiled by each frozen compiler, at O0/O2 and both legacy/scoped lowering: 16 cases total. Every binary links the **same instrumented true-eager runtime object**. Counters observe actual scalar-record allocation requests, actual reference-count increments/decrements (including scoped fast decrements) and helper calls/hits. Destructors assert no active frames/scopes, no pending work and only immortal objects remaining. Persistent-alias programs retain every previous record in a List and verify every saved field after reconstruction.

The following values are identical at both optimizations and lowerings:

| Case / arm | Scalar-record allocations | Requested record bytes | RC increments | RC decrements | Reuse calls / hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unique control | 10,001 | 320,032 | 0 | 10,001 | 0 / 0 |
| Unique FBIP | 1 | 32 | 10,000 | 10,001 | 10,000 / 10,000 |
| Persistent aliases control | 10,001 | 320,032 | 10,000 | 20,002 | 0 / 0 |
| Persistent aliases FBIP | 10,001 | 320,032 | 10,000 | 20,002 | 10,000 / 0 |

This slice avoids 10,000 allocations and 320,000 requested bytes in the unique case, but **adds 10,000 RC increments** there. The shared helper intentionally retains/releases before returning the reused record to preserve its service protocol. It does not reduce decrements in this probe. Aliases still allocate; no mutation-through-alias regression or retained object is hidden. Bytes are allocator requests including record headers, not RSS or allocator-internal overhead. No synthetic timing claim.

## Evidence and reproduction

Remote immutable campaign root: `/home/user/w/perceus/build/perceus-measurement-20261020` (`R`). `R/fbip/candidate/tree` and `R/fbip/control-tree` retain full source/bootstrap artifacts. `R/runs/fbip-{control,candidate}` retain all profile LLVM/binaries, product copies/builds, native manifests, every raw counter/output and command log. `R/fbip/{comparison,timings,eligible-sites}.json` and `R/fbip/synthetic/results.json` are the concise machine-readable results.

Full paired artifact archive copied locally and SHA256 verified: [perceus-fbip-evidence.tar.gz](/Users/luke/Projects/minyar-moonshots-20261020/reports/perceus-fbip-evidence.tar.gz), 58,971,917 bytes, SHA256 `aafbcc1e65f059ab1edca73a2cef09b3d6f7ba8650db9f185d83fbe4f4ef2654`. Extracted under `reports/perceus-fbip-evidence`. A convenient comparison copy is `reports/perceus-fbip-comparison.json`.

Reruns require explicit primary lease and fresh labels/output directories. From the compiler worktree:

```sh
C='/Users/luke/Projects/minyar-moonshots-20261020'
BX_TIMEOUT=1800 "$C/bx" perceus python3 'experiments/memory/perceus-fbip/perceus-measure.py' \
  --label 'fbip-control-repeat' \
  --compiler 'build/perceus-measurement-20261020/fbip/control-tree/build/minyarc' \
  --bundle 'build/perceus-measurement-20261020/fbip/control-tree/build/compiler.min' \
  --runtime-root 'build/perceus-measurement-20261020/fbip/candidate/tree'
```

Repeat with the frozen candidate executable/bundle and a distinct candidate label, then use `perceus-compare-measurements.py` on their summary JSON files. Frozen input/library/products stay fixed across later slices. Scripts `perceus-fbip-counts.py` and `perceus-fbip-finish.py` preserve the original generated-code/count/native timing reproduction; their first-run output directories refuse overwrite.
