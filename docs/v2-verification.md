# v2 implementation and verification map

This checkpoint describes the combined implementation based on
`aaa5bc72b195a8cb779fc0a52a5126bb825595bb` at 21:03 UTC on 2026-10-11.
An implemented API, a passing focused suite and a complete deployment are
separate claims. Retained results establish only their recorded source and
configuration. Combined CI, current macOS/Windows gates, ordinary performance
gates and long application fault measurements remain incomplete.

The original red CI was repaired at `30bcee930480036ab9ae5fa0a0fd0c4d5fead4e7`:
run `38055713661` passed all 17 jobs. That historical result does not certify
the subsequent combined implementation. The current checkpoint preserves the
v2 branches and their evidence; the interrupted thread's recurring scheduler
is disabled so it cannot duplicate this work.

At frozen `43e1b2f020d4ada0c3f50e37cbc6d04cf9f3353a`, 21 standalone Linux
targets passed: feature dispatch; native/sanitizer managed graphs, callbacks,
isolated workers and cycle progress; domain/profile and launcher checks;
Result review/base/bounded profiles; and coverage. The source remained
byte-identical before and after both recorded batches. Coverage measured
79.63% compiler edges, 80.70% runtime lines and 65.28% runtime branches against
the unchanged 79%/72%/55% floors. These checks are not the full CI matrix.
The automatically rejected generated-access sanitizer demonstration remains
held; aggregate targets that require it have not been rerun or reported green.

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

The current Linux native and sanitizer progress matrices passed, including the
unchanged one-second `system-k1024/n2048` idle oracle. The native case measured
about 0.50% of one CPU. This does not resolve the Windows failure. A later
Windows VM readiness attempt exceeded the whole-host 75% resource ceiling
before any current product test ran; the guest was stopped and its retained
backing image was unchanged.

Two subsequent collector fixes passed actual red/green regressions without
changing the 192-unit work bound. Replacing an eligible unregistered leaf
preserves the completed idle primary proof. Retiring an independently captured
owner at real zero can preserve that proof in idle/local collection phases;
gray pinning, proof construction, anchor changes and registered mutations remain
conservative. The captured-owner matrix passed 594 native/sanitizer cases and
21 serial safety commands. Ordinary production runtime objects remained
byte-identical. The unchanged one-second/2% Linux idle oracle passed; Windows
and actual device capacity are separate tests. The current 4,096-device setup
still fails, as recorded below.

A third actual-zero retirement fix now covers fresh owners during local MARK.
The regression fell from 1,264 work units and eight restarted epochs to 24
units and no restarted epochs under the unchanged 192-unit bound. The marker
is issued only after a real zero-count decrement; queued remaining fields
recheck it and fall back when a full rebuild or anchor transfer invalidates it.
The 540 native/sanitizer cases and 23 serial safety commands passed. Ordinary
system/default runtime objects remained identical; native and sanitizer idle
maxima were 1.1504% and 1.1485% under the unchanged one-second/2% gate.
This fixes neither device capacity nor Windows idle.

A separate first-insertion fix now preserves a full proof build when the
source and child are distinct, independently held, unregistered and unexposed
leaves. It classifies their state before normal registration; registration,
shading and publication remain unchanged, and it creates no completed proof.
Six genuine red cases completed safe reclamation before detecting an extra
epoch. The repaired runtime passed 480 native/sanitizer cases, including
copied/taken ownership in ROOTS/MARK/SWEEP and conservative receiver,
descendant, self-cycle and anchor controls. All 25 serial safety commands
passed. Ordinary runtime objects remained identical; native and sanitizer
idle maxima were 0.3594% and 0.5826% under the unchanged one-second/2% gate.
Fresh device capacity and Windows checks remain pending.

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

At the current Linux qualification source `43e1b2f`, the 23 review methods
passed native, sanitizer and bounded profiles. Their executable footer selects
only review methods, so the 26 base methods were also run independently:
native, sanitizer and bounded budgets 1/32/1024 all passed. Coverage remains
an ordinary eager-RC measurement; it does not replace the optional frontend
and collector suites.

Launcher selection uses a parsed request-only probe after the primary compiler
returns 1 or 86. Probe status 87 selects Result; otherwise the existing callback
route or primary diagnostic remains. A successful primary compilation skips
the probe. Source-text searches do not select a frontend.

## Networking and authentication

| Area | Implemented source and focused checks | Verification boundary |
| --- | --- | --- |
| Portable TLS | `tls.min` / `tlsserver.min` drive TLS 1.3 over TCP records or QUIC CRYPTO bytes. OS trust providers build chains and check names, time, purpose and signatures; configured roots are exclusive. Mutual TLS, X25519/native P-256 key shares, delayed-handshake identity revalidation and digitalSignature key usage have native/sanitizer adversaries. Literal IP connections now omit SNI while still verifying IP SANs. | Native validation does not fetch live CRL/OCSP or missing intermediates. Full current-source TLS gates remain pending. This is not an independent security audit or complete RFC certification. |
| Socket reactor | `eventloop.min` uses kqueue, epoll or WSAPoll with timers and recoverable results; `eventcallbacks.min` dispatches on the owner thread. UDP retains packet boundaries and empty/truncated packets; Linux batches use sendmmsg/recvmmsg. AppKit and the Windows GUI can share the reactor's wake source. | Windows WSAPoll scans its socket array. IOCP and io_uring are not implemented. Connect refusal has OS-dependent timing; callers use deadlines rather than assuming one wait reports refusal. |
| UDP offload | Explicit `net.sendDatagramsOffload*` calls use Linux UDP_SEGMENT. Dedicated generation-checked `DatagramOffload` receivers enable UDP_GRO, split coalesced packets and preserve per-packet truncation/source results. | Offload is opt-in, not transparent on every UDP socket. Kernel/MTU failures are recoverable; unsupported macOS/Windows or disabled Linux builds report unavailable. The receiver and its registry have one owner; drain buffered segments to would-block after readiness. |
| QUIC and fallback | QUIC v1 streams, flow control, CUBIC/loss recovery, current-route recovery generations, client path validation, server preferred-address configuration, resumption and explicit replay-safe early data are implemented. Authenticated TLS/yamux supplies the TCP replacement. | The caller opens/maps sockets and handles `TCP_NEEDED`, retired stream generations and explicit application retries. Writes are not silently replayed. BBR, ECN, live v2 and unsolicited server-initiated active migration remain outside the implemented scope. |
| Peer edge | `peeredge.min` combines owned connection state, device authentication, 15-second live-state heartbeats/Redis and gateway relay. Focused relay tests cover binary data, half-close, cancellation and admission limits. | The measured TCP gateway workload below does not establish QUIC device capacity, multi-hour flat memory or deployment readiness. |

The HTTP authority parser had fifteen actual failures covering IPv6 connection
hosts, wire Host ports, query/fragment targets and malformed or overflowing
ports. The repair separates the URI authority from the connection host, uses
numeric IP classification without DNS, and rejects malformed input with a
recoverable response. Four native and four fully instrumented ASan/UBSan/LSan
tests now pass with normal exits and empty target diagnostics. Their four source
files are byte-identical after integration. TLS was unchanged by this repair.

The later literal-IP TLS regression failed against a strict SNI server before
the repair. Nine native and nine fully instrumented sanitizer cases now pass:
DNS names still send SNI; IPv4, IPv6 and expanded IPv6 omit it; wrong names,
wrong IP SANs and untrusted chains still fail certificate authentication.
The tested binaries exited normally with empty diagnostics and stable source
and frontend bindings. This focused result does not replace the full TLS gate.

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
source. The new 128-cell plan covers 16 selected scenarios, four independent
peers and both roles. At this checkpoint, 31 cells have passed, covering every
handshake and Minyar-client ordinary-transfer cell, plus selected ChaCha20,
key-update and multiplexing cells. Five literal unsupported results and seven
literal failures remain nonpasses. These include peer cipher/feature limits,
migration checker or preferred-address fixture limitations, a peer SIGSEGV
and a peer open-file failure; those diagnoses do not turn failures into passes.

Pinned-runner exceptions also retain no protocol verdict: an ICMPv6 packet
caused a migration checker KeyError, and two consecutive large transfers to
the Minyar server timed out before the runner decoded missing stdout. The
quiche and Quinn clients received correct but incomplete prefixes of the
10-MiB workload. The primary sequence is paused after exact ownership cleanup
for a bounded current-native profile of this server bottleneck.
No timeout, protocol checker or completed result has been relaxed or relabeled.
The remaining primary cells and fresh affected repair cells remain pending.

That profile recorded 359 samples with none lost. Inclusive costs overlapped:
polling 95.3%, frame parsing 48.2%, pending-payload reconstruction 36.5% and
bounded RC 35.1%. Two reviewed changes now reuse transient parsed frames,
copy only when pruning changes a payload, and project exact wire size before
allocating a packet that can actually be sent. Native/sanitizer correctness
passed all 14 stages, plus authenticated header-width, pacing-boundary and
automatic key-update assertions. They do not change queue limits or deadlines.
Fresh strict quiche transfers still timed out: the first change received all
three responses after 54.23 request seconds but exceeded the whole scenario
deadline; the second received only 8,343,456 of 10,485,760 application bytes.
Both are nonpasses. Exact teardown closed all owned Compose lifetimes and
confirmed process and container/network absence. Quinn and the primary next
cell remain pending; the combined collector/protocol candidate is unqualified.

The runner transfer endpoint uses the ordinary runtime, without cycle or
callback markers. The collector header fixes therefore cannot change that
executable or explain its transfer performance. A further ordinary-path repair
is being designed before another strict transfer attempt.

Actual runner failures exposed fixture defects in Docker 29 capability
spelling, simulator capture writers that had not flushed during shutdown, and
signal handlers registered only after endpoint network readiness. Focused
red/green controls and fresh affected cells establish the narrow repairs.
Pre-scenario cleanup now runs before the unchanged scenario timeout. Neither
the protocol checker nor an independent peer was changed to accept a failed
or unsupported protocol result. The unsupported quiche cell retains its setup
and controller errors even though our repaired endpoint exited promptly with
143 and its owned objects were absent afterward.

Actual UDP-blocked fallback now passes native and ASan/UBSan/LSan checks both
before connection and after an authenticated Quinn echo. The mid-session test
acknowledges a permanent physical proxy blackhole, observes `TCP_NEEDED` at
generation 1, rejects the retired stream handle, then performs fresh mutual
TLS and sixteen 32-KiB half-closed streams against independent Go yamux.
Minyar and Go exit normally with empty diagnostics. The isolated Quinn oracle
receives owned SIGTERM after proof; this does not certify that helper's
normal-exit leak behavior. This focused fallback pass is not a multi-hour soak.

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

A separate current-source fixture now exercises actual QUIC devices. Its
32-device baseline passed: independent Quinn authenticated each device,
Redis admitted all 32 exact live-state records, 149 heartbeats were observed,
and native retirement ended with zero active peers and retained relays. The
30-second CPU measurement was 1.0395% of one CPU; it does not establish
two-hour flat memory. Intermediate certificate chains and exclusive
device/gateway root rollover also passed native and sanitizer checks.

The current 4,096-device probe uses one freshly built maintained executable
at `3dad1e7`, including both qualified collector fixes and the HTTP native
provider change. It still fails during setup: 1,739 devices authenticated,
Redis admission reached 1,244, and a device hit the unchanged 20,000-ms TLS
deadline. Native CPU consumed 30.67 seconds over 32.07 wall seconds; 27,446
UDP drops were observed. The guard did not abort for resource use. All 11,632
tracked source hashes remained unchanged and owned processes retired, but
controller teardown is not normal product retirement or a capacity pass.

A separate eight-second profile of that exact executable recorded 792 samples
with none lost: the collector unit accounted for 73.99% of self samples and
bounded traced polling for 9.85%. The call paths run through heartbeat JSON
handling rather than TLS crypto. This diagnoses a remaining collector cost,
not its exact invalidation cause. A subsequent bounded diagnostic joined each
actual proof/build invalidation to its same-call state. All 136 tuples summed
to 20,571 events, without table misses, overflow or reaching its report limit.
At 28.04 CPU seconds, 1,085 events involved fresh actual-zero retirement during
local work, and 9,175 involved first registration of a detached source/child
pair during full proof construction. The qualified fresh-MARK fix covers the
narrow retirement case, and the separately qualified first-insertion fix covers
the detached pair case without exempting other mutations. A fresh combined
endpoint and capacity probe remain pending. No steady-state measurement began;
20,000 actual QUIC devices and
two-hour flat memory remain unqualified.

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

Small current AppKit status-item lifetime and Keychain import/signature checks
passed natively and with ASan/UBSan. A notification declaration compile error
was repaired; denial, late completion, cancellation and stale-handle controls
pass. The current direct AppKit/kqueue adapter also passes socket/timer wakes,
one-shot readiness and generation-safe detach in both builds. An earlier
adapter attempt under additional background scheduling timed out and is
retained separately. These direct checks do not certify the public launcher,
managed AppKit cleanup matrix, physical network transitions or normal-exit
leak detection.

Three exact language probes now also pass with compiler and ARM64 object
generation offloaded to Boat: missing-Keychain lookup, ordinary desktop
services, and the shared AppKit/network debug loop. Their original 15-second
execution limits and output checks are unchanged. They completed in 1.89,
1.23 and 2.80 seconds. Actual object/runtime/provider/link bindings and stable
source receipts are retained; local work comprised small native providers and
final links. These native probe passes do not certify the full public launcher,
release/LTO, sanitizer, managed-capture or hardware-identity gates.

The Keychain import fixture proves opaque Minyar identity references, not
hardware nonexportability. A legacy software key that rejected SecItemExport
still yielded a usable private representation through another Security API;
that limitation is recorded without exposing key bytes. An ephemeral Secure
Enclave P-256 key rejected private export and verified signatures, but the
persistent identity fixture requires a properly entitled app and stopped
before Minyar lookup. Hardware identity and OS mutual-TLS qualification remain
pending with production signing work deferred.

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

The portable bundle packager's 14 Python methods now pass on macOS after its
temporary-directory fixture resolves the platform's `/var` pathname alias.
Only fixture paths changed; the packaging implementation remained unchanged.

Current native and ASan/UBSan updater checks also pass: manifest signature
mutations, exclusive locks, durable activation and process-death recovery;
and safe helper launch, descriptor exclusion and publication races. The two
unchanged suites completed in 22.06 and 33.84 seconds with stable inputs and
empty diagnostics. The temporary app-bundle/ad-hoc signing controls passed
separately in 7.60 seconds using system Python. These are fixture results,
without public-launcher, LSan, production signing or R2 publication credit.

The publisher's HTTPS origin validation now rejects credential-bearing,
noncanonical and malformed-port origins before signing. Eleven hostile-origin
regressions first failed; all five publisher controls then passed using public
fixture signing material. This is local contract evidence, not R2 publication.

Usual framework symlink layouts are unsupported. Darwin pathname execution
requires a protected update root and has no absolute same-user TOCTOU guarantee.
See [shipping](shipping.md) for the precise boundary. Production signing and
publication are deferred at the user's request. Developer ID, notarization,
Windows publisher signing and production R2 publication remain unestablished;
fixture signatures and release-tool contract tests do not certify them.
