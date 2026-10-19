# Minyar style

Run `minyar fmt` to give source one quiet, consistent layout. Four spaces mark
each block. Opening braces share the declaration or condition's line; closing
braces align with it. Fields and statements occupy their own lines. A single
space surrounds binary operators and follows a colon or comma. Calls, member
access, ranges and generic type arguments stay together.

Before:

```minyar
record Lantern{name:Text;light:Integer}
let lamp=Lantern{name:"harbour";light:40}
if lamp.light>0{print( lamp.name )}else{print("dark")}
```

After:

```minyar
record Lantern {
    name: Text
    light: Integer
}
let lamp = Lantern {
    name: "harbour"
    light: 40
}
if lamp.light > 0 {
    print(lamp.name)
} else {
    print("dark")
}
```

Comments stay with their source. Literal spelling stays byte for byte,
including interpolation expressions, raw text and the indentation inside
multiline text. Changing that indentation could change the value. Existing
line breaks are retained because Minyar uses them to end statements. Explicit
semicolons become line breaks wherever newlines can serve as separators;
inside parentheses and Lists they remain explicit. Existing paragraph breaks
collapse to one empty line. Files end in one newline. The formatter does not
sort imports, rename names, rewrite expressions or wrap long literal text.

```sh
minyar fmt src tests             # format source files recursively
minyar fmt --check src tests     # print files needing work; exit 1 if any
minyar fmt --stdout src/main.min # preview one file without writing
minyar fmt -- --unusual.min      # stop option parsing
```

With no path, formatting starts in the current directory. Directory walks
skip hidden entries, `build`, `target`, `vendor` and `node_modules`, and never
follow symlinks. An explicit path must be a regular file or directory.
Replacement is atomic, keeps file permissions and rejects a source changed
since it was read. An unfinished literal or block comment leaves its file
untouched. Formatting a directory is a sequence of independent file edits.

`make check-minyar-format` checks golden layouts, literal/comment token preservation,
idempotence, command exit statuses and identical executable LLVM before and after
formatting every language conformance program, plus exact execution at O0/O2.
Raw LLVM includes source-position comments and token-indexed Text/List literal names;
the comparison removes only the debug-line/debug-function comments and consistently renames those
literal symbols by declaration order. All instructions and literal bytes remain
in the comparison. Raw LLVM byte identity is therefore not claimed.
The existing `check-format` target checks C formatting. This wave adds Minyar formatting;
repository-wide formatting remains a separate editorial decision.
