# Runtime performance experiments

These helpers prepare frozen runtime comparisons and retain hardware instruction
counts with semantic oracles. Run builds, checks and counters through the active
coordination lane's `bx`; do not run them on the laptop. They are experiments,
not portable landing gates or substitutes for ownership and sanitizer suites.

The 2026-10-20 qualification's original source snapshots, generated LLVM,
manifests and raw results are supplied through its coordination archive. Consult
`reports/perfcs-codex.md` and `reports/perfcs-durable-helpers-review.md` in
`/Users/luke/Projects/minyar-moonshots-20261020` for provenance and archive paths.
Those original inputs are not vendored in this directory. The original complete
shipping product snapshot is `build/perfcs-final-products-r3` on that perfcs box;
the original self snapshot is `build/perfcs-final-self`. Original `.perfcs/`
helper files and frozen build-directory helper copies remain unchanged.

## Product runtime pairs

`products.py` emits each product/profile's generated LLVM and native objects
once, then links both roles against separate O2 runtime objects, **without LTO**.
It snapshots the compiler, library, runtime trees, fixtures, native references,
build recipes, counter helper and their hashes into a new output directory.
Source inputs default to repo `.perfcs`; `--input-root` accepts an extracted
archive containing `js/`, `safelibs/`, `safelibs-tools/` and `c2min/`. `--library`
selects the library to snapshot (default repo `library/`). Baseline runtime and
candidate runtime paths are explicit and independent of the input root.

Profiles are exactly `default` (`--bounded-owners 32`, system heap/K32 runtime)
and `eager` (`--scope-owners`, eager runtime). JS uses the cycle runtime
transformation; safelibs and jsmn use their frozen compatibility wrappers.
All product runtime objects use `-O2 -g -fPIC -fno-omit-frame-pointer
-Wno-override-module`, with C11/hidden runtime visibility and no LTO.

Measured JS and jsmn runtimes have ownership accounting **disabled**, matching
shipping code. Separate instrumented links use the same generated/native objects
to drain pending work and assert normal-exit ownership; JS requires their exact
stdout to equal shipping stdout. Jsmn checks four parser modes plus upstream,
compatibility and thread clients. Safelibs measurements remain **instrumented**
because the frozen wrapper API requires live-object counts; label those results
accordingly. The measurement driver checks full decoded codec bytes for both
roles and profiles, along with independent dimensions/counts/checksums and JPEG
tolerance. Keep these accounting labels when reporting results.

Example from the repository root, after supplying archived inputs and baseline
runtime paths on the existing box:

```sh
coord='/Users/luke/Projects/minyar-moonshots-20261020'
"$coord/bx" perfcs python3 'experiments/perfcs/products.py' \
  --compiler 'build/minyarc' --input-root '.perfcs' --library 'library' \
  --baseline-runtime '.perfcs/qualification-base/runtime' \
  --candidate-runtime 'runtime' --output 'build/perfcs-products-next'
"$coord/bx" perfcs sudo -n python3 'build/perfcs-products-next/measure-products.py' \
  --manifest 'build/perfcs-products-next/manifest.json' --samples 7
```

Use the build directory's frozen measurement script. `--clang`, `--libz`,
`--libpng` and `--libjpeg` accept explicit toolchain/reference-library paths.
The native codec development headers and libraries must already be available.
Defaults run all three products and both profiles; `--workloads` and `--profiles`
permit a narrow first check, but a partial run is not the full qualification.

`measure-products.py` uses one warmup and seven retained samples per role,
alternating listed/reversed role order each round and pinning one allowed CPU.
Its hardware counter counts user-space instructions from exec, including inherited
children, and rejects counter scaling or incomplete running time. Setup, output
and teardown belong to the counted process. Each worker has a bounded timeout;
failure retains raw logs. It verifies immutable hashes before and after, exact
semantic outputs and complete codec-byte equality. It writes
`measurements/results.json` plus every job/counter/stdout/stderr artifact.

`ablate-products.py` is the preserved two-feature JS ablation recipe from the
original cache-plus-cycle-batching experiment. It requires a complete frozen
shipping product manifest with the exact marked batching block. It adds
cache-only and cycle-only runtime links using the **same existing** JS/native
objects, retaining an `ablation-manifest.json`; measure that manifest with the
frozen product measurement script. A candidate without the marked block should
fail its structural assertion. This helper is historical and should not be
silently adapted to a different feature decomposition. The following requires a
fresh complete product build using that archived two-feature candidate; do not
rerun preparation inside the original qualification directory.

```sh
"$coord/bx" perfcs python3 'experiments/perfcs/ablate-products.py' \
  'build/perfcs-products-with-batching/manifest.json'
"$coord/bx" perfcs sudo -n python3 'build/perfcs-products-with-batching/measure-products.py' \
  --manifest 'build/perfcs-products-with-batching/ablation-manifest.json' \
  --output 'build/perfcs-products-with-batching/ablation-measurements-next' \
  --only 'js-create-default' --samples 7
```

## Same-LLVM self compiler relink

`relink-self.py` copies frozen `default.ll`, `eager.ll` and `compiler-stage2.ll`,
emits each runtime to LLVM, strips the existing target CPU/features/tuning
attributes, then relinks with the selected toolchain's **ThinLTO** flags. This
preserves the original self experiment's link method; product pairs above use
separate no-LTO runtime objects. The helper journals the exact selected compiler,
flags, LTO flags/environment, command working directory, runtime wrapper prefix
and generated LLVM identity. It adds no ownership accounting.

The frozen directory must also contain `compiler.min` and `library/`. The raw
instruction runner compiles this same input through each binary, saves all
per-sample counts and emitted LLVM hashes in `instructions.json`, and requires
every output hash to agree. Its last stdout/stderr/output paths are reused;
archive the JSON observations and outer bx log. There is no new per-sample raw
file retention algorithm in this packaging change. Use a fresh relink/output
directory and an outer bx timeout for every run.

```sh
"$coord/bx" perfcs python3 'experiments/perfcs/relink-self.py' \
  --frozen 'build/perfcs-final-self' \
  --baseline-runtime '.perfcs/qualification-base/runtime' \
  --candidate-runtime 'runtime' --output 'build/perfcs-self-next'
"$coord/bx" perfcs sudo -n python3 'build/perfcs-self-next/frames-instructions.py' \
  --directory 'build/perfcs-self-next' \
  --input 'build/perfcs-final-self/compiler.min' \
  --library 'build/perfcs-final-self/library' --samples 7 \
  --profile 'baseline-default=build/perfcs-self-next/baseline-default' \
  --profile 'candidate-default=build/perfcs-self-next/candidate-default' \
  --profile 'baseline-eager=build/perfcs-self-next/baseline-eager' \
  --profile 'candidate-eager=build/perfcs-self-next/candidate-eager'
```

## Collection scaling study

`collections.c` and `collections-study.py` are the existing ten-kernel Map/Set,
List and Text study. They prepare small O0/O2 and ASan/UBSan/LSan correctness
checks, then doubled-size whole-process counter samples with semantic checks and
full recovery. Its included acyclic system/K32 runtime has test accounting
**enabled** and the integer Text cache disabled. Treat results as an instrumented
native complexity study, not shipping generated-code throughput. Manifest
limitations describe setup, alias checks and retained allocator costs.

```sh
"$coord/bx" perfcs python3 'experiments/perfcs/collections-study.py' \
  --prepare-only --runtime-root 'runtime' --output 'build/perfcs-collections-next'
"$coord/bx" perfcs sudo -n python3 'build/perfcs-collections-next/collections-study.py' \
  --measure-only 'build/perfcs-collections-next/manifest.json' --samples 7
```

Every builder/measurement output directory must be new. Preserve failed runs,
exact manifests, immutable hashes, raw counters and outer logs in the run's
coordination archive. Future reports should link that fixed archived run path,
not a moving worktree or an overwritten default `build/` directory. Record exact
baseline/candidate commits, compiler pin, flags, profile/accounting labels,
retained sample counts and semantic checks; these helpers set no speed threshold.
