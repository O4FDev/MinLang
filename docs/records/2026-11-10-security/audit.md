# Minyar security audit — 10 November 2026

This review follows `../2026-10-19-security/audit.md`. It covers what was added
since then (the HTTP server, HTTP/2, gRPC, Connect and its clients, protobuf
code generation, TLS server work, the parallel runtime, live patching and the
package tooling) and rechecks the earlier fixes. It was a source review with
local reproduction: every confirmed finding below has a reproducer that ran
against code built from this repository, and a regression test. It does not
claim that undiscovered vulnerabilities are absent.

## Confirmed findings

| # | Finding | Attacker controls | Impact and severity | Fix and regression |
| --- | --- | --- | --- | --- |
| 1 | `library/connect.min` removed each envelope from the front of its input buffer (`Exchange.messages` on the server, `Stream.messages` and the reply queue on the client), copying the rest of the buffer once per message. | The body of any client-streaming or bidirectional call, before a handler sees a message; for a client, a server's response chunk. | CPU exhaustion, medium. Cost grew with the square of the envelope count: 200,000 empty envelopes (1 MB, the HTTP server's default body limit) took 25.6 billion instructions, 5.3 s, on one request of a single-owner server. | A cursor and one copy of the unread tail; the reply queue is indexed. `tests/connect/envelopes.min` (in `check-connect`) sends two million envelopes each way, which the old code cannot finish inside the check's limits. |
| 2 | `library/deflate.min` `decompress` reserved and cleared its whole output limit before inflating. `connectgzip` passes `maxRequestBytes` (4 MiB by default) for every compressed envelope and `maxResponseBytes` (16 MiB) for every reply. | How many compressed messages a peer sends; each can be about 25 bytes. | CPU amplification, medium: megabytes of clearing per few-byte message, in addition to finding 1 on the same path. | The output starts near the input's size and grows fourfold up to the limit, so repeated work stays below half the final attempt. `tests/compression.min` inflates a small member 20,000 times under a 256 MiB limit and checks grown output and its bound. |
| 3 | `library/tlsserver.min` checked each ClientHello extension against every extension already seen, with no bound on their number; `library/tls.min` did the same for ServerHello, EncryptedExtensions, CertificateRequest and ticket extensions. | An unauthenticated ClientHello (or a server's handshake messages). | CPU, low: the 16-bit extensions length allows about 16,000 empty extensions, 128 million comparisons per 64 KB hello. | At most 128 extensions per message. `tests/tls-server-protocol.min` sends 16,000 and requires the "too many ClientHello extensions" failure. |
| 4 | The compiler stopped with an internal bounds error (`List position -1`) when a function named like the keyword that opens the program, `record`, was passed as a value. `library/tlsserver.min` has such a function, so some programs that import it could not be compiled. | Source text. | Compiler crash instead of a diagnostic, low. Found when the new fuzz harness would not compile. | The fix already existed on the unmerged branch `goal/fn-value-crash` (1990f2d81) and is landed from there with its regression `Regressions.test_functions_named_like_keywords_pass_as_values`. |

| 5 | `library/connect.min` answered an origin admitted only by `"*"` with that origin and `Access-Control-Allow-Credentials: true` when `Cors.allowCredentials` was set. | Any web page a signed-in user visits, when a service lists `"*"` and allows credentials. | Cross-site requests with the user's cookies whose responses the page can read, medium for a service configured that way. Browsers refuse the literal pair `*` plus credentials to prevent this; echoing the origin defeated it. | Credentials are sent only to origins listed by name; an origin admitted only by `"*"` is answered `*` without credentials. `tests/connect/server.min` covers named, wildcard and mixed lists. |

Findings 1 to 3 are the same class: work that grows faster than the input that
causes it. None is memory corruption, and none lets a peer read or change data.

## Reviewed without a confirmed defect

- **HTTP/1.1 server** (`library/httpserver.min`): request-line and field
  validation before Text conversion, one `Host`, `Content-Length` and
  `Transfer-Encoding` exclusion (no smuggling ambiguity was found), chunk-size
  and trailer bounds, response header validation against splitting, deadlines.
- **HTTP/2 and HPACK** (`library/http2.min`): integer and Huffman decoding,
  dynamic table limits, header list limits, CONTINUATION and SETTINGS floods,
  flow-control arithmetic, output accounting and the stream limit.
- **gRPC and Connect servers**, `connecth2`, `connecthttp`: envelope lengths,
  timeouts, compression negotiation, the idempotency replay cache, CORS.
- **Protobuf** (`library/protobuf.min` and generated readers): varints,
  lengths, group and message nesting depth, the JSON number mapping.
- **TLS** (`library/tlsserver.min`, `runtime/native/tlsverify.c`): ClientHello
  bounds, PSK binder and Finished comparisons in constant time, key-usage
  limits, chain building with the platform verifier, host name checks, strict
  DER framing before the platform parser.
- **Native compression** (`runtime/native/deflate.c`), socket reads and writes
  (`runtime/native/net.c`).
- **Supply chain**: every action in `.github/workflows` is pinned to a commit,
  workflows have read-only permissions, none runs on `pull_request_target`,
  inputs reach scripts through the environment, the one secret is limited to
  pushes to `v2` in the owner's repository, and each LLVM download is checked
  against a SHA-256. `install/install.sh` verifies an Ed25519 signature on the
  release pointer and checksum manifest, checks archive paths and links before
  extraction, and keeps an update floor.
- **Language soundness probes**: twenty programs that mutate collections during
  iteration, replace borrowed payloads, capture state in closures, and use
  hostile sizes, ranges, shifts and divisions were built with ASan and UBSan.
  Each either ran correctly or stopped with the documented checked error. One
  limit is recorded below.

The fixes recorded on 19 October were spot-checked in the current tree
(`files.readAppend` chunking, request-token validation in `http.min`, bounded
JSON parsing, PATH hardening in the launcher) and are still in place.

## Hardening notes and open items

These were not reproduced as defects in `v2`. They are recorded so that a
maintainer can decide.

1. **Connect idempotency replay is scoped by the `Authorization` header only.**
   `Server.prepare` returns a stored response before the handler runs when the
   path, a hash of `Authorization`, the `Idempotency-Key` and a hash of the body
   match. A service that authenticates by cookie, client certificate or another
   header has the same scope for every caller, so a caller who knows another
   caller's key and exact request body receives the stored response without the
   handler's own check. Keys are normally unguessable, which limits this.
   Proposed fix: let `Options` supply the scope (for example a function from
   the request to Text), and document that the default covers `Authorization`.
   The cache also keeps up to `idempotencyEntries` (4,096) whole responses of
   up to `maxResponseBytes` each; a byte budget would bound its memory.
2. **`Bytes(n)` with an impossible size** stops through the allocator (`Minyar
   stopped` in a normal build, an allocator report under ASan) rather than
   through a size check. It is not memory-unsafe; a checked message for sizes
   above the addressable range would be clearer.
3. **`library/zstd.min`** reserves its whole output limit in the same way as
   finding 2. No network path in the library uses it; the frame header carries
   the content size, which a fix can use.
4. **HTTP/1.1 chunked bodies near both limits**: a request whose header block
   and one chunk together exceed `maxHeaderBytes + maxBodyBytes` cannot be
   buffered, and the server then drops the connection without a status. It is a
   correctness edge, not an exposure.
5. **Live patching** (`tools/live-runtime.c`) loads images named by a manifest
   in the build's state directory or by `MINYAR_LIVE_STATE`. It is a
   development feature with the trust of the user who runs the program; a
   production build should not include it.
6. **Unmerged branches.** WebSocket (`goal/websocket`) and the PostgreSQL client
   (`goal/postgres`) are not in `v2` and were read but not tested here beyond
   the one check below. For the branch owners: WebSocket pong replies are queued
   without regard to `maxPendingBytes`, so a peer that sends pings and reads
   nothing grows the output buffer until the write deadline; SCRAM accepts up to
   ten million iterations from the server, which is seconds of work per
   connection attempt; and with `TLS_PREFER` or `TLS_DISABLE` a server chooses
   the authentication method, including a cleartext password, as in libpq. The
   PostgreSQL client does reject plaintext after the TLS answer, and verifies
   the SCRAM server signature in constant time.

## Tooling added

- `tests/protocol-fuzz.min` and `make check-protocol-fuzz`,
  `check-protocol-fuzz-sanitize`: deterministic mutation fuzzing of ten groups
  of socket-free parsers, described in `../../security-review.md`. Before this, fuzzing
  covered only the compiler. It runs in `check-portable`, `check-sanitize`, the
  security pull-request workflow and, with a dated seed and 100,000 cases per
  target, the nightly fuzz workflow.
- `../../security-review.md` now tells reviewers how to look for the class behind
  findings 1 to 3 and how to write a regression for it.

## Verification and limits

The commands and results are in the landing record for this change. Checks ran
on macOS 27 (arm64) and, through the landing gate, on Linux arm64. Windows
paths, the freestanding OS and live deployments were not exercised. The fuzzer
does not cover protected TLS records, whole QUIC packets, tar or EROFS, which
need an identity or a native library; they keep their existing adversarial
tests.
