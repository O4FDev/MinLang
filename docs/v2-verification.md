# v2 implementation and verification map

This checkpoint describes the combined implementation based on
`0e1fc1b4a5cd853ac86d7614c8588a960e7d5f0b` on 2026-10-11.
An implemented API, a passing focused suite and a complete deployment are
separate claims. Retained results establish only their recorded source and
configuration. Combined CI, current macOS/Windows gates, ordinary performance
gates and long application fault measurements remain incomplete.

## Memory and concurrency

Ordinary programs retain non-atomic RC and their untraced ownership layout.
The optional frontend adds typed closures and selected cycle-capable type
components. Hidden capture edges participate in graph analysis. Managed heaps,
callbacks and collectors have one execution-domain owner; copied-message
workers provide process isolation with separate heaps. Shared managed threads
are not implemented. The scalar parallel ABI rejects managed parameters and
results, including unused parameters.

The collector now distinguishes newly registered or exposed edges from an
already proven cohort, and removes irreversibly dead private owners without
invalidating unrelated live-path proofs. Native and ASan/UBSan/LSan focused
gates cover late registration, exposure, phase interleavings, private retirement
and exact reclamation. The retained failing Result-cycle LLVM from frozen
source `907804b` passes with the repaired runtime at O0/O2, with exact
`42/41` output and empty stderr in native and sanitizer runs. This is a focused
safety repair, not a full combined-language-suite pass.

`eventcallbacks.dispatch` services the selected cleanup budget before waiting.
Ordinary retirement debt requests an immediate poll; cycle-only debt, including
a partially scanned cohort, caps the requested wait at 10 ms. Budgets bound
work units rather than CPU time. Private-retirement locality tests and collector
progress tests are separate from the strict idle CPU oracle. See
[the ownership contract](runtime-memory.md) and
[the progress tradeoff](research/cycle-reactor-progress.md).

Actual Windows evidence at frozen `a154153` passed all 21 native progress
cases. Its sanitizer progress gate failed at `system-k1024/n2048` on the
unchanged `idle_cpu <= .02` assertion after seven successful cases.
Registration, witness, additive and registered-growth gates passed separately.
That recurring idle failure remains unresolved; neither a diagnostic pass nor
a collector work-count bound certifies it.

## Recoverable errors

The optional Result frontend supports explicit `Result<T,E>`,
`Ok<T,E>(value)` and `Err<T,E>(error)`; exhaustive two-arm statement
matching; and `let value = try expression` in Result-returning functions or
callbacks. Propagation requires the exact same E type and can change T.
It does not implement postfix `?`, typed throws, general generics or arbitrary
patterns. Runtime bounds and invariant failures remain fatal programmer errors.

`results.min` adapts operation-owned network status records. Empty datagrams,
EOF, would-block and truncated readable prefixes remain distinct. Result
fields cannot be extracted without matching or propagation.

At review source `0b5e801ff06bf299871fac7866391ce902ebb5d8`, the original
26 and independent 22 tests passed native, ASan/UBSan and 1 MiB bounded profiles
with budgets 1/32/1024, including bounded sanitizer budget 1. Stage 2/3 LLVM and
11 ordinary IR controls were identical. Later normal-TCP review fixtures
passed actual Windows NT native/sanitizer checks at their recorded source.
These earlier profiles do not certify the final combined tree. See
[the language contract](research/errors-language.md) and
[the lexical, ABI and ownership review](research/errors-review.md).

Launcher selection uses a parsed request-only probe after the primary compiler
returns 1 or 86. Probe status 87 selects Result; otherwise the existing callback
route or primary diagnostic remains. A successful primary compilation skips
the probe. Source-text searches do not select a frontend.

## Networking and authentication

| Area | Implemented source and focused checks | Verification boundary |
| --- | --- | --- |
| Portable TLS | `tls.min` / `tlsserver.min` drive TLS 1.3 over TCP records or QUIC CRYPTO bytes. OS trust providers build chains and check names, time, purpose and signatures; configured roots are exclusive. Mutual TLS, X25519/native P-256 key shares, delayed-handshake identity revalidation and digitalSignature key usage have native/sanitizer adversaries. | Native validation does not fetch live CRL/OCSP or missing intermediates. This is not an independent security audit or complete RFC certification. |
| Socket reactor | `eventloop.min` uses kqueue, epoll or WSAPoll with timers and recoverable results; `eventcallbacks.min` dispatches on the owner thread. UDP retains packet boundaries and empty/truncated packets; Linux batches use sendmmsg/recvmmsg. AppKit and the Windows GUI can share the reactor's wake source. | Windows WSAPoll scans its socket array. IOCP and io_uring are not implemented. Connect refusal has OS-dependent timing; callers use deadlines rather than assuming one wait reports refusal. |
| UDP offload | Explicit `net.sendDatagramsOffload*` calls use Linux UDP_SEGMENT. Dedicated generation-checked `DatagramOffload` receivers enable UDP_GRO, split coalesced packets and preserve per-packet truncation/source results. | Offload is opt-in, not transparent on every UDP socket. Kernel/MTU failures are recoverable; unsupported macOS/Windows or disabled Linux builds report unavailable. The receiver and its registry have one owner; drain buffered segments to would-block after readiness. |
| QUIC and fallback | QUIC v1 streams, flow control, CUBIC/loss recovery, current-route recovery generations, client path validation, server preferred-address configuration, resumption and explicit replay-safe early data are implemented. Authenticated TLS/yamux supplies the TCP replacement. | The caller opens/maps sockets and handles `TCP_NEEDED`, retired stream generations and explicit application retries. Writes are not silently replayed. BBR, ECN, live v2 and unsolicited server-initiated active migration remain outside the implemented scope. |
| Peer edge | `peeredge.min` combines owned connection state, device authentication, 15-second live-state heartbeats/Redis and gateway relay. Focused relay tests cover binary data, half-close, cancellation and admission limits. | The measured TCP gateway workload below does not establish QUIC device capacity, multi-hour flat memory or deployment readiness. |

Focused QUIC source `26841d1399f82f3189039189deb8b1e94890cb08` and the later
protocol-evidence lifecycle fixes are integrated. The combined focused candidate
`c010c9aae1e848fa565f508c2fc8f124c300986b` passed 260 protocol cases:
migration/recovery, cipher/key-update, local QNS and reserved-version negotiation
at O0/O2 in native and ASan/UBSan/LSan configurations. The sanitizer evidence
binds annotated generated program LLVM plus instrumented runtime/provider
objects. Helper servers are terminated during teardown; this does not certify
their normal-exit leak behavior. Helper, harness, build-wiring, catalogue and
pinned-format checks
also passed. Matching protocol/driver files are present here; separate macOS
and documentation differences mean this is not a whole-tree CI pass.

The official runner at `740c05a10b61d65e8abd3ad38d60898004d335d9` previously
passed selected handshake/transfer cases against quiche, msquic and ngtcp2 in
both roles at frozen source `83a3ebe`; server Retry also passed. Independent
Quinn tests retain migration, resumption and early-data evidence. A later frozen
`5387aea6` run passed all four client 0-RTT peer cells under the unchanged
criterion. Those historical results do not validate the current combined QUIC
source. A new 128-cell plan covers 16 selected scenarios, four independent peers
and both roles; it has not run. Full interoperability remains pending.

## Application measurements and long runs

The completed R6 workload held 20,000 certificate-verified mutual-TLS/HTTP2
gateway connections and one independent TLS/yamux device connection. Its 39
idle intervals in the first-minute gate averaged 1.7929246% of one CPU, below
the unchanged 2% limit. Native execution and the harness exited normally with
empty native stderr. Final counts included zero active connections, 73 calls
opened/released, 73 relays retired and zero retained relays; all observed owned
process lifetimes were absent afterward.

The original companion failed its artifact-publication check and remains
immutable. A separately reviewed offline V3 correction accepted the retained
run by binding the compiler, 32 runtime headers, cache key, publication rule,
object and final executable. It did not rerun the workload. This result is
TCP gateway capacity and a one-minute idle measurement: it is not 20,000 QUIC
devices, a two-hour steady-state run, or flat-RSS certification.

Earlier source-frozen TLS/HTTP, QUIC and socket soaks remain evidence only for
their recorded sources, peers, faults and exit statuses. A foundation
4,096-socket soak is not TLS/QUIC or edge-server capacity proof. Current
multi-hour mixed TLS/HTTP/QUIC load, loss/reordering, slow/half-closed peers,
UDP-blocked fallback, malformed-input and flat-memory measurements remain
required. Resource guard samples bound their sampling interval, not every
instantaneous CPU/RAM peak.

## Desktop and shipping

macOS exposes AppKit controls/menu-bar/accessory mode, notifications and login
items, power/network snapshots, opaque Keychain signing and OS TLS client
identities. See [macOS](macos.md) and
[desktop services](desktop-services.md). Retained hosted AppKit checks at their
earlier source cover a direct 1,024-node capture cycle and a 4,096-anonymous-
capture public-launcher case. `nextEvent` pumps without sleeping while its
Boolean service result reports debt; it does not use the dispatcher's 10 ms
cycle-only wait policy. Current macOS, larger application graphs and production
permission behavior remain unverified.

The retained Windows R14 full bridge gate passed actual native controls,
disposal, layout invalidation, shared-loop idle settling, notifications and
compiled debug/release API contracts. Separate real SChannel checks passed
server rejection cases and nonexportable CNG mutual TLS under TLS 1.2 and 1.3.
These passes supersede the earlier window-handle/shared-loop failures at those
sources, but do not certify current Windows portable CI or the unresolved
sanitizer idle gate. UI parity with macOS is also incomplete; see
[the Windows contract](windows.md).

The updater authenticates Ed25519 manifests, rollout selection and monotonic
versions; installs indexed regular-file app/resource trees; and validates an
independent active receipt for launch/restart. Later Windows publication,
metadata and fixture fixes passed Linux native/sanitizer and actual NT/MSYS
gates at their recorded source. The `f25972dc` packager follow-up passed all 14
MSYS methods and 13 of 14 NT methods with the existing POSIX-framework-layout
skip. Sys-mode link fixtures establish the POSIX-provider rejection contract;
genuine Windows reparse-link evidence is recorded separately. Current combined
shipping gates still need verification.

Usual framework symlink layouts are unsupported. Darwin pathname execution
requires a protected update root and has no absolute same-user TOCTOU guarantee.
See [shipping](shipping.md) for the precise boundary. Developer ID,
notarization, Windows publisher signing and production R2 publication still
require actual distribution identities and operator credentials. Fixture
signatures and release-tool contract tests do not establish those operations.
