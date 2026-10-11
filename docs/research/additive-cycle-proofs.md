# Completed cycle proofs across additive stores

This change is confined to the opt-in managed-graph runtime. It preserves existing completed certificates during a narrow class of owning-edge insertions; it neither gives unknown objects certificates nor suppresses collection requests. Ordinary runtime and maintained compiler sources retain their bytes.

## Defect and test-first evidence

The existing 20,000-gateway setup took about 1,442 seconds according to the edge owner's telemetry. A single 15-second, 49 Hz sample of its frozen binary recorded 251 samples with zero loss: 88.02% in `rc_cycle_unit`, 5.21% in bounded traced polling and 2.42% in shading. These are self-symbol samples; release call chains are unreliable because that binary omits frame pointers. The source-hashed sample and annotation are preserved in `/home/user/minyar-overnight/memory-audit/collector-559947-20261011T023339Z/`.

Previously, each owning addition discarded the completed proof. A later temporary borrow of an old interior node therefore requested another whole captured cohort, including the growing list. Each individual service call and cohort remained bounded, but repeated invalidations multiplied total work.

The tests-only commit `7da4c1f` introduced an independently modeled acyclic root, list, interior node and scalar leaf. It appends new scalar children, services generated-style calls while borrowing the old interior, then requires an explicit linear bound on accounted collector units. Against the old runtime, 256 take-appends needed 36,480 units and 256 epochs and failed the unchanged `8*n + 64` bound. With the fix, both take and copied ownership need 256 units and zero epochs; 2,048 appends need 2,048 units and zero epochs. The final fixture was also rerun against the actual historical e2 runtime and reproduced the same 36,480-unit failure. These counts are deterministic work evidence, not application throughput measurements.

## Safety conditions and call ordering

`rc_cycle_edge_insert` is used only for list append and a record field with no previous nonzero owning value. Owning replacement still uses the conservative `rc_cycle_edge_add`. Removal keeps its existing invalidation.

An insertion may retain certificates only when all of these hold:

- The collector is IDLE, the proof is completed and valid, and no proof is being built.
- Its anchor is still live with an external count, and is not held solely by a collector pin.
- The target already has a certificate in that proof, or is unregistered and therefore has no traced outgoing ownership. Unknown registered or cyclic targets conservatively invalidate.

Registering a fresh owner clears that owner's tags. The optimization does not mark that owner or its new children as proven. A fresh owner's edge pointing to a proven old root does not imply that the root can reach the fresh owner.

The safety argument is monotonic reachability. An additive insertion removes no old path from the independently held anchor to an already certified node. Existing certificate tags and generations therefore still describe those paths. An unknown unregistered child receives no certificate; registering it later clears its tags, and adding an unknown cyclic child remains conservative.

Ownership transfer also changes the definition of an external root. The insertion barrier first registers its source if needed, evaluates the guards, conservatively invalidates when needed, shades the child, and increments the child's incoming count. It then **rechecks the anchor's external count after incoming changes**. A take-store can consume its sole external count without an RC decrement; that must invalidate before the pointer store, any service call, or allocator reuse. The original request logic follows unchanged.

For copied ownership, traced retain happens before the barrier and does not service collection. The slot is committed after the barrier; bounded polling comes after that commit. Taking ownership skips that retain. A record's old reference flag/value is examined before its reference flag is updated. Neither source registration nor the barrier introduces a poll between the incoming change and the post-change root check.

ROOTS, MARK, SWEEP and unfinished builds keep conservative invalidation. No rescan flag is cleared, and no queued request is discarded. Root-count decrements, unregister and the anchor pointer's allocator-reuse boundary keep their existing behavior.

## Independent verification

On the existing included Boat Linux box, all work ran sequentially on one CPU with a 75% aggregate CPU guard. No local builds, Windows work, new machines or new spend were involved.

The source-current additive suite passes 30 native and 30 ASan/UBSan/LSan runs across system, 1 MiB fixed pool, lazy pool and eager heaps; bounded heaps cover budgets 1, 32 and 1024. Sizes are 32, 256 and 2,048. Every run checks actual bounded work and exact final zero objects, bytes and queued debt.

Adversaries include copied ownership of the sole external anchor, consuming the sole external anchor during a take barrier, fresh owners pointing toward an old proof, unknown self-cyclic descendants, callback-shaped captures and replacements, list growth/removal, separate roots, immediate anchor unregister, allocator reuse, and insertion during ROOTS/MARK/SWEEP with a valid certificate and active build. Assertions check the barrier prefix before polling can obscure it.

Unmodified existing fixtures also pass: 14 native plus 14 sanitized witness runs, 21 native plus 21 sanitized progress runs, and the full 160-case independent reachability oracle across five random seeds and budgets 1, 2, 7, 32 and 1024 where applicable. The initial broad insertion proposal failed the existing witness's disconnected-cycle ROOTS boundary; that fixture was retained and the runtime guard was narrowed.

Eight deliberate wrong implementations are checked in isolated evidence directories, never in the audited source tree. They restore repeated scans, omit the post-incoming anchor check, falsely certify a new owner, ignore active phases/builds, omit removal invalidation, retain an unregistered anchor pointer, treat replacement as insertion, or preserve unknown registered targets. All eight variants failed exact runtime assertions in 32 runs, at budgets 1 and 32 under O2 and ASan/UBSan. The mutation driver and per-case source/binary hashes are preserved under `/home/user/minyar-overnight/memory-audit/additive-mutants-v2`.

All 55 unchanged runtime/compiler source files in the baseline archive match byte-for-byte; only the two opt-in headers differ. The ordinary production runtime object compiled from baseline and current sources is byte-identical, SHA256 `effee3192380318446fa53efc9d223dfb98aa04a37bb0c236889bf1131ff306a`.

## Evidence and limits

Evidence root: `/home/user/minyar-overnight/memory-audit/`.

| Evidence | SHA256 of manifest |
| --- | --- |
| `additive-red/manifest.json` | `ad8bb9ae7a377b7761de5815d1d36d880a2bb6354fbe58d5cde2b8c58698ceab` |
| `additive-source-current-v4/native/manifest.json` | `5bbd6a8d2553a48847726ec1fbe5aae190ef06c7f49aef2f2365d06f024ad379` |
| `additive-source-current-v4/sanitize/manifest.json` | `b149dc9d176a6a76c79999ea5a052201cbdf78579d5d93be2a1a4c16c96c87af` |
| `additive-current-red/manifest.json` | `8f43e60bb387a848145497b4bd45b113117d32976b7947183bb038622461d364` |
| `additive-mutants-v2/manifest.json` | `5b236003f758ae2419b3f1fe0ccc9c3d6067c72732bd97375cfb3c543096a449` |

The changed collector header SHA256 is `1fdafc73e86f57d10d019c8da76fedca417b10e2d3a60ee648b73b2aa468e621`; collections is `bcca6e3eff6a407bfe02a45e1ac7ad6701213564cfd59d98407afb881617c7aa`. The additive fixture is `84c42991f588c2627c7af61e5f73f8b870f054bcc3ff8a766afd9e1b04d66076`.

A separate growing-graph control remains acyclic but appends newly registered owners with traced outgoing fields. The system profile at budget 32 still needs 2,604 units and 32 cohorts for 32 branches; the eager profile needs 2,656 units and 32 cohorts. Exact objects and bytes return to zero; this control deliberately reports the remaining cost instead of claiming a general linear bound.

The optimization establishes a narrow additive-growth work bound. It does not establish acceptable setup time for 20,000 TLS/H2 gateways. That application constructs new cyclic callback graphs; unknown registered descendants still require normal cohorts, and any real removal/replacement still invalidates. Repeated full scans may remain in that workload. Source-current application setup and idle measurements belong to the edge owner. macOS, Windows, full CI and production soak readiness are separate gates.
