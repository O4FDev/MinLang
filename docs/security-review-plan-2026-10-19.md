# Security review plan — 19 October 2026

This pass builds on `security-audit-2026-10-19.md`. It treats source files,
package repositories, network peers, update metadata, disk images, editor
messages, and CI event data as hostile at their respective boundaries. A
finding needs an attacker-controlled input, a reachable code path, an impact,
and a focused reproducer before it is called confirmed.

| Area | Vulnerability classes and boundaries to check |
| --- | --- |
| Compiler and generated programs | Lexer/parser termination, malformed UTF-8, unchecked arithmetic and allocation, recursion depth, generated LLVM and C escaping, diagnostics and terminal controls, FFI type and ownership mismatches. |
| Runtime and concurrency | Buffer bounds, integer truncation, use-after-free, double release, thread races, lock ordering, cancellation, and stale handles across native APIs. |
| Files, processes, and local privileges | Path traversal, symlink and time-of-check/time-of-use races, temporary files, inherited environment and descriptors, command arguments, filesystem permissions, and resource caps. |
| Network and cryptography | HTTP framing and redirects, TLS peer identity, QUIC and TCP state transitions, replay and key rotation, peer authorization and revocation, packet parsing, and remote resource exhaustion. |
| Guest OS and data formats | Malformed disk and wire input, bounds before reads or allocation, DNS/DHCP/HTTP/JSON/TAR/zstd parsing, decompression amplification, and recoverable errors instead of fatal crashes. |
| Packages and registry | Untrusted Git transport and configuration, code or hook execution, import confinement, immutable locks, metadata rollback, cache poisoning, resource limits, and credential leakage. |
| Updater, installer, and release | Signature and hash verification, rollback and expiry, artifact activation, archive extraction, path confinement, key changes, race resistance, and release provenance. |
| CLI, editor, and developer tools | Untrusted LSP/JSON and filesystem events, argument and shell injection, terminal escape sequences, workspace confinement, and denial of service. |
| CI and dependency chain | Workflow permissions and event injection, pinned downloads/actions, secret exposure, vendored provenance, dependency alerts, and coverage of platform-specific native code. |
| Cross-cutting abuse limits | Time, memory, disk, file count, connection count, and recursion budgets for each externally controlled input. |

Reviewers record exact `path:line` evidence and distinguish reproduced defects
from hypotheses. Triage ranks reachability and impact first. A fix gets a
focused regression, then a sanitizer or platform gate when applicable. Peer
project advisories and security tests are used to generate candidate cases;
they are not evidence of a Minyar defect by themselves.

The working copy is on macOS, but builds, tests, and vulnerability probes run
only in Boat. Windows-only, freestanding hardware, and live deployment behavior
require separate validation. The user explicitly authorized a Boat source
upload after a secret scan. The tracked source scan found no candidate
credentials or private keys; later edits are scanned before each upload.
