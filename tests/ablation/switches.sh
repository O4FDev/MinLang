#!/bin/sh
# Smoke test for the experimental ablation switches (tools/ablation.sh,
# docs/testing.md "Ablation builds"): an empty or absent ablation file leaves the
# release code byte-identical, every switch keeps the probe's output, and each
# one removes the cost it names (IR or symbol assertion).
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/ablation.XXXXXX")
trap 'rm -rf -- "$work"' 0
probe=$root/tests/ablation/probe.min
fail() { echo "FAIL ablation: $*" >&2; exit 1; }
build() { # build NAME [SWITCH...]
    _name=$1; shift
    : > "$work/$_name.conf"
    for _switch in "$@"; do echo "MINYAR_ABLATE_$_switch=1" >> "$work/$_name.conf"; done
    MINYAR_ABLATION_FILE=$work/$_name.conf "$root/minyar" --release "$probe" -o "$work/$_name" > /dev/null
    "$work/$_name" > "$work/$_name.out"
    cmp -s "$work/base.out" "$work/$_name.out" || fail "$_name changes the probe's output"
}
MINYAR_ABLATION_FILE=$work/absent.conf "$root/minyar" --release "$probe" -o "$work/base" > /dev/null
"$work/base" > "$work/base.out"
build empty
# ThinLTO names promoted locals after the module, whose temporary path differs
# per build, so compare code when the files differ only in those names.
text() { "$objcopy" -O binary --only-section="$1" "$2" "$2.$3"; }
if ! cmp -s "$work/base" "$work/empty"; then
    objcopy=$(dirname -- "$(command -v "${MINYAR_CLANG:-clang}")")/llvm-objcopy
    [ -x "$objcopy" ] || objcopy=objcopy
    section=.text; [ "$(uname -s)" = Darwin ] && section=__TEXT,__text
    text "$section" "$work/base" code; text "$section" "$work/empty" code
    cmp -s "$work/base.code" "$work/empty.code" || fail "an empty ablation file changes the release code"
fi

# Program-IR switches: count the failure paths left after LLVM's own -O2.
"$root/build/minyarc" "$probe" "$work/probe.ll" --release --bounded-owners 32 --library "$root/library"
clang=${MINYAR_CLANG:-${LLVM_CC:-clang}}
optimized() { # optimized SWITCH... -> stdout: optimized IR of the ablated probe
    cp "$work/probe.ll" "$work/switch.ll"
    if [ "$#" -gt 0 ]; then sh "$root/tools/ablation.sh" ir "$work/switch.ll" "$@"; fi
    "$clang" -O2 -S -emit-llvm -Wno-override-module "$work/switch.ll" -o -
}
count() { optimized "$2" | grep -c "$1" || true; }
optimized > "$work/plain.opt.ll"
for pattern in 'call void @minyar_fail_integer_overflow' 'call [a-z0-9]* @minyar_list_[gs]et(' 'call i64 @minyar_text_length('; do
    [ "$(grep -c "$pattern" "$work/plain.opt.ll" || true)" -gt 0 ] || fail "probe no longer exercises: $pattern"
done
[ "$(count 'call void @minyar_fail_integer_overflow' OVERFLOW)" -eq 0 ] || fail "OVERFLOW leaves overflow checks"
[ "$(count 'call [a-z0-9]* @minyar_list_[gs]et(' BOUNDS)" -eq 0 ] || fail "BOUNDS leaves List position checks"
[ "$(count 'call i64 @minyar_text_length(' UNICODE)" -eq 0 ] || fail "UNICODE leaves Character counting"
sh "$root/tools/ablation.sh" runtime RECLAIM | grep -q '^#define MINYAR_COMPILER_ARENA 1$' || fail "RECLAIM does not select the arena"

# Whole builds: same output; runtime switches drop the bounded cleanup service.
for switch in OVERFLOW BOUNDS UNICODE RECLAIM SCHEDULER THREADS; do build "$switch" "$switch"; done
build all OVERFLOW BOUNDS UNICODE RECLAIM THREADS
nm=${NM:-nm}
if command -v "$nm" > /dev/null 2>&1; then
    "$nm" "$work/base" | grep -q rc_bounded_service || fail "baseline lost rc_bounded_service (update this test)"
    for switch in RECLAIM SCHEDULER; do
        if "$nm" "$work/$switch" | grep -q rc_bounded_service; then fail "$switch still links the bounded cleanup service"; fi
    done
fi
echo "ablation switches: ok (empty file: same code; 6 switches + all keep output; costs removed)"
