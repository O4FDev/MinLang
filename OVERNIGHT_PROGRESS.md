# Minyar v2 unification progress — 2026-10-12

Brief: `/Users/luke/overnight/briefs/2026-10-12/minyar-unify.md`.
Current phase: **Phase 1 — combined platform and downstream qualification**. No Phase 2 feature work has started.
Sole integrator: this thread. Candidate: `completion/v2-20261011`, handover base `372d3de`.

## Preserved and inventoried

- Previous programme thread stopped at 09:27 UTC with a clean checkout and no recorded active Boat workloads or pending children.
- Initial inventory: 39 checkouts, 164 root-repository local/remote refs; one missing prunable worktree.
- All eight dirty checkouts saved to independent `snapshot/*-20261012` branches before integration. Original files/indexes were left intact.
- neo-db RC sketch preserved at `fd655b1` in its fork; explicitly excluded from integration pending validation.
- Inventory, snapshot receipts, delegated task IDs and audit reports: `/Users/luke/overnight/runs/minyar-unify-20261012/`.

## Parallel Phase 1 work

Codex `gpt-6.1-sol` subagents, each in a separate `unify/*-20261012` worktree: neo-db durable files; Windows/CI; transport/QUIC; memory/collectors; desktop/performance; shipping/soak/docs; platform/downstream qualification.
Every proposed integration will receive an independent review subagent before the integrator merges it.

## Merged list and gaps closed

- Reviewed desktop, Windows and shipping history merged at `00b7fd1`, `0d1d12b`/`5978c73`, `5288bc0`, retaining current source. Collector test restoration merged at `fa7c906` after exact GREEN and independent R2 approval; reviewed memory history at `3a5bbb3` preserves that source. Every branch is kept. Existing candidate contains TLS cleanup `6518ef3` and unqualified QUIC CID WIP `8daa72c`.
- Collector preservation at `4a1732f` passed 30 C native/SAN configurations, eight restored programs at O0/O2 native/SAN/LSan, and 26 exact finite-heap language cells; parent-owned R2 approved and merged at `fa7c906`. No production collector/compiler change.
- Transport fixes merged at `7edba35`, with reviewed original history at `e297113`. Neo-db durable files/system/net plus all ten R1 repairs merged after R2 approval at `8fc4b60`; original fork history at `a25508a` retains that fixed tree. Every original fork commit is now an ancestor; RC sketch remains outside.
- Wiring-only `80f2b848` passed focused/full RED-to-GREEN and independent review, then merged. All original107 adapter controls plus six forwarding controls are enforced; existing sanitizer/dependency mutations remain.
- No Phase 2 gaps claimed closed yet. Owning project code has not been changed.

## Boat and spending

- W `bx_w8xs3uwb` and Y `bx_y2vp5byg` extended with included credit until 17:27 UTC.
- Dedicated Linux `bx_q9mdad57` for QUIC and `bx_3uusc6gg` for preserved collector stress created with included credit, six-hour lifetimes.
- Neo-db released W after final native/SAN qualification; the dedicated transport box completed its frozen-source run and now owns the two existing build-wiring fixture repairs. Y prepares the retained Windows VM.
- Dedicated 8-CPU/16-GiB Linux `bx_utb76q3g` allocated through 17:50 UTC for whole-tree/downstream qualification and Boat-generated Mac artifacts; dependency setup only until source freeze.
- New paid spend: **$0 / $10**. Other projects' existing Boat boxes are not allocated to this programme.
- No heavy local builds, long local tests, local Windows execution, force pushes or URL opening.

## Current blockers and required qualification

- Branch dispositions and final missing-change tests are being audited; nothing is deemed superseded solely by branch age.
- Transport `cb8fe9f` received independent R2 approval and passed final 172 native + 172 ASan/UBSan/LSan RFC cases, ACK/PTO, yamux/cancel/independent Go/1536/FIN, net-connect and strict edge/full262144-route controls. All1313 input hashes match Git and before/after. Normal integration `7edba35`; reviewed38 original-ref history at `e297113` leaves its source unchanged.
- Neo-db frozen `34833a6` fixes all ten R1 findings plus actual overflow, APPEND/position, negative-boundary, stderr-progress and in-flight signal rollback RED controls. Final W native/SAN maintained and network suites pass; independent R2 approved and integration is complete. Native Mac and Boat Windows net still require final combined qualification.
- Both pre-existing build-wiring fixture failures are repaired and independently approved: complete isolated Make prerequisite and fixed107+6 adapter inventory. Full23-method suite passed on Boat. Combined catalogue/format preflight and full platform suites follow on frozen source.
- Frozen `4c060044` passed combined catalogue and full build-wiring preflight; pinned format23.1.2 exposed formatting errors in `runtime/native/net.c`, `runtime/native/windows.c` and `tests/cycle-idle-invalidation.c`. A separate formatting-only correction is being qualified before independent review and a revised freeze. No product builds/tests have started on the three platform routes.
- Current full Linux/macOS/Windows suites and CI remain unqualified; prior passing commits do not qualify this revision.
- Native macOS is absent on Boat. Owner directed use of this Mac for native checks; heavy builds/long tests remain on Boat. Offloaded ARM64 generation and bounded serial Apple-native checks are being prepared.
- Owner added Phase 2 item 0: shared-memory threads; start after Phase 1, with ±1% single-thread performance, Boat multicore scaling, TSan stress and a neo-db design note.
- Phase 3 remains queued behind Phase 1: interop 72–119, CID qualification, merged-code two-hour soak, Windows idle gate, real 20,000 devices and signed publishing.
