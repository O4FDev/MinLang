# WS3 native performance qualification recipe

The single-thread gate remains candidate/control <= 1.01 for compiler
self-compilation, Minyarcraft, Atacama, JSON and neo-db. These are pending
integrated qualification; feature peer timings do not discharge them.

## Inputs and comparison

Use the same immutable owning-project inputs, machine, toolchain, optimization,
heap profile and limits for both arms. Record source, compiler, runtime and
executable SHA256 hashes, toolchain version, commands and every raw sample.
Build an untouched `bf9c0e9` ordinary control alongside the final candidate;
retain the approved frozen foundation compiler for the separate exact-LLVM
compatibility test (digest `a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf`).
Do not replace whole applications with narrower parsers or headless fixtures.

Warm both arms, run serially with fixed CPU affinity on Linux, and alternate
control/candidate order in paired batches. Keep all failed measurements. Use
the existing workload-specific statistical rules; the unchanged ratio is 1.01.
For short compiler runs, batch enough identical invocations to exceed clock
and process-start noise, preserving per-run and batch CPU/wall measurements.
No threshold, resource limit or expected output changes are authorized.

## Atacama desktop application

The locally inspected owning source is clean commit
`085b55736fda3f7e583170d7e54c66d4eaaaedb6` in
`~/Projects/Atacama-desktop-app`. The integrator's private immutable delivery
must name its exact SHA and complete input manifest; if it differs, record the
delivered revision and use that identical delivery for both arms. Keep private
source in the approved CI input route, not the public Minyar repository.

Required capability: native Darwin with AppKit, a logged-in WindowServer
desktop, and existing Accessibility/event-posting authorization for the exact
driver identity. The runner must report that it can read and operate the app's
AX tree before measurement. A runner lacking those capabilities cannot qualify
this gate. An app link, parsing test or `macos-15` label alone is insufficient.
Screen recording authorization is needed only if screenshots are requested;
the timing recipe below does not request them. Do not mutate TCC or security
settings to obtain capabilities.

Create two isolated copies of the identical Atacama input on the allocated
native runner, one per Minyar arm. In each copy build with its own `MINYAR`
launcher; preserve the existing release/app options from the owning Makefile:

```sh
make MINYAR=/absolute/control/minyar MINYAR_PYTHON=/usr/bin/python3
make MINYAR=/absolute/candidate/minyar MINYAR_PYTHON=/usr/bin/python3
```

Those two commands run in different owning copies. Build the unchanged owning
driver once with the same native toolchain and reuse it for both apps:

```sh
clang -fobjc-arc -fmodules tests/profile/drive.m -o build/drive
python3 tests/profile/stub-server.py 47391 500 3000
```

Keep the stub server in a separate owned process. These are the owning README's
500 saved runs and 3,000 streamed deltas, emitted every 2 ms. Repeat the owning
scenarios `startup`, `history`, `type`, `delete`, and `stream` for both apps,
alternating their order and starting a fresh app for every sample:

```sh
build/drive /absolute/control/build/Atacama.app/Contents/MacOS/application 47391 history
build/drive /absolute/candidate/build/Atacama.app/Contents/MacOS/application 47391 history
STREAM_SECONDS=12 ANSWER_FILE=/absolute/evidence/control-answer.txt build/drive /absolute/control/build/Atacama.app/Contents/MacOS/application 47391 stream
STREAM_SECONDS=12 ANSWER_FILE=/absolute/evidence/candidate-answer.txt build/drive /absolute/candidate/build/Atacama.app/Contents/MacOS/application 47391 stream
```

Substitute each other scenario for `history` without changing its driver logic.
Archive stdout/stderr and exit status; compare the driver's app CPU seconds
and instructions, and retain wall time as a scheduling diagnostic. Verify
history search/erase and prompt typing through the AX tree, require delete's
`first row deleted`, and independently compare each streamed answer to the
stub's complete 3,000-word sequence. Fixed waits alone are not correctness
proof. The driver reports CPU to 1 ms; repeat enough paired samples for a 1%
claim to be resolved rather than rounding noise. Stop only owned app/server
processes after the run.

## Other common workloads

- Compiler: identical fixed `compiler/compiler.min` input path and bytes for
  both compilers; also run the existing fixed-point and `tests/performance.py`
  resource ceilings. A tiny frozen-foundation throughput diagnostic is a
  separate measurement and cannot substitute for self-compilation.
- Minyarcraft: use the actual `examples/craft/main.min --benchmark build` and
  `--benchmark edit` owning application with working GLFW/OpenGL. The existing
  `tests/native-research-craft.min` plus GL mock is useful supplemental evidence
  and is explicitly a headless fixture.
- JSON: use identical `benchmarks/json/history-parse.min`, generated history
  inputs (500 and 5,000 saved runs) and existing JSON benchmark workloads;
  archive independently checked output/checksums and raw paired samples.
- neo-db: immutable owning `tests/sql/bench.min` with `src/sql/parser.min`,
  100,000 iterations of each existing statement case. Copy inputs read-only
  to own Boat; record the owning source manifest and preserve all cases.

## Platform route

Linux development and peer qualification use owned `bx_ez43hrrp`, serial
`flock /home/user/ws3/build.lock`, LLVM 22 with unchanged memory ceilings and
serial ThinLTO linker workers. No root Phase 1 host is admitted.

The integrator will schedule native Mac CI or an explicitly allocated remote
Mac route after Phase 1. If no permitted GUI/AX runner exists, report Atacama
GUI performance **unqualified**, with the capability above still required.
Coordinate Windows execution with WS4/WS7 on their distinct owned Boat
Windows slots/forks; root's qualification VM remains reserved. No paid spend,
heavy local Mac tests or local security operations are admitted.
