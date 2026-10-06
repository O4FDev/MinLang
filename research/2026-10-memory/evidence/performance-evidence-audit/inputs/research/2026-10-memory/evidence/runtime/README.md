# Durable runtime evidence

This bundle survives the repository's `make clean` target, which removes only
`build`. It contains 45 selected result JSON files, a pinned final runtime source
tree, deduplicated fixture/helper versions and compact diffs for earlier runtime
versions. It excludes executables, compiler artifacts, generated LLVM and raw
coverage files. The accompanying runtime timing figures live beside the reports.

[`index.json`](index.json) maps each original acquisition path to its durable copy,
SHA256, recorded status, check count and a short interpretation. Raw result JSON
bytes are unchanged: commands, outputs, expected failures, every timing pair and
timeout records remain available. Expected red tests, rejected policies, invalid
fixture calibration and host-starved incomplete attempts are distinct from final
successful controls. Do not sum this collection into an "all tests passed" claim.

Important entries include:

- `results/final-text-matrix.json`: exact final runtime, 107 asserted checks,
  21 C configurations, 21 generated executions and 21 malformed-input traps.
- `results/text-c-only-correction.json`: the earlier 64-check C-only invocation,
  whose initial progress count was corrected after inspecting saved evidence.
- `results/final-list-timing.json` and `results/ascii-paired-timing.json`: full
  paired CPU/wall observations, including negative timing controls.
- `results/list-object-debt.json`, `results/list-owner-debt.json` and
  `results/rejected-bytes-policy.json`: finite-pool admission counterexamples,
  accepted guard controls and a rejected capacity policy.
- `results/credit-causal-counts.json`, `results/credit-admission-native.json` and
  `results/credit-admission-sanitizer.json`: equal-credit reuse benefit plus a
  retained-capacity admission counterexample; prototype rejected as default.
- `results/api-count-native.json` and `results/api-count-sanitizer.json`: baseline
  view/Boolean counts, including ten actual generated view workloads.
- `results/peer-projections.json`: historical three-method, 18-execution suite; native O0/O2 and sanitizer effectively O1. The correction preserves all semantic observations and incompatible peer contracts.
- `results/peer-projections-expanded.json`: historical four-method, 24-execution suite. Native links were O0/O2; sanitizer links effectively O1, as explicitly corrected.
- `results/peer-projections-final.json`: six original methods and 36 executions (retained corrected predecessor), with actual O0/O2 link argv and generated ASan coverage.
- `results/queue-empty-fragmentation.json`: 16,384 bounded buddy histories,
  with 15,653 admitted appends and no observed placement/admission difference.
- `results/hud-formatting-pilot.json` and `results/hud-formatting-matrix.json`:
  actual generated HUD call mixes, exact public/allocating conversion counts and
  separate intentional cache/static-table storage; no policy or timing claim.
- `results/deferred-isolated.json`, `results/deferred-generated.json` and
  `results/accounting-probes.json`: distinct causal, realistic negative and
  scheduler/retention observations; no speculative reuse policy was deployed.

Every copied result/source/diff was reread and hash checked. Each differing
runtime source was reconstructed from `final-runtime` plus its patch in a
disposable directory and matched its observed source SHA256. Fixture/helper
versions are named by full SHA256 and original basename. Source mappings retain
both the run's recorded hash and the observed archived hash. Two historical
pre-mutation hash records differ from final snapshot bytes; in both cases the
explicit before/after candidate fields explain and verify the difference. Neither
raw result was rewritten to hide that provenance issue.

For a selected runtime source, copy its file from `final-runtime` into a disposable
directory, apply the indexed `diffs` patch with `patch -p1`, and verify the indexed
target hash. Identical versions need no patch. Copy the indexed fixture/helper
content into the expected relative layout before using recorded compile commands.
Generated programs additionally require a compiler matching the separately
recorded artifact/source provenance; this compact bundle is not a hermetic binary
reproduction environment.

`../../runtime-evidence-archive.py` defines the curated selection and validation.
It requires original acquisition directories to regenerate this archive. Reading
and independently reviewing the existing archive requires no `build` directory.
Other campaign lanes maintain their own evidence and the parent shared index.

The sibling `core-production` directory additionally preserves the exact dirty-baseline core patch, baseline sources and verified final hashes. Native size-guard baseline observations are `results/guard-order-native.json` and `results/guard-order-sanitizer.json`; their error observer is test-only.

A [fresh-directory native replay](../runtime-reproduction/run-fczgzr4c/results.json)
passed the archived system/K1/O2 Unicode fixture: 18 semantic cases and one expected
invalid-UTF8 trap. It copied and hash-verified runtime/fixture/helper sources from
this bundle only, then used installed Apple Clang17 and the platform SDK/linker.
No live repository source or build artifact was used. The [runner](../../runtime-evidence-smoke.py)
records every copied hash and command; this demonstrates one source-complete
native smoke, not a hermetic toolchain or generated-program reproduction.

`results/peer-projections-round6.json` preserves the latest eight-method,
48-execution matrix with actual O0/O2 argv and explicit round 6 provenance.
