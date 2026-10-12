# Minyar v2 unification progress — 2026-10-12

Current phase: **Phase 1 — finish consolidation and full platform/downstream qualification**.
Owner's revised scope: this thread finishes Phase 1, writes `PHASE1_DONE` only after pushed v2 and green CI, then continues as the sole serial integrator. Seven separate workstreams own Phase 2/3 outcomes.
Briefs: `/Users/luke/overnight/briefs/2026-10-12/minyar-unify.md` and `minyar-split/{_shared,launch}.md`.
Candidate: `completion/v2-20261011`; handover base `372d3de`. Local v2 remains `2fa8320`; origin/v2 remains `30bcee9`. No push or Phase 1 completion marker.
Evidence, inventories, source manifests, raw RED/GREEN receipts and review reports: `/Users/luke/overnight/runs/minyar-unify-20261012/`.

## Preserved inventory

Initial inventory: 39 checkouts and 164 root local/remote refs, plus the neo-db fork. Eight dirty trees were snapshotted before integration; original files/indexes remain intact. Every branch is retained. The neo-db RC sketch `fd655b1` and two unique unqualified Keychain probes remain preserved outside the candidate. Incompatible collector implementations and superseded docs/snapshots have explicit content dispositions, not age-based exclusions. `docs/BRANCHES-20261012.md` records initial and later refs. Clean dead worktrees may be removed only after their commits are verified in final v2; active/dirty workstream trees are excluded from that cleanup.

## Reviewed merges

| Work | Integrated result / evidence |
| --- | --- |
| Desktop, Windows, shipping history | `00b7fd1`, `0d1d12b`/`5978c73`, `5288bc0`; source-preserving reviewed ancestry |
| Collector preservation | `fa7c906`, history `3a5bbb3`; final `4a1732f`, 30 C configurations, eight restored programs O0/O2 native/SAN/LSan, 26 finite-heap cells; R2 approved |
| QUIC/transport | `7edba35`, history `e297113`; final `cb8fe9f`, 172 native + 172 genuine SAN RFC cases, ACK/PTO, yamux/cancel/Go/1536/FIN, net-connect; actual edge CID stock and 32768-peer/262144-route boundary native/SAN pass; R2 approved |
| neo-db durable files/system/net | `8fc4b60`, fork ancestry `a25508a`; final `34833a6`, all ten R1 findings plus overflow/APPEND/negative-boundary/stderr/signal rollback controls; 96 native/48 SAN review controls and language/network suites; R2 approved |
| Build-wiring fixtures | `3c4e382`; original 107+6 adapter inventory and strict dependency/SAN mutations retained; full 23-method suite passed |
| Pinned formatting | `fc068f2`; `94ebf9c` changes layout only in three C files; full format23.1.2/catalogue506/24/wiring23 passed and reviewed |
| Ledger provenance | `90dcfcaf`; reviewed `3c096c1` retains old trusted driver, admits exact reviewed files/system driver and rejects arbitrary self-consistent tools; all74 controls pass |
| Darwin boolean socket fixture | `5caf47e`; reviewed `b077dcd`, raw and Minyar enabled4/disabled0 diagnostic, native/SAN and omitted-setting mutation; production unchanged |
| Nonblocking net fixture | `448a02d`; reviewed `5e390fe`, empty-listener negative controls and ready1000 before original accept; four genuine Darwin language modes pass |
| Mutation semantic coverage | `19ba895`; reviewed `ce544074`, three test-only CompilerHardening cases; native/SAN33/33, harness14/14, unchanged campaign87.5% against85% floor; all16 byte-identical mutants retained |

Owning project code is unchanged. No Phase 2 gap is claimed closed. Every product/test merge above received an independent review before root integration.

## Phase 1 merge queue

| Stack | State / next gate |
| --- | --- |
| Windows `397362d` → `dda5bd1` | New independent R2 APPROVE, R1 path-with-spaces finding closed; merged at `9a23041`. Actual Boat spaced-path RED, path/mutation GREEN, original22-command SAN/public/cache GREEN and adjacent-DLL loader proof retained. Full combined qualification remains pending. |
| OS `dd71690` → `4fcfaac` → `0fb334e` | Real fail-closed TLS API/provider wiring passed native/SAN/LSan vectors and13580 classifier cases/mode. R1 requested SAN dispatch and provider dependencies; separate third correction passed test-first regressions, full wiring, original TLS native/SAN and both x86/ARM image builds. Exact stack imported by sole Y owner for original native/SAN TLS gates; new independent R2 review follows. Not merged. |
| Workstream requests | None offered for merge. Early unreviewed WS1 selector/progress and WS4 files commit, plus WS3/WS5 drafts, remain in owning branches outside Phase 1. |

After both pending stacks are approved: merge serially, retain stricter tests, run combined pinned preflight, publish one tiny revision over the existing 4c+d1+90 bundle chain, and admit final platform/downstream qualification. Original frozen runs and archives keep their identities.

## Actual platform state

- **Linux generic:** exact90 preflight/fixed point and long correctness prefix passed, then actual `check-mutation-score` RED at log123 (68.75% <85%). The focused reviewed repair passes87.5%; complete revised-source correctness, leak/coverage/AFL/peer/QUIC/interop stages still require qualification. No later generic stages or downstream builds were admitted after RED.
- **LLVM22/23 on W:** final90 GREEN with exact clean closure. LLVM23 ran its full fresh portable/release/launcher/incremental/IR/toolchain/module/native-graphics cell. LLVM22 explicitly credits unchanged d1 prefix plus final90 tail. Initial intermittent adapter timing RED and unchanged113-case retry GREEN remain separate. Final archive `llvm22-23-90dcfcaf-green-v2.tar.gz` retains distinct toolchain records. Combined successor input changes still need appropriate checks.
- **Windows on Y:** original d1 portable stopped after1467s at generated SAN linker selection, before the old ledger pin. Focused Windows two-commit repair now passes true ASan/UBSan with actual spaced-directory DLL binding. All NT Jobs/guard/VM retired normally with no resource excursions. Only original OS TLS native/SAN gates are currently admitted in a new isolated exact0fb copy. Full portable/provider/collector/worker/UDP/net native/SAN qualification awaits the combined freeze.
- **Native Mac:** bounded M1–M9 results cover shared loop, captures, disposable Keychain/desktop, neo C/language portions, packaging and split Atacama app/link. Final strict M6/M7 whole original updater/launch runners pass2.615s/16.165s with UBSan halt, original child bounds and fail-closed Darwin-frontend/Boat-backend/native-link route. Six schema2 genuine native/SAN links are retained. M5 language SAN also passes through that matched LLVM22 route. Prior setup NONPASS receipts remain; an earlier M6 hook-reset attempt truthfully passed but ran a local backend18.76s, an operating-constraint miss with no offload credit. The resource guard is unchanged.
- **Complete Mac gates:** portable111 prerequisites, public cold bootstrap/cache/launcher, full QUIC and native performance/PMU remain unqualified. No native Darwin Boat host exists. `macos.md`, gate inventory and executable scheduling record identify genuine Darwin jobs; selected probes cannot certify those aggregates. Full/public construction remains held on this shared laptop. Owner approved existing macos-15 CI after final Boat Linux/Windows pass; Phase 1 and its marker remain open until macOS and all CI jobs are green. Exact existing-job coverage is being mapped before the push.

## Downstream results and remaining scope

- Frozen neo-db debug/eager-release and craft debug/release pass; GLFW host setup was installed for craft.
- Frozen neo-vm all six original builds and12 SHA checks pass with disclosed supported `CC='clang -flto -fuse-ld=lld'`. Default static guest link RED also reproduces on exact6518 baseline. Static guest has no dynamic dependencies/zstd symbol; reachable-zstd negative still fails. Original dynamic programs retain their existing zstd shim/library linkage. This is a configured-build pass, not default-command PASS.
- OS both original x86_64 and ARM64 static kernels/images pass on unmerged correction stack. No boot claim. Frozen55-file archive remains unchanged; final overlay has54 equal files and separately bound candidate Makefile so new provider dependencies are retained.
- Frozen Atacama `v2-stream` parsing, actual LLVM22 ThinLTO native app link, bundle/resources/ad-hoc signature pass. Its complete public `make check test all` build remains pending genuine Darwin scheduling.
- Final combined-source downstream continuity/build checks remain required; no owning project source was changed.

## Resources, spend and workstream hold

Phase 1 exclusive hosts: W `bx_w8xs3uwb` and Y `bx_y2vp5byg` until17:27UTC; generic `bx_utb76q3g` until17:50; OS/downstream `bx_q9mdad57` until15:27; Mac offload `bx_3uusc6gg` until15:40. No host is admitted to a workstream yet. Y has one owner/controller; WS7 snapshot/fork request is deferred to a closed-job, post-marker admission. New paid spend **$0 / $10** for the whole programme.

Seven workstreams have acknowledged the Phase 1/resource hold and preserved their early work. They may retain read-only preparation, but implementation/builds/tests/provisioning wait for explicit release. Workstream goals may be blocked independently to avoid no-action continuations; the integrator's goal remains active. Recorded callable destinations:

| WS | Owner area | Thread |
| --- | --- | --- |
| 1 | Shared-memory concurrency | `mcp:cf2ffdf9-2f57-4ef7-870d-30d8273c1abb` |
| 2 | Runtime safety/speed | `mcp:0664325c-cd01-40ae-8e89-6d5c4d459414` |
| 3 | Core library/language | `mcp:7bc5eaaf-91de-4351-a5f4-b4acc6a14893` |
| 4 | Systems | `mcp:5e893043-b779-436c-8682-86acfc7443e7` |
| 5 | Formats/crypto | `mcp:9bd59149-31bd-400f-8420-84832e9a24ce` |
| 6 | QUIC/soak | `mcp:6e621cdd-15de-4662-8188-77cf11e0427c` |
| 7 | Windows/CI/release | `mcp:28a542ae-0103-497d-956b-fdc56d4a08fb` |

The earlier WS6 proxy ID is not callable; use the destination above. Disk13Gi free and logged guard suspensions prompted a hold on new full worktrees; no guard policy/bypass or unrelated process change by root. Workstream partial edits and stopped/materialized trees are preserved.

## Completion boundary

Owner-approved order: after full final Boat Linux/Windows and Linux downstream gates, fast-forward v2 and push only v2 without force for the existing macos-15 CI route. Keep Phase 1 open until complete macOS/downstream and all CI gates are green; finish dispositions/dead clean-tree removal, then write `PHASE1_DONE` with pushed SHA and CI run URL. Wake the seven existing threads with that SHA/URL and explicit budgeted Boat admission; do not launch duplicates. Subsequent reviewed chunks merge serially through this thread, with full platform qualification and v2 push/notification. MORNING.md and html_render are due at completion/deadline; no completion marker or acceptance claim is manufactured.
