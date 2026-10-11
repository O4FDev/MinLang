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

An actual eliciting application send on the reply path can carry the pending ACK before its deadline. This repaired the unchanged persistent-congestion fixture without changing its loss sequence or assertions. Separate immediate Initial/Handshake ACK datagrams preserve the imported PTO tests. Retried payloads discard obsolete ACK frames and reconstruct fresh ACKs.

Every generated ACK now fits the fixed 1200-byte path budget, which is no larger than any legal peer max_udp_payload_size. Piggyback admission uses the actual encoded ACK plus application frame, current CID/packet-number header and 16-byte AEAD tag. When the combination does not fit, the application packet and pending standalone ACK remain separate, with unchanged flow-control, flight, pacing and ACK deadlines.

Standalone encoding visits each retained range once and emits the largest/newest prefix that fits. It accounts for range-count varint width and reserves a reciprocal key-phase PING when required. Short-header budgets use the actual current CID; long-header budgets reserve the length-field width of the full path budget. [RFC 9000 §13.2.3](https://www.rfc-editor.org/rfc/rfc9000.html#section-13.2.3) permits omitting old ranges from a frame when it would not fit. Wire omission never removes receive history or changes the rejection floor, including while keys/amplification block transmission. Existing receive-triggered eviction beyond 256 ranges retains its rejection-floor behavior. Close, drain, idle expiry, key discard and version-negotiation failure clear ACK scheduling state.

A reciprocal key-phase confirmation uses one eliciting PING when an otherwise ACK-only response needs acknowledgement. The authenticated exchange terminates after exactly three packets with empty queues and no flight. Ordinary ACK-only traffic remains silent.

Received ACK delay is decoded using the peer exponent with an explicit multiplication bound, then clamped in decoded milliseconds. The existing recovery sampler already applied its own effective delay clamp; this change makes units and overflow handling explicit, and is not evidence of a former effective-clamp bypass.

## Tests and actual TDD evidence

The corrected original 22-mode baseline compiled successfully at both O0 and O2. Each profile had 15 semantic runtime failures and seven passing controls. Earlier setup/compiler mistakes are retained separately and excluded from the semantic-red count.

The first source delivery contained 29 modes covering pair admission, absolute deadlines, gaps/reordering, ACK-only continuity, duplicates, separate spaces, largest timestamps, key/amplification blocking, independent exponents, huge delay values, terminal resets, forgotten packets, actual RTT samples, reply paths, finite key-phase exchange and application ACK piggyback. Its native/sanitized ACK, PTO and full-suite proof remains separately retained.

The packet-size follow-up retains two distinct TDD stages:
- Piggyback-only baseline: the unchanged b6 candidate compiled at O0/O2; six of eight new modes failed semantically in each profile. Actual combined packets reached 1219/1551 bytes, and an adjacent exact boundary emitted 1201 bytes. Two fitting controls passed. The guard-only frozen 22a candidate then passed 37 modes, all PTO modes, both full suites and 23 mutations.
- Standalone baseline: guard-only 22a compiled at O0/O2; nine of eleven new modes failed semantically in each profile, while range-count and mixed-width controls passed. Sparse retained ranges generated 1313/2337/2349-byte packets; reciprocal key-phase output was 2338 bytes. The initial key-phase test decoder used only its current peer key; that setup artifact is excluded. The corrected test authenticates retained current/next/previous keys before parsing and reproduces the actual wire-length failure.

The final 48 modes add long ACKs beside maximum STREAM chunks, PING/control/probe paths, actual resend, blocked queues, exact protected-header/tag boundaries, 4/8-byte sparse gap varints, 63/64 range-count width, 20-byte CID headers, blocked-send refresh, retained and genuinely forgotten duplicates, reciprocal PING reservation and wide-CID mixed count-width transitions. Sparse packet-number jumps remain within the real four-byte reconstruction window and must pass explicit authenticated setup checks. CID-width cases isolate legal header widths through white-box connection state; they do not claim public NEW_CONNECTION_ID negotiation coverage.

Final frozen source 8d676223 passed:
- All 48 ACK modes at O0/O2, both native and ASan/UBSan/LeakSanitizer (192 successful executions).
- All 12 imported PTO modes at O0, O2 and sanitizer O1, with schema-2 raw command records retained.
- The full unchanged native QUIC suite (45.167 s) and sanitizer suite (105.895 s), all 26 recorded commands per suite.
- All 29 isolated mutations compiled at O0/O2 and were killed by the expected runtime result (58 kills): 28 exact fixture assertions and one exact checked-Integer overflow diagnostic per optimization.

The first combined verifier retained its genuine functional greens and then stopped on a mutation-harness compiler error: the stale-queued-ACK variant still called the old four-argument signature. That compiler failure is excluded. A corrected artifact-only variant replay passed all 29 mutations with the production source and fixture hashes unchanged. Every newly introduced wire-budget mutation also requires its captured packet-size diagnostic to exceed 1200 bytes; unrelated nonzero exits do not count.

Mutation variants must compile at both O0/O2 before runtime results are admitted. Exact fixture exit assertions count as semantic kills. Removing the peer-delay multiplication bound is separately admitted only with the exact checked-Integer range diagnostic, empty stdout and runtime exit 1 in both optimizations. Earlier setup errors and the initial mutation expectation mismatch remain separate artifacts and are not counted. The final follow-up includes byte-budget guards for header/CID, tag, count-width and reciprocal PING, and a mutation that incorrectly advances receive history during blocked encoding.

## Narrow RTT fixture clock coordination

The existing RTT fixture polled a lone application packet before the newly public ACK deadline. The first retained baseline compiled successfully and failed with exit 65: receive at 2000, poll at 2001, nextTimer 2025, zero outgoing ACK packets. queuedMixed now polls and delivers its ACK at the public deadline capped at now + 25 ms.

A second genuine runtime exit 1 came from an injected lone PING at 1005 followed by a poll at the same instant. nextTimer was 1030 and no new ACK packet had been sent. The fixture now binds sampleAt to that same capped public deadline, sends at sampleAt and injects the test ACK at sampleAt + 100. The expected sample remains exactly 100 ms. All duplicate-ACK, history, flight, data, FIN, PTO and closed-loop assertions remain unchanged. The gap-driven recoveredDelivery clock remains unchanged.

The focused before/after diff and raw compiler-0/runtime-red traces are retained in the evidence root. No timeout, packet count or protocol threshold was increased.

## Evidence and limits

Original evidence root: /home/user/minyar-overnight/edge/quic-ack-review. Piggyback follow-up: /home/user/minyar-overnight/edge/quic-ack-mtu-review. Combined final follow-up: /home/user/minyar-overnight/edge/quic-ack-standalone-review. The delivery handoff binds source, binaries, compiler/tool identities, argv, raw stdout/stderr, certificates, functional suite manifests and mutation variants. Commands use one remote builder, MAKEFLAGS=-j1 and a CPU/RAM guard at 75%.

The final PTO driver retains complete raw subprocess records and structured tool identities before successful cleanup, while explicitly recording that its successful temporary workspaces are not retained. Older successful PTO workspace records were already deleted by the original harness; their limited evidence is disclosed in the author report and is not reconstructed as a fresh claim.

This is a Linux native/sanitizer source proof. It does not certify fresh Windows/macOS execution, the official msquic byte gate, performance counters, all RFC behavior or production readiness. ECN CE metadata and ACK_FREQUENCY are not implemented here. Application-provided clocks have millisecond precision. The maintained compiler/runtime source is unchanged; no compiler object identity or performance claim follows solely from source identity.
