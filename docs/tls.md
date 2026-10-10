# Portable TLS authentication

`library/tls.min` owns the TLS 1.3 handshake and record protocol. It uses
X25519, SHA-256 and ChaCha20-Poly1305 from `crypto.min`. The `tlsverify`
provider supplies X.509 chain validation and asymmetric signatures without
opening sockets or running another TLS implementation.

`tls.client(host, randomBytes(64))` authenticates the server against the OS
trust store. It requires a matching DNS or IP subject alternative name,
valid dates, server certificate usage, a valid issuer chain and the server's
CertificateVerify signature over the handshake transcript. Finished is
checked after certificate authentication. Unexpected ordering, malformed
lengths, duplicate extensions, unauthenticated application data and all-zero
X25519 exchanges become `FAILED` with an explanatory `session.error`.
There is no certificate-verification bypass. Completed TCP handshakes release
certificate chains, transcripts and handshake secrets so long-lived sockets
do not retain their authentication flight. Names use ASCII DNS/punycode or IP
addresses.

The hosted trust providers are:

- macOS: Security.framework, `SecTrust` and the configured OS roots.
- Windows: CryptoAPI chain engines and SSL policy, Windows certificate roots,
  and CNG RSA-PSS/ECDSA signatures.
- Linux: OpenSSL `libcrypto`, strict server-chain validation and the system
  certificate files/directories. OpenSSL's usual `SSL_CERT_FILE` and
  `SSL_CERT_DIR` overrides apply. Build dependencies are `libssl-dev` and a
  provisioned OS CA bundle, normally `ca-certificates` on Debian/Ubuntu.

Windows imports of PKCS#8 EC signing keys can report an ECDH algorithm name,
as handled by [.NET's ECDsaCng implementation](https://github.com/microsoft/referencesource/blob/main/System.Core/System/Security/Cryptography/ECDsaCng.cs).
The provider accepts that label only for P-256/SHA-256, P-384/SHA-384 or
P-521/SHA-512. Generic EC algorithm names additionally require the exact
`ECCCurveName` property, with the [NIST names used by Microsoft's CNG bindings](https://github.com/microsoft/go-crypto-winnative/blob/main/internal/bcrypt/bcrypt_windows.go).
Another curve of the same size cannot substitute for the selected TLS scheme.
The Windows native fixture checks this matrix, imports independent OpenSSL
PKCS#8 keys, signs and verifies every supported curve, and rejects secp256k1,
wrong schemes and changed messages/signatures before the mTLS cases run.

The chain supplied by the peer can provide intermediates; it cannot create
trust anchors. Validation disables network fetching. This implementation
does not currently fetch missing intermediates or perform online OCSP/CRL
revocation checks. Certificate and handshake buffers are bounded at 1 MiB,
and supplied chains/custom root sets at 16 certificates. OS root stores do
not have that 16-certificate limit.

Use `tls.clientWithTrust(host, entropy, roots)` for an isolated list of DER
trust anchors. A nonempty list replaces OS roots; an empty list selects OS
roots. This is useful for private device PKI and deterministic tests without
modifying a user's system certificate store.

`tls.clientWithIdentity(host, entropy, roots, certificates, privateKey)` adds
mutual authentication. Certificates are a DER chain starting with the client
leaf; the private key is unencrypted PKCS#8 DER. The client responds to the
initial CertificateRequest with its Certificate, a signature using an
offered compatible algorithm, and Finished. The certificate and private key
must match. A missing identity produces an empty certificate response, which
the server may reject. Native signing imports are ephemeral. This API takes
key bytes. On macOS, `keychain.findIdentity(subject, store)` returns the public
certificate and an opaque persistent identity reference. Pass
`[keychain.certificate(identity)]` and `keychain.signingReference(identity)` to
the same TLS constructor. The native provider asks Security.framework to sign
with the Keychain key; it never exports the private key. A key's access policy
can deny signing, which fails authentication. Empty `store` uses the OS search
list; a nonempty path selects an existing file keychain. Exact subject-summary
matches must be unique. The reference is local metadata, not a portable key,
and ceases to work when the identity is removed. It should not be logged or
sent to a peer. Hardware protection depends on how the identity was created.

TCP callers drain `takeOutgoing`, feed records through `receive`, and drain
`takeIncoming`. Call `endInput` when TCP reports EOF: an EOF without an
authenticated close_notify is a truncation error. Portable `http.min` uses
the same authenticated client and propagates failures in `Response.error`.
The freestanding Minyar OS overrides `tlsverify` with a provider that fails
closed: it has no provisioned trust store, X.509 validator or signing
implementation yet. Its HTTPS requests now report that missing capability.

## QUIC handshake adapter

`quicClient(host, entropy, protocol, parameters, roots, certificates, key)`
produces raw ClientHello bytes with an empty legacy session ID, ALPN and QUIC
transport parameters. The transport must drain outgoing bytes before
feeding more input, reassemble CRYPTO stream offsets, and call
`receiveHandshake(session, bytes, level)` with `INITIAL_KEYS` for ServerHello
and `HANDSHAKE_KEYS` for the remainder. Fragmentation is supported; fragments
cannot change encryption levels in the middle of a handshake message.

The session exposes `clientSecret`/`serverSecret` for handshake packet keys,
`clientApplication`/`serverApplication` for application packet keys,
`outgoingLevel` for the client handshake flight, and raw
`peerTransportParameters`. The QUIC transport must validate parameter
semantics, derive the RFC 9001 QUIC packet/header keys, and enforce key usage
limits. It must not use `send`/`receive`, which are the TCP record interface.

This adapter is tested with an independently constructed TLS handshake. It
does not implement QUIC packets, transport, server TLS, AES-GCM, resumption,
0-RTT, HelloRetryRequest or TLS KeyUpdate. The current cipher primitives are
straightforward Minyar code and have not received a timing-side-channel or
independent security audit. This is a constrained TLS 1.3 client, not a claim
of complete RFC 8446/9001 compliance or production certification.

## Test strategy and evidence

`python3 tests/tls-local.py` generates fresh roots, intermediates, server and
device identities, then runs real loopback OpenSSL TLS 1.3 exchanges. It
accepts valid RSA/ECDSA servers, IP SANs, single-label wildcards and complete
intermediate chains. It rejects wrong names, expired/future leaves, client-only
EKU, unknown issuers, self-signed leaves, missing/expired intermediates,
non-CA issuers, forged certificate issuer signatures, CN-only names and invalid
wildcard depth; it also proves RSA and ECDSA mutual TLS against an OpenSSL
server requiring client authentication. Portable HTTP must reject a private
issuer when configured with default OS trust.
`python3 tests/tls-local.py --sanitize` instruments generated code, the native
provider and the runtime with ASan/UBSan on supported Clang hosts.

`tests/tls-protocol.min` drives the entire raw handshake, including valid
certificate signatures and Finished. Adversarial cases forge signatures
while keeping the rest of the handshake well formed, substitute the leaf
key, omit CertificateVerify, corrupt Finished, change encryption levels,
duplicate/reorder messages, omit QUIC ALPN/parameters, and send an all-zero
X25519 point. It tests byte-by-byte fragmentation, every truncation of a
real DER leaf, 2,048 deterministic malformed-record inputs and 1,536 inner
handshake parser inputs with valid outer framing. Authenticated AEAD records
carrying application data before peer authentication are rejected. These bounded
fuzz cases are regressions, not a replacement for a continuous fuzz campaign.

The methodology follows the independent issuer/name/usage/time fixtures in
[Go's X.509 verification tests](https://go.dev/src/crypto/x509/verify_test.go)
and real reference-server/client-authentication tests in
[Go's TLS client tests](https://go.dev/src/crypto/tls/handshake_client_test.go).
Transcript signature construction follows
[RFC 8446 section 4.4.3](https://www.rfc-editor.org/rfc/rfc8446#section-4.4.3).
The separation of handshake bytes and packet keys follows the interface
exposed by [rustls QUIC](https://rustls.dev/docs/rustls/quic/index.html) and
[RFC 9001](https://www.rfc-editor.org/rfc/rfc9001).

The first TDD run against the old implementation exited 1 with
`SECURITY: TLS accepted an untrusted self-signed certificate`, after the old
portable HTTP client returned HTTP 200 from that server. The repaired suite
passes locally on macOS, including when generated code, the native provider
and runtime are compiled with AddressSanitizer/UndefinedBehaviorSanitizer.
Platform validation beyond these local runs is recorded separately; a
Windows cross-compile does not constitute a Windows runtime test.
