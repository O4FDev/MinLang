#!/bin/sh
# usage: run.sh file.min [extra minyar flags]  -> compiles with --release in the gaps worktree and runs
f=$1; shift
W=/Users/luke/Projects/minyar-goal-20261030/wt/gaps
R=/Users/luke/Projects/minyar-goal-20261030/reports/gaps-repros
b=$R/bin/$(basename "$f" .min)
mkdir -p "$R/bin"
cd "$W" || exit 1
echo "--- compile $f $*"
./minyar --release "$@" "$R/$f" -o "$b" 2>&1 | head -30
[ -x "$b" ] || { echo "--- (no binary)"; exit 0; }
echo "--- run"
( cd /tmp && timeout 60 "$b" 2>&1 | head -30; echo "--- exit $?" )
