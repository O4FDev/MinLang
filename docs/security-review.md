# Security review workflow

Security reviews use small, independent scopes. A reviewer owns one boundary
(compiler and language semantics, runtime and native APIs, network protocols,
OS and format parsers, or package and release tooling) and writes findings as
they are found. Each report records the input an attacker controls, the exact
code path, impact, a safe reproduction, whether the behavior was reproduced or
inferred, and the regression that will close it. Keep unverified suspicions in
a separate section. The dated audits in `docs/records/2026-10-19-security/audit.md`
and `docs/records/2026-11-10-security/audit.md` track the earlier reviews and
their remaining gaps. The current scan categories
and threat boundaries are in `docs/records/2026-10-19-security/review-plan.md`.

## Gates and timing

| When | Gate | Purpose |
| --- | --- | --- |
| Individual commit | Existing `check-commit` selection | Fast checks for edited code; no new security scan was added here. |
| Pull request | `.github/workflows/security-pr.yml`: `sh scripts/security-static-analysis.sh` | Pinned Clang 23 on macOS and Clang 18 on Linux analyze native runtime entry points, including Linux EROFS, TAR, and zstd parsing and macOS HTTP Objective-C; diagnostics fail the job. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-security-os` | Compile the x86-64 kernel and loader plus the Arm64 kernel through the self-hosted compiler, then check that freestanding square root lowers to an LLVM intrinsic. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-security-os-http check-security-os-http-sanitize` | Run hostile HTTP response bytes through the same pure parser used by the guest, normally and with ASan/UBSan. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-os-net-stack check-os-net-stack-sanitize` | Exercise the guest's UDP, DHCP, DNS, ARP, and TCP receive guards with malformed packets and boundary lengths. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-virtio-used-ring` | Reject forged, replayed, or out-of-range virtio completions before device metadata becomes an offset. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-minyar-lsp` | Exercise LSP framing, malformed input, and bounded compiler diagnostics. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-protocol-fuzz check-protocol-fuzz-sanitize` | Mutation-fuzz the socket-free protocol parsers (HTTP/1.1, HTTP/2 and HPACK, gRPC, Connect, protobuf, JSON, RESP, yamux, the peer wire, PEM, TLS hellos, QUIC frames and transport parameters) with a fixed seed, at O0, O2 and under ASan/UBSan. Also part of `check-portable` and `check-sanitize`. |
| Pull request | Existing `.github/workflows/ci.yml` | Platform matrix, sanitizer tests, short AFL++ run, protocol and integration checks. |
| Pull request | `.github/workflows/security-pr.yml`: vendored SHA-256 check | Detect byte changes to the checked-in C sources and license copies so each change receives explicit review. |
| Nightly | Existing `.github/workflows/fuzz-nightly.yml` | Longer AFL++ compiler campaign and generated-program differential fuzzing, with retained corpus and evidence. |
| Nightly | `.github/workflows/fuzz-nightly.yml`: `protocol-parsers` | The same protocol fuzzer with the date as its seed and 100,000 cases per target. |

Run the native analysis locally with `make check-security-static`. Its source
list is in `scripts/security-static-analysis.sh`. A new native security boundary
should be added to that list after analyzer warnings are triaged. The analyzer
does not understand Minyar `.min` source; reviewers must exercise compiler,
language, and protocol behavior through their focused Minyar tests. A passing
analyzer result is not a claim that all native code is safe.

## Protocol parser fuzzing

A failed bounds check, checked overflow or `fail` stops a Minyar program, so in
a server each one reachable from a peer's bytes is a remote crash. The fuzzer in
`tests/protocol-fuzz.min` drives every socket-free parser with mutated input and
accepts only a recoverable error or a result; it also checks the bounds each
protocol documents (queued output, retained streams, buffered input) and, where
a parser has a writer, that accepted input survives a round trip. Cases are
built from valid conversations and then damaged, because a parser's later
checks are reached only by input that is still nearly valid. The driver fails
when a target stops reaching its handlers, so a change that makes every case
die early cannot pass silently.

```sh
make check-protocol-fuzz                      # fixed seed, 300 cases per target
make check-protocol-fuzz PROTOCOL_FUZZ_SEED=7 PROTOCOL_FUZZ_ITERATIONS=100000
build/protocol-fuzz/debug --seed 7 --iterations 100000 --target http2 --trace | tail -3
build/protocol-fuzz/debug --seed 7 --target http2 --only 4711    # replay one case
```

A new parser of untrusted bytes gets a target here (seeds, a case function and
a reach counter) in the change that adds it. The TLS target stops at the first
signature or protected record, because the fuzzer holds no certificate: it
covers what an unauthenticated peer can reach. Protected TLS records, whole
QUIC packets, tar and EROFS are not covered and keep their own adversarial
tests.

The fuzzer finds crashes, not slowness. Review input-driven loops for work that
grows faster than the input: removing parsed items from the front of a buffer
(`buffer = buffer.slice(used, buffer.length)` inside a loop), a linear search
per parsed item, and output space reserved from a configured limit instead of
from the data. Each of these let a small message cost megabytes of copying or
clearing (see `docs/records/2026-11-10-security/audit.md`). A regression test for such
a defect uses an input large enough that the quadratic form cannot finish
inside the check's limits, not a wall-clock comparison.

## Reviewer handoff

1. Record a finding with exact `path:line` evidence and state any deployment or
   caller precondition. Use private temporary files for reproductions that may
   contain sensitive input; do not run traffic floods against live services.
2. Reproduce with the narrowest test possible. Distinguish a source-path proof
   from an executed exploit. For a stateful issue, use an injected small limit
   or a loopback peer instead of production-scale traffic.
3. Fix the underlying boundary and add a regression in the nearest existing
   test suite. Run the focused test first, then its sanitizer form, then the
   relevant broader PR gate. Record the commands and platform tested.
4. Have another reviewer inspect the fix for changed semantics and missed
   variants. Mark a finding closed only after the regression and affected
   gates pass. Carry unrun platforms and other limits into the dated audit.

Reviewers should search for input-derived allocations, arithmetic and offset
checks, parse termination, path confinement, terminal and wire framing,
authentication revalidation, key rotation, and persistent resource caps. For
dependencies, inspect lockfiles and vendored source separately: Dependabot now
monitors npm, Cargo, Go, and Actions manifests, but it does not audit vendored
C bytes.
