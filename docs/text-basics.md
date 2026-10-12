Text methods use Unicode scalar positions and exact UTF-8 matches, without
normalization. Every method validates the receiver and any Text argument before
empty-string or length shortcuts.

| API | Result |
| --- | --- |
| `text.find(needle: Text): Integer` | First scalar index, or `-1`; an empty needle returns `0`. |
| `text.split(separator: Text): List<Text>` | Nonoverlapping matches, preserving leading, trailing and adjacent empty fields. An empty separator yields scalars; empty Text then yields an empty List. |
| `text.startsWith(prefix: Text): Boolean` | Exact prefix; an empty prefix is true. |
| `text.endsWith(suffix: Text): Boolean` | Exact suffix; an empty suffix is true. |
| `text.trim(): Text` | Removes Unicode White_Space from both ends, including NBSP; preserves zero-width space and BOM. |
| `Integer(text: Text): Integer` | Signed decimal ASCII, surrounding ASCII whitespace, full consumption, checked signed-64 range. Invalid syntax, UTF-8 and overflow stop the program with a diagnostic. |
| `list.clear(): Nothing` | Releases managed elements, preserves identity and capacity, and empties the List for every alias. |

`use "text" as text` provides recoverable `parseInteger(Text)` and
`parseIntegerBytes(Bytes)`, returning `errors.IntegerResult`. A successful zero
is distinct from failure. Invalid UTF-8, syntax and overflow return `invalidData`.
`text.validUTF8(Bytes)` checks bytes without converting them into Text.

Split and trim use the existing immutable Text slice policy: retain a flattened
owning Text, or copy a tiny portion of a large allocation. `Text(Bytes)` and
`Bytes.slice` continue to copy; mutable buffers are never interior views.
Search uses a reusable KMP prefix table for linear worst-case matching, with
an allocation-free one-byte-separator path. Traced List clearing removes each
visible edge and incoming reference before a release can poll the collector.

Verification targets: `check-text-basics`, `check-text-basics-sanitize`, and
`check-text-basics-models`. The independent model uses Python scalar strings,
an explicit Unicode White_Space set, and unbounded integers. The C harness
checks exact ownership accounting across heap profiles and retained aliases.
