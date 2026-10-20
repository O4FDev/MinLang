# Standard-library benchmarks

From the repository root:

```sh
./minyar bench --manifest-path benchmarks/standard-library
./minyar bench --manifest-path benchmarks/standard-library -- --json
./minyar bench --manifest-path benchmarks/standard-library List.sorted -- --samples 25
```

The three cases exercise List sorting, Unicode Text search and JSON parsing.
Their inputs depend on runtime arguments and every body checks its result.
Builds use the release profile. Each case runs sequentially in its own process;
module setup and process startup are untimed.

Defaults are 15 measured batches after calibration and three warmup batches,
with a 5 ms calibration target. Median, unscaled MAD and nearest-rank p95
describe the batch-average ns/op samples. An operation includes the full body,
callback and timing-loop overhead. JSON retains every integer batch duration
and derived sample, together with build flags, for independent recomputation.

See [the testing guide](../../docs/testing.md) for maintained checks and
[the language guide](../../docs/language.md#tests-beside-the-code) for control
bounds and property cases with deterministic shrinking.
