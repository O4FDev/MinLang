# Generational handles

The `handles` module stores values behind opaque, typed identities. A delayed
window event, timer or resource request can keep a handle without keeping its
payload alive. Removing a value invalidates every copy of its handle. Reusing
the slot gives the replacement a new generation; another pool has a different
domain even when its slot and generation happen to match.

```minyar
use "handles" as handles
let windows = handles.create<Text>()
let old = handles.insert(windows, "Morning")
handles.remove(windows, old)
let current = handles.insert(windows, "Evening")
print(handles.get(windows, old).isNone())
print(handles.get(windows, current).unwrap())
```

`get` and `remove` return `Maybe<Item>`. Wrong-pool and stale handles return
`None`; `contains` and `replace` return false. Replacement preserves identity.
`clear` invalidates all live handles without resetting identity history.
Handles and pool internals are private, so callers cannot forge identities or
rewrite generations. A handle's type also keeps differently typed pools apart.

`withGenerationLimit<Item>(limit)` bounds how many generations each slot may
issue. The default is the largest positive Integer. Once exhausted, a slot
retires permanently. Pool domain allocation also stops before Integer overflow;
neither counter wraps. `count` reports live values; `slotCount` includes live,
available and retired slots. Storage does not compact while stale handles exist.

Lookup, removal and replacement take constant time. Insertion takes amortized
constant time; clearing visits all allocated slots. Pools, slots, handles and
boxed choice payloads have ordinary managed allocation and ownership costs.
Handles do not retain a pool or payload. Values returned by `get` retain their
ordinary ownership: a returned record stays usable after removal, and its
aliases observe ordinary field mutation.

A pool belongs to one Minyar execution domain. Keep every operation on that
owner's event loop, or send requests to it. These operations provide no locks,
cross-thread deletion guard, persistent IDs or native-pointer validation. A
generation check alone cannot protect a raw pointer from concurrent deletion.
The module's managed global domain allocator follows the compiler's existing
thread-effect restrictions.

The [window gallery](../examples/gallery/handles.min) shows a delayed event
remaining harmless after its window's slot is reused.
