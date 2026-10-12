# WS4 systems library

Started 2026-10-12 from frozen unified candidate `bf9c0e9` on `ws4/systems-library`.
Integrator: `mcp:b814e5f7-fef7-4fcd-8d92-66fa4104f2d1`. Only the integrator merges and pushes `v2`.

## Baseline

The neo-db fork's durable files, ranged reads, background syncer, shutdown signal socket,
stderr writer and open-file limit raiser are in this candidate. Existing regressions:
`tests/files-system.min`, `tests/files-review.c`, `tests/files-sync-failures.c`,
`tests/system-review.c`, `tests/neodb-packages.py`, `tests/neodb-review.py`.
The launcher currently rejects `files` and `system` on Windows.

## In flight

Owner released development and Boat testing on 2026-10-12. The earlier development
hold is revoked; only merging into `v2` waits for Phase 1. All three implementation
children have resumed in their existing worktrees from `bf9c0e9`.

- `ws4/files`, isolated `ws4-files`: preallocation, background prepare-file worker,
  Windows files backend, ranged-read and worker lifecycle regressions.
- `ws4/system-process`, isolated `ws4-system-process`: environment/getenv, rlimit
  controls, portable system services, safe spawn and wait, child SIGPIPE isolation.
- `ws4/http-server`, isolated `ws4-http-server`: reusable event-loop HTTP/1.1 server,
  protocol regressions, equivalent Minyar/Rust axum cache-front fixtures and p50/p99 gate.
- Parent coordinates independent reviews, Boat platform checks, benchmark evidence,
  the merge queue and downstream gap annotations. At most three child tasks run at once.

## Merge requests

None yet. Each chunk requires independent review and source-bound platform evidence.
No new code has been merged into `v2` by this workstream.

Implemented chunks, awaiting review/remaining qualification:

- Files `8283581` + `35c7378` (`6141695` evidence): Linux 70 native and 35 sanitizer
  controls plus retained review/sync-failure cases pass; Mac 68 native/34 sanitizer pass.
  Independent R1 found a sparse-prefix Darwin preallocation false-success bug; fix and
  a new mandatory regression are underway before a fresh review. Windows companion pending.
- System `d3f7b9`, process `055ada54` with qualification companions through `0944f8f`:
  environment/rlimits/signals/stderr and safe spawn/waits implemented. Mac unprivileged
  and Linux services/language cases pass; source-pinned process/sanitizer/root cases are
  running after retained compiler-stamp and canonical runtime ABI helper diagnoses.
  Native Mac privileged credential success still needs an admitted platform route.
- HTTP `a1edb5d` + `0f50104` evidence: reusable event-loop server API and mandatory wire
  tests pass Linux debug/release and ASan/UBSan/LSan. The actual library cache-front and
  equivalent axum benchmark fixture are in progress. Windows/Mac execution pending.

## Gates and coordination

- `PHASE1_DONE` gates integration, not development or tests. Keep branches on the
  frozen candidate until the integrator releases the pushed `v2` base, then rebase.
- Owner admitted separate WS4 Boat sandboxes on included credit, with $0 paid spend.
  Linux qualification sandbox `bx_ppv9fjr7` is provisioning (4-hour TTL). Root's
  Phase 1 boxes and their controllers/VMs remain forbidden to WS4. Windows needs
  the root-arranged completed snapshot/fork boundary; WS4 will not operate Y.
- Own Windows recipient `bx_r5nrrwwx` (8 CPUs / 16 GiB, 4-hour TTL) has authenticated
  transfer ingress and 121 GiB free. Root admitted a private verified immutable-base/profile
  relay from WS7's separate box after its source receipt. No bytes/Windows boot or test
  readiness is claimed yet; WS4 creates and owns its eventual overlay/controller.
- `tools/clang-driver.py` has overlapping minimal files/system routing edits; parent
  resolves them when assembling chunks. WS5 adds zstd/deflate registration separately.
- Acceptance remains Linux/macOS/Windows suites, HTTP p50 and p99 both at most 1.5x
  equivalent axum, ordinary single-thread workloads within the shared 1% budget,
  reviewed integrator merges and truthful `fixed in v2 <sha>` gap annotations.

## Preserved work and review findings

- `ws4/files` has `82835810e2cfef2161636881637a8cd18d1eb45c`: bounded allocation at
  EOF for ranged reads. Five focused Mac controls passed; no independent review or
  Linux/Windows qualification yet. The prepare-file prototype and its seven Mac
  controls remain uncommitted; startup/durability fault injection and real event-loop
  integration are still required. New tests also need mandatory Make/catalogue wiring.
- System and HTTP worktrees are fully populated and clean at the frozen base.
- macOS public `spawn.h` lacks arbitrary credentials, but Apple's XNU private header
  declares direct uid/gid/groups spawn attributes since 10.15 and the local SDK exports
  them. Investigate a bound SPI path with permission/lifecycle tests before concluding
  the feature is unsupported. No working macOS credential-spawn result is claimed.
