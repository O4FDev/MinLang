# v2 performance work (2026-10-10)

What limited the real Minyar programs (the Atacama desktop app, Minyarcraft,
Minyar-OS and the compiler itself), found by profiling them, in the order the
fixes were made. Each entry gives the problem, the evidence, the fix, the
before/after numbers and the test. Instruction counts are retired
instructions of the application process (`proc_pid_rusage` or
`/usr/bin/time -l`). They are steadier than wall time on this shared, heavily
loaded machine; the load average was 30-76 throughout. By size of gain, the
largest are 1 (10x), 5 (51x on long Texts), 2 (4x), 8 (2x builds) and 4 (-32%).

## Results

| # | Problem | Fix | Before | After | Gain |
| --- | --- | --- | --- | --- | --- |
| 1 | Atacama history: every search keystroke rebuilt a stack of views per row | `macos.list`, a virtualized NSTableView | 112.6G instructions, 11.4 s CPU | 11.0G, 1.8 s CPU | 10.2x |
| 2 | Atacama streaming: each network chunk re-laid out the whole answer | background wake-ups capped at 60 Hz in `macos.nextEvent` | 60.5G instructions, 6.8 s CPU | 14.0G, 2.0 s CPU | 4.3x |
| 3 | Every function, even a one-line accessor, called the runtime's call-depth guard, so LLVM never inlined hot leaves | leaf functions carry no call-depth frame | Minyarcraft world build 32.1G instructions; compiler self-compile 91M | 25.6G; 81M | -20%; -11% |
| 4 | `record.field[i] = v` retained, registered and released the field on every store | no borrow when the rest of the statement makes no call | Minyarcraft 25.6G | 17.3G | -32% |
| 5 | `record.text = record.text + piece` copied the whole Text each time (quadratic) | in-place append when the record holds the only other reference | 80,000 appends 4.11G | 79.8M | 51x (and linear) |
| 6 | Compiling multi-module programs spent 27% of its time comparing symbol names character by character | symbol tables ordered by length, then from the last character | OS kernel compile 485M; Minyarcraft 109M; Atacama 80.5M | 342M; 71.4M; 58.1M | -28% to -35% |
| 7 | `json.parse` built every string from a parts list, a slice and a join | one slice when a string has no escapes | 20 parses of a 143 KB history response 1.22G | 0.95G | -22% |
| 8 | Every macOS app build recompiled the Objective-C bridges (`macos.m` 0.46 s, `http.m` 0.12 s) | content-keyed object cache, already used for `graphics.c`, now for every native bridge | Atacama default build 0.93-1.11 s; release app 1.86-2.41 s | 0.48 s; 1.39-1.46 s | about 2x |
| 9 | Minyarcraft's GPU vertex buffers dominated its memory (40-byte float vertices, six per quad) | 32-byte vertices (Float16 colour and light) and `graphics.updateQuads` (four vertices per quad, shared indices) | peak RSS 602 MB, footprint 892 MB, 17.30G instructions | 419 MB, 697-725 MB, 16.44G | -30% RSS, -5% instructions |

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

**Test.** `verifyWakeThrottle` posts 200 wake-ups 1 ms apart from another
thread and requires at least one return, and at most one per frame (60 a
second) for as long as the posting takes, plus 10. A mutant with the interval
set to 0 fails it.

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
locals, 1,024 temporaries and 1,024 labels, gets no call-depth frame. It
cannot deepen recursion, and its frame (about 18 KiB at most, even
unoptimized) fits in the 128 KiB reserve that its caller's check keeps
(`MINYAR_STACK_RESERVE_BYTES`). This is the same reasoning as Go's `NOSPLIT`
leaf functions. The parser counts the user calls it emits in each body (parser
state slot 14), so the check costs nothing measurable.

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

### 4. Indexed stores through a field borrowed the field

**Problem.** `world.blocks[index] = block` read `world.blocks`, retained it,
registered it as a frame temporary, stored the byte, and released it at the
end of the statement, in case evaluating the index or value replaced the
field. Commit `650d79b` (September) already skipped this borrow for indexed
reads, which made meshing 3.9x faster; stores still paid it.

**Evidence.** After change 3, an `xctrace` Time Profiler run of
`craft --screenshot` showed `terrain.put` at 110 inclusive samples, with
`rc_bounded_poll_work`, `minyar_rc_keep` and malloc/free under it. Its IR
was `record_get`, `rc_borrow`, the arithmetic, `bytes_set` and `rc_step`.

**Fix.** When the target is `record.field[...]` and the rest of the statement
(the remaining target path and the value) contains no call, no code can run
between reading the field and storing into it, so the borrow is omitted. Line
ends (kind-6 tokens) can appear inside a statement's brackets: across the lines
of a record literal's braces, and as `;` separators anywhere. So the scan ends
the statement at a line end only outside all brackets, or at a closing bracket
below its start.

The first version stopped at any line end, and the review workflow found two
programs where that was unsound:
- `board.cells[0] = Cell {⏎ first: 1⏎ value: replace(board) }`: the line end
  after `first: 1` stopped the scan before the call.
- `grid.rows[0] = [; resetGrid(grid)]`: the `;` did the same.

In both, the borrow was dropped, and ASan reported a heap-use-after-free when
the call replaced the List. `tests/codegen/owned-join.min` (`storeLiteral`,
`storeSeparated`) now requires the borrow in both; these checks fail on the
earlier compilers. The append rewrite in change 5 also now checks token kinds,
so a string literal `"+"` cannot pass for the operator.

| Workload | Before | After | Change |
| --- | ---: | ---: | ---: |
| Minyarcraft `--screenshot noon` (3 runs each) | 26.84G, 25.59G, 25.57G | 17.31G, 17.29G, 17.30G | -32% |

Since the start of the night, Minyarcraft's world build has gone from 32.1G
to 17.3G retired instructions (1.86x).

**Test.** `tests/codegen/owned-join.min` FileChecks that a call-free store has
no `minyar_rc_borrow` and that a store whose value calls a function that
replaces the field keeps it. The program's output (42, then 7) is checked at
O0 and O2, and the same program ran clean under ASan and UBSan. The contract
fails on the previous compiler.

### 5. Appending to a Text field was quadratic

**Problem.** `local = local + piece` already appended in place
(`minyar_join_text_take_left`), but `record.field = record.field + piece`, and
`record.field += piece`, borrowed the field, copied it into a new Text, and
replaced the field. Atacama does this per streamed delta
(`run.text = run.text + event.text`).

**Evidence.** A record field grown by 20,000, 40,000 and 80,000 appends:

| Appends | Before | After |
| ---: | ---: | ---: |
| 20,000 | 340.0M | 27.2M |
| 40,000 | 1,143.8M | 44.8M |
| 80,000 | 4,105.0M | 79.8M |

Before, each doubling cost 3.4-3.6x; after, each costs about 1.7x, roughly
linear once the ~10M instructions of process start-up are subtracted.

**Fix.** The compiler treats `name.field = name.field + rest` like `+=`, which
keeps left-to-right evaluation: it reads and borrows the field, evaluates the
rest, then calls `minyar_record_append_text(record, field, current, right)`. If
the field still holds the borrowed Text and the record and that borrow are its
only two owners, nothing else can observe it, so it grows in place with
doubling capacity. Otherwise it falls back to the old join and replace. In
Atacama the answers are only about 25 KB, so streaming did not get measurably
faster (14.3-14.6G instructions either way); the fix removes the quadratic
cost for longer texts.

**Tests.** `tests/codegen/owned-join.min` FileChecks the append call and the
absence of `minyar_record_replace`, and checks that an earlier alias of the
field keeps its old value. A separate program covered aliases, another record
sharing the Text, self-append, Unicode, a right side that replaces the field
first, nested fields and List elements. It printed the same output as the v2
compiler under the system, eager, fixed and lazy memory profiles, `--release`
and `--debug`.

### 6. Symbol lookups dominated multi-module compiles

**Problem.** Compiling the Minyar-OS kernel cost about 5x more instructions
per line than the compiler compiling itself.

**Evidence.** An `xctrace` Time Profiler run over 60 kernel compiles put
`compareText` at 271 of 1,013 samples (27%). The symbol table is heap-sorted
and binary-searched, so the number of comparisons was already O(n log n), but
each comparison walked the shared prefix of module-qualified names
(`minyar_module_12_...`) through checked Text indexing.

**Fix.** The table needs a consistent total order, not alphabetical order, so
`compareSymbolName` orders by length and then from the last character. Equal
names still sort together, which the duplicate-declaration check relies on.
The two other `compareText` callers keep the lexicographic comparison: the
integer-literal range check and the integer dispatch lowering's ordering
check.

| Front-end compile (retired instructions) | v2 | Now | Change |
| --- | ---: | ---: | ---: |
| Minyar-OS kernel | 485.2M | 341.5M | -30% |
| Minyar-OS loader | 132.2M | 92.3M | -30% |
| Minyarcraft | 109.3M | 71.4M | -35% |
| Atacama | 80.5M | 58.1M | -28% |
| The compiler itself (one file) | 89.9M | 80.9M | -10% (mostly change 3) |

These figures include change 3, which alone cut the compiler self-compile by
about 10% and the other programs' compiles by 7-9%. For change 6 alone, the generated IR
is byte-identical for all five programs.

**Tests.** Byte-identical output is the main check. `check-modules` (including
the duplicate-declaration diagnostics), `check-diagnostics` and
`check-regressions` pass. `tests/symbol-order.py` (`check-symbol-order`)
pinned `compareSymbol` to alphabetical order. Its oracle now uses the new
order (UTF-8 length, character count, characters from the end, kind). It
still checks reflexivity, antisymmetry, transitivity, equal names comparing
equal, and the lookup permutation, and it fails on the previous compiler.
`compareText` is still checked against alphabetical order.

### 7. JSON strings were assembled from parts

**Problem.** The `json` package (used by Atacama for history and streaming,
and by Minyar-OS) parsed about 420 instructions per byte. While measuring the
Astra port on a real payload (Atacama's 500-run history response, 143 KB) I
profiled it with `xctrace`: allocation, free and deferred-cleanup work
dominated, much of it from `parseString`, which allocated a parts list, a
slice and a joined copy for every string, even strings with no escapes.

**Fix.** Scan for the closing quote first; if no backslash comes before it,
return one slice of the source. Strings with escapes take the existing path.

| 20 parses of the history response | Before | After |
| --- | ---: | ---: |
| Retired instructions (3 runs) | 1.216G, 1.223G, 1.213G | 0.954G, 0.955G, 0.940G |

Most of what remains is the incremental release of the previous round's
trees, which the benchmark throws away each time.

**Test.** `tests/packages/json.min` now covers a plain string, an empty
string, a tab escape, an escaped backslash at the end, and two unterminated
strings. A separate program covering quote, `\u00e9` and surrogate-pair
escapes printed the same output as the v2 base. Atacama's `make test` passes.

### 8. Native bridges were recompiled on every build

**Problem.** Profiling an Atacama build after a one-line change: `--check` takes
0.23 s and the front end about 0.02 s, but a default build took about 1 s. The
driver compiled `runtime/native/macos.m` (0.46 s) and `http.m` (0.12 s) into a
fresh temporary directory on every link, so every macOS app paid about 0.6 s
for code that had not changed.

**Fix.** `tools/clang-driver.py` already cached `graphics.c` by content. That
cache is now `native_object`, keyed by the source, every runtime header, the
compiler's identity and version, and the flags, and it serves `graphics`,
`macos`, `http` and `net`. The compiler identity is computed once per link.

| Atacama build (wall time) | Before | After (cache warm) |
| --- | ---: | ---: |
| `./minyar src/main.min` | 0.93 s, 1.11 s | 0.48 s, 0.48 s |
| `./minyar --release --app ...` | 2.41 s, 1.86 s | 1.39 s, 1.46 s |

**Test.** `tests/native-object-cache.py` (`check-native-cache`, part of
`check` and `check-portable`) builds a native object twice and requires the
second build to reuse it without recompiling. Changing a runtime header, the
source or the flags must each produce a new object, and no temporary files
may be left behind. `tests/native-graphics.py` and a Minyarcraft build still
pass.

### 9. Mesh vertices were 40 bytes of Float32

**Problem.** `craft --screenshot` peaks at about 600 MB of RSS and an 892 MB
memory footprint. The world itself is 21 MB of blocks, so most of the rest is
the 1,024 chunk meshes uploaded with `glBufferData`. Each vertex was ten
Float32 values, and each quad is six vertices.

**Fix.** Mesh vertices are 32 bytes. Position and texture coordinates stay
Float32, so atlases up to 8192 px keep exact texel positions. Colour, sky and
glow become Float16, which still holds values above 1 and is far finer than
8-bit display. Lines keep their ten-Float32 layout. The conversion uses the
processor's half-precision conversion where the compiler has `_Float16`; a
portable round-to-nearest-even routine (`runtime/native/half-float.h`) is the
fallback. Indexed quads (four vertices instead of six) would save more, but
they would change the `graphics` API, so they are left for later.

| `craft --screenshot noon` (3 runs) | Before | After |
| --- | ---: | ---: |
| Peak RSS | 602, 603, 602 MB | 447, 450, 523 MB |
| Peak memory footprint | 892, 892, 897 MB | 815, 815, 844 MB |
| Retired instructions | 17.31G, 17.29G, 17.30G | 17.24G, 17.22G, 17.21G |

A first version that converted in software everywhere cost +6% instructions
(18.33G), which is why the hardware path is used where available.

**Quads.** Every chunk face is a quad, but meshes were plain triangle lists,
six vertices per quad. `graphics.updateQuads(mesh, vertices)` takes four
vertices per quad, a b c d, and draws a b c and a c d through one shared
index buffer that grows to the largest quad mesh. Minyarcraft's `quad()`
emits four vertices: starting at b instead of a picks the other diagonal, as
its ambient-occlusion split needs. The sky meshes stay triangles.

| `craft --screenshot noon` (3 runs) | 40-byte triangles | 32-byte triangles | 32-byte quads |
| --- | ---: | ---: | ---: |
| Peak RSS | 602-603 MB | 447-523 MB | 419 MB (all 3 runs) |
| Peak memory footprint | 892-897 MB | 815-844 MB | 697-725 MB |
| Retired instructions | 17.29-17.31G | 17.21-17.24G | 16.43-16.45G |

`tests/graphics-render.py` (`check-graphics-render`, macOS desktop) renders
the fixed scene twice as triangles and once as quads. It requires the two
triangle renders to be identical and the quad render to be identical to
them, and an incomplete quad must stop with "four vertices per quad".

**Tests.**
- `benchmarks/desktop/render-check.min` draws a fixed scene with a range of
  colours, sky and glow; two runs of one build give identical PNGs. Against
  the 40-byte build, the largest difference in any colour channel is 1/255,
  on 0.4% of bytes, from half-precision rounding. The Minyarcraft screenshot
  looks the same, selection lines included.
- `tests/half-float.c` (`check-half-float`, part of `check` and
  `check-portable`) compares the software conversion with `_Float16` for one
  float32 bit pattern in 13 and every exactly representable half. Run with
  `all`, it checks all 2^32 values; they all match. A mutant without
  ties-to-even fails with 2,363 mismatches.
- `tests/native-graphics.py` passes.

### 10. Two competing `http` packages

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

## A bug introduced and fixed tonight

The clean-up after review moved leaf detection onto a new parser-state slot,
index 14. That slot was already the base of the ownership-slot map
(`ownershipSlot` stores entries from index 14). When a body's call count
happened to equal its generation number, a binding got ownership slot -1, an
out-of-bounds store. The module test `private-fields` crashed about 30% of
the time; ASan showed a heap-buffer-overflow in `minyar_rc_local_take`. The
map now starts at index 15. `tests/regressions.py` has a deterministic case,
which fails on the broken build and passes now. The broken commit had been
merged into v2 but not pushed; the suite run on it was stopped.

## Tried and reverted

- **Joining the compiler's output once.** `compileTokens` returned
  `joinText(globals) + joinText(output)`, copying the 1.8 MB module twice.
  Giving the globals slot 0 of `output` produced byte-identical output but
  measured 81.2-81.8M instructions against 81.8-83.3M before, and the same
  10.55 MB peak footprint (the compiler's arena dominates). That is within
  noise, so it was reverted.

## Measured and not pursued

- **Record field bounds checks.** `minyar_record_get` checks the field index
  on every read, although the compiler always emits a valid one. Removing the
  check in a variant build took Minyarcraft from 17.30G to 16.69G
  instructions (-3.6%). It stays: it is part of the runtime's hardening and
  turns a compiler or layout mismatch into a clean stop instead of memory
  corruption.

## Measured and not a bottleneck

- **Atacama start-up.** Launch, session check, loading and parsing 500 runs,
  and the first render: about 2.04G instructions and 0.31 s of CPU, the same
  before and after tonight's changes. AppKit set-up dominates, and the
  history parse is about 3% of it. The driver's `startup` scenario measures
  this.
- **Typing in Atacama.** 300 keystrokes, 20 ms apart: 2.8G instructions and
  0.61 s of CPU, about 2 ms per key. The main thread waits in `nextEvent` 95%
  of the time, and the rest is AppKit's key handling, not the app's re-render.
- **Atacama build after a one-line change.** The front end takes about 0.02 s,
  so an incremental front end would not help. What is left after change 8 is
  clang: about 0.4 s for a default build, and about 1 s more for `--release`
  LTO.

- **Compile times.** Before tonight, front-end compiles of real programs cost
  92M instructions (the compiler itself, 6,159 lines), 110M (Minyarcraft),
  495M (the Minyar-OS kernel) and 81M (Atacama). End-to-end `./minyar` builds,
  including clang, took 0.8 s (Minyarcraft) to 2.6 s (Atacama `--release`).
  The kernel cost about 5x more per line than the compiler, which led to
  change 6. After changes 3, 6 and 8, see the tables in those sections.
- **Minyar-OS** boots to the desktop in 632 ms under QEMU TCG. Its own frame
  profiler reports an average frame work of 0.2-2.3 ms against an 8 ms budget.

## Not merged: Astra cycle collection

The bake-off winner was ported onto v2 on branch `port/astra-cycles`. A
subagent then spent three rounds cutting its cost, and the branch includes
tonight's work up to `c986a76` (merged as `ebb02ba`); the later JSON, native
cache, graphics and correctness commits are not on it. In particular it still
has the first version of the store-borrow scan, which misses multi-line record
literals (see change 4), so merge current v2 into it before merging it
anywhere. The base below is v2 at the time of each
measurement.

| Workload | v2 | First port | Final port |
| --- | ---: | ---: | ---: |
| Compiler on the system runtime | 364.5M | 397.6M (+10%) | 363.6M (~0%) |
| 100,000 `List<Point>.add` | 46.5M | 57.3M (+23%) | 46.6M (+0.2%) |
| 20 x 5,000 chain (`acyclic.min`) | 193.3M | 227.1M (+17.5%) | 218.3M (+12.9%) |
| 100,000-record linked chain | 168.2M | 201.6M (+19.8%) | 189.9M (+12.9%) |
| Peak memory, linked chain | 12.1 MiB | 21.3 MiB | 18.2 MiB |

On the real programs, measured on the final port:

- Minyarcraft is +0.06% and the compiler self-compile +1.0%. Atacama
  streaming is within noise (14.36-14.73G against 14.34-14.36G).
- `json.Value` holds `items: List<Value>`, so it counts as a type that can
  form a cycle. Parsing Atacama's 500-run history response 20 times went from
  1.22G to 1.57G instructions (+29%), and peak memory rose from 3.0 to
  3.4 MiB.

What it costs, in the subagent's analysis (`research/cycles/README.md` on the
branch):

- Objects of self-referential types carry a 32-byte header and keep exact
  registry and incoming-edge counts, because the first cycle-forming
  mutation can close a cycle through objects built earlier.
- Once tracing is on, collection scans the global set of traced objects:
  about 37,000 instructions per add in a tree-mutation benchmark.

Since the rule tonight was not to land regressions, it stays on its branch.
If it is merged, telling the compiler that `json.Value` can never form a
cycle (it is built bottom-up) would remove the JSON cost, but that needs a
language-level "acyclic" annotation.
