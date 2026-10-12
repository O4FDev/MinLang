# WS5 report — implementation and fresh review checkpoint

2026-10-12. Required modules are implemented on workstream branches; none is
merged into v2. Root integrator alone owns merge/push and final platform gates.
No paid spend or root-host use; owned included-credit Boat only. No local
privileged/security operations were performed.

## Commits under review

| Chunk | Author SHA | Parent SHA |
| --- | --- | --- |
| Standalone streaming SHA | dca5d8c | 89e8b2e |
| Initial matched SHA/tar provider routing | 2d2c23e | 2d2c23e |
| zstd/gzip/zlib/raw DEFLATE | dab7d4c | 5ad3a37 |
| OCI tar reader/writer | 033dbf6 | e6b8a86 |
| Static codec/effective-header corrections | afd0529 | afd0529 |

Backend choices and measured limitations are in
`docs/formats/backend-decisions.md`. Exact raw evidence is in
`docs/evidence/{compression,sha256,tar}`. SHA pure failed even portable C's 1.5
preference. Tar pure also failed; native preserves additional strict metadata
semantics but payload roundtrip costs 11.048x C. Compression has no measured
pure candidate. No thresholds were relaxed or gap closure inferred.

## Fresh independent review

SHA r1 found no algorithm/ownership P1, but required provider/test repairs:
actual loaded image identity, secondary-header prefix enforcement, explicit
POSIX backslash handling, Mac canonical temp paths, and truthful build evidence.
Compression r1 found no codec/ownership P1; its renamed-DSO and effective-flags
P2s are corrected/tested and undergoing fresh r2 review. Tar r1 found absolute
pathname, empty hardlink and order-dependent PAX-bound P2s; fixes are active.
All original preparation findings were carried into implementation, including
strict mutation oracles, exact negative fractional times, binary/vendor attrs,
shared-close state, complete framed decoding and explicit RAW dictionaries.

## Validation and pending work

SHA native/generated-code sanitizer: 3,864 splits, 64 alignments, 519 guard
cases. Compression original native/sanitizer plus independent review cohorts:
canaries, every truncation, deterministic malformed mutations, independent
interop, small chunks, dictionaries, complete trailers/concatenations/recovery.
Corrected codec provider tests and both modes passed at 15:38 UTC on own Boat.
Tar native/generated-code sanitizer: 2,073 cases each, exact resource/span/type
and writer contracts, Python and maintained-C metadata/payload comparisons.
Fresh review found the three omitted edge cases now being added.

The combined formats fixture, aggregate normal/sanitizer targets, provider
fixes, and complete proposed neo-vm shim deletion note still require final
review. The note is a diff only; no downstream code is changed. WS7 actual
Windows ABI checks, full integrator suites, and the unchanged existing-workload
±1% gate remain required. Rebase onto qualified v2 when pushed. Only after
confirmed merge will owning gaps docs append `fixed in v2 <sha>` for bounded
compression, standalone SHA and the tar portion. Streaming large OCI layers
and optional erofs/ext4 writing remain explicitly open.
