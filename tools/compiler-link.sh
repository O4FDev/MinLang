#!/bin/sh
# compiler-link.sh CLANG ARG...: link a compiler-sized program with exactly the arguments its rule gives Clang, but in
# parallel. When the link is a ThinLTO one (-flto=thin) and llvm-split ships beside the real driver, the largest LLVM
# IR input is split into MINYAR_LINK_PARTITIONS (4) modules by function, each prelinked in parallel, and the ThinLTO
# backend runs one job per module: the single-module link was the longest serial step of a cold build (45-58 s, 17-20
# s split). The partition count is fixed, never the host's core count, so every machine links the same program; the
# ThinLTO cache keys each module, so an edit relinks only the modules it touches. Anything else runs unchanged.
set -eu
clang=$1
shift
partitions=${MINYAR_LINK_PARTITIONS:-4}
thin=0 output= largest= largest_size=0
previous=
for arg in "$@"; do
    case $arg in -flto=thin) thin=1 ;; esac
    if [ "$previous" = -o ]; then output=$arg; fi
    case $arg in
        *.ll)
            size=$(wc -c < "$arg" 2>/dev/null || echo 0)
            if [ "$size" -gt "$largest_size" ]; then largest=$arg; largest_size=$size; fi ;;
    esac
    previous=$arg
done
resolved=$(command -v "$clang" 2>/dev/null || printf '%s\n' "$clang")
while [ -h "$resolved" ]; do
    link=$(readlink "$resolved")
    case $link in /*) resolved=$link ;; *) resolved=$(dirname -- "$resolved")/$link ;; esac
done
split=$(dirname -- "$resolved")/llvm-split
if [ "$thin" != 1 ] || [ -z "$output" ] || [ -z "$largest" ] || [ "$partitions" -lt 2 ] || [ ! -x "$split" ]; then
    exec "$clang" "$@"
fi
work=$(mktemp -d "$output.parts.XXXXXXXX")
trap 'rm -rf -- "$work"' 0
"$split" -j "$partitions" "$largest" -o "$work/part"
# Prelink each module with the rule's compile options (everything but inputs, the output and link-only options).
compile_options=
previous=
for arg in "$@"; do
    case $previous in -o|-Xlinker) previous=$arg; continue ;; esac
    case $arg in
        -o|-Xlinker) ;;
        *.ll|*.o|*.a|*.bc|-l*|-L*|-Wl,*|-fuse-ld=*|-pthread|-static|-shared) ;;
        *) compile_options="$compile_options $(printf "'%s'" "$(printf '%s' "$arg" | sed "s/'/'\\\\''/g")")" ;;
    esac
    previous=$arg
done
index=0
pids=
while [ "$index" -lt "$partitions" ]; do
    eval "\"\$clang\" $compile_options -c -x ir \"\$work/part$index\" -o \"\$work/part$index.bc\"" &
    pids="$pids $!"
    index=$((index + 1))
done
for pid in $pids; do wait "$pid"; done
# The link itself: the same arguments with the split modules in place of the largest input.
# -flto-jobs reaches lld as --thinlto-jobs and Apple's ld as -mllvm -threads.
set -- "$@" "-flto-jobs=$partitions"
count=$#
index=0
while [ "$index" -lt "$count" ]; do
    arg=$1
    shift
    if [ "$arg" = "$largest" ]; then
        part=0
        while [ "$part" -lt "$partitions" ]; do set -- "$@" "$work/part$part.bc"; part=$((part + 1)); done
    else
        set -- "$@" "$arg"
    fi
    index=$((index + 1))
done
"$clang" "$@"
