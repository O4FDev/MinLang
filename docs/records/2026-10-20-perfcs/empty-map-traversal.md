# Empty Map traversal

Design recorded before a private prototype on October 20, 2026, based on
`7b36666d8`. Implementation measurements and qualification are recorded in
[results.md](results.md).

A Map keeps its peak bucket capacity after removal. `keys()` and equality
previously scanned all buckets even when the live length is zero. The collection
study measured roughly doubled whole-process instructions at doubled historic
capacity for empty Maps. Those observations include population, removals,
validation and teardown; they are not isolated traversal costs.

The proposed empty fast paths preserve all existing ownership service points:

- `keys()` still creates the fresh List, assigns its reference kind and calls
  the same reserve operation. When live length is zero, it then returns that
  empty result before loading or scanning the historic bucket arrays.
- Equality retains recovery, null, length and key-kind checks. It enters the
  same read guard and reaches the same guard cleanup, including both releases.
  If the already matched live length is zero, it sets the result to true and
  bypasses only the bucket scan. No callback would have run in that scan.

Valid Maps have exactly live-length nonzero hash buckets. At length zero every
bucket is empty, so the skipped loop could neither add a key nor compare a
value. The result remains identical for all value types, including nested Maps,
Float NaNs and records. Key-kind mismatch remains false. The early path adds
no cleanup work and removes no poll, allocation, release, barrier, callback or
guard. Nonempty Maps follow the original scan. No shrinking, representation,
capacity, mutation or ABI change is proposed.

For a Map with historic capacity C and zero live entries, bucket traversal
changes from Theta(C) to O(1), excluding the unchanged fresh result allocation
and ownership service. Construction/removal and later retirement still cost
work proportional to their original inputs/capacity, so whole-process scaling
need not become constant. Sparse nonempty Maps retain Theta(C) traversal.

Before landing: compare exact result kind/length, capacities, reference counts,
guard chain, bounded pending work/next queue and cleanup after each call against
the original. Exercise fresh and emptied scalar/Text/record-key Maps, same and
different Maps, nested values, key-kind mismatch, recovery, eager/cycle/system/
fixed/lazy/arena profiles and K1. Run existing Map, ownership, cycle and sanitizer
checks and the complete portable gate. Benchmark unchanged fixture/compiler
objects across both runtimes, retaining every raw counter and semantic oracle.
