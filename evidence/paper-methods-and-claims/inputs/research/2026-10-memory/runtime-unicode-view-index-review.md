# Unicode slice metadata: source-grounded rejection

Preserving `end-start` as a known Unicode slice character count while leaving
`character_offsets=NULL` is **invalid in the current representation**. The
existing slice constructor deliberately preserves a count only when slice byte
length equals scalar length. No candidate, execution, metadata extension or
production change was made for this hypothesis.

The frozen runtime translation unit is
`c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4`.
This review reads its indexing, slicing, join and construction consumers;
it does not supply new runtime counts or application timings.

| Consumer | Current source rule | Consequence for proposed known Unicode count with NULL index |
| --- | --- | --- |
| `ensure_text_index` | Build only when `character_length < 0`. | It would skip required index construction. |
| `minyar_text_length` | Ensure, then return the count. | The proposed numerical count alone could appear correct. |
| `minyar_text_character_at` | Known in-range count with NULL offsets returns `bytes[position]`. | UTF-8 bytes would be returned as scalar values. |
| `minyar_text_slice` | After ensure, NULL offsets map scalar bounds directly to byte positions. | A later slice could split a UTF-8 sequence. |
| Borrowed and consuming joins | Preserve a known result count only for byte/scalar equality; consuming join invalidates old offsets otherwise. | The reviewed join repair relies on precisely this representation invariant. |
| Formatting/construction | Public Float output is certified ASCII; Character Unicode encoding, file/argument data and Unicode slice copies remain unknown. | Existing constructors do not establish a general known-count/unindexed Unicode state. |

A hand-derived counterexample uses root `Aé🙂Z` and the proper scalar slice
`[1,3)`, whose bytes spell `é🙂`: two scalars and six bytes. Forcing the proposed
count two with NULL offsets would let `.length` return two, then Character zero
would return byte `0xC3` (195) instead of U+00E9 (233). A nested `[0,1)` slice
would select only that first UTF-8 byte. This is a source consequence of a
hypothetical representation mutation, **not an executed red**. The earlier
[consuming-join repair](runtime-unicode-join.md) separately contains an actual
red for this same invariant class.

The initial backing-index-sharing idea also lacks a small local implementation:
root breadcrumbs and the mutable trailing cursor use root coordinates, while
views use relative coordinates and may have different index word widths. The
view must retain its root, but its current destructor owns/frees any non-NULL
view offsets. Direct pointer sharing would therefore require coordinate and
free-ownership changes; pointer reuse alone is unsafe. Full slices already
retain the existing Text, ASCII slices already preserve counts, tiny slices of
large roots may copy, and compiler-arena short slices use a bounded cache.

The actual lexer first indexes its source, creates literal/chunk slices, and
`escapeLLVMText` may later query token length and Characters. This supplies a
compatible call-pattern source link, not a measured prevalence or a compiler
hot-path claim. Under compiler arena the views have no retained-root field, so
an ordinary-runtime root-sharing design would not directly cover that path.
No further count experiment is needed to reject the invalid single-field
propagation. A different lazily indexed Unicode representation would need its
own explicit contract and evidence; it is not proposed during the frozen cohort.
