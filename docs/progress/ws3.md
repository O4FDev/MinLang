# WS3 — Core library and language basics

Development/testing resumed on 2026-10-12 after the owner revoked the Phase 1
development hold. Only integration into `v2` is queued. Base: `bf9c0e9`.

## In flight

- Map language/runtime support in `ws3/map`; native draft and model tests retained.
- Stable natural and comparator List sorting committed as `58c5fa3`; independent
  R1 review in flight.
- Text operations, Integer(Text) and List.clear committed as `13d9e9a`;
  independent R1 review in flight.
- Octal literals and reserved-name publication/diagnostics in `ws3/core-library`.
- Annotated module-level tables/one-time initialization implemented; queued
  behind Map/sort for integration. Includes retained roots, dependency/cycle
  diagnostics and startup before main/top-level statements.

## Verification and resources

- Separate owned Boat sandbox: `bx_ez43hrrp` (large, included credit, $0 paid).
  Phase 1 hosts remain untouched. Heavy workloads run serially per sandbox.
- `8d8e4c3`: octal/reserved names local commit; LLVM 22 new repro tests,
  compiler-hardening, regressions, List literals, self-host fixed point and new
  ASan/UBSan tests passed. Initial LLVM 22 linker OOM retained; limiting linker
  worker counts passed the unchanged 768 MiB cap.
- Map: initial eight O0/O2 language contracts and all ordinary/module/callback/
  Result/request frontend builds passed; profile and comparative benchmarks run.
- Sort: 13 O0/O2 API contracts and 48 native/ASan/UBSan ordinary/traced runtime
  configurations passed. Rust/Swift/Python peer checksums agree; Minyar median
  for two million SHA256 Text hashes was 0.669 seconds.
- Text/List.clear: 581 independent native-model comparisons across ordinary/
  traced profiles passed; new frontend native/sanitizer tests, fixed points and
  frozen ordinary IR compatibility passed. Initial compiler diagnostic failed
  at 1.014866x; a narrow call-path optimization passed revised paired batches
  at 0.99557x. Failed raw evidence is retained; review checks methodology.
- Module constants: independent 2,048-cell CRC32C table, diamond imports,
  dependencies/recursive init, literal records/Bytes/scalars, normal-return
  exact ownership and cyclic-root reclamation passed. Expanded matrix passed
  52 checks across four frontends and five ordinary native/sanitizer profiles;
  all nine language tests run at O0/O2. Traced native/sanitizer gate and frozen
  exact-LLVM four-case gate passed. Source hashes match the retained receipt.
- Read-only audit identified octal underscore suffix validation (now corrected)
  and Map cycle-runtime store barriers (implementation task includes correction).
- WS2 approved pinned baseline stack `193c8af`, `47a1159`, `39a8e72` adopted as
  `4f2d21e`, `141ad91`, `7957ab9`; frozen digest remains `a5f30a...`.
- The full 1% common workload gate and real macOS/Windows qualification remain
  required. Map compiler diagnostic failed at 1.022692x, retained without a
  performance acceptance claim. The exact native Atacama recipe and capability
  requirement are in `ws3-native-performance.md`; the integrator schedules the
  permitted native Mac route. Headless parsing checks do not establish GUI
  performance. Windows execution will use WS4/WS7 owned slots after admission.

## Merge requests and gaps

None offered yet. Every chunk needs independent review, applicable platform
suites and benchmark evidence before it is sent to the integrator. No gap is
marked fixed until the corresponding change is merged into `v2`.
