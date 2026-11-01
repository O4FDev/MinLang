#!/bin/bash
# cache-run.sh RUN SHARDS JOBS: the shard-cache box's part of a fast gate, run as `agent` in /home/agent/fgc/RUN.
# While the shards boot it builds the compiler and the check runner in the gate tree exactly as the single-box gate
# does and plans and packs the full gate (plan.py, pack.py); the shards then copy tree/ (sources and build outputs,
# mtimes kept) and out/assignment.json over the VPC rsync daemon. With FAST_GATE_PREBUILD=1 it first also builds the
# slowest shared builds (prebuild.py); off by default, since the shards that need them build them in the same time.
set -u
run=/home/agent/fgc/$1 shards=$2 jobs=$3
fg=$run/fg out=$run/out
mkdir -p "$out"
stamp() { echo "$(date +%s.%N) $*" >> "$out/status"; }
finish() { stamp "CACHE-DONE $1"; touch "$out/done"; exit "$1"; }
. /etc/profile.d/goal-toolchains.sh
export MINYAR_CLANG=/opt/llvm-23.1.3/bin/clang LLVM_CC=/opt/llvm-23.1.3/bin/clang MINYAR_TEST_TIMEOUT_SCALE=${MINYAR_TEST_TIMEOUT_SCALE:-2}
checks=$(cat "$fg/checks.txt")
cd "$run/tree" || finish 9
stamp START
make build/minyarc > "$out/build.log" 2>&1 || { stamp BUILD-FAILED; finish 3; }
make build/tooling/tools/check-in-parallel >> "$out/build.log" 2>&1 || { stamp RUNNER-BUILD-FAILED; finish 3; }
early=$(python3 "$fg/plan.py" --early . 2>> "$out/build.log")
[[ -n $early ]] && { make $early >> "$out/build.log" 2>&1 || stamp "EARLY-BUILD-FAILED $early"; }
stamp BUILT
python3 "$fg/plan.py" . $checks > "$out/plan.json" 2> "$out/plan.err" || { stamp PLAN-FAILED; finish 4; }
python3 "$fg/pack.py" "$out/plan.json" "$fg/times.tsv" "$fg/goal-times.tsv" "$shards" "$jobs" > "$out/assignment.json" || { stamp PACK-FAILED; finish 4; }
stamp "PLANNED $(sha256sum < "$out/plan.json" | cut -c1-16) $(sha256sum < "$out/assignment.json" | cut -c1-16)"
if [[ ${FAST_GATE_PREBUILD:-0} == 1 ]]; then
  python3 "$fg/prebuild.py" . "$out/plan.json" "$fg/goal-times.tsv" "$(nproc)" "${FAST_GATE_PREBUILD_MS:-8000}" > "$out/prebuild.log" 2>&1
  stamp PREBUILT
fi
finish 0
