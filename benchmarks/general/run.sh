#!/bin/bash
# General benchmark set: Minyar (release) vs C (clang -O2) on the same host.
#   benchmarks/general/run.sh [OUT_DIR] [REPEATS] [WORKLOAD...]
# Builds everything, checks that each Minyar program prints exactly what its C
# reference prints, then alternates C and Minyar runs and reports the median
# retired user instructions and wall time of each, and their ratio.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-build/general}; repeats=${2:-3}; shift 2 2>/dev/null || shift $#
mkdir -p "$out"
CC=${CC:-clang}
MINYAR=${MINYAR:-minyar}
workloads=("$@")
(( ${#workloads[@]} )) || workloads=(wordfreq logstats orders service matrix nbody)
"$CC" -O2 "$here/gen.c" -o "$out/gen"
[[ -s "$out/words.txt" ]] || "$out/gen" words 50000000 > "$out/words.txt"
[[ -s "$out/log.csv" ]] || "$out/gen" log 1000000 > "$out/log.csv"
input() { case $1 in wordfreq) echo "$out/words.txt" ;; logstats) echo "$out/log.csv" ;; esac; }
measure() { # measure FILE command... → appends "instructions wall_ms" to FILE
  local stat; stat=$(mktemp)
  perf stat -x, -e instructions:u -o "$stat" "$@" > /dev/null
  local ins; ins=$(awk -F, '/instructions/ {print $1}' "$stat")
  local wall; wall=$(awk '/seconds time elapsed/ {print $1}' "$stat" 2>/dev/null || true)
  rm -f "$stat"
  echo "$ins" >> "$1.ins"
}
median() { sort -n "$1" | awk '{a[NR]=$1} END {print a[int((NR+1)/2)]}'; }
printf '%-10s %14s %14s %8s %10s %10s %8s\n' workload c_instr minyar_instr ratio c_ms minyar_ms ratio
for w in "${workloads[@]}"; do
  "$CC" -O2 "$here/$w.c" -lm -o "$out/$w-c"
  "$MINYAR" --release "$here/$w.min" -o "$out/$w-minyar" > "$out/$w-build.log" 2>&1 || { echo "$w: minyar build failed"; tail -20 "$out/$w-build.log"; continue; }
  arg=$(input "$w")
  "$out/$w-c" $arg > "$out/$w-c.out"
  "$out/$w-minyar" $arg > "$out/$w-minyar.out"
  cmp -s "$out/$w-c.out" "$out/$w-minyar.out" || { echo "$w: OUTPUT DIFFERS"; diff "$out/$w-c.out" "$out/$w-minyar.out" | head; continue; }
  rm -f "$out/$w-"{c,minyar}.{ins,ms}
  for r in $(seq "$repeats"); do
    for side in c minyar; do
      s=$(mktemp)
      perf stat -x, -e instructions:u,task-clock -o "$s" "$out/$w-$side" $arg > /dev/null
      awk -F, '/instructions/ {print $1}' "$s" >> "$out/$w-$side.ins"
      awk -F, '/task-clock/ {print $1}' "$s" >> "$out/$w-$side.ms"
      rm -f "$s"
    done
  done
  ci=$(median "$out/$w-c.ins"); mi=$(median "$out/$w-minyar.ins")
  cm=$(median "$out/$w-c.ms"); mm=$(median "$out/$w-minyar.ms")
  printf '%-10s %14s %14s %8.2f %10.1f %10.1f %8.2f\n' "$w" "$ci" "$mi" "$(echo "$mi / $ci" | bc -l)" "$cm" "$mm" "$(echo "$mm / $cm" | bc -l)"
done
