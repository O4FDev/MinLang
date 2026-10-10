# Remote managed graph candidate evidence

Source branch: `feat/v2-managed-graphs`, based on foundation `32dadce`
(cherry-pick of `e8787355f74557ae9e5cf3862518318b9c58496d`).
Host: Ubuntu 24.04 x86_64, Linux 6.8.0-142-generic, two dedicated vCPUs,
4 GiB RAM. Toolchain: Ubuntu Clang 23.1.2, GCC 13.3.0; matched LLVM 23
opt/llvm-cov/llvm-profdata. Captured 2026-10-10, around 15:30 UTC.
These checks ran remotely; no laptop runtime execution was used for this
validation. The source hashes in `coverage.json` identify the measured core.

`callbacks-launcher-final.log` records 18 callback checks at native O0/O2 and
ASan/UBSan O0/O2, plus the optional compiler stage2/stage3 fixed point.
`launcher-final.log` records the final three launcher tests: system/fixed/eager,
POSIX lazy, and incremental/check fallback. `mutation-final.log` records a
passing control and three deliberately faulty compilers detected for their
intended reasons, including real use-after-free at both optimization levels.
The idle, nested generic dispatch and feature-looking value-name regressions
retain their initial failing output alongside subsequent passing suites.

`collector-profiles.log` preserves the native/sanitized four-heap matrix at
budgets 1/32 and seeds 314159/4294967295 (eager uses its one profile). Every
run uses independent reachability and exact object/byte/debt accounting.
`domains-service-green.log` covers owner entry, foreign callback/environment
rejection, unique IDs and direct bounded idle cycle reclamation.

`default-runtime-identity.log` compares O2 system-heap ordinary runtime objects
compiled from the saved foundation runtime archive and candidate runtime.
Both SHA256 values are `42b29918246ca3d4ea99508ad4e77b971bf424f5b12821904afe1d71d070c61d`.
The managed graph suite additionally compares exact LLVM for ordinary JSON,
acyclic recursive trees, record/List mutation and a user record named Callback.

`coverage.json` reports all original gates unchanged: compiler edges
2305/2892 (79.70%, minimum 79%), ordinary eager-runtime lines 1278/1583
(80.73%, minimum 72%) and branches 524/792 (66.16%, minimum 55%). Both
instrumentation orders preserve the self-hosted fixed point. No compiler
guard/function is excluded. This is the established ordinary-runtime coverage
configuration, not a coverage claim for the opt-in collector or native bridges.

The selfcompile/PMU files are **earlier paired measurements before moving
collector emitter bookkeeping out of the ordinary frontend**. They are not
measurements of the final candidate. Foundation/candidate wall and CPU p90
pass 25/22 ms ceilings, but **both fail** the unchanged Apple-calibrated
10 MiB RSS limit on this Linux host. The available x86 PMU user instruction
counter differs from the macOS retired-instruction metric. Do not report a
passing absolute performance gate from these results. Compatible macOS
performance validation and native Windows execution remain required before
merging the candidate.
