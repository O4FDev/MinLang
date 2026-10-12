# WS3 — Core library and language basics

Development/testing resumed on 2026-10-12 after the owner revoked the Phase 1
development hold. Only integration into `v2` is queued. Base: `bf9c0e9`.

## In flight

- Map language/runtime support in `ws3/map`; native draft and model tests retained.
- Stable natural and comparator List sorting in `ws3/sort`.
- Text operations, Integer(Text) and List.clear in `ws3/text`.
- Octal literals and reserved-name publication/diagnostics in `ws3/core-library`.
- Module-level tables/one-time initialization design; implementation follows the
  first Map/sort chunks.

## Verification and resources

- Separate owned Boat sandbox: `bx_ez43hrrp` (large, included credit, $0 paid).
  Phase 1 hosts remain untouched. Heavy workloads run serially per sandbox.
- Before the former hold, native Map eager/system O0 model checks passed; new
  octal/reserved-name repro tests failed against the baseline as expected.
- Generator/optional adapter assembly and Python syntax checks passed before
  the hold. No candidate compiler qualification or performance claim yet.
- Read-only audit identified octal underscore suffix validation (now corrected)
  and Map cycle-runtime store barriers (implementation task includes correction).
- Frozen compiler comparator digest must remain unchanged; pinned source design
  is being coordinated with WS2 and the integrator.

## Merge requests and gaps

None offered yet. Every chunk needs independent review, applicable platform
suites and benchmark evidence before it is sent to the integrator. No gap is
marked fixed until the corresponding change is merged into `v2`.
