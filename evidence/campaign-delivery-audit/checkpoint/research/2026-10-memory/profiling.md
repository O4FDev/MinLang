# Compiler and codebase profiling

The initial command `make -j1 check-performance check-conformance check-diagnostics`
ran from 2026-10-03 23:55:48 to 23:57:25 UTC. It rebuilt bootstrap stages one,
two and three and passed the compiler fixed point, eleven conformance programs at
O0/O2 and nineteen byte-for-byte diagnostics. `profiling-initial.log` preserves
commands and output. Measurements under the development limiter include changed
scheduling; they are not the absolute budget oracle.

## Subsystems and existing gates

| Subsystem | Maintained sources | Main acceptance evidence |
| --- | --- | --- |
| Stage-zero subset | `bootstrap/stage0.c`, `vendor/stb_ds.h` | Bootstrap portability, record support, stage fixed point |
| Lexer/source origins | `compiler/compiler.min` tokenization and typed `SourceMap` | Tokenizer storage, source maps, diagnostics, Unicode and fuzz cases |
| Declarations and types | Single self-hosted compiler unit | Compiler hardening, conformance, generated type/ownership graphs |
| Expression/control lowering | Same unit: parser, ownership and LLVM emitter share state | Arithmetic/scalar models, short circuit, mutation, O0/O2 and sanitizer tests |
| Module load/rewrite | Core compiler module loader and token rewrite | Module correctness/performance, imports, linkage and symbol ordering |
| Incremental frontend | `compiler/module-compiler.min`, guarded adapter | Interface/body hashes, invalidation, delta replay, memory/performance |
| Build/cache publication | `minyar`, `tools/module-build.c`, toolchain scripts | Cold bootstrap, cache identity, atomic publication and path isolation |
| Runtime/ownership | `runtime/minyar_runtime.c` and private fragments | Independent eager/bounded scheduling models, profiles, traps and sanitizers |
| Allocator/pools | `runtime/minyar_heap.h`, `runtime/minyar_pool.h` | Capacity, fragmentation, recovery, allocation/retirement accounting |
| Native interfaces | `runtime/native`, `library` | Graphics loading, native ABI/linkage, real examples |
| Research tooling | `experiments`, profiling/coverage/mutation tools | Harness fault injection, paired samples, source identities, retained results |

`check-portable` is the cross-platform correctness gate. `check` includes the
broader local gate, absolute budgets and instrumented builds. Profile matrices,
coverage, systematic mutation and duration-based AFL campaigns have separate
entries. No single passing gate establishes every listed property.

## Phase probes

`python3 scripts/peer-research-profile.py --samples 9` instruments twelve coarse
function boundaries in a disposable copy of stage-two LLVM, then links a separate
compiler. Nested calls charge inclusive process CPU to their enclosing phase;
exclusive CPU subtracts marked children, including recursive module loading.
These are function boundaries, not perfectly disjoint language phases: body
compilation includes type checking, ownership decisions and LLVM text creation.

Every sample, including an explicit warmup, is retained. The tool requires each
instrumented process to produce LLVM identical to the original compiler. The
marker calls change optimization and code layout, so their absolute costs are
**diagnostic only**. The unmarked compiler is measured separately.

First evidence: `build/peer-research/profiling-8j7fw1ra/results.json`.
Seven workloads each passed nine retained samples and one warmup.

| Workload | Marked entry CPU median | Largest exclusive costs |
| --- | ---: | --- |
| Compiler compiling itself | 5.267 ms | Body compilation 53.0%; lexer 23.0%; remaining compileTokens 16.6% |
| 500 functions | 0.850 ms | Body 34.5%; lexer 18.8%; symbol lookup building 12.5% |
| 2,000 functions | 3.184 ms | Body 34.4%; lexer 19.3%; symbol lookup building 17.9% |
| 4,000 locals | 1.324 ms | Body 53.9%; lexer 32.5% |
| 16,000 locals | 5.021 ms | Body 55.9%; lexer 33.7% |
| 32 imported modules | 0.931 ms | Module loading excluding marked lexer/recursive calls 70.0%; rewriting 9.2% |
| 128 imported modules | 3.659 ms | Module loading 71.6%; rewriting 11.1% |

Fourfold input increases phase-entry CPU by 3.75×, 3.79× and 3.93× for functions,
locals and module width respectively. Symbol lookup building increases 5.38×;
its sorting cost is consistent with an n log n component. This does not establish
a bottleneck by itself, or a need to replace the existing indexed lookup.

## Uninstrumented resources

Run `python3 scripts/peer-research-profile.py --measure-existing build/peer-research/profiling-8j7fw1ra --samples 11`.
A fresh Python worker launches exactly one native process per observation,
preventing a previous Clang child from contaminating native RSS. Every observation
and warmup is retained in `production-resources.json`. Source, compiler and LLVM
output identities are checked against the phase campaign.

| Workload | CPU median | Wall median | Peak RSS median |
| --- | ---: | ---: | ---: |
| Self | 7.701 ms | 10.794 ms | 9.25 MiB |
| Functions 500 | 2.902 ms | 4.707 ms | 2.86 MiB |
| Functions 2,000 | 5.508 ms | 8.063 ms | 6.44 MiB |
| Locals 4,000 | 3.315 ms | 6.255 ms | 4.48 MiB |
| Locals 16,000 | 7.226 ms | 9.782 ms | 12.98 MiB |
| Modules 32 | 2.988 ms | 4.956 ms | 2.50 MiB |
| Modules 128 | 5.712 ms | 7.357 ms | 4.84 MiB |

Production CPU ratios for fourfold inputs are 1.90×, 2.18× and 1.91×. Process
startup and complete compiler I/O comprise a large fixed cost at these sizes;
these ratios do not contradict the larger phase-only ratios. Self medians are
below the existing resource ceilings; the unchanged budget gate uses batch p90
and retired instructions, so medians cannot stand in for that acceptance test.

## TDD and measurement integrity

The phase tool started with six tests before implementation and failed due to
the missing module. Six tests then passed. Two additional timeout/failed-child
oracles failed before `resource_probe` existed; all eight now pass. They reject
missing functions, duplicate selections, incomplete phase evidence, mismatched
phase identities, impossible exclusive time, failed children and timeouts.
The source-retrieval tool similarly started with a missing-module failure and
then passed five pinned-SHA/path/bounds/review-status fault-injection tests.

New peer semantic regressions were written before execution. All eight already
pass on the baseline at O0/O2; they expose no production red test or claimed bug.
Their provenance, excluded semantics and individual upstream dispositions are
in `peers.json` and `peers.md`.

## Next measurements

1. Split body costs further using selected expression/lookup/ownership functions
   and count-only probes, retaining the coarse probe as an overhead comparison.
2. Attribute compiler arena allocation counts/bytes and generated output copying,
   independently of process RSS, without installing an instrumented runtime.
3. Measure complete native compile/link and incremental edit paths. Profile
   module I/O, cache validation and LLVM/link work independently.
4. Use compatible individually reviewed peers to choose correctness oracles
   before any implementation change; preserve unsupported semantics explicitly.
