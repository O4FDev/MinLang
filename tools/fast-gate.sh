#!/bin/sh
# fast-gate.sh TREE [--shards N] [--jobs N] ...: Minyar's full gate for TREE on on-demand shard boxes (tools/fast-gate).
exec python3 "$(dirname "$0")/fast-gate/fast_gate.py" "$@"
