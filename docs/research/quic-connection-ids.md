# QUIC connection-ID supply and edge routing

RFC 9000 sections 5.1.1, 5.1.2 and 19.16 require issued IDs to reach the existing connection and define replacement and retirement handling: https://www.rfc-editor.org/rfc/rfc9000.html#section-5.1.1.

The transport now maintains two active local IDs, bounded by the authenticated peer limit. Each replacement has a monotonic sequence and fresh eight-byte ID and sixteen-byte reset token. NEW_CONNECTION_ID uses the existing reliable packet queue. Unknown future retirements and retirement of the packet destination fail with protocol error; repeated retirements are harmless.

The production edge dispatcher tracks the active IDs and a change counter. It removes the Initial-only route after Initial key discard, then adds the spare. Retirement removes obsolete routes before replacement, and peer disposal removes all remaining owned routes. Its existing two-routing-slots-per-peer capacity stays unchanged. Unchanged routing generations avoid rebuilding the list on each packet.

## Tests-first evidence

The original transport fails the new lifecycle assertion with exit32. The original edge provider, compiled against the new transport, establishes mTLS and then fails the first alternate-ID retirement with exit15. Compilation succeeds in both cases.

The fixed source passes complete native and ASan/UBSan QUIC suites. Eighteen transport guard mutants fail the expected application assertions at O0, O2 and under sanitizers. Four additional provider mutants are killed by actual UDP traffic: omit route refresh, retain retired IDs, retain the Initial-only alias, and retain disconnected routes.

tests/peer-edge-cids.py starts an actual Redis-backed edge with max_connections=1 and a mutually authenticated QUIC client. Three consecutive sessions each perform 128 retirements through the alternate active ID and duplicate retirement checks. The table has only two routing slots, so obsolete routes cannot accumulate unnoticed. Exact counters require three allocated/retry-validated peers, one reused peer slot and zero active peers. Native and sanitized executions pass; commands, raw byte outputs, binary hashes and lab inputs are retained.

## Scope

This slice supplies, routes and retires connection IDs. Per-path privacy-preserving CID selection and stateless reset processing remain separate work. The current official advanced interoperability matrix still has failed cells, and this report does not imply that they passed. Random reset tokens are advertised; advertising them alone does not implement stateless reset reception.
