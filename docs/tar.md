# Bounded tar archives

`use "tar" as tar` reads and writes in-memory OCI image layer archives through
libarchive. It never extracts filesystem paths. Path traversal names and OCI
whiteout names are returned as bytes for the caller's policy.

`reader(source, maximumBytes, maximumPath)` rejects an oversized source before
opening the provider. `readerWithLimits` additionally takes
`maximumMetadata`, `maximumChain`, and `maximumHeaders`. Defaults are 1 MiB
extension data/effective attributes, 64 extension headers per member, and one
million physical headers. Metadata counts cumulatively across each member's
extension chain, including overwritten records. Persistent global attributes
and effective global/local attributes also obey the metadata bound. Replacements
and deletions are resolved before checking the final byte/count bounds, including
updates within a global header; equivalent maps do not depend on keyword order. At most
4096 distinct attributes are retained. Names, links, uname and gname obey the
byte path limit, without embedded NULs. These are resource limits, not an
extraction policy.

`next(reader)` returns `{entry, end, error}`. Errors and EOF are sticky. Complete
members before a later terminal error remain available. The parser checks
checksums (unsigned and historical signed), numeric grammar/range, extension
record spans, payload plus padding, and footer padding. V7, ustar, GNU long
names/links, GNU base-256 numbers, and PAX local/global records are supported.
Regular files, hardlinks, symlinks, directories, character/block devices and
FIFOs are supported. Sparse headers/attributes are explicit unsupported errors.
A valid footer has two zero blocks followed only by whole zero record blocks;
nonzero member payload padding is allowed.

Entry fields are `path`, `link`, `uname`, `gname` (Bytes), `mode`, signed `uid`
and `gid`, signed `mtime` plus `mtimeNanos` in 0..999999999, `type`, `size`,
`deviceMajor`, `deviceMinor`, and `attributes: List<Attribute>`. Timestamps use
floor seconds: `-1.25` becomes `(-2, 750000000)`. Decimal timestamp conversion
is exact; nonzero precision beyond nanoseconds and signed-range overflow fail.
`entry(path, type)` creates editable metadata with regular defaults.

`payload(reader, entry)` and `memberBytes(reader, entry)` return BytesResult.
`memberStart`, `headerOffset`, `payloadOffset`, and `memberEnd` return physical
offsets. A member span includes its preceding GNU/PAX/global extension chain,
base header, payload and member padding, excluding the archive footer. These
ranges use validated private lengths, so editing public size/path fields does
not alter the original payload range. Provenance checks bind ranges to the
reader's source buffer. Spans after a previous global record may depend on that
record's state; use the writer to make an independently readable member.

Reader and Writer are typed shared records. Copies alias their context and
closed state. Use a context exclusively; there is no concurrent-use locking.
Keep source bytes unmodified until reader close. EOF/error closes a reader
exactly once; `close(reader)` is required on early exit. `finish`/error closes
a writer; `closeWriter(writer)` is required on early exit. Repeated close is
safe. Payload/member copies remain available after close while source bytes
remain unchanged. Abandoning an unfinished context without close leaks its
native resources; these records have no automatic finalizer.

Raw effective PAX attributes retain vendor fields, binary xattrs and file
capabilities, including embedded NUL/newline/value bytes. Duplicate keys use
the last record. Global empty values delete persistent attributes. Local
empty values suppress a global attribute for that member, restoring the base
field; later members retain the global value. Multiple local headers combine
in physical order. PAX fields override GNU long names/links and base fields.
`hdrcharset=BINARY` needs no lossy Text conversion. `xattrs(entry)` is an optional
normalized view: SCHILY names/values are raw; LIBARCHIVE names use percent
escapes and values use base64. Conflicting aliases or malformed encodings
return an error in that view while raw attributes remain accessible.

`writer(maximumBytes)`, `append(writer, entry, payload)` (BooleanResult), and
`finish(writer)` (BytesResult) produce deterministic ustar/PAX output. The
exact output limit includes header/extension/payload padding and the two-block
footer. The writer adds no extra record blocking. Typed fields take precedence
over stale standard PAX attributes; supplied payload length determines size.
Unknown nonempty attributes are preserved. Accepted empty-target hardlinks keep
their hardlink wire type; callers still own filesystem/link-target policy.
Absolute byte paths that cannot use a nonempty ustar prefix remain exact PAX
paths. Wide signed fields and exact
timestamps are materialized in PAX without passing extreme values to the
provider's decimal formatter. Finish is idempotent and returns an independent
copy. Append after finish fails. Invalid append/limit errors are sticky.

The native provider validates headers and writes base headers/payload padding;
the bounded wire scanner resolves the byte metadata and physical spans that
its public API does not expose. Global/multiple-local PAX chains are resolved
before validating the physical base header because libarchive's semantics and
recursion limits differ. Payload copies use validated source ranges.

## Build and check

The shared launcher links `runtime/native/tararchive.c` automatically from
the `tararchive` native marker. Use `./minyar --release demo.min -o demo`.
The parent-owned `tools/format_provider.py` resolves one matched 64-bit provider
prefix, verifies its header/runtime version and ABI, fingerprints compiler
dependencies and the actual shared library (or Windows DLL/import archive),
and adds the required rpath. `MINYAR_TARARCHIVE_PREFIX` selects a prefix.

For custom linking, compile Minyar to LLVM, compile the chosen runtime, then
call `format_provider('tararchive', clang, compileFlags)` from that helper.
Pass the returned cflags when compiling `runtime/native/tararchive.c` and pass
the returned libraries after its object when linking with generated LLVM and
the runtime. The flags are literal argument lists; do not concatenate them
into a shell command. Preserve the same compiler, ABI and compile flags.

`python3 tests/tar.py --quick` is the small native check. Full seeded mutation
and ASan/UBSan runs are `python3 tests/tar.py` and
`python3 tests/tar.py --sanitize`; generated LLVM, runtime and native binding
are instrumented. The test compares exact Python metadata, independent wire
spans/attributes, libarchive metadata/payloads, complete entries before errors,
writer round trips, binary xattrs, context aliases and exact resource limits.
An isolated tar branch may set `MINYAR_TAR_PROVIDER_TOOLS` to the parent-owned
tools directory until those shared changes are integrated.

Initial `033dbf6` Linux verification (2026-10-12, `bx_ev9fa25q`) passed 2073 cases
in both native and generated-LLVM/runtime/binding ASan/UBSan modes, including
LeakSanitizer. `native-final-r3.log` and `sanitize-final-r3.log` retain output;
`commands-r3.json` retains command `cmd_4faxchwpxjsx` and its 15:18:26–15:18:43
UTC bounds. The full native run also verifies public/shared-driver linking.
No macOS provider runtime run is claimed: libarchive development files were
absent. Windows provider qualification and full integration remain with WS7
and the integrator. No shared compiler/runtime code was changed here.

The C oracle uses byte-preserving UTF-8 getters when locale getters fail.
Global/multiple-local records are independently materialized for C comparison,
and empty base links receive a placeholder so C retains the link type. The
only timestamp exception is the observed libarchive **3007002** negative PAX
fraction bug; its incorrect value is asserted before substituting the exact
decimal expectation. Other provider versions receive no such exception.

## Backend evidence

The preserved pure candidate is `benchmarks/tar/pure-tar.min`. Its seven-sample
prebuilt Boat run is `docs/evidence/tar/pure-linux.json`, with timing bounds in
`pure-timing.log` (command `cmd_ymmcmyx4gpuz`, 14:19:02–14:19:17 UTC,
2026-10-12). Pure/C median time ratios were 8.479 metadata read, 4.849 metadata
round trip, 3.119 payload read, and 3.089 payload round trip. These exceed the
unchanged 1.5 preference, so the maintained native provider was selected.

`benchmarks/tar/run.py --prepare` builds the native API demo and matched C
reference in `build/tar-native-benchmark`, retaining source/binary/provider
hashes. `--measure --samples 7 --output PATH` verifies prepared inputs and runs
only those binaries. Run measurement in a parent-approved quiet Boat slot
under `flock -n /tmp/ws5-benchmark.lock`. Both programs read every metadata
field and copy each full payload; round trip additionally writes every member
and closes the archive. Fixtures cover many small and fewer large payloads.
The Minyar API also performs strict validation, byte/span bookkeeping and
recoverable error checks. Native overhead must be reported from these samples;
selection of a C backend does not establish a 1.5 native/C ratio.

The `033dbf6` native run (`cmd_sytxxef4wwiy`, 15:23:56–15:24:06 UTC, 2026-10-12)
retains seven alternating Minyar/C samples per operation in
`docs/evidence/tar/native-linux-r3.json`. Median native/C ratios are **3.948**
for metadata read, **3.348** for metadata round trip, **2.041** for payload
read, and **11.048** for payload round trip. Each sample performs 100 complete
operations; all observable checksums match. These measurements include the
extra validation and API/output copies, but do not isolate their individual
costs. The 11.048 payload round-trip ratio is a remaining performance
limitation; this API does not meet a 1.5 native/C bound. No threshold was
changed. Backend selection follows the failed pure preference above, not a
claim that native is faster on every workload.

`native-manifest-r3.json`, `native-preflight-r3.json`, `native-prestart-r3.utc`,
`native-processes-before-r3.txt`, `native-timing-r3.log`, and `commands-r3.json`
retain provider/source identities, preflight results, quiet prestart inventory,
UTC bounds and command outcomes. Measurement verified all 14 prepared inputs
and all 83 actual provider inputs, then used only the prebuilt binaries under
the parent-approved `flock -n` slot. Compiler/provider discovery occurred at
preparation time. Broader platform and shared 1% performance gates remain
integration work; these new-module measurements do not qualify those gates.

## Completed-review fixes

The first completed review of `033dbf6` reproduced three gaps: loss of the
leading slash on a 101-byte absolute path, conversion of an empty-target
hardlink to a regular file, and order-dependent rejection of a valid final PAX
map. `tests/tar-review.min` and `tests/tar_review.py` add direct-write/rewrite
and byte/count-bound regressions. The same map-construction bug also affected
global replacements/deletions and the 4096-attribute boundary; those cases are
covered. Exact 100-byte and 4096-key final maps pass, while one-over maps fail.
Raw wire, cumulative extension and ownership limits are unchanged.

`docs/evidence/tar/fixes-r1/` retains RED/green outcomes, source/compiler/LLVM/
binary hashes, complete commands and a new prebuilt provider manifest. The
original candidate fails eight focused variants; the corrected implementation
passes all 21 controls, the original 2073-case corpus and generated-LLVM/runtime/
binding ASan/UBSan/LeakSanitizer. Command `cmd_nziqfhzjbg0z` ran full native,
full sanitizer, focused sanitizer and prebuild checks at 15:50:09–15:50:40 UTC
on 2026-10-12 in the separate owned `/home/user/ws5-tar-fixes` directory using
the read-only base compiler. `tests/tar.py` includes these regressions in both
ordinary and sanitizer runs; the standalone script takes `--artifacts PATH`.

`finish` now retains its owned native status packet directly and slices only
the independently owned caller value. Repeated/aliased finish still returns
fresh bytes, including at a 1 MiB payload's exact archive cap. The non-timing
Linux `tests/tar_copy_count.py --artifacts PATH` probe proves one large output
slice and one native output extent, each 4,228,096 bytes. The earlier review
counted two such slices plus that extent. The unchanged reader counts and
observable checksums accompany the counters in `copy-results.json`. This
removes one complete output copy; it does not transfer the C buffer or weaken
caller ownership. No new timings were collected. The 11.048 ratio above belongs
to `033dbf6` and is preserved as historical evidence, not a measurement of the
fixed source. New timings need green prebuilt binaries and parent quiet-slot
approval. A new fresh review and all platform/integration gates remain pending.

This implements the tar portion of IMAGE-4. erofs/ext4 image writing is still
deferred; no IMAGE-4 completion or integration claim follows from this module.
