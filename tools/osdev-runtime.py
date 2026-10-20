#!/usr/bin/env python3
"""Select one program's freestanding runtime from authoritative LLVM markers."""

import argparse
import os
from pathlib import Path
import sys
import tempfile


WRAPPER_INCLUDE = '#include "../minyar_runtime.c"'
ENGINE_INCLUDES = (
    ('#include "minyar_rc.h"', '#include "minyar_cycle_rc.h"'),
    ('#include "minyar_collections.h"', '#include "minyar_cycle_collections.h"'),
)
CYCLE_PREFIX = """#define MINYAR_SORT_GRAPH 1
#define MINYAR_MAP_CYCLE_RUNTIME 1
#if defined(__GNUC__) || defined(__clang__)
#define MINYAR_NOINLINE __attribute__((noinline))
#else
#define MINYAR_NOINLINE
#endif
"""
CYCLE_SUFFIX = '\n#include "minyar_callbacks.h"\n'
INITIALIZE_PREFIX = '#define minyar_initialize_arguments minyar_freestanding_initialize_arguments\n'
INITIALIZE_SUFFIX = """
#undef minyar_initialize_arguments
void minyar_initialize_arguments(int count, char **values) {
    (void)minyar_callback_domain();
    minyar_freestanding_initialize_arguments(count, values);
}
"""
CYCLE_MARKERS = frozenset(("; minyar-cycle-runtime: 1", "; minyar-callback-runtime: 1"))
UNSUPPORTED_MARKERS = {
    "; minyar-thread-runtime: 1": "managed thread",
}
# Data parallelism already has a freestanding serial/custom-backend path in
# minyar_parallel.h; its marker neither rejects nor requires a cycle engine.
NATIVE_PREFIX = "; minyar-native-library: "


def profile(program):
    """Use the same full-line marker contract as tools/clang-driver.min."""
    cycles = False
    for entry in program.split("\n"):
        line = entry[:-1] if entry.endswith("\r") else entry
        if line in UNSUPPORTED_MARKERS:
            raise ValueError(f"{UNSUPPORTED_MARKERS[line]} runtime is unsupported by the freestanding OS profile")
        if line in CYCLE_MARKERS:
            cycles = True
        if line.startswith(NATIVE_PREFIX) and line[len(NATIVE_PREFIX):].strip() in ("runtime", "callbackruntime"):
            cycles = True
    return "cycle" if cycles else "ordinary"


def require_one(source, directive, description):
    count = source.count(directive)
    if count != 1:
        raise ValueError(f"{description} requires exactly one {directive}; found {count}")


def cycle_engine(source):
    """Mirror the shared cycleSource transform over the actual common engine."""
    for before, after in ENGINE_INCLUDES:
        require_one(source, before, "common runtime")
        source = source.replace(before, after, 1)
    return CYCLE_PREFIX + source + CYCLE_SUFFIX


def read_source(path):
    return path.read_bytes().decode("utf-8")


def render(root, program):
    selected = profile(program)
    wrapper = read_source(root / "runtime/freestanding/runtime.c")
    require_one(wrapper, WRAPPER_INCLUDE, "freestanding wrapper")
    if selected == "ordinary":
        return selected, wrapper
    common = read_source(root / "runtime/minyar_runtime.c")
    expanded = wrapper.replace(WRAPPER_INCLUDE, cycle_engine(common), 1)
    return selected, INITIALIZE_PREFIX + expanded + INITIALIZE_SUFFIX


def publish(program, root, output):
    program = program.resolve(strict=True)
    root = root.resolve(strict=True)
    output = output.resolve()
    inputs = (program, root / "runtime/freestanding/runtime.c", root / "runtime/minyar_runtime.c")
    if output in inputs:
        raise ValueError("runtime output must not overwrite a program or runtime input")
    selected, source = render(root, read_source(program))
    # Validate everything before creating/replacing the destination. A rejected
    # profile or malformed include contract leaves prior output untouched.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=output.parent, prefix=output.name + ".",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source)
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", required=True, type=Path, help="this program's LLVM IR")
    parser.add_argument("--root", required=True, type=Path, help="Minyar source root")
    parser.add_argument("--output", required=True, type=Path, help="generated runtime C path")
    args = parser.parse_args(argv)
    try:
        selected = publish(args.program, args.root, args.output)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"osdev runtime: {error}", file=sys.stderr)
        return 2
    print(f"osdev runtime: {selected} for {args.program}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
