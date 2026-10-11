# v2 implementation and verification map

This is a source-specific checkpoint from 2026-10-11. An implemented API, a
passing focused suite and a complete deployment are separate claims. Historical
evidence remains useful for its recorded source; it does not establish that a
newer combined tree has passed. The complete hosted matrix, ordinary performance
gates and long application measurements still need final integrated evidence.

## Memory and concurrency

Ordinary programs retain non-atomic RC and their untraced ownership layout.
The optional frontend adds typed closures and selected cycle-capable type
components. Hidden capture edges participate in graph analysis; managed heaps
and callbacks remain owned by one execution domain. Copied-message workers
provide process isolation, rather than shared managed threads.

The revised cycle wait policy at `9a33f02689e97efce3bd917c55513b935b1eff2d`
services the existing budget, then caps a wait at 10 ms when only cycle debt
remains, including midcohort work. Native and ASan/UBSan tests cover 32, 2,048 and
4,096 live nodes, bounded budgets, continued borrowed churn, eventual exact
reclamation and work-unit accounting. The ordinary production runtime object
was byte-identical before and after this change. The deadline/latency tradeoff
is recorded in [the progress report](research/cycle-reactor-progress.md).

This is collector evidence. The latest 2,048-gateway edge measurement still
exceeded the 2% idle CPU target; the application loop and larger capacity
measurements remain under verification.

## Recoverable errors

The optional Result frontend supports explicit `Result<T,E>`,
`Ok<T,E>(value)` and `Err<T,E>(error)`; exhaustive two-arm statement
matching; and `let value = try expression` in Result-returning functions or
callbacks. Propagation requires the exact same E type and can change T.
It does not implement postfix `?`, typed throws, general generics or arbitrary
patterns. Runtime bounds and invariant failures remain fatal programmer errors.

`results.min` adapts existing operation-owned network status records. Empty
datagrams, EOF, would-block and truncated readable prefixes remain distinct.
Result fields cannot be extracted without matching or propagation.

At review source `0b5e801ff06bf299871fac7866391ce902ebb5d8`, the original 26
and independent 22 tests passed native, ASan/UBSan and 1 MiB bounded profiles
with budgets 1/32/1024, including bounded sanitizer budget 1. Stage 2/3 LLVM and
11 ordinary IR controls were identical. See [the language contract](research/errors-language.md)
and [the lexical, ABI and ownership review](research/errors-review.md).

Launcher selection uses a parsed request-only probe after the primary compiler
returns 1 or 86. Probe status 87 selects Result; otherwise the existing callback
route or primary diagnostic remains. A successful primary compilation skips
the probe. Source-text searches do not select a frontend.

## Networking and authentication

| Area | Implemented source and focused checks | Verification boundary |
| --- | --- | --- |
| Portable TLS | `tls.min` / `tlsserver.min` own TLS 1.3 over TCP records or QUIC CRYPTO bytes. OS trust providers build chains, check names/time/purpose and signatures; configured roots are exclusive. Mutual TLS, X25519 and native P-256 server key shares, current identity revalidation at delayed handshake completion and TLS digitalSignature key usage have native/sanitizer adversaries. | Native validation does not fetch live CRL/OCSP or missing intermediates. This is not an independent security audit or complete RFC certification. |
| Socket reactor | `eventloop.min` uses kqueue, epoll or WSAPoll with timers and recoverable results; `eventcallbacks.min` supplies owner-thread `dispatch`. UDP preserves empty/truncated packets and packet boundaries; Linux batches use sendmmsg/recvmmsg. AppKit can observe the same reactor. | Windows WSAPoll scans its socket array. IOCP, io_uring and UDP GSO/GRO are not implemented. Connect refusal has OS-dependent timing; callers use deadlines rather than assuming one wait reports refusal. |
| QUIC and fallback | `quic.min`, `quicretry.min`, `transport.min` and `yamux.min` implement v1 streams, flow control, CUBIC/loss recovery, client path validation, resumption and explicitly enabled replay-safe early data. TCP replacement uses authenticated TLS/yamux and retires old stream handles. | The caller opens and maps replacement sockets and decides which operations to retry; application writes are not silently replayed. BBR, live v2 and server-initiated migration remain outside the implemented scope. |
| Peer edge | `peeredge.min` combines owned connection state, device authentication, 15-second live-state heartbeats/Redis and gateway relay. Focused relay tests exercise binary data, half-close, cancellation and admission limits. | Tens-of-thousands capacity, large idle CPU and final mixed fault-soak results remain pending. |

The official QUIC interop runner at
`740c05a10b61d65e8abd3ad38d60898004d335d9` tested frozen Minyar source
`83a3ebeaf6106dd48f87f57238380e9010af54d2`. Handshake and transfer passed
against quiche, msquic and ngtcp2 in both roles; Retry passed with Minyar as
server. Independent Quinn roles also cover migration, resumption and early data.
The runner directories under
`/home/user/minyar-overnight/security/interop-lab/current-*` retain matrices,
logs and source/image metadata. These selected cases do not cover every runner
scenario or deployment network.

Source-frozen two-hour TLS/HTTP and QUIC fault soaks with 64 peers were launched
remotely. Their exit markers, all process-role samples and final reports must be
checked before claiming completion or flat memory. The separate 4,096-socket
foundation soak is not TLS/QUIC or edge-server capacity proof.

## Desktop and shipping

macOS exposes AppKit controls/menu-bar/accessory mode, desktop notifications and
login items, power/network snapshots, opaque Keychain signing and OS TLS client
identities. See [macOS](macos.md) and [desktop services](desktop-services.md).
The direct AppKit fixture reclaims a 1,024-node capture cycle and then sleeps
at budgets one/32 under native and sanitizer profiles. Actual hosted debug and
release runs also passed a 4,096-anonymous-capture public-launcher check.
`nextEvent` pumps without sleeping while its Boolean service result reports
debt; it does not use the dispatcher's 10 ms cycle-only wait policy. These
focused checks do not establish large application graphs or production
permission behavior.

Actual Windows 11 SChannel checks passed server rejection cases and
nonexportable CNG mutual TLS with independent peers under TLS 1.2 and 1.3.
Strict notifications passed against the real OS after first-use state handling
was corrected. The separate native window-handle failure remains open; this is
not a complete Windows bridge or portable-suite pass. Retained guest evidence
is under `/home/user/minyar-overnight/windows/shared/evidence`, including
`platform-next-schannel.log`.

The updater at shipping source `2aad5806ff2ab9009d0555a768309e0b3e4a88f0`
authenticates Ed25519 manifests, rollout selection and monotonic versions;
installs complete indexed regular-file app/resource trees; and checks an
independent active receipt for launch/restart. Linux normal/sanitized launch
tests passed. Actual macOS and Windows launch checks are separate requirements.
Usual framework symlink layouts are unsupported. Darwin pathname execution
still requires a protected update root and has no absolute same-user TOCTOU
guarantee. See [shipping](shipping.md) for the precise boundary.

Developer ID, notarization, Windows publisher signing and production R2
publication require the actual distribution identities and operator credentials.
Fixture signatures and fake-tool policy tests do not establish those production
operations. No production credential or full-project completion claim is made
by this checkpoint.
