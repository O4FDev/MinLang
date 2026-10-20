#!/bin/sh
set -eu

compiler=${MINYAR_CLANG:-clang}
scratch=$(mktemp -d "${TMPDIR:-/tmp}/minyar-freestanding-math.XXXXXX")
trap 'rm -rf "$scratch"' EXIT HUP INT TERM

# Under -ffreestanding, Clang can lower __builtin_sqrt to a call to sqrt.
# If this implementation is sqrt itself, LTO treats the recursion as undefined.
"$compiler" --target=x86_64-unknown-none-elf -march=x86-64-v2 -O2 -flto \
    -ffreestanding -fno-builtin -nostdinc \
    -isystem "$("$compiler" -print-resource-dir)/include" \
    -isystem runtime/freestanding/include \
    -mno-red-zone -fno-stack-protector -fno-pic -Wall -Wno-unused-function \
    -S -emit-llvm runtime/freestanding/freestanding.c -o "$scratch/freestanding.ll"

sed -n '/^define .*@sqrt(/,/^}/p' "$scratch/freestanding.ll" > "$scratch/sqrt.ll"
if ! grep -q '@llvm.sqrt.f64' "$scratch/sqrt.ll" || grep -Eq 'call .*@sqrt\(' "$scratch/sqrt.ll"; then
    echo 'freestanding sqrt must lower to llvm.sqrt without a self-call' >&2
    exit 1
fi
echo 'freestanding sqrt lowers to llvm.sqrt without recursion'
