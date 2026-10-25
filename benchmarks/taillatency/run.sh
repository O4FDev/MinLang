#!/bin/bash
# Build every variant and run them in alternating rounds. Usage: run.sh [rounds]
# Run from the repository root on a Linux host with rustc and go on PATH.
set -eu
rounds=${1:-5}
here=benchmarks/taillatency
out=${TAIL_OUT:-build/taillatency}
mkdir -p "$out"
native=(--native-source "tailidle=$here/idle.c")
./minyar --release "${native[@]}" "$here/cache.min" -o "$out/minyar-k32"
./minyar --release --memory-profile eager "${native[@]}" "$here/cache.min" -o "$out/minyar-eager"
./minyar --release --cleanup-budget 1024 "${native[@]}" "$here/cache.min" -o "$out/minyar-k1024"
rustc -C opt-level=3 -C codegen-units=1 "$here/cache.rs" -o "$out/rust"
(cd "$here" && GOFLAGS=-buildvcs=false go build -o "$OLDPWD/$out/go" cache.go)
variants=${TAIL_VARIANTS:-"minyar-k32 minyar-eager minyar-k1024 rust go"}
for round in $(seq 1 "$rounds"); do
  for v in $variants; do
    printf 'round=%s variant=%s ' "$round" "$v"
    case $v in
      minyar-k32-idle) TAIL_IDLE=1 taskset -c 2,3 "$out/minyar-k32" ;;
      minyar-k1024-idle) TAIL_IDLE=1 taskset -c 2,3 "$out/minyar-k1024" ;;
      rust-defer) TAIL_DEFER=1 taskset -c 2,3 "$out/rust" ;;
      *) taskset -c 2,3 "$out/$v" ;;
    esac
  done
done
