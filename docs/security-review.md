# Security review workflow

Security reviews use small, independent scopes. A reviewer owns one boundary
(compiler and language semantics, runtime and native APIs, network protocols,
OS and format parsers, or package and release tooling) and writes findings as
they are found. Each report records the input an attacker controls, the exact
code path, impact, a safe reproduction, whether the behavior was reproduced or
inferred, and the regression that will close it. Keep unverified suspicions in
a separate section. The dated audit in `docs/security-audit-2026-10-19.md`
tracks the current review and its remaining gaps.

## Gates and timing

| When | Gate | Purpose |
| --- | --- | --- |
| Individual commit | Existing `check-commit` selection | Fast checks for edited code; no new security scan was added here. |
| Pull request | `.github/workflows/security-pr.yml`: `sh scripts/security-static-analysis.sh` | Pinned Clang 23 analysis of the native runtime, 13 C entry points, and macOS HTTP Objective-C with core, Unix, and security checkers; diagnostics fail the job. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-security-os` | Compile the x86-64 kernel and loader plus the Arm64 kernel through the self-hosted compiler after parser changes. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-security-os-http check-security-os-http-sanitize` | Run hostile HTTP response bytes through the same pure parser used by the guest, normally and with ASan/UBSan. |
| Pull request | `.github/workflows/security-pr.yml`: `make check-os-net-stack check-os-net-stack-sanitize` | Exercise the guest's UDP, DHCP, DNS, ARP, and TCP receive guards with malformed packets and boundary lengths. |
| Pull request | Existing `.github/workflows/ci.yml` | Platform matrix, sanitizer tests, short AFL++ run, protocol and integration checks. |
| Pull request | `.github/workflows/security-pr.yml`: vendored SHA-256 check | Detect byte changes to the checked-in C sources and license copies so each change receives explicit review. |
| Nightly | Existing `.github/workflows/fuzz-nightly.yml` | Longer AFL++ compiler campaign and generated-program differential fuzzing, with retained corpus and evidence. |

Run the native analysis locally with `make check-security-static`. Its source
list is in `scripts/security-static-analysis.sh`. A new native security boundary
should be added to that list after analyzer warnings are triaged. The analyzer
does not understand Minyar `.min` source; reviewers must exercise compiler,
language, and protocol behavior through their focused Minyar tests. A passing
analyzer result is not a claim that all native code is safe.

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
