# Hearth device and dial authentication

`use "peerauth" as auth` verifies the Hearth contract in
`HEARTH_PEER_SUPPLY.md` §§10.3.1–10.5 in the Tolum project. Protocol parsing,
policy, time checks and registry binding are Minyar. Ed25519 verification uses
the existing updater's native verification hook and the **unmodified pinned
Monocypher 4.0.3** optional Ed25519 implementation. No signing function or key
discovery endpoint is added. Certificate chain/EKU/signature/possession checks
remain in the existing native trust provider and Minyar TLS 1.3 handshake.

Load `parseKeys(jwksBytes)` only from authenticated internal control-plane
configuration. Check `keysOk` / `keysError` before publishing a new bundle;
keep the last valid bundle if refresh fails. The caller polls at most every
five minutes and retains verification keys according to the contract's rotation
rules. This module performs no network lookup for a token-supplied `kid`.

After an actual mTLS handshake has reached `tlsserver.ESTABLISHED`, call
`bindDevice(session, trustedRegistryDeviceID, trustedRegistryExitID, revoked)`.
The same helper accepts a QUIC server connection's `serverTLS` session after
its authenticated handshake. Registry arguments are trusted configuration;
they must never come from an agent's heartbeat or request. A successful binding
requires client authentication, a single URI SAN equal to
`hearth://device/{trustedRegistryDeviceID}`, and a nonrevoked registry entry.
Check `bindingOk` / `bindingError`, then read `boundDeviceID` / `boundExitID`.
The application owns registry consent/quarantine eligibility and refreshes
revocation data within one minute. Recheck before every heartbeat/dial and drop
revoked muxes immediately. Pass the actual TLS session rather than constructing
its public protocol-state fields yourself.

To authorize an open, call:

```minyar
let result = auth.inspect(tokenBytes, keys, boundExit, requestExit, requestConn,
    nowSeconds, establishmentDeadlineSeconds)
if auth.grantOk(result) {
    // Use only the verified destination and IDs when opening the bound mux.
    let host = auth.targetHost(result)
    let ip = auth.targetIP(result)
    let port = auth.port(result)
    let expiry = auth.expires(result)
}
```

`exitID` and `connID` are also checked getters. Failure is a recoverable
`errors.permissionDeniedCode()` result; malformed JWKS is
`errors.invalidDataCode()`, and failed device binding is
`errors.certificateCode()`. All success fields are private. Extracting a field
from a rejected result traps as a programmer mistake. An empty/malformed token,
unknown key, malformed UTF-8 or duplicate decoded JSON member returns a failure
without trapping.

`grantBytes` returns the exact verified compact JWT for forwarding to the agent,
which must independently verify the gateway signature. The verifier retains a
private copy only after successful verification, and the getter returns a copy;
mutating either the original input or a returned buffer cannot change that
retained signed token. The getter traps on a rejected grant like all other
success getters.

The protected header requires `alg=EdDSA`, `typ=hearth-dial-grant` and a known
`kid`, and rejects unsupported JOSE extensions or embedded keys. Public JWKS
entries require `kty=OKP`, `crv=Ed25519`, a unique nonempty `kid`, canonical
32-byte `x`, and compatible optional `alg`, `use` and verify-only `key_ops`.
Private-key fields are rejected. Pure low-order keys cannot pass the provider's
identity/zero-scalar verification control. Minyar checks canonical compressed
point encodings because Monocypher intentionally accepts some noncanonical
encodings. Curve and signature arithmetic are exclusively Monocypher.

The verifier signs no data: it verifies the **exact received** header/payload
base64url bytes separated by `.`. It rejects padding, whitespace, invalid
alphabet, nonzero unused pad bits and extra/missing segments. JSON whitespace
and member order are valid when signed exactly as transmitted; no JSON
reserialization or canonical-JSON requirement is invented. Duplicate names are
checked **after escape decoding**, including nested objects. Strict metadata
rejects unpaired UTF-16 escape surrogates; ordinary `json.parse` retains its
existing replacement policy.

Claims require `iss=proxy-gateway`, the bound/request exit, request connection,
exactly one syntactically valid ASCII DNS hostname or IPv4/IPv6 literal, port
1–65535, and canonical integer `iat`/`exp` with `0 < exp-iat <= 60`. A payload
`kid`, if present, must match the protected header. DNS resolution belongs to
the agent; the edge forwards the verified hostname unchanged. Target policy,
LAN/loopback refusal and concurrency admission remain application/agent duties.

Time parameters use Unix seconds. The issued-time allowance is 30 seconds;
expiry validation also includes the contract's 30-second allowance. The
**establishment deadline must be later than now and at most `exp`**, so skew
alone cannot authorize a new open after expiry. Recheck the deadline when
establishment completes; an established stream may outlive the grant. Grant
verification alone is not a replay cache: the application owns connection-ID
uniqueness and mux lifecycle.

Bounds are 8192 token bytes, 1024 decoded protected-header bytes, 4096 decoded
claim bytes, 65536 JWKS bytes, 64 keys, 128-character identifiers, 256 members
per JSON object, 4096 total JSON values and 64 JSON nesting levels. Every DER
read for URI SAN extraction is bounded to the authenticated leaf (32768 bytes).
Checked timestamp parsing avoids float conversion and signed-integer overflow.

## Evidence and provenance

All program/build/test execution was on the existing authorised remote Digital
Ocean host (`minyar-lab-main`, Clang 23); local activity was source editing,
reading, git and source transfer. The initial verifier stub returned a typed
rejection for the independently signed accepted fixture (`--red`), establishing
the TDD control before implementation. `tests/peer-auth.py` uses pyca
cryptography 41.0.7/OpenSSL for test-only signing (with a separately tested
OpenSSL CLI fallback when pyca is unavailable) and checks the exact pinned
Monocypher C hashes before compiling. Tests never use Minyar signing to produce
their expected accepted fixtures.

Primary sources:

- [RFC 7515 §§3.1, 5 and Appendix C](https://www.rfc-editor.org/rfc/rfc7515):
  compact JWS, exact signed bytes, protected headers and unpadded base64url.
- [RFC 4648 §3.5](https://www.rfc-editor.org/rfc/rfc4648): unused zero pad bits
  and canonical base64 encodings.
- [RFC 7519 §§4.1.4–4.1.6](https://www.rfc-editor.org/rfc/rfc7519): NumericDate
  and expiration semantics; Hearth supplies the tighter lifetime/skew contract.
- [RFC 8037 Appendix A](https://www.rfc-editor.org/rfc/rfc8037): the fixed public
  key and exact independent Ed25519/JWS signature fixture. The private seed is
  public RFC test material used solely by the test harness.
- [RFC 8032 §5.1.3 and §7.1](https://www.rfc-editor.org/rfc/rfc8032): canonical
  compressed-point encoding and the public Ed25519 test seed/key.
- [RFC 8410 §7](https://www.rfc-editor.org/rfc/rfc8410): PKCS#8 wrapping of that
  test seed for the independent OpenSSL CLI signer.
- [RFC 5280 §4.2.1.6](https://www.rfc-editor.org/rfc/rfc5280): URI SAN in
  GeneralNames; the policy requires one exact registry URI with no CN fallback.
- [Monocypher Ed25519 manual](https://monocypher.org/manual/ed25519) and
  [pinned 4.0.3 source](https://github.com/LoupVaillant/Monocypher/tree/4.0.3):
  provider API/provenance, not a new crypto implementation. Vendor hashes and
  licensing are recorded in `vendor/README.md`.
- [pyca Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/):
  the independent fixture signer. OpenSSL mTLS clients exercise real Minyar TLS
  verification using disposable test-only CA/leaf fixtures from `tls-local.py`.

Run the explicit normal/sanitizer gates with `make check-peer-auth` and
`make check-peer-auth-sanitize`, and the named weakness controls with
`make check-peer-auth-mutants`. The normal/sanitizer gates are also dependencies
of portable check targets. The mutation harness copies only changed library
sources into a temporary override directory; it never edits production sources.

Remote results on 2026-10-10: 125 grant/key/format/boundary cases and the fixed
RFC 8037 signature plus 64 single-byte signature mutations passed with the pyca
signer under ASan/UBSan and separately with the OpenSSL CLI signer at normal
optimization. Eleven actual OpenSSL mTLS/registry/revocation cases passed in
normal and ASan/UBSan builds. All seven deliberate policy weaknesses were
killed by named cases. The ordinary JSON regression corpus passed 79,655 cases
at O0 and O2 under ASan/UBSan. The integration branch supplies the preexisting
transport source catalogue additions from `85f8758`; this change adds only
the three authentication harness dispositions.
