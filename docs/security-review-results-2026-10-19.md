# Minyar Lang security review — Boat execution record

Date: 2026-10-19. All commands, builds, fuzzing, and probes in this review ran on Boat `bx_xp8ryq89` in `/home/user/Minyar-Lang`. The source upload was authorized after a secret scan. The final source tree was scanned again for private-key blocks and common live-token signatures; no matching files were found.

## Scope and triage plan

The review followed `docs/security-review-plan-2026-10-19.md` and covered ten areas:

| Area | Main attack surfaces |
| --- | --- |
| Compiler and LLVM | hostile source, IR generation, caching, diagnostic limits, hangs |
| Runtime and concurrency | allocation, text/bounds checks, native helpers, cancellation |
| Files, processes, local privileges | paths, symlinks, temp files, inherited PATH, subprocess capture |
| Network and crypto | TLS, HTTP framing, QUIC, Yamux, certificates, stream limits |
| Guest OS and formats | virtio, disk/EROFS, boot paths, TCP, input events |
| Packages and registry | manifests, lockfiles, Git refs, release witnesses, archive extraction |
| Updater and release | checksum, install replacement, CI provenance |
| CLI and editor | launcher, LSP, diagnostics, shell invocation |
| CI and dependencies | pinned tools, Go/Cargo/npm advisories, sanitizer gates |
| Resource budgets | CPU, memory, file size, record counts, fuzzing oracles |

The initial baseline and prior fixes are documented in `docs/security-audit-2026-10-19.md`. This file records the additional late-pass findings and tests.

## Confirmed issues fixed

- Removed inherited relative PATH components before the public launcher and toolchain invoke external programs. The compiler-driver lookup also skips relative components. Before the fix, a project-supplied `clang-23` or `git` in the current directory could execute when PATH contained `.`.
- Replaced predictable PID temporary files for project manifests/locks, compiler cache artifacts, package Git release refs, and test runner state with private staging and exclusive creation. The native compiler-cache copy now opens a regular source with `O_NOFOLLOW`, writes the destination with `O_EXCL | O_NOFOLLOW`, and copies through file descriptors. Regression cases include hostile symlinks and PID reuse.
- Serialized first-write package release witnesses with a regular no-follow lock file and rechecked the witness while holding the lock. This closes a concurrent first-fetch retag race; the immutable release record is written before the mutable latest hint.
- Hardened virtio used-ring ownership, replay, and length checks. The acquire fence follows the observed index for Arm64. Input events require exactly eight used bytes; block reads require the exact data-plus-status length before their DMA buffer is consumed. Short and excessive block completions have regression cases.
- Gave test scratch directories private atomic creation and runner records exclusive private staging.
- Kept the launcher isolation test aligned with the hard diagnostic-capture limit: a flooding child now correctly produces a bounded limit error rather than the child’s requested exit code.
- Raised the scheduled Go FIN interoperability test's child memory budget from 768 MiB to 2 GiB to allow the updated Go 1.26 compiler to build under the harness. The transport implementation was unchanged by this adjustment.
- Updated test-only Go peer modules to Go 1.26.9 where a Go 1.23.4 standard library had 24 reachable advisories. Peergrpc was already clean on Go 1.26.9. Quinn’s test-only Rust TLS dependency moved to rustls 0.23.46. The earlier audit also records fixes to HTTP header-drip handling, QUIC duplicate stream and ACK work, Yamux reset scans, guest TCP ACK compaction, registry witness handling, bounded Git fetch, installer checksum order, diagnostic capture, and EROFS spool limits.

Changed paths include `minyar`, `tools/toolchain.sh`, `tools/driver-support.min`, `tools/project.min`, `tools/clang-cache.min`, `tools/clang-driver-host.c`, `tools/package-git.min`, `tools/testing-host.c`, `tools/testing.min`, `tools/check-runner.min`, `os/shared/virtio/block.min`, `build-support/checks.mk`, tests, peer Go modules, and the security CI workflow. Exact-file secret scans of edits were clear, followed by the final tree scan above.

## Peer comparison and validation

Peer-oriented reviews compared Go's PATH hardening and module/toolchain advisory process, Cargo/RustSec and npm advisory tools, and virtio/QEMU/Linux conventions for used-ring ordering and completion lengths. The reviews guided the concrete PATH, immutable-witness, and virtio checks above. Detailed Boat reports are in `/tmp/minyar-cli-peer-inspiration-final.md`, `/tmp/minyar-cli-last-pass.md`, `/tmp/minyar-virtio-peer-final.md`, `/tmp/minyar-guest-last-pass.md`, `/tmp/minyar-dependency-final-pass.md`, and `/tmp/minyar-scratch-privacy-fix.md`.

- AFL compiler campaign: 12,465,389 logged executions across two phases; zero saved crashes, hangs, or timeouts. Final corpus: 6,759 files. A frozen full-corpus oracle found 6,694 normal rejects and 65 accepted programs; all accepted output passed LLVM 23 assembly and verification. ASan/UBSan runtime smoke of the 65 accepted cases found no sanitizer marker, signal, or timeout; one intentionally invalid checked Text slice exited with status 1. Reports: `/tmp/minyar-afl-final-corpus-triage.md` and `/tmp/minyar-afl-followup-final-triage.md`.
- Clang 23 and Clang 18 static analysis passed all 19 native C sources. Focused normal and ASan/UBSan runner and virtio used-ring tests passed. `make check-virtio-used-ring check-security-os` passed for x86 and Arm64 kernels/loaders. Both QEMU boot smoke runs reached the desktop and ran until intentional 25-second timeout without a kernel stop.
- `make check-transport-go` and `make check-transport-go-sanitize` passed, including ordinary 16-stream and 1,536-RPC cases and scheduled FIN cases, after the harness memory adjustment.
- The native QUIC suite passed at O0, O2, and ASan/UBSan settings. Focused QUIC ACK and Yamux churn regressions passed in normal and sanitizer modes; Yamux exercised 1,536 sequential RPCs and 60,000 coalesced controls. The guest OS HTTP response parser passed normal and sanitizer tests.
- Official `govulncheck` rescans of Go peers reported no reachable vulnerabilities after toolchain updates. `cargo audit` reported zero advisories/warnings in Quinn and Axum lockfiles; npm audit reported zero severities for the VS Code package lock.
- Focused package Git, compiler cache, project CLI, registry, toolchain portability, and launcher isolation regressions passed. The complete `check-minyar-runner` target reached the Linux-runner matrix and then failed because its test assumes `/usr/lib/llvm-23/bin/ld.lld`, which is absent on this Boat image. The focused runner tests and sanitizer variants passed.

## Limits and disposition

A malicious active writer in a shared, nonsticky compiler-cache parent could still replace final artifacts or witnesses. The default cache is owner controlled; shared-writable caches are outside the supported trust boundary. A malicious virtio device or VMM can still deny service in this single-address-space guest, and a full-length disk response has no cryptographic authenticity check. The live hostile-device injection matrix was not run.

The Boat upload has no `.git` directory, so no commit or PR was created there. After the user clarified that reviewed source files could be synced, 122 reviewed files were copied into the local checkout using Boat SCP. No local build or test was run. The earlier automated review had rejected a workflow-file transfer while the Boat-only instruction was ambiguous; the user’s clarification resolved that scope. The local sync manifest is `docs/security-sync-manifest-2026-10-19.txt`.

