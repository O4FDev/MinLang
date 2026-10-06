# Baseline runtime API count probes

No production change or timing comparison. Four C configurations (system/fixed K1/K32) each execute48 baseline cases:36 threshold/fan-out/capacity slices, four nested slices, eight Boolean/literal formatting controls. A separate actual generated Minyar program runs ten view-lifetime cases on system/K32. The native and sanitizer runs each record 192 C observations plus ten generated observations, not 202 distinct scenarios. Sources and results are durable in the [native evidence](evidence/runtime/results/api-count-native.json) and [sanitizer evidence](evidence/runtime/results/api-count-sanitizer.json).

The Text root sizes 4096/4097/8192 and token sizes immediately below/at/above one eighth characterize the existing strict copy rule. Exact-capacity and geometric-capacity roots are separate C controls; generated repeated joins confirm actual capacities 8192/16384 at these lengths. One or 32 survivors and flattened nested slices retain independently verified `x` bytes after dropping their source. Final roots, objects, backing buffers and frame caches fully recover. The generated observer drains detached debt at the first print to separate dead queued owners from still-live views. In the measured generated cases the pending queue is already empty, so that observer performs zero work. This test observation is not a proposed extra service hook.

| Existing-policy case, C fixed/K32 | Surviving payload | Requested retained bytes | Pool charge retained | Slice data/header allocations | Slice service hooks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Root 4097, capacity 8192, one copied 512-byte token |512 |569 |1088 |1/1 |2 |
| Same root, 32 copied 512-byte tokens |16384 |18208 |34816 |32/32 |64 |
| Same root, 32 viewed 513-byte tokens |16416 |9784 |18496 |0/32 |32 |

The adjacent 512/513-byte cases have different values and follow the current rule; they are not a same-input candidate comparison or a proof that a different threshold is better. They identify lifetime/fan-out as necessary workload dimensions. In the generated system/K32 program, 32 copied 512-byte tokens retain 18568 requested bytes versus 10152 for 32 viewed 513-byte tokens, including the live List and mode Text. One small copied token retains691 total bytes; one 513-byte view retains 8418. The former releases its oversized root, while the latter retains it. Live logical root ownership is distinct from dead queue debt; neither pending-task count nor token length alone describes retained storage.

Boolean formatting executes 1000 conversions per value/query control. Each current conversion allocates one backing and one header. At K32, conversion plus explicit caller release offers 95 queued units and uses one immediate unit when no other debt exists (three helper hooks), so 1000 conversions offer 95000 and perform 1000 immediate destructions. Actual queued work is zero. Querying `.length` builds 1000 lazy indexes, with 4000/5000 input bytes for true/false. The valid immortal literal control allocates no data/header and builds no index; explicit release still invokes one K helper hook per iteration, offering 32000 units rather than zero. Index input bytes are an input-size counter, not CPU load instructions. No Boolean cache/metadata change is proposed or accepted: removing allocations changes two service opportunities and requires generated workload, admission and alias controls of its own.

Native C uses exact byte/content/recovery assertions. The sanitizer run instruments C with ASan+UBSan and generated LLVM with ASan attributes on every recorded definition. Generated UBSan is not asserted and leak detection is disabled. The initial missing-size_t adapter compilation is preserved separately; it executed no runtime case. No quiet-host throughput, tail latency, general view-policy optimum or complete API coverage claim follows from these counts.

```
python3 tests/memory-research-credit-relocation.py --api-probes --language
python3 tests/memory-research-credit-relocation.py --api-probes --language --sanitize
```

Recorded generated sanitizer definition count: 12/12.
