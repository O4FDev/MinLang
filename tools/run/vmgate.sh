#!/bin/sh
# vmgate.sh REF REPO LOGFILE CHECKS...: inside the gate VM, run CHECKS (default check-portable) of REF, fetched from
# REPO, in one warm tree ($HOME/gate-run). The log's first line names the commit so the train can refuse a stale
# log. Toolchains come from $HOME/.cache/minyar/toolchains (the tree bootstraps them on first use).
set -u
ref=$1; repo=$2; log=$3; shift 3; checks=${*:-check-portable}
mirror="$HOME/minyar"; tree="$HOME/gate-run"
for bin in "$HOME"/.cache/minyar/toolchains/llvm-*/bin "$HOME/go-sdk/go/bin"; do [ -d "$bin" ] && PATH="$bin:$PATH"; done
export PATH
exec 9>"$HOME/gate.lock"; flock 9
[ -d "$mirror/.git" ] || git clone -q "$repo" "$mirror" || exit 2
cd "$mirror" && git fetch -q "$repo" "$ref" && sha=$(git rev-parse FETCH_HEAD) || exit 2
[ -d "$tree" ] || git worktree add -q --detach "$tree" "$sha" || exit 2
cd "$tree" && { git checkout -q -f --detach "$sha" || { echo "checkout failed" >&2; exit 2; }; }
echo "gate $sha checks: $checks" > "$log"
make check-in-parallel CHECKS="$checks" CHECK_JOBS="${MINYAR_GATE_JOBS:-6}" >> "$log" 2>&1 9>&-
echo "GATE-EXIT $?" >> "$log"
