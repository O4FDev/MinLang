# Hearth live capacity state

`peerlive` implements the global live Redis contract in Tolum's
`HEARTH_PRODUCT_SPEC.md` §10.3.1. Heartbeats arrive every fifteen seconds; keys
`peer:live:{exit_id}` expire after forty-five seconds. Every edge writes the same logical global Redis
cluster, and all gateway regions read it. Dial targets the current advertised
`edge_instance` rather than a regional anycast name; sticky resume must read
the current live key again. The edge supplies the
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


## Edge certificate configuration

The `peeredge` reactor accepts `certificate`, `device_roots` and
`gateway_roots` as either one DER certificate file path or an ordered array of
1–16 paths. Existing scalar configurations retain their behavior. The server
identity array is leaf first, followed by its intermediate certificates;
client and gateway roots are independently selected trust anchors. Presenting
an intermediate does not make it a trusted root. Multiple roots support a
planned CA overlap without adding the new intermediate or root to the OS store.
The private key, registry and JWKS remain single paths. The complete
configuration stays capped at 8192 bytes; paths are nonempty, at most 4095
characters, and contain no control characters.

For example:

```json
{
  "certificate": ["edge.der", "edge-intermediate.der"],
  "device_roots": ["device-ca-current.der", "device-ca-next.der"],
  "gateway_roots": ["gateway-ca-current.der", "gateway-ca-next.der"]
}
```

These fields load only operator-selected files. The edge reloads registry
state every fifteen seconds and JWKS every five minutes from local files;
an authenticated control-plane synchronizer must publish those files atomically.
The current Redis transport uses a private plaintext endpoint; deployments
requiring Redis authentication or TLS need a provisioned private proxy or an
explicit transport integration. This source does not configure a managed
Redis deployment, a desktop enrollment client, or a gateway Select adapter.

`make check-peer-edge-pki` and `make check-peer-edge-pki-sanitize` exercise
actual TLS admission with an intermediate-issued server, overlapping roots
for both device and gateway clients, rejection of a registry-listed gateway
and device from an omitted root, and malformed path-array configuration. Both gates require normal reactor
shutdown with zero active peers/relays, so sanitizer leak checks run at exit.
The existing scalar edge gate remains a separate compatibility control.


## Independent QUIC device capacity fixture

`tests/interop/quinn/src/bin/peer-edge-scale.rs` supplies a pinned Quinn/rustls
client for actual device connections. It verifies the server as `localhost`,
uses ALPN `hearth-peer`, and presents a distinct signed device certificate on
each connection. Each device keeps one bidirectional HPW1 control stream open
and sends HELLO followed by staggered fifteen-second HEARTBEAT messages.
Heartbeat processing continues while the cohort connects, waits for the common
measurement start, and shuts down. A failed task or early stream/connection
closure fails the entire cohort; the peer never reconnects or skips a device.

The Python fixture runs the supplied native edge against disposable Redis.
Admission requires every expected `peer:live:{exit_id}` key, a distinct stable
ownership epoch, the correct edge and region, and the complete healthy state.
Client `AUTHENTICATED` output reports TLS and initial writes; server
`ADMITTED` output establishes actual Redis-backed device admission.
Gateway connection counts cannot substitute for device admission.

Run load only on an authorized remote Linux host under its resource guard.
The fixture additionally requires `MINYAR_REMOTE_LOAD=1`. It accepts
1–20,000 devices, 30–82,800 measurement seconds and 30–1,800 setup seconds.
The certificate generator uses disposable P-256 keys, unique device URI SANs
and serials, and one shared lab leaf key. This is not a provisioning workflow.

Build the peer separately, keeping Cargo serial:

```sh
CARGO_BUILD_JOBS=1 cargo build --release --locked \
  --manifest-path tests/interop/quinn/Cargo.toml --bin peer-edge-scale -j1
```

The client arguments are:

```text
peer-edge-scale ADDRESS FIXTURES PEERS DURATION_SECONDS START_FILE [SETUP_DELAY_MS]
```

For a local-to-host short fixture, generate certificates with
`python3 -B tests/peer-edge-device-scale.py --make-fixtures --fixtures DIR --peers 32`,
then start the server with `--binary EDGE_BINARY --fixtures DIR --peers 32
--seconds 30 --setup-seconds 60 --host :: --port 24567 --output EVIDENCE
--start-file START_FILE`. Start the peer against `[::1]:24567` with the same
fixtures, count, duration and initially absent start file. Only after server
`ADMITTED 32` and client `AUTHENTICATED 32`, atomically write
`{"utc_start": INTEGER_UNIX_SECONDS}` with a future start within thirty
seconds. Separate hosts require the same fresh value in their respective start
files. The client maps this once to monotonic time and holds every connection
at least ten seconds beyond measurement before staggered closes.

The measurement checks all devices remain present and all heartbeat timestamps
advance after the common start. Idle edge CPU must remain at most 2% of one
core. For a run of at least 7,200 seconds, RSS growth must stay at most 16 MiB and
its fitted slope at most 0.2 KiB/s. Teardown requires all live keys to retire,
normal native exit, empty native stderr, zero active peers/retained relays and
balanced opened/released relay calls. A short fixture is functional admission
and teardown evidence; the sustained 20,000-device run is a separate capacity
measurement.

`make check-peer-edge-device-scale-controls` exercises adversarial Redis
accounting and certificate fixtures. `make check-peer-edge-device-scale-peer`
runs the Rust argument, common-start, framing and timing unit controls.
Neither target starts the load fixture or certifies production deployment.
