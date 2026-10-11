# QUIC receive credit and ACK-only key updates

Reading one byte no longer emits one MAX_STREAM_DATA/MAX_DATA packet. A stream
refills when at most half its 65,536-byte advertised receive window remains.
Connection credit follows the same rule for its 262,144-byte receive window.
Both updates share the existing reliable frame queue; discarded RESET_STREAM
final-size credit is counted once. Near the QUIC maximum varint, credit saturates
without waiting for a full half-window increase.

The strict key-update suite exposed a dependence on the extra credit traffic:
an authenticated ACK-only response using a new key phase was never acknowledged,
so the next otherwise permitted peer phase was rejected. The receiver schedules
one acknowledgement for that new receive phase even if it contains only ACKs.
The existing peer-update confirmation, encryption, packet-number/replay, and
old-key retention checks remain. See RFC 9001 sections 6.2 and 6.3:
https://www.rfc-editor.org/rfc/rfc9001.html#section-6.2

Tests first reproduced the tiny-read control storm (exit 41), final partial-window
stall (exit 59), and unacknowledged ACK-only phase (exit 64). Additions to the
existing stream-control and key-update fixtures exercise 512 tiny reads, reliable
credit despite dropped packets, 393,216 bytes across repeated receive windows,
reset/discarded final-size accounting, the maximum-varint boundary, and four
key updates without application reads. Existing assertions were retained.

The exact source passed the full native and ASan/UBSan QUIC suites on Boat, plus
focused native/sanitized tests. Six isolated guard changes failed exact runtime
assertions under O0, O2, and ASan/UBSan (18 kills; compile failures were not counted).
Evidence: /home/user/minyar-overnight/edge/quic-key-credit-current-results.json
and quic-key-credit-mutants-current/results.json. Ordinary compiler/runtime
sources were not modified.

These suite results do not establish the official runner's zero-RTT byte limit,
all migration cases, hardware/NIC behavior, or latest-source long-running tests.
Those checks remain separate.
