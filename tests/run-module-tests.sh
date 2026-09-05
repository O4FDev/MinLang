#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compiler=${MINYAR_TEST_COMPILER:-"$project_dir/build/minyarc"}
clang_command=${MINYAR_TEST_CLANG:-clang}
build_dir="$project_dir/build/module-tests"
mkdir -p "$build_dir"

compile_and_run() {
    name=$1
    source=$2
    expected=$3
    llvm="$build_dir/$name.ll"
    executable="$build_dir/$name"
    "$compiler" "$project_dir/$source" "$llvm"
    "$clang_command" -O0 -Wno-override-module "$llvm" "$project_dir/build/minyar-runtime.o" -o "$executable"
    actual=$($executable)
    if [ "$actual" != "$expected" ]; then
        echo "module test '$name' produced unexpected output" >&2
        echo "expected: $expected" >&2
        echo "actual:   $actual" >&2
        exit 1
    fi
}

expect_error() {
    name=$1
    source=$2
    expected=$3
    error_file="$build_dir/$name.error.txt"
    if "$compiler" "$project_dir/$source" "$build_dir/$name.invalid.ll" 2>"$error_file"; then
        echo "module test '$name' unexpectedly compiled" >&2
        exit 1
    fi
    if ! grep -F "$expected" "$error_file" >/dev/null; then
        echo "module test '$name' produced the wrong diagnostic" >&2
        echo "expected to contain: $expected" >&2
        sed -n '1,12p' "$error_file" >&2
        exit 1
    fi
}

compile_and_run basic tests/modules/basic/main.min "Hello, Ada
42
Ada"
compile_and_run diamond tests/modules/diamond/main.min "42"
compile_and_run explicit-main tests/modules/explicit-main/main.min "42"
compile_and_run windows-path tests/modules/windows-path/main.min "42"

expect_error private tests/modules/errors/private/main.min "'library.secret' is private to its module"
expect_error missing-member tests/modules/errors/missing-member/main.min "module 'library' has no function named 'missing'"
expect_error duplicate-alias tests/modules/errors/duplicate-alias/main.min "module alias 'repeated' is already used"
expect_error cycle tests/modules/errors/cycle/main.min "module import cycle:"
expect_error top-level tests/modules/errors/top-level/main.min "imported modules may contain declarations but not executable top-level statements"
expect_error package tests/modules/errors/package/main.min "package module 'minyar/http' is not available yet"
expect_error type-identity tests/modules/errors/type-identity/main.min "an argument passed to number has the wrong type"
expect_error malformed-use tests/modules/errors/malformed-use/main.min "use expects a quoted module name"
expect_error missing-file tests/modules/errors/missing-file/main.min "does-not-exist.min' could not be opened"
expect_error private-record tests/modules/errors/private-record/main.min "'library.Hidden' is private to its module"
expect_error missing-as tests/modules/errors/missing-as/main.min "use expects 'as' after the module name"
expect_error bad-alias tests/modules/errors/bad-alias/main.min "use expects a module alias after 'as'"
expect_error public-statement tests/modules/errors/public-statement/main.min "public must describe a function or record declaration"

echo "module resolution, visibility, identity, cycles, and native linking verified"
