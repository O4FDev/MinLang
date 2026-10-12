# SHA-256 implementation evidence — 2026-10-12

Branch `ws5/sha256`; assigned local worktree `ws5-sha256`. Heavy work used only
owned Boat `bx_ev9fa25q`, `/home/user/ws5-sha256`, with the parent's prepared
compiler/runtime and existing dependencies. No base mutation, compiler rebuild
on the laptop, new box, or paid spending. Parent owns lifecycle and shared files.

RED before implementation: `tests/sha256.py --cases 0` with the existing Mac
compiler failed because `library/sha256.min` could not be opened. The preserved
drafts were expanded before the candidate implementation; they were not an
implementation approval. The current tests retain all original vectors and
split checks and correct the earlier selected-prefix coverage claim.

Final direct independent-object checks on Boat:

```sh
cd /home/user/ws5-sha256
python3 tests/sha256.py --cases 1024
python3 tests/sha256.py --cases 1024 --sanitize
python3 tests/sha256.py --module sha256pure --cases 512 --sanitize
```

The native checks passed 3,864 corpus cases, all 64 address alignments and 519
protected-page cases. ASan annotation assertions covered all 72/70/75 generated
functions in the three native test programs, with a freshly instrumented C
runtime/provider. The pure sanitized run passed 3,352 cases, with 71/69/74
annotated functions. Native final direct-object logs are in `logs/`; pure
`logs/pure-sanitize-r2.log` was captured before the Windows fixture branch was
added (the POSIX guard/oracle semantics were the same). Small Mac checks used
the existing compiler at `/Users/luke/Projects/Minyar-Lang/build/minyarc`, default
runtime object and local OpenSSL, and are recorded separately. Windows support
is implemented but has not been qualified by this child.

## Matched benchmark reproduction

The portable comparator uses the unmodified Mbed TLS 3.6.5 source files
`library/sha256.c` and `library/platform_util.c`, with a generated minimal
configuration containing only `#define MBEDTLS_SHA256_C`. No CPU SHA intrinsics
or assembly are enabled. Source/archive hashes are recorded; it is a benchmark
dependency, not vendored production code.

```sh
cd /home/user/ws5-sha256/bench
curl --fail --location --silent --show-error \
  https://github.com/Mbed-TLS/mbedtls/archive/refs/tags/v3.6.5.tar.gz \
  -o mbedtls-v3.6.5.tar.gz
tar -xzf mbedtls-v3.6.5.tar.gz
cd ..
MINYAR_SHA256_PORTABLE_PREFIX=/home/user/ws5-sha256/bench/mbedtls-3.6.5 \
  python3 tests/sha256-bench.py --prepare-only --build-dir bench/native-object-final
```

Archive SHA-256:
`b7cbbfb717f0c38521192d7954a2eb6b7ada5a10a44f72dadbae6655e7300023`.
OpenSSL distribution: 3.0.13, Ubuntu `3.0.13-0ubuntu3.16`, Debian amd64 ABI,
Clang 18.1.3. Compiler/library metadata and hashes are in each final JSON's
manifest. `provider_hashes` identifies the actual resolved libcrypto DSO;
`preparation_commands` contains compiler/object/link commands and flags.

Actual samples used only prebuilt binaries after parent-granted quiet slots,
with no child builds/fuzz/tests in flight. First candidate samples used local
terminal session 40300 and are retained in `pure-r1-results.json` and
`bench-pure-r1.log`. That exploratory C reference consumed the final context;
the final authoritative references explicitly copy every context for
nonconsuming finalization and repeat the pure measurement too.

Final samples ran in session 97995, **14:21:24–14:21:36 UTC**, after a process
inspection returned no live compiler/build/module-test processes:

```sh
flock /tmp/ws5-benchmark.lock python3 tests/sha256-bench.py \
  --run-prepared --build-dir bench/native-object-final \
  --bytes 1048576 --iterations 64 --samples 5 --output bench/native-final-results.json
flock /tmp/ws5-benchmark.lock python3 tests/sha256-bench.py \
  --run-prepared --build-dir bench/native-object-final \
  --bytes 64 --iterations 32768 --samples 5 --output bench/native-64-results.json
flock /tmp/ws5-benchmark.lock python3 tests/sha256-bench.py \
  --run-prepared --build-dir bench/native-object-final \
  --bytes 1024 --iterations 8192 --samples 5 --output bench/native-1024-results.json
```

There is one untimed warm-up batch per mode/provider; provider order rotates
each sample. JSON stores every command/environment, elapsed nanoseconds,
checksum, hashes, compiler/version/CPU metadata and medians. All providers
produced the same digest checksums. Each lifecycle hashes the prefix, snapshots
it, clones the live context, feeds identical remaining chunks to both states,
and snapshots both finals. Full hashing, context copies and digest consumption
are inside each operation timer; input generation is outside. Minyar allocates
heap-owned output Bytes and performs their RC cleanup before the ending clock
call. Direct OpenSSL SHA and Mbed TLS use stack contexts and digest buffers,
with no corresponding output heap allocation/disposal. EVP uses its ordinary
default provider, including context allocation/freeing and final-copy overhead
inside the timer. Disabling
`OPENSSL_ia32cap` is reported separately and is not described as portable C.

At 1 MiB, one-shot/lifecycle median times in milliseconds were:

| Provider | One-shot | Snapshot/clone lifecycle | Sample CV %, one-shot/lifecycle |
| --- | ---: | ---: | ---: |
| Pure Minyar | 234.428 | 361.536 | 3.02 / 3.82 |
| Selected native Minyar | 27.555 | 41.281 | 5.88 / 2.52 |
| OpenSSL EVP default | 27.685 | 42.853 | 4.28 / 4.90 |
| OpenSSL direct SHA default | 27.749 | 41.598 | 5.08 / 3.46 |
| OpenSSL disabled x86 caps | 109.821 | 171.204 | 6.21 / 1.71 |
| Mbed TLS portable C | 128.997 | 191.047 | 5.04 / 4.87 |

The pure candidate is far above 1.5× under both maintained default and portable
references; native selection does not rely on noise near the threshold. Small
input evidence is retained, including the native wrapper's overhead relative
to direct stack-context C. These module-only benchmarks do not establish the
shared whole-program/compiler performance gate; the parent owns that gate and
the normal launcher integration. This branch changes neither compiler nor
runtime core nor `crypto.min`.

For nonoverlap with tar's 14:19:02–14:19:17 samples: prior SHA preparation's last
log write was 14:18:55.282121031 UTC, manifest write 14:18:55.281121037 UTC; the
terminal returned exit 0 before the parent completion notice. Exact process
exit UTC was not explicitly logged. Tar also inspected process quiescence.

## Parent provider and launcher validation

The parent's latest `format_provider.py`, `sha256_provider.py` and additive
driver were copied only onto this child's Boat directory for validation, and
are not committed on the module branch. `parent-provider-launcher-receipt.json`
records their file hashes, selected arguments and all 106 dependency/library
inputs. Matched provider fingerprint:
`4d735c754c6f6e95b77faa98164442780f20439fe09df9555c4de38612e1a2b1`.
It selects `/usr/include` and the actual
`/usr/lib/x86_64-linux-gnu/libcrypto.so.3`, with `-ldl -pthread` and an explicit
rpath. The version/64-bit/abc-digest probe, wrapper/direct provider calls,
independent SHA-object link, and normal launcher all passed.

Reproduce on Linux with a prepared compiler/runtime after the parent
integration files are available:

```sh
python3 docs/evidence/sha256/provider-check.py
```

The retained script expects the repository root as its working directory and
writes its receipt to `logs/`. The first attempt caught the normal launcher
refreshing the copied compiler/toolchain stamp: its automatic compiler link
flags added `-fuse-ld=/usr/lib/llvm-18/bin/ld.lld -Wl,--threads=1` to the parent's
`-flto=thin`. The prepared compiler binary consequently changed from `f4f589...`
to `0b8bd2...`; runtime bytes remained `effee319...`. Stage-2 compiler LLVM and
compiler/runtime source bytes remained identical to the read-only base; see
`launcher-toolchain-comparison.log`. The second attempt passed the before/after
compiler/runtime identity assertion. Benchmark JSON retains the original
prepared compiler/runtime hashes and prebuilt benchmark binary hashes. This is
an integration smoke check, not the parent's broader neutrality gate.
The SHA consumer generated by the base compiler and relinked normal compiler
also matches byte-for-byte (`sha256-codegen-identity.log`), SHA-256
`077d80d23e2d891fee6fcc72e0b847d74afcf0b13fe88ec651ddf41e3252aee5`.

The historical script's dry-run assertion searched for unquoted `clang ` and
`cc `, missing the quoted compiler recipes present in the retained receipt.
That assertion did not prove reuse without rebuilding. Equal before/after
artifact hashes establish byte identity only. The updated script removes the
assertion and records this limit explicitly; no absence-of-rebuild claim is
made. It writes `logs/provider-image-launcher-receipt.json`, leaving the old
receipt filename untouched. Historical JSON and raw logs remain unchanged.
Its old provider receipt also predates actual-image validation: the independent review confirmed the
retained default Linux image/hash, but arbitrary copied prefixes were not
validated by that receipt. Fresh provider regression evidence is recorded
below separately from the original SHA and launcher runs.

Remaining: fresh independent review, parent public-driver integration commit,
WS7 Windows ABI qualification, shared
performance gates, and integrator-controlled merge after Phase 1. No merge or
gap closure is claimed by this evidence.


## Provider review fixes, fresh non-timing checks

Branch `ws5/provider-fixes`, selective local worktree `ws5-provider-fixes` and
independent owned Boat directory `/home/user/ws5-provider-fixes` on
`bx_ev9fa25q`. Only provider/test files and SHA evidence-script/docs changed.
The base directory was not mutated; no installs, box lifecycle actions, compiler
bootstrap, timing benchmarks, security changes, shared driver edits or merges
were performed.

The ten-test RED run failed on the original provider on both hosts. It reproduced
copied real shared-library image mismatches, mixed secondary/forced OpenSSL
headers, literal-backslash diagnostics, and missing effective link-flag support.
Linux also reproduced mixed archive headers and a normal `LD_LIBRARY_PATH`
override. Additional regression discovery retained separate RED logs for a
forced configuration header outside an `openssl` directory and non-PIE ELF PLT
addresses. The final suite also rejects an extra shared image supplying only
`SHA256_Final`, while the primary API remains in the selected provider.

Final commands:

```sh
# Mac: installed Clang/OpenSSL; libarchive development headers are absent.
python3 tests/format-provider.py --kind sha256 -v
# Owned Boat, /home/user/ws5-provider-fixes:
python3 tests/format-provider.py -v
```

The final Linux run passed all 12 tests, including real SHA and libarchive
providers, all image/header negatives, effective flag validation/fingerprints,
and the real static-archive fallback with space/apostrophe and primary/secondary
header refresh. Mac ran the same 12-test suite with 9 passing and 3 explicit
skips: missing libarchive development headers and the two ELF-only tests.
Temporary fixture prefixes are canonicalized before deriving child paths,
including macOS `/var` to `/private/var` resolution. Literal POSIX backslash
prefixes are explicitly unsupported, with an independent real compile/run
showing that this is a dependency-path limitation rather than a bad provider.

[The fresh manifest](provider-fixes-r1/manifest.json) binds source/test/script
SHA-256 values to both hosts' provider receipts and raw RED/GREEN files. The
receipts include every selected input hash and the verified actual API image:
Mac OpenSSL `/opt/homebrew/Cellar/openssl@3/3.6.5/lib/libcrypto.3.dylib`; Linux
OpenSSL `/usr/lib/x86_64-linux-gnu/libcrypto.so.3` and libarchive
`/usr/lib/x86_64-linux-gnu/libarchive.so.13.7.2`. Boat command handles and full API
responses are retained in the new `*.transport.json` files.

The updated launcher evidence script was syntax-checked, not rerun in this
selective worktree. The parent's fresh public-driver/launcher integration and
independent review remain required. Windows API-image logic is implemented but
unqualified; no Windows, performance-gate or merge claim follows from these
provider checks.
