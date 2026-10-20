# Importing a C header

Select the declarations your program needs. Clang reads the header, resolves
its typedefs and evaluates its integer constants. The importer writes an
ordinary Minyar module, a C adapter and a JSON description of the checked
interface. No header code runs during import.

```sh
python3 tools/import-c.py tests/c-import/fixtures.h \
    --output build/c-import/gallery --library fixtureffi \
    --include lantern_measure --include lantern_echo \
    --clang "$(sh tools/toolchain.sh default-clang)"
```

The two functions use `LanternPoint` and `LanternReading`. Their record
declarations are imported automatically, including nested record fields.
The [harbour gallery](../examples/gallery/header-lantern.min) uses them:

```minyar
use "../../build/c-import/gallery.min" as harbour

let shore = harbour.LanternPoint { east: 3; north: 4 }
let light = harbour.lantern_measure(shore, 42.0)
print(light.glow)
```

Compile Minyar source as usual, then give the C adapter and the library's
implementation to the native linker. The existing aggregate adapter handles
the platform's register and structure-return conventions:

```sh
./build/minyarc examples/gallery/header-lantern.min build/header-lantern.ll \
    --library library
./build/tooling/tools/clang-driver link "$PWD" build/header-lantern.ll \
    build/minyar-runtime.o build/header-lantern 0 0 \
    examples/gallery/header-lantern.min \
    --native-source fixtureffi=build/c-import/gallery.c \
    --native-source fixtureffi=tests/c-import/fixtures.c
./build/header-lantern
```

Use a distinct `--library` name for each imported interface. Repeat
`--include NAME` to select functions, structs, typedefs, enums, individual enum
cases, static const integers or object-like integer macros. Selecting an enum
also exports its cases. Constants become literal Minyar Integers, including
macro expressions with casts, shifts, `sizeof` and conditional operators.
Values outside the signed 64-bit Integer range are rejected.

Pass target, SDK, include and preprocessor options after `--`:

```sh
python3 tools/import-c.py include/device.h --output build/device \
    --library deviceffi --include Device --include DEVICE_READY \
    -- --target=aarch64-linux-gnu --sysroot=/path/to/sdk -DDEVICE_VERSION=2
```

Generate separately for each target. Use the same target, SDK, preprocessor
options and header version when compiling the C adapter and Minyar program.
The generated C includes the original header by absolute path; regenerate
after relocating it. `MINYAR_CLANG` selects Clang when `--clang` is omitted.
Python 3 and Clang with JSON AST output are required. Each Clang invocation
has a 60-second limit, adjustable with `--timeout` from 1 to 600 seconds.

## Layout and ownership

Supported structs contain fixed-width integers, Boolean, float/double,
fixed byte arrays and other supported structs. Ordinary and explicitly
packed structs become `record Name native "c"` or `"c_packed"`.
The importer compares every field's offset and width, the total size and
alignment with Clang. An unrepresentable layout stops import. Generated C
keeps static assertions so a later header or target change fails compilation.
Field types, function signatures, scalar widths, signedness and constant
values are checked there too. The JSON description records the target triple,
scalar dimensions, header hash, compiler version and flags.

Integer parameters use Minyar Integer. Wrappers check the range before
converting to a narrower C integer. A UInt64 parameter or result preserves all
64 bits: Minyar `-1` is the bit pattern of C `UINT64_MAX`. Float parameters and
results use Minyar Float; conversion to C float rounds to 32 bits. A value
outside C float's finite range is rejected. Boolean stays Boolean.
Record arguments and results use Minyar's existing C-layout ownership:
by-value arguments are independent C values, and returned records own a copy.

Raw pointers, pointer fields, callbacks, variadic functions, unions, bitfields,
flexible arrays, non-byte arrays, unusual alignment and volatile/atomic storage
are rejected. A `const` pointer does not prove lifetime or prevent retention;
put those operations behind a C facade with an explicit ownership contract.
C functions remain responsible for their own behavior, just as other native
libraries do.

## Costs and evidence

Calls use statically linked native symbols. There is no libffi dispatcher,
dynamic signature interpretation or runtime layout discovery. Narrow integer
and float parameters have range checks; same-width scalar adapters only need
ordinary C conversions. Cross-language inlining depends on the final LTO
configuration. This first importer does not promise that all wrappers disappear.
Functions whose parameters need no narrowing checks are public native
declarations, without an additional Minyar forwarding function.

C-layout records use managed backing storage. Returning a record allocates
and copies that value; this is the existing aggregate ABI's cost. Constants
are substituted literals and static layout assertions have no runtime cost.

`make check-c-import` runs constants, scalar and aggregate calls, packed/nested
layouts, checked narrowing, header-layout drift, unsupported-interface
rejections, deterministic generation, normal-return ownership cleanup and the
gallery at O0/O2. Failed imports preserve previous output files.
On Linux x86_64 with KVM headers installed, the gate also imports the real
`kvm_userspace_memory_region`, `kvm_regs` and KVM API constants. It needs no
virtualization device.

Clang's [AST introduction](https://clang.llvm.org/docs/IntroductionToTheClangAST.html)
describes the parser interface. Its
[JSON node dumper](https://clang.llvm.org/doxygen/JSONNodeDumper_8h_source.html)
does not promise a stable format across major Clang releases; the toolchain
pin and the importer gate must move together.
