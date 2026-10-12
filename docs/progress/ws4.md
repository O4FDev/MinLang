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
  Independent R1 found a sparse-prefix Darwin preallocation false-success bug.
  Separate fix `ab22fb9` (`462c99d` evidence) passes Mac 82 native/41 sanitizer and
  Linux 84 native/42 sanitizer controls, plus retained checks. Fresh independent R2
  review resolved the sparse-hole finding, but found a mapped APFS clone prefix can
  still need new overwrite storage. A separate clone/reservation fix and mandatory
  control are underway. Windows companion pending.
- System `d3f7b9`, process `055ada54` with qualification companions through `68948fb`:
  environment/rlimits/signals/stderr and safe spawn/waits implemented. Mac unprivileged
  and Linux services/language cases pass; source-pinned process/sanitizer/root cases are
  qualified at exact `68948fb` with all six source-pinned suites and the existing
  instrumentation audit passing. Fresh independent R1 found two P1s: arm64 kernel
  signal-action layout is undersized, and TSan inserts a child function-entry call.
  Separate fixes and expanded mandatory ABI/zero-call controls are underway.
  Native Mac privileged credential success still needs an admitted platform route.
- HTTP `a1edb5d` + `0f50104` evidence + benchmark `283a5ad`: reusable event-loop server
  and mandatory wire tests pass Linux debug/release and ASan/UBSan/LSan, plus small Mac
  wire/cache-front checks. The full cache-front gate passed on exclusive own Boat
  `bx_8b8ercp7`: three alternating paired rounds, all five cohorts, both p50 and p99
  within 1.5x axum. Pinned 548-query/raw replay bodies, LRU and causal/concurrent HoL
  controls passed. Command `cmd_bi3qixj4jzoc`, PID 33738, exited 0 at 15:08:04 UTC.
  Immutable compiler `f4f589` and runtime IR `4119757` were invoked directly; the
  earlier launcher-rebuilt shared correctness compiler `0b8bd2` is recorded separately.
  Samples/evidence committed in `bd43f2b`; worst ratio is 1.304x. Fresh independent R1
  review independently reproduced all 16,434 samples/gates, but found a write-phase
  half-close/backpressure HUP spin. The separate fix's combined regression is green;
  exact source `1751f1e` passes Linux debug/release/sanitizer and Mac native tests.
  Its full benchmark rerun failed hit p99 at 1.6303x (188.1/115.4 us); all other nine
  cells pass. All failure samples are retained. Generic small-response coalescing
  `f6d9dfb` passed the complete unchanged gate (worst 1.103x); binary packing
  boundary tests `64bb2e9` and evidence `2e7a50f` preserve all prior failures.
  Fresh independent R2 review is running; the final Linux debug/release/sanitizer
  and bounded Mac native checks pass.
  Windows execution pending.

## Gates and coordination

- `PHASE1_DONE` gates integration, not development or tests. Keep branches on the
  frozen candidate until the integrator releases the pushed `v2` base, then rebase.
- Owner admitted separate WS4 Boat sandboxes on included credit, with $0 paid spend.
  Linux qualification sandbox `bx_ppv9fjr7` has a verified read-only baseline and
  separate files/system/HTTP namespaces. Root's
  Phase 1 boxes and their controllers/VMs remain forbidden to WS4. Windows needs
  the root-arranged immutable transfer boundary; WS4 will not operate Y.
- Own Windows recipient `bx_r5nrrwwx` (8 CPUs / 16 GiB, 4-hour TTL) has authenticated
  transfer ingress and 121 GiB free. Root admitted a private verified immutable-base/profile
  relay from WS7's separate box after its source receipt. No bytes/Windows boot or test
  readiness is claimed yet; WS4 creates and owns its eventual overlay/controller.
  WS7's own task public key is installed with forced receive-only rsync restricted
  to the recipient root through a serial 75% resource guard. Source verification
  failed before admitting all eight hashes; no transfer or retry is authorized.
  Receiver remains empty and is normal-stopped with authorization preserved by
  integrator order. No binding/Windows boot readiness is claimed.
- `tools/clang-driver.py` has overlapping minimal files/system routing edits; parent
  resolves them when assembling chunks. WS5 adds zstd/deflate registration separately.
- Acceptance remains Linux/macOS/Windows suites, HTTP p50 and p99 both at most 1.5x
  equivalent axum, ordinary single-thread workloads within the shared 1% budget,
  reviewed integrator merges and truthful `fixed in v2 <sha>` gap annotations.

## Review and remaining proof

- Files independent R1 reproduced Darwin preallocation returning success for an
  existing sparse prefix without reserving it. The fix inspects physical extents,
  flushes and retries delayed allocation, and rejects unsupported existing holes
  truthfully. Mandatory punched-hole regressions and fresh/dense extension controls
  pass on the committed fix; R2 confirmed resolution. R2's shared APFS clone finding
  remains open; private writable allocation cannot be inferred from physical mapping.
- Exact system `68948fb` qualification reruns all six native/sanitizer/language/root
  suites. Earlier `a086d75` receipts remain intact. Linux credentials use native-only
  clone-vfork; the expanded instrumentation audit must also exclude TSan function
  entry calls and enforce exact supported kernel signal-action layouts.
- macOS credential spawn uses Apple's dynamically resolved attributes with explicit
  group semantics. Unprivileged failure/parent-state checks pass; positive privileged
  proof must run on CI, never on this laptop.
- Windows receipt, private own overlay/controller readiness and actual contract tests
  remain required. The files backend is still pending. POSIX-only Windows failures
  require explicit ENOTSUP contract checks, not broad skips.
- Shared single-thread 1% gates, reviewed integrator merges, and downstream gap
  annotations remain open. No gap is labelled fixed before its merged v2 SHA exists.
- No local sudo, admin/authentication, keychain/trust/privacy/firewall/profile changes
  are permitted. No root Phase 1 host/VM/controller use or paid spend is admitted.
