# QUIC ACK scheduling

Application packets now receive an ACK after two distinct eliciting packets or an absolute 25 ms deadline, with an earlier ACK when an actual eliciting application transmission can carry it. Initial and Handshake packets, gaps, reordered packets and eliciting duplicates receive immediate feedback. ACK-only packets are recorded without starting ACK loops.

## Standards and motivation

[RFC 9000 §13.2.1](https://www.rfc-editor.org/rfc/rfc9000.html#section-13.2.1) requires immediate ACKs for eliciting Initial/Handshake packets and bounded application ACK delay, and recommends prompt feedback for gaps and reordering. [§13.2.2](https://www.rfc-editor.org/rfc/rfc9000.html#section-13.2.2) recommends ACKing at least every second eliciting packet and permits earlier ACKs. [§13.2.5](https://www.rfc-editor.org/rfc/rfc9000.html#section-13.2.5) measures delay from the arrival of the largest acknowledged packet, including when that packet contained only ACKs. [RFC 9002 §5.3](https://www.rfc-editor.org/rfc/rfc9002.html#section-5.3) describes the corresponding RTT adjustment.

The original b01 official matrix delivered all 40 requested files correctly, but msquic exceeded the unchanged 5000-byte 0RTT gate: 9889 0RTT bytes and 5228 1RTT bytes. Both independently retained captures contained exactly 5228 protected payload bytes. Their decoded packet summary included 53 ACK frames and 1166 ACK-packet bytes. The capture already showed valid Finished-before-application ordering and nine genuine early drops; those are preserved. This implementation has not yet rerun that official matrix and does not claim that its byte gate is green.

Independent test design also used pinned Quinn pending-ACK/de-duplication tests, ngtcp2 ACK range/timestamp tests and quiche's largest-received timestamp and exponent handling. Only behavior informed the tests; peer source was not copied. Pinned revisions and source hashes are retained under the evidence root's research/sources.json.

## Behavior and bounds

Each packet-number space owns its ACK count, fixed deadline, largest-received timestamp, reply path and single queued-ACK marker. Repeated nextTimer queries and later arrivals do not slide the first packet's deadline. Initial, Handshake and application spaces remain separate, including the PTO client's independent no-flight handshake alarm.

The local policy uses the RFC defaults of 25 ms and exponent 3. Parsed peer max_ack_delay and ack_delay_exponent govern received ACKs and do not change our advertised send policy. ACK delay is rebuilt from the current largest packet's receive timestamp when the ACK actually leaves the queue. Initial/Handshake ACK delay is zero.

Queued ACKs retain state while keys or amplification credit block transmission. They refresh packet ranges, timestamp and path on the actual send, and occupy at most one generated pending entry per space. The queue and retained ACK-range limits remain 4096 and 256. When old ranges are evicted, an explicit receive floor rejects forgotten packet numbers rather than admitting the same old packet again.

An actual eliciting application send on the reply path can carry the pending ACK before its deadline. This repaired the unchanged persistent-congestion fixture without changing its loss sequence or assertions. Separate immediate Initial/Handshake ACK datagrams preserve the imported PTO tests. Retried payloads discard obsolete ACK frames and reconstruct fresh ACKs. Close, drain, idle expiry, key discard and version-negotiation failure clear ACK scheduling state.

A reciprocal key-phase confirmation uses one eliciting PING when an otherwise ACK-only response needs acknowledgement. The authenticated exchange terminates after exactly three packets with empty queues and no flight. Ordinary ACK-only traffic remains silent.

Received ACK delay is decoded using the peer exponent with an explicit multiplication bound, then clamped in decoded milliseconds. The existing recovery sampler already applied its own effective delay clamp; this change makes units and overflow handling explicit, and is not evidence of a former effective-clamp bypass.

## Tests and actual TDD evidence

The corrected original 22-mode baseline compiled successfully at both O0 and O2. Each profile had 15 semantic runtime failures and seven passing controls. Earlier setup/compiler mistakes are retained separately and excluded from the semantic-red count.

The final 29 modes cover pair admission, an absolute lone deadline and repeated queries, gaps/reordering, ACK-only continuity, eliciting duplicates, immediate Initial/Handshake spaces, largest ACK-only timestamp, lower reordered timestamps, key blocking before and after queue insertion, amplification blocking, independent local/peer exponents, huge delay values, closing/draining/idle resets, 300 gapped packet ranges, forgotten packet suppression, monotonic clocks, actual sent-packet RTT adjustment, reply paths, finite key-phase exchange and application ACK piggyback.

Adding the two piggyback adversaries first produced compiler-0/runtime-47 failures at both O0/O2. The product fix then passed those tests and the unchanged persistent-congestion regression.

Final frozen source verification passed:
- All 29 ACK modes at O0/O2, both native and ASan/UBSan/LeakSanitizer.
- All 12 imported PTO modes at O0, O2 and sanitizer O1.
- The full existing native QUIC suite (40.346 s) and sanitizer suite (101.008 s).
- The corrected PTO raw-retention driver's nine serialization controls.

Twenty isolated semantic mutations are required to compile at O0/O2 before their runtime results are admitted. Nineteen are killed by exact fixture exit assertions. Removing the peer-delay multiplication bound instead causes the exact checked-Integer range diagnostic, empty stdout and runtime exit 1 at both optimizations. That failure is recorded separately from assertion kills; the initial mutation runner's expectation mismatch is preserved. Compiler failures, setup errors and unrelated diagnostics do not count as kills.

## Narrow RTT fixture clock coordination

The existing RTT fixture polled a lone application packet before the newly public ACK deadline. The first retained baseline compiled successfully and failed with exit 65: receive at 2000, poll at 2001, nextTimer 2025, zero outgoing ACK packets. queuedMixed now polls and delivers its ACK at the public deadline capped at now + 25 ms.

A second genuine runtime exit 1 came from an injected lone PING at 1005 followed by a poll at the same instant. nextTimer was 1030 and no new ACK packet had been sent. The fixture now binds sampleAt to that same capped public deadline, sends at sampleAt and injects the test ACK at sampleAt + 100. The expected sample remains exactly 100 ms. All duplicate-ACK, history, flight, data, FIN, PTO and closed-loop assertions remain unchanged. The gap-driven recoveredDelivery clock remains unchanged.

The focused before/after diff and raw compiler-0/runtime-red traces are retained in the evidence root. No timeout, packet count or protocol threshold was increased.

## Evidence and limits

Evidence root: /home/user/minyar-overnight/edge/quic-ack-review. The delivery handoff binds source, binaries, compiler/tool identities, argv, raw stdout/stderr, certificates, functional suite manifests and mutation variants. Commands use one remote builder, MAKEFLAGS=-j1 and a CPU/RAM guard at 75%.

The final PTO driver retains complete raw subprocess records and structured tool identities before successful cleanup, while explicitly recording that its successful temporary workspaces are not retained. Older successful PTO workspace records were already deleted by the original harness; their limited evidence is disclosed in the author report and is not reconstructed as a fresh claim.

This is a Linux native/sanitizer source proof. It does not certify fresh Windows/macOS execution, the official msquic byte gate, performance counters, all RFC behavior or production readiness. ECN CE metadata and ACK_FREQUENCY are not implemented here. Application-provided clocks have millisecond precision. The maintained compiler/runtime source is unchanged; no compiler object identity or performance claim follows solely from source identity.
