# Checked pages

`use "pages" as pages` gives fixed-size page images, bounded named regions,
and forward-only cursors. This is useful for a database header, directory,
device image, or other binary format whose boundaries must survive aliases.
It uses ordinary records and Results; it does not change the language.

```minyar
use "pages" as pages
use "errors" as errors

function header(): Result<Bytes, errors.Error> {
    let page = try pages.create(4096, "orders page")
    let header = try page.region(0, 16, "header")
    let cursor = header.cursor()
    let version = try cursor.take(4, "version")
    let count = try cursor.take(4, "count")
    let lsn = try cursor.take(8, "lsn")
    let written = try version.writeUInt32LE(1)
    written = try count.writeUInt32LE(12)
    written = try lsn.writeInt64LE(42)
    return Ok<Bytes, errors.Error>(page.bytes())
}
```

`create(size, name)` allocates a zero-filled Page. Sizes must be from 1 to
`maximumBytes` (16 MiB). `fromBytes(data, size, name)` requires exactly that
many bytes and copies them. A short image returns `truncatedCode()`; a long
image or invalid size returns `invalidDataCode()`. Memory exhaustion remains
a fatal runtime failure, as it is for Bytes; this module does not reserve
memory or provide an allocation-failure Result.

`Page.size()` never changes. `Page.bytes()` returns an independent copy.
`Page.region(offset, length, name)` creates a shared view with immutable
bounds. `Region.region(offset, length, name)` uses offsets relative to that
region, so it cannot reach a neighboring field even when the page has room.
Negative ranges return `invalidDataCode()`. Out-of-bounds ranges return
`truncatedCode()`, including ranges whose mathematical end exceeds Integer.
Checks use subtraction rather than overflowing offset + length arithmetic.
Zero-length regions at the end are valid; past-the-end regions are not.

`Region.size()` reports its fixed length; `bytes()` copies its contents.
`write(data)` replaces exactly that many bytes and returns `Ok(true)`.
A size mismatch returns `invalidDataCode()` before any write. No operation
exposes backing Bytes, changes the page's size, or converts untrusted bytes
to Text. External Bytes may be resized after import without changing the
page; exported Bytes may be resized or modified freely.

`Region.cursor()` starts at zero. `Cursor.take(length, name)` returns the
next region and advances only on success. `position()` and `remaining()`
report the partition. Claims from one cursor never overlap unless empty.
Cursor aliases share their position. Separate cursors and explicit regions
can intentionally overlap and share writes; they are not exclusive borrows.
A region keeps its page alive after the creating locals leave scope.
These mutable references need ordinary synchronization if shared across
threads; they provide no locking or transactional multi-field writes.

Typed fields must have exactly the requested width. Methods return
`Result<Integer, errors.Error>` for reads and `Result<Boolean, errors.Error>`
with `Ok(true)` for writes:

| Read / write suffix | Bytes | Accepted Integer range |
| --- | ---: | --- |
| `UInt8` | 1 | 0 to 255 |
| `Int16LE` | 2 | -32768 to 32767 |
| `UInt16LE` | 2 | 0 to 65535 |
| `Int32LE` | 4 | -2147483648 to 2147483647 |
| `UInt32LE` | 4 | 0 to 4294967295 |
| `Int64LE` | 8 | -9223372036854775808 to 9223372036854775807 |

For example, `field.readUInt32LE()` and `field.writeUInt32LE(value)` require
a four-byte region. Width mismatches return `invalidDataCode()`; integer
range failures return `overflowCode()`. Failed writes leave bytes unchanged.
Multi-byte operations use little-endian order at any alignment. There is no
unsigned 64-bit numeric type here, no floating-point/UTF-8 validation, native
pointer API, schema generator, or static proof of offsets. Names appear in
error contexts as `page/region/field`.

The runnable [page ledger](../examples/gallery/page-ledger.min) encodes and
decodes one 120-byte page: a 64-byte header, an eight-byte payload, and two
24-byte directory entries. This shape comes from neo-db's snapshot header
and chunk directory (`src/storage/snapshot.min`), but the ledger has its own
magic and version and is not a compatible snapshot reader. Its decoder
checks metadata, reserved fields, directory size and contiguous tiling of
the payload. It rejects overlapping entries, gaps, truncation, negative or
huge lengths, and ranges crossing the payload. It performs no CRC,
durability, crash-recovery, or database integration checks.

Costs are explicit. Creation allocates and zeroes O(page size) bytes. Import
copies O(page size); exporting a page or region allocates and copies its
length. `Region.write` copies O(region size). Page, Region, Cursor and Result
values are managed heap records under the current runtime; calls allocate
Result wrappers and helper checks can allocate additional wrappers. Region
creation and scalar access perform constant-time runtime checks, with the
underlying Bytes accessors checking again. Names are concatenated for each
subregion; failures allocate errors, messages and context text. Regions and
cursors share the page without copying its bytes. This API promises checked
boundaries and stable alias behavior, not zero overhead or packed C ABI.

Successful paths construct the following values in this implementation:

| Operation | Result constructions | Other managed values |
| --- | ---: | --- |
| `create` / `fromBytes` | 2 | one Page and one Bytes image |
| `Page.region` / `Region.region` | 2 | one Region and its joined name |
| `Cursor.take` | 3 | one Region and its joined name |
| `Region.cursor` | 0 | one Cursor |
| typed read / `writeInt64LE` | 2 | no byte copy |
| other typed write | 3 | no byte copy |
| `Region.write` | 1 | no additional Bytes image |
| `Page.bytes` / `Region.bytes` | 0 | one copied Bytes image |

These are source-level construction counts, including helper Results;
they are not measured allocator calls or a promise about optimizer removal.
Each typed read checks width and then Bytes bounds. Narrow writes also
check the value range twice (here and in Bytes); Int64 needs no value check.
`take` checks the child range before adding its already bounded length to
the cursor. There is no unchecked access path.

Run `make check-pages` for O0/O2 executions with exact ownership cleanup,
malformed-image cases, integer endpoints, private-field rejections and the
gallery's expected output. `make check-pages-sanitize` uses the existing
compiler/runtime ASan and UBSan path.
