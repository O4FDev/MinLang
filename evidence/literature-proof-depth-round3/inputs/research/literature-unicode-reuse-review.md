# Independent consuming-Text Unicode review

The engineer identified a semantic defect in `minyar_join_text_take_left`. Independent static inspection confirms the invariant mismatch, and the engineer's source-snapshotted system/K32/O2 [red execution record](../../build/memory-research-text-join-index-red/run-8o4rlalr/results.json) compiles successfully then observes U+00C3 where U+00E9 is required. This lane inspected that record, rather than independently rerunning it. No native execution or production edit was made by this lane; the engineer owns the red fixture and fix. Current source is the frozen snapshot recorded in the accounting evidence's raw `runtime/minyar_runtime.c` hash. This finding concerns cache validity during unique reuse, not a new reclamation algorithm or established publication novelty.

`ensure_text_index` builds an index only when `character_length < 0`. Index building leaves ASCII with a known count and no offsets; non-ASCII has a known count and allocated offsets. `minyar_text_character_at` directly reads `bytes[position]` when the count is known and offsets are null. Therefore successful valid UTF-8 objects satisfy:

```text
known character length + no offsets => ASCII => character length = byte length
unknown character length (-1) => later access rebuilds/validates index
known non-ASCII character length => usable offsets
```

Unique owning consuming join frees the left offsets and sets them null, while summing two known character counts regardless of UTF-8 width. For indexed left `é🙂` (six bytes/two characters) plus known ASCII `!` (one byte/one character), it publishes seven bytes/three characters/no offsets. Predicted first Character access returns byte `0xC3` instead of code point `0xE9`; other accesses also read UTF-8 continuation/leading bytes. A length-only assertion can pass because three is numerically correct. Slice also relies on offset validity and must be checked independently.

| Input/control | Consuming-path assessment | Needed oracle |
| --- | --- | --- |
| Known indexed Unicode left + known ASCII right | Invalidates left offsets but preserves non-ASCII known count | Character code points, bytes, slice and length |
| Known ASCII left + known indexed Unicode right | No left index existed, yet combined count falsely certifies ASCII | Same, including right-side Character |
| Both Unicode/indexed | Same invariant mismatch | Full decoded sequence |
| Unicode + known empty Text | Even zero added bytes frees the existing required index | Original sequence remains unchanged |
| Indexed Unicode self-join | Explicit `right == left` support repairs byte pointer after resize but does not repair index state | Doubled decoded sequence, exact ownership recovery |
| ASCII + ASCII, including self-join/empty | Known count without offsets is valid | Preserve no-index fast path and bytes |
| Either character count unknown | Existing sentinel branch resets to unknown | Lazy index builds correctly; control against broad failure claim |
| Shared owner or view on left | Copy fallback constructs unknown-length result | Control ownership/reference validity and identical Unicode result |
| Right view retaining left root | The root has an additional owner, so unique mutation must fail and copy | Preserve view bytes/root and result |

The suggested minimal repair keeps a known count only if both **old** character counts equal their saved byte lengths; otherwise it sets the unknown sentinel after freeing offsets. Use saved `left_length`/`right_length`, because `left->byte_length` has already changed and `right` may alias `left`. For known valid UTF-8, equality certifies ASCII; concatenated ASCII remains ASCII with count equal to combined byte length. This maintains the common ASCII no-index path without retaining stale Unicode metadata. Always setting unknown would also restore correctness, with a separate performance tradeoff. An empty-append special case could retain old offsets but is a distinct optimization, unnecessary to close this invariant defect.

Reusing storage safely requires preserving semantic metadata as well as counts/aliases. The indexed cache is derived from the bytes, so any reuse path changing bytes must establish a valid cache state. This is a concrete obligation for future uniqueness/reuse experiments; a successful owner-count model does not verify Text decoding semantics. The new accounting model deliberately has no UTF-8/index representation and cannot detect this defect.

Generated-language reachability is statically plausible with `let text = "é" + "🙂"; print(text.length); text = text + "!"; print(text[0])`. The first join creates a fresh owned Text; `.length` builds its Unicode index; `compileStatement` recognizes `x = x + e`, and `takeOwner` transfers its local ownership into the consuming join. ASCII literals are emitted with known byte/character count. Execution must still check the generated call and dynamic uniqueness rather than treating this reasoning as a completed source regression.

Pending evidence: fixed result across eager/system/fixed/lazy profiles and representative budgets, actual generated-language execution of the optimized path, ASCII allocation/latency controls, and exact final owner/byte recovery. Compilation remains reserved. The one first-character red case above is completed engineer evidence; the broader matrix and generated-language cases remain pending.

## Independent isolated candidate result

Parent-authorized tiny independent execution subsequently used [peer-memory-unicode-join.c](../../tests/peer-memory-unicode-join.c) against both saved runtime snapshots at system/K1/O2. [Retained result](../../build/peer-memory-unicode-independent-tv6xn_4n/results.json): baseline aborts on the slice-first byte-length oracle; isolated candidate passes twelve orientation/control cases and a long Unicode index boundary at Character positions127/128/130. It checks exact header reuse versus shared/view fallback and zero final managed objects/bytes/system allocations. The malformed unknown UTF-8 case exits1 with the same lazy-validation diagnostic on both versions. Candidate diff was independently inspected: only previously certified ASCII counts remain known after index discard; all other cases reset to unknown using saved old byte lengths, including `right == left`.

An initial fixture helper `invalid_utf8` collided with the included runtime's static function and failed compilation before execution. Renaming it to `review_invalid_utf8` resolved the adapter issue; it is recorded separately from the actual baseline semantic failure. No production source was edited by this lane. This independent result closes the selected native invariant/slice/ownership/malformed-policy checks, not the pending generated-language, full-profile/sanitizer or performance evidence. The engineer separately reported an earlier eight-configuration candidate matrix; that matrix was not independently rerun here.
