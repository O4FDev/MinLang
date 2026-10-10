# v2 performance work (2026-10-10)

What limited the real Minyar programs (the Atacama desktop app, Minyarcraft,
Minyar-OS and the compiler itself), found by profiling them, in the order the
fixes were made. Each entry gives the problem, the evidence, the fix, the
before/after numbers and the test. Instruction counts are retired
instructions of the application process (`proc_pid_rusage` or
`/usr/bin/time -l`). They are steadier than wall time on this shared, heavily
loaded machine; the load average was 30-76 throughout. By size of gain, the
largest are 1 (10x), 5 (51x on long Texts), 17 (10x on a long streamed
answer), 12 (4x on long lists), 2 (4x), 8 (2x builds), 4 (-32%) and 15
(-28%).

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
| 11 | The compiler missed its self-compile budget: Text comparisons with literals were calls, and the 1.9 MB output was joined before being written | Inline length check for Text equality; `writeTextFile(path, List<Text>)`; a shorter call-depth guard | self-compile 80.40M instructions, 10.81 MiB; Minyarcraft 16.44G | 72.18M, 9.23 MiB; 15.74G | -10% and -15% (budget met); -4.3% |
| 12 | Lists of a self-referential record (such as `json.Value`) could only grow by copying: `items = items.appended(v)` was quadratic | `x = x.appended(e)` moves x's owner into the append, and a List with no other owner grows in place | 500-run history, 20 parses: 1.115G; 5,000 runs, 2 parses: 3.06G | 0.836G; 0.756G | -25%; 4.0x (linear) |
| 13 | Minyarcraft frames: each of the 276 chunk draws a frame (plus water) looked up and re-sent seven uniforms, and each water draw toggled blending, so the GL driver kept revalidating its state | uniform locations cached at link time; uniforms, program, texture, opacity and blending changed only when they differ | 15.7M instructions per idle frame | 8.05M | -49% per frame |
| 14 | The call-depth guard in every non-leaf function was about 20 instructions, and meshing inlines dozens of small guarded functions per block | the guard's common path is two comparisons; the exact checks moved to a cold path | world build 15.65G; one block edit 28.7M | 14.19G; 25.8M | -9.3%; -10% |
| 15 | Small functions that only call unchecked functions still paid the call-depth check (Minyarcraft's meshing helpers) | two levels of such functions above the leaves drop their check | `--benchmark build` 13.66G; `edit` 33.35G | 9.86G; 25.40G | -28%; -24% |
| 16 | Release builds used full LTO | ThinLTO for `--release` and for the compiler | Minyarcraft 15.73-15.81G; JSON 0.834G; self-compile 71.95M | 14.90-14.94G; 0.806G; 70.55M | -5.5%; -3%; -2% |
| 17 | Atacama streaming: the answer label measured, typeset and drew all of its text every frame | `macos.textView` and `appendText` (TextKit 1), no text checking in read-only text, no URL cache in `http`, buttons skip drawing outside their bounds | 12,000-delta answer 123.0G instructions, 14.0-14.2 s CPU; 3,000 deltas 14.3-15.0G | 11.8-12.3G, 3.3-4.1 s CPU; 3.5-3.7G | 10.2x; 4.0x |
| 18 | Minyarcraft's mesh writer called into the runtime for each 32-byte vertex, which zeroed the bytes before they were written | `minyar_native_bytes_append`, an inline append in the native header that writes in place while capacity lasts | `--benchmark build` 9.85-9.87G; `edit` 25.06-25.20G | 9.53-9.54G; 24.24-24.26G | -3.3%; -3.5% |
| 19 | Atacama history: each search keystroke built every visible list cell again, buttons included, because `reloadData` discards the cells on screen instead of queueing them for reuse | a list keeps the cells it had on screen and hands them back on reload | search over 500 runs 10.38-10.39G instructions, 1.69-1.74 s CPU | 6.35-6.36G, 0.89-0.94 s | -39% |

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

### 11. The compiler's self-compile budget

**Problem.** `make check-budget` limits the compiler compiling itself to 75M
retired instructions and 10 MiB of peak memory. It had failed all night (80.4M,
10.8 MiB). About 9M of any process here is fixed: a C program that returns at
once retires 9.07M instructions on this macOS.

**Evidence.**
- An instrumented runtime that reads `proc_pid_rusage` around the final join
  showed `joinText(output)` costing 8.4M instructions: 199,228 pieces making
  1.9 MB, about 42 instructions a piece, plus faulting in a fresh 1.9 MB
  buffer that existed only to be written to the file.
- Arena statistics at exit: Text data 2.46 MiB, of which 1.81 MiB was that
  joined module.
- A cycle-sampling profile (`xctrace` CPU Profiler) put the expression parser
  (`parseExpression`, `parseAnd`, `parseUnary`, `parseAtom`, `operatorLevel`)
  and `minyar_texts_are_equal` near the top. Every `token == "*"` was a call.
  Even inlined, each comparison first tested whether both sides were the same
  object, which stopped LLVM from sharing the length and byte loads across a
  run of comparisons. `operatorLevel` makes up to 16 of them per operand.

**Fix.**
- `minyar_texts_are_equal` is an always-inline runtime entry with no identity
  shortcut. With link-time optimisation, comparing a Text with a literal is
  now a length compare and a load of one to a few bytes; `token == "&&"` is a
  single two-byte compare. Equality means the same as before.
- `writeTextFile(path, contents)` also accepts a `List<Text>` (in the compiler
  and the C bootstrap compiler). It writes what `joinText(contents)` would,
  through a 256 KiB buffer, without building the joined Text. The compiler
  returns its module as pieces, and `main` writes them. Programs with globals
  still join them into one leading piece, as before.
- The call-depth guard's common path became two comparisons, with the full
  original check run only on the first call or when a call might fail. The
  measurement below used my first version of this. The subagent working on
  Minyarcraft made the same change independently (change 14), and its
  version, which is equivalent and also pins the guard's shape in a test, is
  the one that was kept.

| Self-compile (best of 5-7 runs) | Instructions | Peak RSS |
| --- | ---: | ---: |
| v2 | 80.40M | 10.81 MiB |
| + inline Text equality | 77.97M | 10.80 MiB |
| + `writeTextFile` with pieces | 76.84M | 9.25 MiB |
| + shorter call-depth guard | 76.06M | 9.27 MiB |
| + no identity shortcut in Text equality | 71.76M | 9.23 MiB |
| Final, rebuilt to its fixed point (7 runs) | 72.18-72.54M | 9.23-9.27 MiB |

`make check-budget` now passes: 72.73M instructions and 9.2 MiB, with 90th
percentile CPU 8.53 ms against a 22 ms limit.

The runtime changes help every program built with link-time optimisation:

| Workload (3 runs each) | v2 | Now |
| --- | ---: | ---: |
| Minyarcraft `--screenshot noon` | 16.44G, 16.44G, 16.43G | 15.74G, 15.74G, 15.74G |
| Minyarcraft front-end compile | 73.3M, 68.7M, 67.1M | 66.2M, 63.8M, 61.9M |
| Atacama front-end compile | 25.0M, 23.6M, 23.4M | 23.0M, 22.8M, 23.0M |

The Minyarcraft screenshots look the same. Two runs of one build already differ
in a few pixels, so they can't be compared byte for byte. Minyar-OS, whose
freestanding runtime includes the same file, builds and reaches its desktop
in QEMU (612 ms).

**Tests.**
- The bootstrap is itself a test of the new `writeTextFile`: stage 0
  (C) compiles the compiler, which writes its own output in pieces, and
  stage 2 equals stage 3.
- `tests/regressions.py` `test_write_text_file_writes_list_pieces_without_joining`
  writes 120,004 pieces through the buffer, including a 350,000-byte piece
  larger than the buffer, Unicode and an empty piece. It compares the file
  with Python's expected bytes and with `joinText`, at O0 and O2. It also
  checks that the call is `minyar_write_text_parts` and that an unwritable
  path stops with "could not be created". `test_builtin_types` now rejects
  `writeTextFile("x", [1, 2])`.
- `check-regressions`, `check-modules`, `check-codegen`, `check-stack-overflow`
  (with and without sanitizers), `check-examples` and `check-budget` pass.

### 12. Lists of a self-referential record grew quadratically

**Problem.** The language rejects `items.add(v)` when the List's element type
can contain itself, because the mutation could close an ownership cycle ("this
List mutation could create a reference cycle; construct a new List instead").
Such Lists must be built with `items = items.appended(v)`, which copies the
whole List, retaining every element, on each append. `json.parse` builds every
array and object this way, because `json.Value` holds `items: List<Value>`.
So parsing Atacama's history (one array of runs) was quadratic in its length.

**Evidence.** `benchmarks/json/history-parse.min` parses the history response
that Atacama's stub server sends (`benchmarks/json/history.py`) and reads each
run's fields the way `src/api.min` does. A CPU Profiler trace put
`minyar_list_appended` at 17% inclusive, under `parseString`'s caller, and
much of the deferred cleanup (54%) released the copies. Ten times the runs
cost 27 times the instructions.

**Fix.** When the right side of `x = x.appended(e)` starts with the target
local, the compiler moves x's owner into the call (the same transfer that
`x = x + text` already used for Text). It does this after evaluating `e`,
so `e` can still read x. The new runtime entry `minyar_list_appended_take`
appends in place when that moved owner was the List's only one, and otherwise
copies and releases it. A List with no other owner is not held by any record
or List, so `e` cannot reach it: appending in place cannot form a cycle, and
nothing can observe the change. An alias, a `for` loop over the List (which
holds its own reference), or a List stored in a record all keep the copying
path.

| `history-parse` (3 runs each) | v2 | Now |
| --- | ---: | ---: |
| 500 runs (143 KB), 20 parses | 1.114G, 1.117G, 1.115G | 0.837G, 0.836G, 0.836G |
| 5,000 runs (1.4 MB), 2 parses | 3.069G, 3.063G, 3.038G | 0.757G, 0.756G, 0.755G |

Per parse, 500 runs went from 55.7M to 41.8M instructions, and 5,000 runs from
1,530M to 378M. Ten times the runs now cost nine times as much, where they cost
27 times before. Both versions print the same counts.

**Tests.**
- `tests/codegen/owned-join.min` FileChecks that `x = x.appended(e)` emits
  `minyar_rc_local_move` and `minyar_list_appended_take`; this fails on the v2
  compiler. Its output (run at O0 and O2) checks that an alias keeps the List
  it saw, that a `for` loop iterates only the List it started with, and that
  `x = x.appended(x[0])` reads x before consuming it.
- The same program printed the same output under the system, eager, fixed and
  lazy memory profiles and `--release`, and ran clean under ASan and UBSan.
### 13. Every chunk draw re-sent the frame's uniforms

Sections 3, 4 and 9 measured `--screenshot`, which is almost all world build.
Play is different: the world is built once, then every frame draws, and every
block edit updates its column's sky light and re-meshes the chunks around it.

**Measuring play.** `./craft --benchmark build|idle|walk|edit [image.png]`
builds a fresh world at noon, plays 600 scripted frames with a fixed 1/60 s
step, saves the last frame if asked and exits without saving the world. `idle`
stands still, `walk` flies forward while turning, and `edit` breaks the top
block of a column in a 16 by 16 patch in front of the player, then fills the
hole with planks on the next frame. Each edit changes the column's top, so it
marks the chunks within 4 blocks dirty, about 2.1 chunk rebuilds per edit.
`build` stops after two frames, so subtracting it gives the cost of play; the
per-frame figures below divide that by 600. Because the time step is fixed,
the saved frames are byte-identical between runs and between builds; every
image in this section and the next has the same MD5 as the original build's.

| Original build (instructions, 3 runs) | Total | Per frame or edit |
| --- | ---: | ---: |
| `build` | 15.66G, 15.68G, 15.63G | |
| `idle` | 25.12G, 25.06G, 25.04G | 15.7M per frame |
| `walk` (1 run) | 25.09G | about the same as `idle`: the world is fixed, so walking loads nothing |
| `edit` | 42.22G, 42.25G, 42.26G | 28.6M per edit on top of the frame |

**Evidence.** An `xctrace` Time Profiler run of `idle` (2,390 samples, about a
quarter of them start-up and the world build): `minyar_graphics_drawMesh` 567
inclusive samples, `drawTranslucentMesh` 190, `use_world_program` 227 and
`glGetUniformLocation` 136, against 440 for presenting the frame (`nextFrame`,
mostly `CGLFlushDrawable`). Minyar code per frame (sky, clouds, HUD text) was
small. The game draws every chunk within 150 blocks (276 meshes at the spawn),
plus the water meshes of those that have water, and each draw called
`use_world_program`: seven `glGetUniformLocation` string lookups, seven
uniform uploads and a texture bind. Each water mesh also enabled blending,
turned off depth writes and culling, and turned them back on. Under the draw
calls, Apple's OpenGL driver spent its time revalidating state
(`gldUpdateDispatch` 202 inclusive samples, `buildPipelineStateDescriptor` and
`updateUniformBindings` among the self samples).

**Fix.** `runtime/native/graphics.c` looks up the uniform locations once when
it links the programs. `setCamera`, `setFog` and `setLight` mark the world
uniforms stale, and the next draw uploads them once. The program, texture and
opacity are set only when they change. Translucent state stays on across
consecutive translucent meshes and is switched off before the next opaque
mesh, line batch, overlay or `clear` (depth writes must be on for the depth
buffer to clear). Programs need no change.

| `--benchmark` (instructions, 3 runs) | Before | After | Change |
| --- | ---: | ---: | ---: |
| `idle` | 25.12G, 25.06G, 25.04G | 20.44G, 20.50G, 20.45G | 15.7M to 8.05M per frame (-49%) |
| `build` | 15.66G, 15.68G, 15.63G | 15.63G, 15.63G, 15.62G | none |

The `idle` and `edit` images are byte-identical before and after. Leaving each
mesh's vertex array bound after drawing, instead of unbinding it, saved a
further 0.1M per frame in one run (20.39G against 20.44G), within noise, so
the unbind stays. A profile after the fix has `drawMesh` at 259 of 2,084
samples and no uniform lookups; presenting the frame (474) is now the largest
part of a frame. The game still draws the chunks behind the camera too; culling
them is a game change and was not tried.

**Tests.** `benchmarks/desktop/render-states.min` draws, in one frame, a
square at light 0.25, one at light 1.0, one under full red fog, a translucent
square at opacity 0.5, then a back-facing square, a near green square and a
far blue square over the same pixels, and an overlay rectangle.
`tests/graphics-render.py` (`check-graphics-render`) reads the PNG back and
requires each colour within 3 of the expected value: 64 grey, white, red, the
half blend, the clear colour (the back face is culled) and green (depth is
written after translucency). It passes on the old and new library. Two mutants
fail it: without the stale mark in `setLight` the second square is 64 grey,
and without switching translucency off before an opaque draw the back face
shows. `tests/native-graphics.py` passes.

### 14. The call-depth guard cost a third of meshing

**Problem.** After change 13, an edit costs about three and a half idle
frames, almost all of it in `meshing.buildChunk`. Per edit the game rebuilds
about two chunks (16 by 16 by 80 blocks each), about 13M instructions per
chunk, or 650 per block.

**Evidence.** In a profile of `edit` (3,237 samples), `buildChunk` has 741
self samples and `terrain.get` 448. Annotating `buildChunk`'s machine code
with the sampled addresses spreads the samples thinly, with recurring hot
spots on the inlined call-depth guard: the ready flag, the stack bounds
(`ldp`), the depth comparisons and the counter store. Change 3 removed the
guard from leaf functions, but `showFace` (which calls `isOpaque`),
`occludes`, `ambient`, `quad` and the other small helpers each call something,
so each keeps its guard, and LLVM inlines all of them into the per-block loop
with their guards. As a bound, deleting every `minyar_stack_enter`/`leave`
call from the emitted IR (unsafe, measurement only) took the world build from
15.65G to 10.54G instructions (-33%).

**Fix.** `minyar_stack_enter` is now two comparisons and an increment:

    if (depth >= depth_limit || current - stack_low <= RESERVE) slow(current)
    depth++

The depth limit starts at zero, so the first call takes the slow path, which
finds the stack bounds and sets the limit to the lowest cap that applies (the
logical maximum, or the fallback when the bounds are unknown). The unsigned
distance from the stack's low end is at most the reserve for every address
inside the reserve, and addresses below the stack wrap to huge values. So the
fast check catches every case the exact checks stop on, and the slow path
repeats the exact checks unchanged. With unknown bounds the low end is zero,
and only the depth limit applies. `minyar_stack_leave` is unchanged.

| Instructions (3 runs unless noted) | Before | After | Change |
| --- | ---: | ---: | ---: |
| `--benchmark build` | 15.74G, 15.63G, 15.65G | 14.19G, 14.19G, 14.19G | -9.3% |
| `--benchmark edit` | 37.71G, 37.67G, 37.71G | 34.46G, 34.48G, 34.42G | 28.7M to 25.8M per edit (-10%) |
| `--benchmark idle` | 20.44G, 20.50G, 20.45G | 18.93G, 18.99G, 18.92G | 8.05M to 7.93M per frame |
| Compiler self-compile (8 runs, alternating) | 80.5M-84.5M (median 81.2M) | 79.2M-83.0M (median 80.0M) | about -1.5% |

The compiler's output is unchanged (stage 2 is byte-identical to before, and
stage 3 equals stage 2), and its self-compile gets slightly cheaper, not
dearer. With both changes, `--screenshot noon` went from 16.44G, 16.42G,
16.42G to 14.72G, 14.73G, 14.72G (-10.4%), with peak RSS 398 MB either way, a
whole edit frame from about 44M to 34M instructions, and `walk` from 25.09G to
18.92G (one run each, identical images).

**Tests.** `tests/stack-limits.py` (`check-stack-limits`) still checks the
exact depth boundaries with known and unknown bounds, at O0 and O2, including
a fallback larger than the maximum. It now also compiles the runtime and
requires `minyar_stack_enter` to contain exactly two comparisons and no
reference to the ready flag, the stack's high end or the bounds query; the old
runtime has seven comparisons and fails. `check-stack-overflow`,
`check-stack-overflow-sanitize`, `check-codegen`, `check-ownership` and
`check-portable` (which includes `check-regressions`, `check-modules` and the
stage 2 and 3 comparison) pass.

**What is left.** Most of the guard's cost is still there: 14.19G against the
10.54G bound (measured before this change). A function that calls only
functions without a guard, at most a few levels deep, cannot recurse either,
so it could drop its guard as leaves do. Simulating that on Minyarcraft's IR
(a function loses its guard when every callee was emitted earlier without one,
at most two levels deep) drops 29 guards, including `showFace`, `occludes`,
`quad` and `torch`, and takes the world build from 14.17G to 10.78G (-24%);
three levels gives 10.60G. A chain of three frameless frames (heights 2, 1 and
0) below a guarded caller uses at most about 54 KiB of the 128 KiB reserve,
even with the 18 KiB worst-case frames of change 3. It is not done here
because the compiler has no per-function table that the call emitter can read:
`functionParameterCounts` already carries a second section found by halving
its length, the module compiler rebuilds that table when it reads a cached
one, and `compiler/module-compiler-adapter.patch` rewrites `compileFunctions`,
so the change touches both compilers and the patch. The height table also has
to be private to each `compileFunctions` call, so that an incrementally cached
module never depends on another module's bodies.

### 15. Call trees that cannot recurse kept their checks

**Problem.** Change 3 removed the call-depth check from leaves. After change
14 the check is two comparisons, but Minyarcraft's meshing still calls dozens
of small functions per block (`showFace`, `occludes`, `quad`) that only call
leaves. The Minyarcraft subagent removed every check from the emitted IR as an
upper bound (unsafe, measurement only), and the world build fell by a third.
Its simulation of the rule below gave -24%.

**Fix.** A function whose every call goes to a function without a check cannot
recurse: each of those calls returns without calling back. So after all
functions are compiled, `dropTreeGuards` also removes the check from two
levels of small functions above the leaves. A function qualifies when:
- it is within the leaf limits on locals, temporaries and labels, is not
  `main`, parallel or a machine intrinsic, and has no stack ownership frame;
- it makes at most 16 user calls (the bound keeps the analysis cheap);
- every callee is a leaf, or (for the second level) a first-level function.
The callees are read back from the emitted calls. A function whose recognised
calls number fewer than the parser counted keeps its check, so an unexpected
call form can only cost speed. Recursion, direct or mutual, never qualifies.
At most three frames of about 18 KiB run below the caller's check, inside the
128 KiB reserve it left (`MINYAR_STACK_RESERVE_BYTES`).

| Workload (3 runs each) | Before | After |
| --- | ---: | ---: |
| Minyarcraft `--benchmark build` | 13.68G, 13.65G, 13.66G | 9.86G, 9.86G, 9.87G |
| Minyarcraft `--benchmark edit` | 33.34G, 33.35G, 33.36G | 25.40G, 25.40G, 25.40G |
| Compiler self-compile (5 runs) | 70.14-70.78M | 71.22-71.37M |

The saved `edit` frames are byte-identical. Minyarcraft keeps 31 checked
functions, down from 67. The compiler keeps 54, down from 109 before
tonight. The analysis costs the self-compile about 1% net. A first version that
looked up every call in every candidate cost 5%; the 16-call bound removed
most of that. Another version dropped the checks of functions marked as never
qualifying. The guard count fell further than it should have, which is how I
noticed. The test below now covers it.

**Tests.** `tests/stack-overflow.py` now requires:
- no check in a function that calls only an imported leaf, or in one that
  calls it and a local leaf;
- a check in a third level, in two mutually recursive functions, and in a
  small function whose callee is large;
- the clean stop at the deepest recursion, with the leaf still running there.

The fixed point holds. `check-stack-overflow`, `check-stack-overflow-sanitize`,
`check-stack-limits`, `check-regressions`, `check-modules`, `check-codegen`
and `check-budget` (71.7M) pass.

### 16. Release builds used full LTO

**Problem and evidence.** `--release` linked the program and the runtime with
`-flto`. While trying a ThinLTO cache to speed up release links, the binaries
built with `-flto=thin` turned out to run faster, consistently.

| Workload (3 runs each) | Full LTO | ThinLTO |
| --- | ---: | ---: |
| Minyarcraft `--screenshot noon` | 15.81G, 15.73G | 14.92G, 14.90G, 14.94G |
| `history-parse`, 500 runs, 20 parses | 0.835G, 0.834G, 0.834G | 0.807G, 0.832G, 0.806G |
| Compiler self-compile (5 runs) | 71.95-72.79M | 70.55-71.99M |

The link takes as long (about 1 s for Minyarcraft) and the binary is 10%
larger (180,504 to 198,200 bytes). The cache made an unchanged relink 0.3 s, but
after a change to the program it took as long as before, so it was not kept.

**Fix.** `tools/clang-driver.py` links release programs with `-flto=thin`, and
the Makefile builds the compiler with it (`COMPILER_LTO_FLAGS`). CI on Linux
sets its own LTO flags and is unaffected.

**Tests.** `tests/release-build.py` and `tests/launcher-isolation.py` accept
any `-flto` form. Both pass, as does `check-budget`.
### 17. Streamed answers were laid out again in full every frame

**Problem.** After change 2, Atacama still set the whole answer on its
NSTextField label once a frame while a run streamed. A label keeps no layout
between changes: each `setText` measures all of the text again for Auto Layout
(`intrinsicContentSize` → `boundingRectWithSize`), then typesets and draws
it again. Each frame cost more as the answer grew, so a stream's total grew
with the square of its length.

**Evidence.** Retired instructions of the app for the stream scenario (3 runs
each, load average 4-32), by answer length:

| Deltas (answer size) | Before |
| ---: | ---: |
| 0 | 0.63G, 0.52G, 0.52G |
| 3,000 (15.8 KB) | 14.42G, 14.34G, 15.05G |
| 12,000 (63.3 KB) | 122.99G, 122.15G, 124.58G |

Four times the length cost 8.5 times as much. An `xctrace` Time Profiler run
of the 3,000-delta stream had 358 on-CPU samples: 259 on the main thread, of
which 130 were drawing the label's text (`__NSStringDrawingEngine`), 52 were
measuring it (`-[NSTextField intrinsicContentSize]`) and 20 were drawing
buttons; the other 98 were on network threads.

**Fix.** Four parts, each found by profiling after the one before.

1. `macos.textView(parent, text)` is read-only, selectable text that wraps to
   its width and grows to fit, built on a TextKit 1 layout manager, and
   `macos.appendText(handle, text)` adds to the end of its text storage (or a
   `textEditor`'s). The layout of the earlier text is kept, so an append lays
   out only the last line and the new text, and a selection survives it.
   Atacama's answer is now a textView. While a run streams, `render` records
   how many characters the view shows and appends only the rest. Any other
   change (a new run, a saved run, the placeholder) sets the whole text, as
   before. With only this part, a 12,000-delta stream cost 31.29-32.29G.
2. The profile of that build (12,000 deltas, 5,305 samples) had 557 samples
   in AppKit's text checking: after every edit the layout manager re-applies
   the selection, and `NSTextCheckingController` (spelling marks, correction
   bubbles and candidates) asks the view for the text around it three times.
   With a one-paragraph answer, that is the whole answer, copied every frame
   (`-[NSBigMutableString getCharacters:range:]`, 181 samples of self time).
   Turning the checking settings off did not stop it. Read-only text has
   nothing to check, so the textView now answers
   `annotatedSubstringForProposedRange:actualRange:` with nothing. In a
   window, through the bridge, 200 frames of 10 appended words then cost
   537-540M instructions at every length from 4,000 to 12,000 words, against
   972M growing to 2,207M before.
3. The same profile had 857 samples on network threads in CFNetwork's
   `conCatData`: the default NSURLSession configuration keeps a response for
   its URL cache, and each received chunk rebuilt the list of all earlier
   chunks (`dispatch_data_create_concat`, then disposing of the old list), so
   12,000 chunks cost quadratic time. The `http` package now has no URL cache,
   like the portable backend. Atacama always wants fresh answers and
   history, and the cache had been writing responses to disk (`sample` of
   the old build shows `_CFURLCacheFSWriteCachedResponseToFS`). The cache
   cost 0.45G at 3,000 deltas and 8.6G at 12,000: 19 times as much for 4
   times the length.
4. That left costs that are the same each frame. In a profile of the build
   with parts 1-3 (12,000 deltas, 3,878 samples), 388 of the main thread's
   2,423 samples were drawing buttons (`-[NSControl drawRect:]`), although no
   button changed. A test window showed why: the Copy and Edit prompt buttons
   sit below the answer, and each time the answer gained a line and pushed
   them down, AppKit asked each one to draw the strip it had left, a
   rectangle wholly outside its bounds. Skipping `enabled` calls that change
   nothing, another layer redraw policy, and ignoring invalidations outside
   the bounds did not stop it. A button now draws only when the rectangle it
   is asked to draw meets its bounds. In the test window its cell drawing
   went from 36 times in 60 appends to none, and the window looked the same,
   pixel for pixel.

Each step, measured with the app built at that step (3 runs each):

| Build | 3,000 deltas | 12,000 deltas |
| --- | ---: | ---: |
| Before: label | 14.42G, 14.34G, 15.05G | 122.99G, 122.15G, 124.58G |
| 1: textView and appendText | 6.06G, 6.28G, 5.97G | 31.76G, 31.29G, 32.29G |
| 2: and no text checking | 4.48G, 4.46G, 4.45G | 22.26G, 22.83G, 22.33G |
| 3: and no URL cache | 4.04G, 3.97G, 4.02G | 14.44G, 13.71G, 13.19G |
| 4: and no button drawing outside the bounds (final) | 3.75G, 3.54G, 3.55G | 11.95G, 12.34G, 11.80G |

The step 1 runs at 3,000 deltas may have overlapped native GUI tests I was
running at the time; the others ran alone.

After parts 1-3, the main thread's on-CPU samples per 5 seconds stayed flat
while a 12,000-delta answer streamed (428, 449, 443, 445, 422), so the cost
of a frame no longer grows with the answer.

| Deltas | Before | After (3 runs) | Change |
| ---: | ---: | ---: | ---: |
| 0 | 0.63G, 0.52G, 0.52G | 0.51G, 0.51G, 0.51G | none |
| 3,000 | 14.42G, 14.34G, 15.05G (2.15-2.31 s CPU) | 3.75G, 3.54G, 3.55G (1.03-1.11 s) | 4.0x |
| 12,000 | 122.99G, 122.15G, 124.58G (14.04-14.19 s CPU) | 11.95G, 12.34G, 11.80G (3.33-4.05 s) | 10.2x |

Four times the length now costs 3.3 times as much (3.7 times without the
0.51G that the scenario costs with no answer), about linear, where it cost
8.5 times as much before.

**Layout.** The final text is the same: the answer's accessibility value
after the stream is byte-identical before and after (5,283, 15,836 and 63,336
bytes for 1,000, 3,000 and 12,000 deltas), and equals the stub server's text.
For a 1,000-delta answer the screenshots are identical at the top of the
answer, and at its end differ only in the blinking caret
(`docs/v2-evidence/atacama-stream-1000-before.png` and `-after.png`).

For 3,000 and 12,000 deltas the line breaks differ, and the old label cut off
its last line: at 3,000 deltas its answer visibly ends "...the atacama desert
is a", while the text ends "...is a plateau in south america covering a
strip", which the textView shows (`atacama-stream-3000-end-before.png` and
`-after.png`, and the same for 12,000). The cause is the label. A test window
with the same styling showed it laying out the same words with slightly wider
spacing once its text passed somewhere between 8,441 and 10,557 characters
(1,600 words matched the textView exactly; 2,000 words did not), so its
wrapping changed in the middle of a stream, and (it appears) the height it
measured no longer fitted what it drew. The textView keeps the wrapping that the label has for shorter
text, and shows all of it. The text is still selectable and copies as plain
text.

What is left is the work of each frame. A profile of the final build
(12,000 deltas, 2,778 samples) has 1,942 on the main thread: AppKit's display
cycle 384 (Auto Layout 174, drawing 226, of which the text view 78), the
background layout of the new text 277, and Atacama's `render` 353 (233 of
them appending). Button drawing is down to 2 samples. The 834 samples on
other threads are mostly socket reads for the 12,000 chunks.

**Tests.** `tests/macos-native.m` `verifyTextView` appends 2,000 times to a
textView in a scroll view. Each append must produce exactly one text-storage
edit, of the appended characters only, and text laid out before an append
must stay laid out. The content, the selection, the height (grows to fit,
rewraps when the window narrows, shrinks after `setText`), attributes on
appended text, alignment, `selectable`, plain-text copy, appending to an
editor, and the absence of text for text checking are checked too. A misuse
diagnostic covers `appendText` on a label (`append-type`). Three mutants fail
it: an append that sets the whole string again, one that invalidates all
layout, and the view without the text-checking override.
`verifyMovingButton` pushes a button down by 40 appends to the textView above
it and requires that its cell is not drawn, then that it is drawn after its
title changes; it fails without the `drawRect:` check. `tests/http.min`
fetches a response marked cacheable for ten minutes twice and requires two
different answers; with the URL cache left on, the second came from the
cache. `check-macos` (with and without ASan/UBSan), `check-modules`,
`check-http` and Atacama's `make test` pass.

### 18. Each mesh vertex was a call into the runtime

**Problem.** A profile of the world build on final v2 (`--benchmark build`,
587 samples) has 46 samples in writing vertices: 25 in
`minyar_graphics_addLitVertex` itself, 13 in `minyar_bytes_extend` and 8 in
the `memset` it calls. `graphics.c` is a native object outside the program's
LTO, so every vertex was a call into the runtime that reserved and zeroed 32
bytes, which `add_vertex` then overwrote in full.

**Fix.** `runtime/minyar_native.h` has `minyar_native_bytes_append(bytes,
count)`, for native writers that fill every byte they append. Bytes keep
their capacity in `character_length` (as `minyar_bytes.h` documents), so
while it lasts the append is a comparison and an addition, inline, with no
zeroing. Beyond it, or for a negative count, it calls `minyar_bytes_extend`,
which grows or stops as before. `add_vertex` uses it.

| 3 runs each | Before | After |
| --- | ---: | ---: |
| `craft --benchmark build` | 9.871G, 9.852G, 9.851G | 9.540G, 9.532G, 9.541G |
| `craft --benchmark edit` (2 runs) | 25.06G, 25.20G | 24.24G, 24.26G |

**Tests.** `tests/native-bytes.c` (`check-native-bytes`, part of `check` and
`check-portable`) links the header against the program runtime. Appends
within capacity must not move the storage, appends beyond it must keep the
earlier contents, a cleared Bytes must refill in place, 65,536 bytes of
random appends must match a model (also clean under ASan and UBSan), and a
negative count must stop with the runtime's message. A program that writes
lit and plain vertices in three rounds, across growths and two clears,
ending with 5,108 vertices (163,456 bytes), produces byte-identical output
built from v2 and from this change.
`check-graphics-render`, `tests/native-graphics.py` and
`tests/native-object-cache.py` pass. The opt-in research probe
`tests/native-research-graphics.c` counts calls to `minyar_bytes_extend`
per vertex; it already expected the 40-byte vertices of before change 9, and
is not a maintained gate, so it is unchanged.

### 19. A refilled list built its visible rows from scratch

**Problem.** With change 1, a History search costs 10.4G instructions for 20
keystrokes, about 90 ms of CPU per key. A Time Profiler run of the search
(1,706 samples on the app's main thread) has 993 in `-[NSTableView layout]`.
Of those, 455 are in `-[MNList tableView:viewForTableColumn:row:]`, 321 of
them creating row buttons (`+[NSButton buttonWithTitle:target:action:]`),
and 310 are in `_updateKeyViewLoopForRowView:` for the new rows. MNList
already asks for reusable cells (`makeViewWithIdentifier:owner:`), but a
counter in a build of Atacama showed 420 cells created for 420 requests:
none was ever reused. A harness on the real bridge showed why. Scrolling
reuses cells (48 requests, 1 new cell), but `reloadData`, which every
refill ends with, drops the cells on screen without queueing them, and the
reuse queue is empty afterwards.

**Fix.** Before `reloadData`, `-[MNList reload]` takes the cells on screen
out of their rows and keeps them. When the table asks for a cell and its
queue is empty, it gets one of those. Every request already configured a
cell completely (text, fonts, colours, hidden lines, button and
constraints), so a kept cell is the same as a new one. Row views are not
kept: handing the old row views back made one row lose its cell in the test
below, because the table still tracks them until its next layout.

| History search, 500 runs (3 runs each) | Before | After |
| --- | ---: | ---: |
| Retired instructions | 10.39G, 10.39G, 10.38G | 6.35G, 6.36G, 6.36G |
| CPU | 1.736 s, 1.710 s, 1.686 s | 0.893 s, 0.942 s, 0.937 s |

The screenshot of the filtered list is byte-identical before and after.
Keeping the row views too measured 5.16G; that is the 1.2G left on the
table, for a design that does not lose cells.

**Tests.** `tests/macos-native.m` `verifyList` refills a list and requires
every cell on screen to be one that was on screen before. Each must sit in
its own row view, show its new row's text and hidden lines, and keep its
button. A click on a reused row's button must report the new row. Without
the fix it fails at `reused == shown`. A separate harness refilled 500
rows ten times, with wrapped rows of two heights: every visible row showed
its own text, row heights matched each cell's fitting height, no view
appeared twice, and 30 cells were created for 300 requests. `check-macos`
(including its ASan/UBSan build), Atacama's `make check` and `make test`,
and the driver's `delete` scenario (the first row's trash button deletes
it) pass.

## Gates

`make check-budget` (the compiler's self-compile budget) was already failing
before tonight. It passes after change 11:

| | Instructions (limit 75.0M) | Peak memory (limit 10.0 MiB) |
| --- | ---: | ---: |
| v2 at the start of the night | about 91M | 10.8 MiB |
| after change 3 | 80.7M | 10.8 MiB |
| after change 11 | 72.7M | 9.2 MiB |

## Bugs introduced or found, and fixed, tonight

**Ownership slot collision.** The clean-up after review moved leaf detection onto a new parser-state slot,
index 14. That slot was already the base of the ownership-slot map
(`ownershipSlot` stores entries from index 14). When a body's call count
happened to equal its generation number, a binding got ownership slot -1, an
out-of-bounds store. The module test `private-fields` crashed about 30% of
the time; ASan showed a heap-buffer-overflow in `minyar_rc_local_take`. The
map now starts at index 15. `tests/regressions.py` has a deterministic case,
which fails on the broken build and passes now. The broken commit had been
merged into v2 but not pushed; the suite run on it was stopped.

**Call-depth fallback cap.** A review of change 11 found that my first guard
ignored `MINYAR_MAX_CALL_DEPTH` when the fallback depth was larger, which
`tests/stack-limits.py` checks. Fixed; the guard kept is change 14's.

**Growing a value in place that someone else still holds.** A review of
change 12 found two ways that `x = x + e` (Text, since 6 October) and
`x = x.appended(e)` (change 12) could change a value that someone else still
held:
- On a parameter before its first assignment, the local owns nothing, so the
  caller's only count passed the uniqueness test. The callee grew and then
  freed the caller's value: the caller's Text printed empty, with a
  use-after-free under ASan.
- When x was read again later in the statement (`t = t + "!" + t`), the later
  read saw the change: `abcd!abcd!` instead of `abcd!abcd`.

The move now gives the consumer a new count when the local owns nothing
(`minyar_rc_local_move_owner`). The transfer is skipped when the name is read
again in the statement (member names and field labels don't count).
`tests/regressions.py`
`test_consuming_self_assignment_respects_parameters_and_later_reads` fails on
v2 and passes now.

## Tried and reverted

- **Writing the compiler's pieces through a 32 KiB buffer.** The copy loop
  costs 2.1M instructions, but the 58 file writes it made cost more than one
  1.9 MB write (79.1-80.5M against 78.7M in total). Each write call costs tens
  of thousands of instructions in the file system. A 256 KiB buffer (8 writes)
  gets the gain while adding only 0.25 MiB at peak.
- **Large compiler Lists in `malloc`/`realloc` instead of the arena.** The
  three token Lists grow in step, so each growth copies the List and leaves
  about 1 MB of old copies in the arena. Moving them to `realloc` raised peak
  RSS by 1 MiB (11.8 MiB) for no instruction gain, so the arena stays.
- **`inlinehint` on leaf functions.** No measurable change (76.1-76.7M against
  76.1-76.5M).
- **Joining the globals into slot 0 of the output.** Nothing to gain for the
  self-compile, which has no globals. Change 11 covers it for programs that
  do.

- **Joining the compiler's output once.** `compileTokens` returned
  `joinText(globals) + joinText(output)`, copying the 1.8 MB module twice.
  Giving the globals slot 0 of `output` produced byte-identical output but
  measured 81.2-81.8M instructions against 81.8-83.3M before, and the same
  10.55 MB peak footprint (the compiler's arena dominates). That is within
  noise, so it was reverted.

- **Leaving vertex arrays bound after drawing.** See change 13: 20.39G
  against 20.44G for 600 idle frames, one run each, within noise.

## Measured and not pursued

- **Record field bounds checks.** `minyar_record_get` checks the field index
  on every read, although the compiler always emits a valid one. Removing the
  check in a variant build took Minyarcraft from 17.30G to 16.69G
  instructions (-3.6%). It stays: it is part of the runtime's hardening and
  turns a compiler or layout mismatch into a clean stop instead of memory
  corruption.
- **Forcing `terrain.get` inline.** Before change 14, marking it
  `alwaysinline` in the emitted IR took the world build from 15.65G to 14.87G
  (-5%) and an `edit` run from 42.29G to 40.47G. Change 12 and the frameless
  call trees described there address the larger cost around it.

## Measured and not a bottleneck

- **Atacama start-up.** Launch, session check, loading and parsing 500 runs,
  and the first render: about 2.04G instructions and 0.31 s of CPU, the same
  before and after tonight's changes. AppKit set-up dominates, and the
  history parse is about 3% of it. The driver's `startup` scenario measures
  this.
- **Accessibility clients on long lists.** The driver's `delete` scenario
  finds the first row's trash button by walking the accessibility tree,
  which makes the table realize a view for every row: 94.6-103.8G
  instructions and about 15 s of CPU for one delete over 500 runs, the same
  before and after change 19. It measures the driver's search more than the
  app, but VoiceOver walking a long list would pay the same.
- **Non-ASCII streamed answers.** An in-place Text append (change 5) drops
  a non-ASCII Text's character index, so each frame's `answer.length` and
  `slice` in Atacama rebuild it over the whole answer. With an em dash, a
  curly apostrophe and an ellipsis among the stub's words, a 12,000-delta
  answer cost 11.24G instructions against 10.79G for ASCII (+4%, one run
  each), because the rebuild reads ASCII eight bytes at a time. Extending
  the index on append instead would remove that.
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
  At the end of the night, one boot of each on the loaded machine: the start
  of the night reached the desktop in 488 ms with 0.66-1.03 ms of average
  frame work, final v2 in 628 ms with 0.55-0.59 ms. Under TCG that is within
  noise either way.

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
