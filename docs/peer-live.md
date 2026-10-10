# Hearth live capacity state

`peerlive` implements the regional Redis contract in Tolum's
`HEARTH_PEER_SUPPLY.md` §10.3.1. Heartbeats arrive every fifteen seconds; keys
`peer:live:{exit_id}` expire after forty-five seconds. The edge supplies the
registry identity, pause/quarantine decision, its own instance ID, admitted
stream count, health factor and unpredictable connection epoch. A peer cannot
set these fields in heartbeat JSON.

`heartbeat(bytes)` checks bounded strict UTF-8 JSON, duplicate decoded members,
canonical nonnegative counts, IP syntax, ASN, country and a SHA-256 policy
hash. Sticky inputs are bounded flat scalar metadata. Failed input is a typed
invalid-data error. `payload` takes the larger of the reported and admitted
stream counts, then computes the contract's capacity weight. Paused,
quarantined and full peers have zero weight. The optional health factor is
trusted edge policy, never an agent claim.

The payload adds `exit_id` and `_epoch` for ownership fencing. A fresh owner
uses `bindCommand`; subsequent heartbeat and disconnect commands compare the
stored epoch atomically before refreshing or deleting the single key. Redis
`EVAL` names exactly one key, so the operation also fits a Redis Cluster slot.
A delayed heartbeat/drop from an old mux cannot change its replacement.
Malformed stored JSON and absent keys return zero; stale heartbeats do not
resurrect them. The owner must check operation replies. After a Redis restart,
only the current local owner may claim a fresh epoch and republish its state;
failed writes never make a peer eligible locally.

The returned commands are binary RESP2 and use no interpolated Redis command
text. The socket-independent `redis` pipeline handles partial writes, fragmented
replies, FIFO correlation, backpressure, EOF and recoverable connection failure.
The application owns reconnect, reply-to-operation bookkeeping and timers;
writes are never implicitly replayed.

Tests began with a missing module, then checked policy and the exact emitted
Minyar commands against an independent disposable Redis server. Native O0/O2
and compiler/runtime ASan/UBSan checks passed on the authorised remote Linux
host. They cover replacement races, delayed old heartbeats/disconnects,
corrupted state, exact initial/refreshed TTL and expiry. These are functionality
checks, not long-running peer-edge capacity measurements.

Primary references: [Redis RESP](https://redis.io/docs/latest/develop/reference/protocol-spec/),
[atomic script execution](https://redis.io/docs/latest/develop/programmability/eval-intro/)
and [SET expiration](https://redis.io/docs/latest/commands/set/).
