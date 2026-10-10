#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compiler=${MINYAR_TEST_COMPILER:-"$project_dir/build/minyarc"}
clang_command=${MINYAR_TEST_CLANG:-clang}
build_dir="$project_dir/build/module-tests"
mkdir -p "$build_dir"

link_module() {
    optimization=$1
    llvm=$2
    executable=$3
    MINYAR_CLANG="$clang_command" MINYAR_CLANG_FLAGS="$optimization -Wno-override-module" \
        python3 "$project_dir/tools/clang-driver.py" link "$project_dir" "$llvm" \
        "$project_dir/build/minyar-runtime.o" "$executable" 0
}

compile_and_run() {
    name=$1
    source=$2
    expected=$3
    llvm="$build_dir/$name.ll"
    executable="$build_dir/$name"
    "$compiler" "$project_dir/$source" "$llvm"
    link_module -O0 "$llvm" "$executable"
    actual=$("$executable")
    if [ "$actual" != "$expected" ]; then
        echo "module test '$name' produced unexpected output" >&2
        echo "expected: $expected" >&2
        echo "actual:   $actual" >&2
        exit 1
    fi
}

# Like compile_and_run, for programs that use the standard library packages.
compile_and_run_with_library() {
    name=$1
    source=$2
    expected=$3
    llvm="$build_dir/$name.ll"
    executable="$build_dir/$name"
    "$compiler" "$project_dir/$source" "$llvm" --library "$project_dir/library"
    link_module -O1 "$llvm" "$executable"
    actual=$("$executable")
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
compile_and_run character-literals tests/modules/character-literals/main.min "4"
compile_and_run_with_library json tests/packages/json.min "atacama
1
Berlin Wall
0.25
true
café \"quoted\"
\"line\\nbreak\"
true
6
5
abc|0|a	b|x\\
true
true"
compile_and_run_with_library crypto tests/packages/crypto.min "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7
077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5
3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865
d31a8d34648e60db7b86afbc53ef7ec2
1ae10b594f09e26a7e902ecbd0600691
true
false
8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a
4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742
4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"
compile_and_run_with_library parallel tests/parallel/main.min "57
8"

expect_error private tests/modules/errors/private/main.min "'library.secret' is private to its module"
expect_error missing-member tests/modules/errors/missing-member/main.min "module 'library' has no function named 'missing'"
expect_error duplicate-alias tests/modules/errors/duplicate-alias/main.min "module alias 'repeated' is already used"
expect_error cycle tests/modules/errors/cycle/main.min "module import cycle:"
expect_error top-level tests/modules/errors/top-level/main.min "imported modules may contain declarations but not executable top-level statements"
expect_error package tests/modules/errors/package/main.min "package module 'minyar/http' is not available yet"
expect_error type-identity tests/modules/errors/type-identity/main.min "an argument passed to number has the wrong type"
expect_error malformed-use tests/modules/errors/malformed-use/main.min "use expects a quoted module name"
expect_error parallel-reference tests/parallel/errors/reference.min "parallel function 'bad' may use only Integer, Float, Boolean and Character values"
expect_error parallel-call tests/parallel/errors/call.min "parallel function 'bad' can only call parallel functions, not 'ordinary'"
expect_error parallel-entry tests/parallel/errors/entry.min "parallelEntry needs a parallel function, and 'ordinary' is not one"
expect_error missing-file tests/modules/errors/missing-file/main.min "does-not-exist.min' could not be opened"
expect_error private-record tests/modules/errors/private-record/main.min "'library.Hidden' is private to its module"
expect_error missing-as tests/modules/errors/missing-as/main.min "use expects 'as' after the module name"
expect_error bad-alias tests/modules/errors/bad-alias/main.min "use expects a module alias after 'as'"
expect_error public-statement tests/modules/errors/public-statement/main.min "public must describe a function, record, or constant declaration"
compile_and_run private-fields tests/modules/private-fields/main.min "crate 43 true 4"

# --library may be repeated: the first directory with a package wins.
"$compiler" "$project_dir/tests/modules/search-path/main.min" "$build_dir/search-path.ll" \
    --library "$project_dir/tests/modules/search-path/first" --library "$project_dir/tests/modules/search-path/second"
link_module -O0 "$build_dir/search-path.ll" "$build_dir/search-path"
if [ "$("$build_dir/search-path")" != "first farewell" ]; then
    echo "module test 'search-path' did not prefer the first package directory" >&2
    exit 1
fi
# library/arch/arm64 before library replaces `machine` with the Arm intrinsics.
"$compiler" "$project_dir/tests/modules/search-path/arm64.min" "$build_dir/arm64.ll" \
    --library "$project_dir/library/arch/arm64" --library "$project_dir/library"
if ! grep -F "cntvct_el0" "$build_dir/arm64.ll" >/dev/null || ! grep -F "cntfrq_el0" "$build_dir/arm64.ll" >/dev/null; then
    echo "module test 'arm64' did not lower machine intrinsics to Arm instructions" >&2
    exit 1
fi
expect_error private-field-read tests/modules/errors/private-field-read/main.min "field 'secret' of record 'Vault' is private to its module"
expect_error private-field-write tests/modules/errors/private-field-write/main.min "field 'secret' of record 'Vault' is private to its module"
expect_error private-field-create tests/modules/errors/private-field-create/main.min "record 'Vault' has private fields, so only its own module can create one"

echo "module resolution, visibility, identity, cycles, and native linking verified"
