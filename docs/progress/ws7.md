# WS7: Windows, CI and release

Updated 2026-10-12. Development and testing are authorized by the owner's
explicit release. Only integration into `v2` waits for Phase 1. Work is based on
`bf9c0e9bb6ced1f40d8d7c51bedca769b05909c0`; the integrator alone merges and
pushes. No paid spending is authorized or performed.

## Owner restriction: local signing and OS settings

The owner stopped a signing diagnostic after `security add-trusted-cert -r
trustRoot` displayed a Certificate Trust Settings password prompt on this Mac.
The owner cancelled the prompt and the integrator killed the process. The
signing child was interrupted; no trusted-signing pass is claimed.

Never run local `sudo` (including `sudo -n`), change trust settings, create or
modify keychains (including temporary ones), login items, TCC/privacy settings,
firewall rules, profiles, other system security state, or anything requiring an
administrator password or Touch ID on the owner's Mac. This also applies to
automated cleanup mutations. Any already-created state must be reported using
read-only inspection for owner-run cleanup. Local `codesign -s -` is permitted
only for structural checks.

Trusted-certificate signing tests belong in CI or on owned Boat environments.
Mac identity/keychain/trust setup steps must be explicit owner-run instructions
in the signing checklist. Continue the Windows idle work independently.

## In flight

- `ws7/windows-idle`, `/tmp/minyar-ws7-windows`: owned Boat Windows fork
  `bx_jbb3dmp3`: all eight immutable base/profile inputs were received and
  verified. The guest became ready, but the strict host guardian aborted during
  source binding at 15:09:55 UTC: CPU 77.5% exceeded the unchanged 75% limit.
  The binding has no receipt; no NT Job closure or product verdict is claimed.
  The original sanitizer, focused cohort, portable suite and signing never ran.
  No runtime/test edits exist. Normal stop and snapshot completed at 15:14:51.
  Snapshot inventory was truncated; actual restored bytes must be verified.
  The admitted relay-only resume also ended NONPASS: the read returned, then a
  size/mtime/inode assertion failed before saving its SHA. No transfer occurred;
  all eight restored byte hashes remain unadmitted. Its actual guardian deadline
  was 10,800 seconds, despite later 1,200-second prose; observed duration was
  521.94 seconds with zero resource excursions. Owned PIDs/group were proved
  absent; hydrated=true/error=null was observed. Normal stop completed 15:32:15.
  A new source verification requires fresh integrator admission, a labeled
  1,200-second bound and digest persistence before ancillary metadata checks.
  Guest restart and product tests require separate resource admission.
  The unchanged one-second `system-k1024/n2048`, `idle_cpu <= .02`, remains the
  required repro before any optimization; full native/portable gates follow.
- `ws7/test-signing`, `/tmp/minyar-ws7-signing`: explicit test-certificate
  pipeline committed as `3ed25bd`; 19 mocked signing contracts and 12 shipping
  contracts pass. Registration `fe66b86` passes catalogue and Make checks.
  Independent review blocked core code on unbounded Ed25519 subprocesses and
  acceptance of a nonexistent CI runner directory; fixes are underway.
  Actual trusted macOS CI and Windows Boat signing remain unrun.
  Production signing/notarization checks
  remain strict. Native Windows signing waits for a separately admitted slot.
- `ws7/ci-speed`, `/tmp/minyar-ws7-ci`: owned Boat Linux `bx_ck6a9vnc`,
  4 vCPU/8 GiB. Preserve all 135 current Linux targets and extra gates while
  partitioning into isolated serial builds. Measure baseline and candidate on
  the same host/toolchain. Initial immutable `bf9` baseline is RED at
  `check-toolchain-stamp`, 229.593 seconds total, after 21 rows. Original evidence
  is retained; cancelled candidate is not a speed result. Narrow stamp fix
  `ca33c6e` passed independent review and four focused Boat tests; both future
  timing sides must use that same disclosed prerequisite. CI sandbox is stopped
  pending focused corrections. Review of `2ff58a3` blocked approval on resume
  accepting newly added inputs and timing comparison accepting incomplete source
  inventories. Fixes and regressions are in progress; full timing is deferred
  until independent approval. Integrator owns distinct Phase 1 macOS
  qualification additions on `unify/macos-ci-qualification`.
- Parent: device-test cost plan, release Make/catalogue registration, independent
  review rounds, and merge requests. WS5 module Windows checks are queued in a
  separate source/build directory after the primary and signing slots.

## Retained evidence and limits

Historical Actions run `38108224749` took 3,071 seconds; Linux 3,068 seconds,
Windows failed after 1,216 seconds. That source has 111 explicit Linux targets,
whereas this candidate has 135. Historical green `38068620325` has only 60.
These are bottleneck evidence, not a valid before/after speed comparison.
Read-only metadata/logs are in `/tmp/minyar-ws7-ci-evidence`.

The Windows idle cause remains unproven. An unfinished cohort at timed entry
and scheduler unit overhead are hypotheses. Threshold, duration, work budgets
and safety oracles must not change. WS1 cleared narrow opt-in collector work;
new scheduler state must follow its future thread-local ownership requirement.

Phase 1's sanitizer-path correction (`397362d` plus `dda5bd11`) belongs to its
owner. The exact reviewed stack is normally merged onto the owned Windows
branch as `e563c578`; the immutable `bf9` idle baseline remains separate.

Apple notarization needs actual Developer ID and notary credentials. A generated
test certificate can establish local signature/bundle/manifest behavior, not
Apple acceptance. Windows public signing requires a suitable protected signer;
test store trust and generated keys must be scoped and removed.

## Merge queue and remaining acceptance

The independently reviewed stamp-only branch `ws7/ci-stamp`, `0150ba5`, is
offered to the integrator's queue. No WS7 change has landed on `v2`. Each chunk needs
an independent subagent review and platform-appropriate Boat evidence. Merge
requests include branch, SHA, test commands, source-bound evidence and applicable
performance results. After Phase 1, rebase onto the pushed `v2` and let the
integrator run the full suites and CI.

Remaining: strict Windows idle fix; full Windows suite; actual comparable CI
before/after and green CI on `v2`; real test-certificate pipeline; exact owner
checklist; reviewed 20,000-real-device cost plan and <= $10 pilot design; merged
fixes. None of these is claimed complete by provisioning or design alone.

Public resource-abort evidence is retained at
`~/overnight/runs/minyar-unify-20261012/ws7-windows-idle/closeout.json` and
`owned-abort-public-evidence.tar` (204,800 bytes, SHA256
`c693b638c79022d41871c51e0d80728606242e08aaa87ecf210f6a32a8c6fdc0`).
Private image/profile/key bytes remain entirely remote.
The separate failed relay record is `ws7-windows-idle/relay-closeout.json`;
it does not repair or replace the original guard-abort record.
