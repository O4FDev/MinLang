# Compression API contract

`use "zstd" as zstd` and `use "deflate" as deflate` use maintained native
libzstd/zlib. There is no pure codec candidate or measured pure-code ratio in
this change. The native decision delivers complete codec interoperability;
the benchmark measures actual Minyar binding and allocation costs against
complete equivalent maintained C operations, not an assertion about a pure
implementation's speed.

## Buffers and ownership

`compress` / `decompress` return a private `Result`; `ok`, `status`, and `data`
inspect it. Success includes empty output; error output is empty. The caller
supplies `maxOutput` (0..256 MiB), never inferred from untrusted frame metadata.
Minyar's ordinary Bytes allocation policy still applies; this does not make
runtime allocation failures recoverable. Codec/native context allocation
failures return MEMORY or an unopened owner.

`compressInto` / `decompressInto` return the written length or a negative tag.
Destination length stays unchanged. Failures may have written an untrusted
prefix of up to its full length; no prefix length is returned and the caller
must discard it. Input and output regions must not overlap. Raw signatures
use `(src, srcLen, dst, dstCap)` plus context/format/level as applicable.
`zstd.decompressCtxRaw(owner: DCtx, src, srcLen, dst, dstCap)` is the repeated
operation replacing neo-vm's shim while preserving caller-owned DCtx reuse.
`zstd.rawDecompress(src, srcLen, dst, dstCap)` creates/frees a context per call.

CCtx/DCtx/CDict/DDict owners contain private shared cells; record copies share
closed state. `closeCCtx`, `closeDCtx`, `closeCDict`, `closeDDict` are idempotent
across copies. Explicit close is required: native resources have no automatic
destructor. Contexts and close require exclusive use, normally one DCtx per
thread. Dictionary use is a synchronous borrow; contexts detach references
before returning, so dictionaries can then be closed before contexts. By-copy
constructors accept up to 256 MiB of dictionary bytes; level validation and
allocation failure produce unopened owners. `isOpen*` detects that failure.

Explicit public `rawCreate*`, `rawClose*`, `raw*Ctx`, `raw*Dict` functions use
**unsafe Integer native handles**, solely for custom low-level integrations.
Only a live handle returned by the matching constructor is allowed. Destroy
exactly once; no stale/arbitrary/wrong-kind handle validation is promised.
Copying the Integer does not share close state. All raw addresses denote
caller-owned live readable/writable regions in the signed pointer range.
Numeric checks cannot prove mapped memory. Zero is allowed only for zero
length. Negative/overflowing ranges, overlapping buffers and output capacity
over 256 MiB are rejected before codec work.

## Complete formats and error precedence

zstd accepts complete concatenated normal/skippable frames and requires full
input; its decoder window is capped at 128 MiB. gzip accepts complete
concatenated members, including trailing empty members at an exact output cap.
zlib and raw DEFLATE accept exactly one stream and reject trailing bytes.
All framed checksums/trailers are validated before success. A one-byte scratch
probe detects overflow while allowing trailers and empty members at exact cap;
no byte from that probe reaches destination memory.

Tags are INVALID=-1, LIMIT=-2, TRUNCATED=-3, CORRUPT=-4, DICTIONARY=-5,
MEMORY=-6, CLOSED=-7, TRAILING=-8. Invalid numeric/format/level inputs are
rejected first by native operations, followed by null context/dictionary.
Result allocation wrappers validate output bounds and closed owners before
allocating. During decoding, a codec error observed in the current step takes
precedence over that step's probe output. Otherwise probe output establishes
LIMIT immediately: the decoder does not scan beyond overflowing output to
find later errors. Input exhaustion without completion is TRUNCATED, including
an incomplete trailing gzip member. Non-gzip unused input is TRAILING;
malformed gzip/zstd continuation bytes are CORRUPT or TRUNCATED according to
the observed parser state. State resets on the next zstd call recover from
limits, invalid data, truncation, dictionary failures and errors.

CDict/DDict use `ZSTD_dct_rawContent` and `ZSTD_dlm_byCopy` explicitly, including
bytes that start with formatted-dictionary magic. Compression uses
`ZSTD_compress_usingCDict`. Decompression attaches the prepared raw DDict to
the bounded streaming decoder. A wrong RAW dictionary may silently yield
wrong data: DICTIONARY reports only a diagnosed dictionary-ID/content error.
It cannot prove raw dictionary identity. Default compression has no checksum;
checksummed external frames are verified, but applications needing identity
or authenticity must enforce that separately.

## Providers and custom linking

`tools/compression_provider.py::codec_provider(codec, clang)` returns exact
header flags and selected archive paths. Set `MINYAR_ZSTD_PREFIX` and/or
`MINYAR_ZLIB_PREFIX` to a single provider prefix, or let pkg-config (Homebrew
fallback on macOS) discover it. zstd **always selects the absolute libzstd.a**,
never merely `-lzstd`: advanced APIs are static-only. Header and archive live
under the same provider prefix; their hashes participate in native object
cache identity. A compiled/executed version/64-bit ABI probe rejects mismatches.
MSYS2 uses the same active provider/compiler prefix and CRT; actual Windows
qualification is an integration gate, not established by the Linux evidence.
Apple SDK zlib may use its absolute stable public API `.tbd` link stub; zstd
still uses a Homebrew static archive with its own matched headers.

Manual custom link recipe (substitute the provider's exact output):

```sh
build/minyarc program.min program.ll --library library
clang -O2 -DMINYAR_SYSTEM_HEAP=1 -c runtime/minyar_runtime.c -o runtime.o
clang -O2 program.ll runtime.o runtime/native/zstd.c runtime/native/deflate.c \
  -isystem /usr/include /usr/lib/x86_64-linux-gnu/libzstd.a \
  /usr/lib/x86_64-linux-gnu/libz.a -pthread -lm -o program
```

The standard `./minyar` discovers native module markers and selects providers.
`tests/compression.py --mode native|sanitize --artifacts DIR` covers normal
launcher/link-driver and manual custom linking. `--compiler` / `--clang` (or
MINYAR_TEST_COMPILER / MINYAR_TEST_CLANG) select existing tools. Sanitizer mode
annotates generated IR through `tests/llvm_sanitizer.py`, instruments runtime
and providers, and runs a native canary/mutation cohort at default and seven-
byte chunks. Its Python ctypes oracle cohort is separately unsanitized; the
static archive is hidden inside that oracle bridge, still statically selected.
The provider archives themselves are distribution binaries, not rebuilt with
sanitizers. `--native-only` skips all Minyar compilation/link verification.

`benchmarks/compression.py --artifacts DIR --prepare-only` builds reference and
Minyar binaries and fixture inputs without timing. Request a parent quiet slot,
then use `flock /tmp/ws5-benchmark.lock python3 benchmarks/compression.py
--artifacts DIR --run-only`. Every sample retains argv, ns, operation counts and
source/compiler/provider/corpus hashes. Dict construction and reuse are
separate; the C reference constructs explicit RAW/byCopy CDict/DDict and calls
usingCDict/usingDDict. Into/raw reuse buffers; buffer comparisons include
allocation/release on both sides. These are codec boundary measurements, not
whole-project performance gates.
