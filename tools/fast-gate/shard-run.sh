#!/bin/bash
# shard-run.sh TREE INDEX SHARDS JOBS: one shard's part of a fast gate, run as `agent` from /home/agent/fg.
# Builds the compiler and the check runner exactly as the single-box gate does, plans the full gate in this tree
# (plan.py), packs it onto SHARDS shards (pack.py, the same answer on every shard), then runs the tree's own
# `make check-in-parallel` over the full check list with the make shim finishing other shards' checks at once.
# Progress lines go to out/status; results to out/.
set -u
fg=/home/agent/fg
tree=$1 index=$2 shards=$3 jobs=$4
out=$fg/out
mkdir -p "$out"
stamp() { echo "$(date +%s.%N) $*" >> "$out/status"; }
finish() { stamp "SHARD-DONE $1"; exit "$1"; }
. /etc/profile.d/goal-toolchains.sh
export MINYAR_CLANG=/opt/llvm-23.1.3/bin/clang LLVM_CC=/opt/llvm-23.1.3/bin/clang MINYAR_TEST_TIMEOUT_SCALE=${MINYAR_TEST_TIMEOUT_SCALE:-2}
checks=$(cat "$fg/checks.txt")
cd "$tree" || finish 9
stamp START
make build/minyarc > "$out/build.log" 2>&1 || { stamp BUILD-FAILED; finish 3; }
make build/tooling/tools/check-in-parallel >> "$out/build.log" 2>&1 || { stamp RUNNER-BUILD-FAILED; finish 3; }
stamp BUILT
python3 "$fg/plan.py" . $checks > "$out/plan.json" 2> "$out/plan.err" || { stamp PLAN-FAILED; finish 4; }
python3 "$fg/pack.py" "$out/plan.json" "$fg/times.tsv" "$fg/goal-times.tsv" "$shards" "$jobs" > "$out/assignment.json" || { stamp PACK-FAILED; finish 4; }
python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["assignment"][int(sys.argv[2])]; open(sys.argv[3],"w").write("".join(x+"\n" for x in a["skip"]))' \
  "$out/assignment.json" "$index" "$out/skip.txt" || finish 4
stamp "PLANNED $(sha256sum < "$out/plan.json" | cut -c1-16) $(sha256sum < "$out/assignment.json" | cut -c1-16)"
PATH=$fg/shim:$PATH FAST_GATE_SKIP=$out/skip.txt FAST_GATE_ROOT=$(pwd -P) \
  make check-in-parallel CHECKS="$checks" CHECK_JOBS="$jobs" > "$out/gate.log" 2>&1
status=$?
stamp "GATE-EXIT $status"
run=$(ls -d build/check-in-parallel/run-* 2>/dev/null | tail -1)
[[ -n $run ]] && cp "$run/times.tsv" "$run/results.json" "$out/" 2>/dev/null
# Keep the logs of this shard's failed checks for the report.
if [[ -f $out/results.json ]]; then
  python3 - "$out/results.json" "$out/skip.txt" "$out/failed-logs" <<'EOF'
import json, os, shutil, sys
results = json.load(open(sys.argv[1])); skip = set(open(sys.argv[2]).read().split("\n")); os.makedirs(sys.argv[3], exist_ok=True)
for check in results["checks"]:
    if not check["passed"] and check["target"] not in skip and check["log"]:
        for suffix in ("", ".err"):
            if os.path.exists(check["log"] + suffix):
                shutil.copy(check["log"] + suffix, os.path.join(sys.argv[3], check["target"] + (suffix or ".log")))
EOF
fi
finish 0
