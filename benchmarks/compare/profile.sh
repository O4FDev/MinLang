#!/bin/bash
# Profile one compare program's Minyar build with line information.
#   benchmarks/compare/profile.sh NAME [small|full|N]
# Builds main.min with --release plus -g for the program and runtime, runs it
# under callgrind on the chosen workload, and writes to build/compare-profile/NAME/:
#   self.txt       functions by exclusive Ir
#   inclusive.txt  functions by inclusive Ir (who pays for the runtime calls)
#   lines.txt      hottest source lines, runtime C and Minyar alike
# Callgrind counts the same retired instructions as cachegrind; the -g build
# can differ slightly from the measured binary, so take ratios from run.py.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
name=${1:?usage: profile.sh NAME [small|full|N]}
size=${2:-full}
out=$repo/build/compare-profile/$name
mkdir -p "$out"
read -r full small < "$here/$name/sizes"
n=$full; [[ $size == small ]] && n=$small; [[ $size =~ ^[0-9]+$ ]] && n=$size
arg=$n
if [[ -f $here/$name/gen.c ]]; then
    "${CC:-clang}" -O2 "$here/$name/gen.c" -o "$out/gen"
    "$out/gen" "$n" > "$out/input.txt"
    arg=$out/input.txt
fi
flags="-O2 -Wno-override-module -g"
(cd "$repo" && MINYAR_CLANG_FLAGS="$flags" MINYAR_RUNTIME_FLAGS="$flags" ./minyar --release "$here/$name/main.min" -o "$out/minyar") > "$out/build.log" 2>&1
MINYAR_PARALLEL_THREADS=4 valgrind --tool=callgrind --callgrind-out-file="$out/callgrind.out" "$out/minyar" "$arg" > "$out/stdout.txt" 2> "$out/valgrind.log"
callgrind_annotate --inclusive=no "$out/callgrind.out" > "$out/self.txt"
callgrind_annotate --inclusive=yes "$out/callgrind.out" > "$out/inclusive.txt"
callgrind_annotate --auto=yes --context=1 --threshold=99 "$out/callgrind.out" > "$out/lines.txt" 2>/dev/null || true
echo "$out"
head -40 "$out/self.txt" | tail -25
