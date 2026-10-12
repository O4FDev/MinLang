# Map dictionaries

`Map<K, V>()` creates a mutable dictionary. `Map()` needs a contextual Map
type from a binding, parameter, record field, List element, or return value.

```minyar
let seen: Map<Text, Integer> = Map()
seen["usr/bin/tool"] = 1
if seen.has("usr/bin/tool") { print(seen["usr/bin/tool"]) }
print(seen.remove("usr/bin/tool"))
seen.clear()
print(seen.length)
```

Keys are Integer, Text, Character, Boolean, or Float. Text keys compare UTF-8
bytes, consistently with Text equality. Float zeros share one key; NaN keys
stop with `NaN cannot be used as a Map key.` Scalar and managed values are
supported, including nested Lists, Maps, records, callbacks, and Results.

- `m[k]` returns the value and stops with `Map key is absent.` when missing.
- `m[k] = v` inserts or replaces. Compound assignments read the existing key.
- `m.has(k)` returns Boolean.
- `m.remove(k)` returns whether a key was removed.
- `m.length` returns Integer. `m.clear()` removes all entries.

Aliases share the same dictionary. Saved managed values remain alive after
replacement, removal, or clear. Map equality expressions are unsupported.
There is no key iteration/order API in this implementation.

The runtime uses an ordinary fixed record owning three bucket Lists, with
open addressing, a 75% growth threshold, and backshift deletion. Existing
record, List, Text, RC, and allocator layouts are unchanged. Bucket owners
stay untraced, but cycle-runtime stores retain children through the traced
store API. Growth/backshift transfer ownership counts; clear retires the old
arrays through the selected cleanup budget.

Map mutations whose declared value graph can reach the same Map type are
rejected with `Map mutation could create a reference cycle`. This includes
callback capture edges discovered after a store was lowered. Unrelated traced
graphs can be stored and reclaimed normally. This restriction is conservative:
it rejects a potentially cyclic type even when a particular value is acyclic.

Legacy positive List IDs are preserved. Negative structural IDs have a
three-bit tag (List 0; Map the scalar key kind 1/2/3/4/7) and a zigzag child.
Construction checks arithmetic bounds and rejects excessive nesting. Nominal
IDs 9–15 remain distinct child IDs; their reference semantics come from WS1's
`isReferenceType` extension at integration. Compiler traversal helpers are
`isMapType`, `mapKeyType`, `mapValueType`, `isContainerType`, and
`containerValueType`. The core, module, callback, Result, and Result-request
frontends share these types. Module interfaces traverse Map-contained types.

The native ABI is `minyar_map_new(key_kind, value_references)`,
`minyar_map_get(map, key)`, `minyar_map_set(map, key, value)`,
`minyar_map_has(map, key)`, `minyar_map_remove(map, key)`,
`minyar_map_length(map)`, and `minyar_map_clear(map)`. Keys and values occupy
64-bit List slots; `get` borrows like List indexing. The compiler roots managed
results and any Text key that can be invalidated by right-side evaluation.

Validation and measured limits are in
[the implementation evidence](research/evidence/ws3-map-2026-10-12/README.md).
The parent adds Map to its central reserved-name table and generated builtin
documentation during integration.
