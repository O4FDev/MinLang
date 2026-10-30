#!/bin/sh
# Micro-measures for reports/serial-and-parallel.md (Linux, valgrind on PATH):
# thread-share.min (copying a List into threads vs FrozenBytes; a typed channel
# vs local calls) and parallel-dispatch.min (one small parallel for). Run from
# the repository root after building build/minyarc.
set -eu
out=build/bothmodes-variants/micro
mkdir -p "$out"
./minyar --release benchmarks/bothmodes/variants/thread-share.min -o "$out/thread-share" > "$out/thread-share.log"
./minyar --release benchmarks/bothmodes/variants/parallel-dispatch.min -o "$out/parallel-dispatch" > "$out/parallel-dispatch.log"
ir() { valgrind --tool=cachegrind --cache-sim=no --cachegrind-out-file=/dev/null "$@" 2>&1 >/dev/null | sed -n 's/.*I *refs: *//p'; }
for n in 1000000 4000000; do
    for mode in copy frozen channel local; do
        printf 'thread-share %-8s n=%-8s Ir %s\n' "$mode" "$n" "$(ir "$out/thread-share" "$mode" "$n")"
    done
done
for t in 1 4; do
    for r in 10000 20000; do
        printf 'parallel-dispatch threads=%s rounds=%s Ir %s\n' "$t" "$r" "$(MINYAR_PARALLEL_THREADS=$t ir "$out/parallel-dispatch" "$r")"
    done
done
for t in 1 2 4; do
    for i in 1 2 3; do
        printf 'parallel-dispatch threads=%s wall: %s\n' "$t" "$(MINYAR_PARALLEL_THREADS=$t "$out/parallel-dispatch" 200000 | tail -1)"
    done
done
