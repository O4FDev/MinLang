# Minyar v2 unification progress — 2026-10-12

Brief: `/Users/luke/overnight/briefs/2026-10-12/minyar-unify.md`.
Current phase: **Phase 1 — inventory and branch reconciliation**. No Phase 2 feature work has started.
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

- Independent reviews running for shipping, desktop, Windows, collector preservation and neo-db. No new integration merges yet. Existing candidate contains TLS cleanup `6518ef3` and unqualified QUIC CID WIP `8daa72c`.
- No Phase 2 gaps claimed closed yet. Owning project code has not been changed.

## Boat and spending

- W `bx_w8xs3uwb` and Y `bx_y2vp5byg` extended with included credit until 17:27 UTC.
- Dedicated Linux `bx_q9mdad57` for QUIC and `bx_3uusc6gg` for preserved collector stress created with included credit, six-hour lifetimes.
- W reserved for neo-db durable I/O qualification; dedicated Linux box reserved for existing QUIC CID WIP qualification; Y reserved for Windows.
- New paid spend: **$0 / $10**. Other projects' existing Boat boxes are not allocated to this programme.
- No heavy local builds, long local tests, local Windows execution, force pushes or URL opening.

## Current blockers and required qualification

- Branch dispositions and final missing-change tests are being audited; nothing is deemed superseded solely by branch age.
- CID RED and corrected 68-case native/cipher GREEN passed; stale IPv6 evidence verifier repaired test-first. Independent R1 now blocks product integration on production peer-edge routing capacity (third live CID can drop a peer); actual-edge RED and narrow repair assigned before final RFC/SAN qualification.
- neo-db review R1 blocks merge on ten concrete durability, directory framing/error, syncer lifetime/setup, signal narrowing/rollback and diagnostic bounds defects. Two already have actual RED; remaining test-first repairs assigned to the same code owner on W. No obsolete-source broad reruns.
- Current full Linux/macOS/Windows suites and CI remain unqualified; prior passing commits do not qualify this revision.
- Native macOS is absent on Boat. Owner directed use of this Mac for native checks; heavy builds/long tests remain on Boat. Offloaded ARM64 generation and bounded serial Apple-native checks are being prepared.
- Owner added Phase 2 item 0: shared-memory threads; start after Phase 1, with ±1% single-thread performance, Boat multicore scaling, TSan stress and a neo-db design note.
- Phase 3 remains queued behind Phase 1: interop 72–119, CID qualification, merged-code two-hour soak, Windows idle gate, real 20,000 devices and signed publishing.
