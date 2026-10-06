# Native size-guard failure order

Baseline-only audit during the frozen-source soak. No production defect or optimization is claimed. Existing `checked-scalars.py` already covers shift extremes, Unicode surrogate/range rejection, exact Float→Integer bounds, NaN/infinities, absolute-value overflow and clamp diagnostics. Existing Bytes models cover 20,000 independent payload mutations and refill/self-append/native-writer behavior. These were read before choosing a different gap: direct size guards with already-detached debt and exact managed-service/allocation observation.

The fixture creates a protected 16-byte Bytes object and retires a 129-field mixed record, leaving one pending task at K1 or K32. Counters activate only after setup. Eleven cases exercise negative/max Bytes construction, max resize/extend, negative native extend, an int64 writer at LLONG_MAX position, negative/max record construction, record field-map/header size overflow, and borrowed/consuming Text join length overflow. The latter record/Text cases use synthetic unallocatable ABI sizes with NULL payloads; they test defenses before dereference/allocation, not huge reachable generated values.

[Native results](evidence/runtime/results/guard-order-native.json) and [ASan+UBSan results](evidence/runtime/results/guard-order-sanitizer.json) each execute 44 controls: 11 cases across system/fixed K1/K32. Each retains the exact expected diagnostic, managed object/data/resize allocation count 0, helper-service count 0, queued/immediate work 0, and unchanged pending count 1 at the trap. A test-only process destructor then releases the protected root and drains/caches to exact full recovery. This observer does not claim production unwinding or recovery from fatal errors. Libc allocations in diagnostic formatting are outside the managed counters. The sanitizer cohort additionally injects one pre-guard service call in the harness and detects it by post-trap assertion failure; this calibrates the sensor, not a production mutation score.

The observation is specific to the listed entry points. It is not a universal validation-before-allocation policy: List `appended` already allocates its result header before checking an impossible source length, and lower-level managed allocators may service debt before their own size checks. Those source-order differences are preexisting and cannot be silently normalized by a future scheduling optimization. Current tests and source audit found no new arithmetic/ownership defect here.

```
python3 tests/memory-research-credit-relocation.py --guard-probes
python3 tests/memory-research-credit-relocation.py --guard-probes --sanitize
```
