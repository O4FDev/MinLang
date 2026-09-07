#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
afl_cc=${AFL_CC:-afl-clang-fast}
afl_fuzz=${AFL_FUZZ:-afl-fuzz}
seconds=${MINYAR_AFL_SECONDS:-60}
findings=${MINYAR_AFL_FINDINGS:-$project_dir/build/afl-findings}
target_dir=$project_dir/build/afl
target=$target_dir/minyarc-afl
candidate=$target_dir/candidate.ll

command -v "$afl_cc" >/dev/null 2>&1 || {
    echo "AFL++ compiler '$afl_cc' is required (set AFL_CC to override)." >&2
    exit 2
}
command -v "$afl_fuzz" >/dev/null 2>&1 || {
    echo "AFL++ runner '$afl_fuzz' is required (set AFL_FUZZ to override)." >&2
    exit 2
}
case "$seconds" in ''|*[!0-9]*) echo "MINYAR_AFL_SECONDS must be a positive integer." >&2; exit 2 ;; esac
[ "$seconds" -gt 0 ] || { echo "MINYAR_AFL_SECONDS must be positive." >&2; exit 2; }

mkdir -p "$target_dir" "$project_dir/build"
make -s -C "$project_dir" LLVM_CC="${MINYAR_TEST_CLANG:-clang}" build/compiler-stage2.ll

# AFL++'s LLVM mode instruments the already self-hosted compiler IR as well as
# its arena runtime. Sanitizers make memory/undefined-behaviour findings fatal.
AFL_QUIET=1 AFL_USE_ASAN=1 AFL_USE_UBSAN=1 "$afl_cc" \
    -O1 -g -Wno-override-module -DMINYAR_COMPILER_ARENA \
    "$project_dir/build/compiler-stage2.ll" "$project_dir/runtime/minyar_runtime.c" \
    -o "$target"

if [ -d "$findings" ]; then
    export AFL_AUTORESUME=1
fi
export AFL_SKIP_CPUFREQ=1
export AFL_NO_UI=1
# AFL++ requires ASan symbolization to be disabled during the campaign.
export ASAN_OPTIONS=abort_on_error=1:detect_leaks=0:symbolize=0
"$afl_fuzz" -V "$seconds" -m none -t 5000+ \
    -x "$project_dir/tests/fuzz-corpus/minyar.dict" \
    -i "$project_dir/tests/fuzz-corpus/inputs" -o "$findings" \
    -- "$target" @@ "$candidate"

failures=0
for category in crashes hangs; do
    directory=$findings/default/$category
    [ -d "$directory" ] || continue
    for input in "$directory"/*; do
        [ -f "$input" ] || continue
        case "$(basename -- "$input")" in README*) continue ;; esac
        echo "AFL++ found $category input: $input" >&2
        failures=$((failures + 1))
    done
done
[ "$failures" -eq 0 ] || exit 1
echo "AFL++ coverage-guided campaign completed without crashes or hangs ($seconds seconds)."
