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
and snapshots both finals. Construction, output allocation/copy, disposal and
full hashing are within the operation timer; input generation is outside.
EVP uses its ordinary default provider, including normal setup/final-copy
overhead. Direct OpenSSL SHA uses stack value contexts. Disabling
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

Remaining: fresh independent review, parent public-driver integration commit,
WS7 Windows ABI qualification, shared
performance gates, and integrator-controlled merge after Phase 1. No merge or
gap closure is claimed by this evidence.
