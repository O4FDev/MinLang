# Debugging Minyar programs

Build with `minyar --debug "app.min" -o "app"`, or use `minyar build` in a
project. Debug builds retain original `.min` source locations, typed arguments,
initialized locals and lexical scopes. A matching `.dSYM` stays beside the
executable on macOS. Keep it with the executable when moving a build.

Start LLDB with `lldb "./app"`. Set a source breakpoint, run, and inspect the
current frame without evaluating an expression:

```text
(lldb) breakpoint set --file app.min --line 12
(lldb) run
(lldb) frame variable
(lldb) next
(lldb) thread backtrace
```

In GDB, use `gdb "./app"`, then `break app.min:12`, `run`, `info locals`,
`next` and `backtrace`. Debuggers show source fields of ordinary records from
their DWARF types. For a record pointer `point`, inspect `point->x` in GDB or
`frame variable point->x` in LLDB. The hidden `minyar_record_length` field is
runtime bookkeeping. A variable before its initializer, or a value removed by
optimization, may be unavailable.

The default managed runtime supplies the layouts described below. Arena builds
currently keep record and Map types opaque because their storage differs;
Text, Bytes and List prefixes are shared. Native C-layout records and callable
values are also opaque. Scalarized records are reconstructed as values from
their existing field operands. Closures describe their parameters and captured
values; parallel workers describe their captures, loop bindings and locals.

## Optional value formatters

The scripts in `tools/debugger` add bounded previews of Text, Bytes, typed
Lists, Maps and choices. They require a debugger built with Python 3 support.
Use the absolute path to your checkout in these commands; import them once per
debugger session.

```text
(lldb) command script import "/path/to/Minyar-Lang/tools/debugger/minyar_lldb.py"
(lldb) frame variable -P 2 -D 5 message values scores shape
```

```text
(gdb) source /path/to/Minyar-Lang/tools/debugger/minyar_gdb.py
(gdb) print message
(gdb) print values
(gdb) print scores
(gdb) print shape
```

For paths containing spaces, run GDB's import through Python instead:

```text
(gdb) python import sys; sys.path.insert(0, "/path with spaces/Minyar-Lang/tools/debugger")
(gdb) python import minyar_gdb
```

Previews have this shape; pointer addresses and debugger punctuation vary:

```text
message = "stars"
values = List<Integer>(length=3) { [0] = 10, [1] = 20, [2] = 30 }
scores = Map<Text, Integer>(length=1) { [0].key = "Ada", [0].value = 42 }
shape = Shape.Circle { radius = 2.5 }
```

Text previews read at most 256 UTF-8 bytes, preserve embedded zero bytes as
`\u0000`, and end truncated previews with `…`. Bytes use a hexadecimal preview
with the same byte limit. Lists show at most 64 elements. Maps show at most
32 occupied key/value pairs after scanning at most 256 buckets; a partial
preview reports its scanned bucket count. Bucket order is unspecified. Choices
show the active case and up to 64 fields of its payload. Narrow Boolean and
Character values retain the runtime's eight-byte collection slot spacing.

These formatters read memory and debug metadata only. They never call program
functions or allocate objects in the stopped program. Invalid lengths, invalid
tags, null values and unreadable memory produce `<Minyar: ...>` summaries.
Unavailable children are omitted. Previews do not validate an entire object
graph, and a truncated Map scan may find no entries even when the Map is not
empty.

To inspect the underlying layout, use `frame variable --raw-output values` in
LLDB, or `print /r values` in GDB. Disable the LLDB formatters with
`type category disable Minyar`; re-enable them with `type category enable
Minyar`. In GDB use `disable pretty-printer global Minyar` and `enable
pretty-printer global Minyar`.

The adapters follow the semantic types emitted by current debug builds. Older
executables that describe references only as opaque pointers need rebuilding.
Release builds omit Minyar debug metadata. Source stepping and frame inspection
are most useful in the default debug profile; optimized builds can move or
remove source-level values.

Full-debug ARM64 links use LLVM's SelectionDAG instruction selector: the pinned
GlobalISel path loses SSA Boolean locations at O0. This can change debug machine
code and compilation time. It adds no Minyar LLVM instructions, storage or value
uses. Line-only and release builds keep their usual selector.

## Formatter checks

`python3 "tools/debugger/test_formatters.py"` checks corruption bounds, Unicode
previews, sparse Maps, active choice payloads and eight-byte slot addressing
with portable debugger stubs. Compiler debug-info tests also check the emitted
DWARF and real debugger behavior where supported.

`make check-debugger-values` checks the value gallery, recursive record types
and direct/cached DWARF, then exercises installed LLDB and Linux GDB. Set
`MINYAR_TEST_LLDB` to select LLDB and `MINYAR_REQUIRE_DEBUGGERS=1` to require live
debugger coverage. The pinned compiler and `llvm-dwarfdump` still build and
verify the programs; the debugger may be a compatible system installation.
