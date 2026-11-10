# Minyar security audit — 19 October 2026

This review covered the current shared working tree, including changes that were
already staged when the audit began. Scoped GPT-6 Sol and Daybreak Blue agents
reviewed the compiler and language semantics, native runtime, file API,
networking and peer edge, freestanding OS, data formats, packages, updater,
release tooling, and CI. A second adversarial pass crossed reviewer scopes and
found three more defects. Detailed evidence is in `/private/tmp/minyar-*-audit.md`
and `/private/tmp/minyar-security-secondpass-*.md`. This document records the findings and the
checks run after remediation. It does not claim that source review can prove the
absence of undiscovered vulnerabilities.

## Confirmed findings and disposition

Every confirmed defect found in this review has a code fix in the working tree.
All runnable focused regressions passed; platform and hardware validation
limits are stated below.

| Finding and attacker-controlled boundary | Fix and regression |
| --- | --- |
| `files.readAppend` reserved the requested length before reading any bytes; an excessive caller length could exhaust memory even at EOF. POSIX `files.list` could stop on a directory name containing invalid UTF-8. | `runtime/native/files.c` reads in 64 KiB chunks and handles raw directory names without a fatal UTF-8 conversion. `tests/files-ranges.c` and `tests/files-r2.min` passed, including seven macOS ASan/UBSan cases. The Linux directory-name branch awaits the Linux CI run. |
| Text diagnostics and launcher path/status lines could print attacker-controlled terminal controls from source, import names, and file paths. | `compiler/stages/diagnostics.min` and `minyar` escape C0, DEL/C1, line separators, and bidi controls in human-facing output while preserving JSON diagnostic values and actual filesystem arguments. Byte-exact diagnostics (126 cases), launcher isolation (8 cases), and shell syntax passed. |
| The second pass found a native-input/output collision diagnostic and Clang's inherited stderr could still print terminal controls from native paths. | `tools/driver-support.min` escapes human diagnostics and `tools/clang-driver.min` routes Clang stderr through bounded capture in `tools/clang-driver-host.c`; structured JSON/SARIF output stays machine-readable. Launcher isolation covers the collision, native source diagnostics, invalid UTF-8, and a diagnostic flood; all eight launcher cases and native host C syntax checks passed. |
| A persistent gateway kept its role after its certificate fingerprint was removed from a valid registry refresh. | `library/peeredge.min` rechecks bound gateway certificates on refresh and drops removed peers. `tests/peer-edge-pki-test.min` proved revocation of an existing session and continuity of a retained gateway in normal and ASan/UBSan runs against a post-fix edge binary. |
| QUIC Retry issuance stopped permanently at the per-key limit, preventing new QUIC peers until restart. | `library/quicretry.min` rotates its key at the issuance limit and retains previous keys through token expiry. `tests/quic-retry.min` used a small injected limit and passed normal and ASan/UBSan rollover/overlap tests. |
| Portable and macOS HTTP request APIs accepted embedded line breaks or invalid method/header framing; ordinary buffered responses had no default body cap. | `library/http.min`, `library/platform/macos/http.min`, and `runtime/native/http.m` validate request tokens and fields, reject caller-owned framing headers, and give ordinary buffered requests a 128 MiB body limit and 30 s deadline. Explicit bounded POST/general request APIs were added; streaming remains explicit. Portable and macOS normal and ASan/UBSan tests passed, including invalid identity-stream header handling. |
| The second pass found that the macOS body cap rejected valid bodyless HEAD and 304 replies solely from their advertised `Content-Length`. | `runtime/native/http.m` skips the declared-length precheck for HEAD, 204, and 304 while retaining the received-byte cap. The platform-backend HEAD and 304 fixtures passed normal and ASan/UBSan tests with a one-byte limit below the advertised length. |
| Guest UDP lengths below eight, truncated DHCP options, and malformed DNS names/RDATA could reach fatal checked reads and halt the OS. ARP could grow an unbounded cache. | `os/kernel/net/wire.min` validates these packets before use; `stack.min` applies source/state checks and bounds the ARP cache to 64 entries. The hosted parser regression passed normally and under ASan/UBSan. |
| The second pass found that tuple-matching TCP RST and ACK segments could change guest connection state without a receive-sequence check. | `os/kernel/net/stack.min` uses shared predicates in `wire.min` before reset, window, or ACK state changes, and randomizes the initial client port and each connection's sequence number. The hosted tests call those production predicates and passed normally and under ASan/UBSan; x86-64 and Arm64 freestanding kernel compiles passed. |
| Guest HTTP could buffer unbounded responses, fatally decode malformed UTF-8 headers/bodies, and overflow checked integers while parsing lengths. | `os/kernel/net/httpresponse.min` is a bounded, recoverable response parser; `http.min` caps incoming plaintext and aborts malformed exchanges. Agent consumers validate JSON bytes before Text conversion. Hostile-response tests passed normally and under ASan/UBSan. |
| Completed and failed guest HTTP requests could leave a live TCP connection resident indefinitely when a peer did not complete shutdown. | `os/kernel/net/http.min` aborts the connection after owned complete responses, TLS failure, and premature close. Terminal connection retention is tested through the same `wire.min` helper used by `stack.min`. The full `http.poll` transition received state-path review and x86-64/Arm64 freestanding compilation; a hosted direct run is unavailable because it imports hardware/interrupt assembly. |
| A malformed Minyar boot-disk directory count could index beyond its fixed table; a huge declared file size could force excessive reads. Direct ATA requests could exceed the hardware count contract or wait indefinitely. | `os/shared/disk.min` validates table spans/count and caps file reads at 16 MiB. `os/shared/ata.min` checks count/LBA and bounds status polling. Both x86-64 loader/kernel and Arm64 kernel LLVM builds passed. No malicious-disk boot or ATA hardware test was run. |
| JSON metadata budgets were applied after tree allocation, and duplicate-name checking was quadratic for large LSP objects. Nonfinite exponents could produce a non-JSON numeric value. | `library/json.min` enforces value/member limits while parsing, sorts decoded keys for O(n log n) duplicate detection, and rejects nonfinite numbers. `tests/json-metadata-limits.min` passed at O0/O2, including 8,192 distinct names and escaped duplicates; normal and sanitizer parser suites passed 79,655 cases each. OS network JSON consumers now use bounded strict parsing. |

The supply-chain review found no confirmed signature bypass, archive escape,
or CI secret exposure. Existing update-bundle, manifest, and release-signing
checks passed 13, 5, and 21 cases respectively.

## Security tooling now in the working tree

- `.github/workflows/security-pr.yml` runs only on pull requests or manual
  dispatch. It verifies vendored source/license hashes, runs pinned Clang 23
  static analysis on 13 native C sources and macOS HTTP Objective-C, compiles
  both freestanding OS variants, and runs normal plus ASan/UBSan hostile HTTP
  and packet parser tests. No new security step was added to `check-commit`.
- `scripts/security-static-analysis.sh` and `build-support/security.mk` expose
  the same native and OS gates locally. `build-support/networking.mk` adds the
  packet parser targets without adding them to each individual commit.
- `.github/dependabot.yml` now watches npm, Cargo, Go, and GitHub Actions
  manifests. `vendor/SHA256SUMS` fingerprints the current checked-in C sources
  and license copies; the PR gate checks all eight entries. Changing the
  manifest itself still requires source/provenance review.
- `docs/security-review.md` gives agents a scoped finding format, validation
  order, and handoff rule. The existing CI and nightly workflows retain their
  broader sanitizers, protocol tests, AFL++ compiler fuzzing, and generated
  program differential fuzzing.

## Verification and limits

On this macOS host, the combined new PR gate passed:

```sh
make -j1 LIMITED= SANITIZER_LIMITED= check-security-os check-security-os-http check-security-os-http-sanitize check-os-net-stack check-os-net-stack-sanitize
```

Clang static analysis reported 14 native sources clean. The eight vendor
fingerprints, workflow YAML parse, and `git diff --check` passed. The
compression provider/native interop/fuzz target also
passed after replacing a GNU-only `readlink` use in its test with the existing
cross-platform path resolver.

The new GitHub workflow has not yet run on GitHub; branch protection and
repository security settings could not be read from this host. The full test
suite, Linux-specific file-name behavior, dynamic malicious boot-disk/ATA
hardware behavior, and a live guest HTTP state-machine test were not run here.
The TAR dynamic suite requires a discoverable `libarchive.pc` on this host.
These are validation gaps, not known unfixed defects. Run the existing full CI
matrix and the new PR workflow on the resulting pull request before merging.

The PR analyzer currently covers the listed native sources on macOS. It does
not yet analyze Linux-only erofs, libarchive/zstd, Windows credential/TLS, or
other platform-native branches; those need dependency-aware jobs on their
respective platforms. The guest TCP test runs the production acceptance
predicates, while live packet injection into the hardware-bound receiver and
an adversarial boot-media run remain untested.

Further defense work that was not a confirmed exploit in this review includes
parser-specific coverage-guided fuzzing beyond the existing compiler campaigns,
complete upstream provenance for vendored files, a private vulnerability
reporting channel and `SECURITY.md`, and release SBOM/build provenance plus
archive expansion bounds. The release key and live repository settings need a
separate operational review before a public binary release.
