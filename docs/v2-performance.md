# v2 performance work (2026-10-10)

What limits real Minyar programs, ranked by measured gain. Each entry gives
the problem, the evidence, the fix and the before/after numbers. Instruction
counts are retired instructions of the application process (`proc_pid_rusage`
or `/usr/bin/time -l`). They are steadier than wall time on this shared,
heavily loaded machine; the load average was 30-76 throughout.

## Ranked results

| # | Problem | Fix | Before | After | Gain |
| --- | --- | --- | --- | --- | --- |
| 1 | Atacama history: every search keystroke rebuilt a stack of views per row | `macos.list`, a virtualized NSTableView | 112.6G instructions, 11.4 s CPU | 11.0G, 1.8 s CPU | 10.2x |
| 2 | Atacama streaming: each network chunk re-laid out the whole answer | background wake-ups capped at 60 Hz in `macos.nextEvent` | 60.5G instructions, 6.8 s CPU | 14.0G, 2.0 s CPU | 4.3x |
| 3 | Every function, even a one-line accessor, called the runtime's call-depth guard, so LLVM never inlined hot leaves | leaf functions carry no call-depth frame | Minyarcraft world build 32.1G instructions; compiler self-compile 91M | 25.6G; 81M | -20%; -11% |

### 1. Long lists rebuilt as stacks of views

**Problem.** The AppKit bridge had no table path. Atacama's History page built
one row stack per saved run (a column with three labels, a delete button and a
rule), and rebuilt them all whenever the runs or the search text changed.

**Evidence.** `benchmarks/desktop/history-rows.min` rebuilds Atacama's rows.
The median time per rebuild, layout included:

| Rows | Stack of views | `macos.list` |
| ---: | ---: | ---: |
| 50 | 183 ms | 117 ms |
| 200 | 977 ms | 118 ms |
| 800 | 10,427 ms | 117 ms |
| 5,000 | not run | 118 ms |

The stack version grows faster than the row count (4x the rows, 10.7x the
time). `sample` puts 4,583 of 4,584 main-thread samples in
`-[NSISEngine optimize]`, the Auto Layout solver.

**Fix.** `macos.list(parent)` keeps each row as up to three lines of text,
and a view-based NSTableView builds cells only for the visible rows, reusing
them while scrolling. Rows are added with `addRow`, styled for the whole list
with `listLine`, `listColors`, `rowButton` and `insets`, and cleared with the
existing `clear`. A click delivers `ACTION` from the list; `clickedRow` and
`clickedButton` say where. The reload is coalesced and happens at the start of
the next `nextEvent`.

**Real app.** The Atacama app's History page now uses `mac.list`. The
scenario: a stub server provides 500 saved runs, then the driver opens View >
History, types "question 1" into the search field one key every 250 ms and
erases it again (`tests/profile/drive.m` in the Atacama repository):

| Build | App CPU | App instructions |
| --- | ---: | ---: |
| Before (stack rows) | 11.36 s, 11.59 s | 112.6G, 112.1G |
| After (`mac.list`) | 1.81 s, 1.83 s, 1.82 s | 11.0G, 11.0G, 11.0G |

Before the change, the app had not drawn the typed search text by the time
the screenshot was taken, because it was still rebuilding rows.

**Tests.** `tests/macos-native.m` `verifyList` covers 5,000 rows, fewer than
100 realized row views, cell contents, hidden empty lines, button events and
tooltips, a disabled list delivering no clicks, `clear`, insets, and two
misuse diagnostics (`list-line`, `list-type`). It runs with and without
ASan/UBSan in `check-macos`.

### 2. Streaming updates were not throttled

**Problem.** Every `http` progress wake-up ended `macos.nextEvent`, and
Atacama re-rendered the whole answer each time. A wrapping NSTextField
re-measures all of its text (`intrinsicContentSize` → `boundingRectWithSize`)
and redraws it, so the cost per chunk grows with the answer, and the total
grows quadratically.

**Evidence.** The stub server streams a 3,000-delta answer, one delta every
2 ms. `sample` shows the main thread in `NSTextField intrinsicContentSize`
(1,032 samples), CoreText typesetting (481) and glyph drawing (343).

**Fix.** `nextEvent` returns for background work at most once a display frame
(60 Hz), and keeps handling native events in between. Input events still
return at once. Programs need no change.

| Build of the original Atacama | App CPU | App instructions |
| --- | ---: | ---: |
| Unthrottled | 6.78 s, 6.95 s | 60.5G, 60.7G |
| 60 Hz | 2.12 s, 2.00 s | 14.0G, 14.1G |

The final window screenshots are byte-identical (same MD5).

**Test.** `verifyWakeThrottle` posts 200 wake-ups over 0.2 s and requires
between 3 and 40 returns. A mutant with the interval set to 0 fails it.

### 3. Call-depth frames blocked inlining of leaf functions

**Problem.** Every generated function began with `minyar_stack_enter()` and
ended with `minyar_stack_leave()`, the guard that turns runaway recursion into
a clean error instead of a crash. Minyarcraft's hottest function,
`terrain.get` (a bounds check and a Bytes load), paid a counter update and a
stack-range check per call, and the opaque runtime calls kept LLVM from
inlining it into the meshing loops.

**Evidence.** `sample` of `craft --screenshot` (world generation, lighting,
meshing and 30 frames): `meshing.showFace` 270 samples, `terrain.get` 267,
`remesh` 123, `occludes` 72. The disassembly of `terrain.get` showed the
guard's prologue and epilogue around eight instructions of real work.

**Fix.** A function whose body calls no Minyar function, and has at most 256
locals, gets no call-depth frame. It cannot deepen recursion, and its frame
fits in the 128 KiB reserve that its caller's check keeps
(`MINYAR_STACK_RESERVE_BYTES`). This is the same reasoning as Go's `NOSPLIT`
leaf functions. Calls are recognised from the emitted pieces (" @.minyar.fn."
or a quoted module name), so the check costs nothing measurable.

| Workload | Before | After | Change |
| --- | ---: | ---: | ---: |
| Minyarcraft `--screenshot noon` (3 runs each) | 32.84G, 32.13G, 32.10G | 25.57G, 25.60G, 25.58G | -20.3% |
| Compiler self-compile (front end) | 92M, 89M | 81M, 82M | -10% |
| Minyarcraft front-end compile | 109M | 99M | -9% |
| Minyar-OS kernel front-end compile | 497M | 462M | -7% |

The self-hosting fixed point holds (stage 3 equals stage 2).

**Test.** `tests/stack-overflow.py` now compiles a program with a Text-building
leaf, a caller of a local function and a caller of an imported one. It
requires that the leaf has no guard and both callers keep theirs, and that the
leaf still runs at the deepest allowed frame before the clean overflow stop.
The test fails on the previous compiler.

### 4. Two competing `http` packages

Not a speed fix, but one of the limits the brief named. appkit's NSURLSession
`http` and minyar-os's portable socket/TLS `http` both arrived in v2 under the
same name with the same blocking API. They are now one package with two
backends, chosen by the package search path in the way `library/arch/arm64`
already replaced `machine`:

- `library/http.min` is the portable client (`net` + `tls`; it does not
  validate certificates).
- `library/platform/macos/http.min` is the NSURLSession client. `./minyar`
  searches it first on macOS, and it adds the streaming handle API that
  Atacama uses.
- `./minyar` gained `--library DIR`, searched before the standard
  directories, so `./minyar --library library` selects the portable client on
  macOS.

`examples/fetch` builds unchanged against either backend. On macOS it links
`minyar_http_*` by default and `minyar_net_*` with `--library library`, and
both fetched from a local server. `check-http`, `check-modules` and
`tests/tls-local.py` (now forced onto the portable backend) pass, and the
Atacama app builds and streams.

Packages cannot hold state ("imported modules contain declarations only"),
so a portable `start`/`read` would need a request record instead of an
integer handle. That is the remaining gap if streaming is ever needed outside
macOS.

## Gates

`make check-budget` (the compiler's self-compile budget) was already failing
before tonight. The leaf-function change narrowed the gap but did not close
it:

| | Instructions (limit 75.0M) | Peak memory (limit 10.0 MiB) |
| --- | ---: | ---: |
| v2 before | about 91M | 10.8 MiB |
| v2 after | 80.7M | 10.8 MiB |

A Time Profiler trace of 300 self-compiles (`xctrace`, all processes) puts
`minyar_join_texts` at 14% self time, dyld start-up at about 20%, and the rest
spread across `compileFunctions`, `parseAtom`, `tokenIs` and `findLocal`, which
are already tuned.

## Tried and reverted

- **Joining the compiler's output once.** `compileTokens` returned
  `joinText(globals) + joinText(output)`, copying the 1.8 MB module twice.
  Giving the globals slot 0 of `output` produced byte-identical output but
  measured 81.2-81.8M instructions against 81.8-83.3M before, and the same
  10.55 MB peak footprint (the compiler's arena dominates). That is within
  noise, so it was reverted.

## Measured and not a bottleneck

- **Compile times.** Front-end compile of real programs, in retired
  instructions: the compiler itself (6,159 lines) 92M; Minyarcraft 110M;
  the Minyar-OS kernel 495M; Atacama 81M. End-to-end `./minyar` builds,
  including clang, take 0.8 s (Minyarcraft) to 2.6 s (Atacama `--release`).
  The OS kernel costs about 5x more per line than the compiler; that is the
  next thing to look at if compile time ever matters.
- **Minyar-OS** boots to the desktop in 632 ms under QEMU TCG. Its own frame
  profiler reports an average frame work of 0.2-2.3 ms against an 8 ms budget.

## Not merged: Astra cycle collection

The bake-off winner was ported onto v2 on branch `port/astra-cycles`
(`b9702e9`, `f819fbb`). Measured on v2, it costs programs that never form a
cycle:

| Workload | v2 | Astra port | Change |
| --- | ---: | ---: | ---: |
| Compiler self-compile (arena) | 87.9M | 88.1M | +0.2% |
| Compiler, system runtime | 361.5M | 397.6M | +10.0% |
| 20 x 5,000 chain (`acyclic.min`) | 193.3M | 227.1M | +17.5% |
| 100,000-record linked chain | 168.3M | 201.6M | +19.8% |
| 100,000 `List<Point>.add` | 46.6M | 57.3M | +23.1% |

Peak memory rose 63-76% on record-heavy programs (chain: 12.1 → 21.3 MiB),
from a 48-byte header on every List and every record that holds a reference.
Because of the rule "do not land regressions", it waits for a decision; see
MORNING.md.
