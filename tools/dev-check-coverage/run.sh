#!/bin/sh
# Instrumented gate for the dev-check function index (docs/dev-check.md). Run on the warm base tree, then
# `python3 tools/dev-check.py coverage --data build/dev-check/cov/data --results build/dev-check/cov/gate.log ...`.
# Usage: sh tools/dev-check-coverage/run.sh [jobs]
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
jobs=${1:-6}
real=${LLVM_CC:-$(sh tools/toolchain.sh default-clang)}
real_make=$(command -v make)
c=$root/build/dev-check/cov
rm -rf "$c"; mkdir -p "$c/bin" "$c/data/_lost" "$c/data/_build" "$c/data/_top"
cp tools/dev-check-coverage/clang tools/dev-check-coverage/make "$c/bin/"
sed -i.bak "s|exec /usr/bin/make|exec $real_make|" "$c/bin/make" && rm -f "$c/bin/make.bak"
"$real" -O2 -fPIC -c tools/dev-check-coverage/covexit.c -o "$c/bin/covexit.o"
python3 -c 'import json,os,sys; [os.makedirs(sys.argv[2]+"/"+n, exist_ok=True) for n in json.load(open(sys.argv[1]))["checks"]]' \
    build/dev-check/index.json "$c/data"
export DEVCHECK_REAL_CLANG="$real" DEVCHECK_COV_DATA="$c/data" PATH="$c/bin:$PATH" LLVM_CC="$c/bin/clang" MINYAR_CLANG="$c/bin/clang"
export LLVM_PROFILE_FILE="$c/data/_build/%p.profraw"
# Rebuild every compiler, runtime object and program so each is instrumented or carries the profile runtime.
find build -maxdepth 1 -type f -perm -u+x ! -name '*.*' > "$c/prebuild.list"
find build -name '*.o' \( -path '*runtime*' -o -path 'build/testing/*' \) ! -path 'build/thinlto-cache/*' ! -path 'build/dev-check/*' >> "$c/prebuild.list"
find build/tooling -type f -perm -u+x ! -name '*.*' >> "$c/prebuild.list"
xargs rm -f < "$c/prebuild.list"
"$real_make" -s --no-print-directory -k $(make -pnq FORCE 2>/dev/null | sed -n 's/^\(build\/[^ :%]*\):.*/\1/p' | grep -Fx -f "$c/prebuild.list" | tr '\n' ' ') > "$c/prebuild.log" 2>&1 || true
export LLVM_PROFILE_FILE="$c/data/_top/%p.profraw"
"$real_make" --no-print-directory check-in-parallel CHECKS=check-portable CHECK_JOBS="$jobs" > "$c/gate.log" 2>&1 || true
echo "coverage gate finished; results in $c/gate.log"
