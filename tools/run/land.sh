#!/bin/sh
# land.sh LANE: run from your lane worktree with everything committed. Queues your branch head on the merge train
# (tools/run/train.py), which stacks every queued lane on the run branch, gates the stack once and fast-forwards and
# pushes on green. Prints LAND-GREEN or LAND-RED with the reason. Run it in the background; never poll it.
set -u
lane=${1:?usage: land.sh LANE}; C=${MINYAR_RUN_DIR:?set MINYAR_RUN_DIR}
branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = "${MINYAR_RUN_BRANCH:-v2}" ] && { echo "LAND-RED: run from your lane branch, not $branch"; exit 2; }
[ -n "$(git status --porcelain)" ] && { echo "LAND-RED: uncommitted changes"; exit 2; }
id="$(date +%s)-$lane"; sha=$(git rev-parse HEAD)
echo "$lane $sha" > "$C/queue/$id.tmp" && mv "$C/queue/$id.tmp" "$C/queue/$id.req"
echo "queued $id ($sha); result: $C/queue/done/$id.res"
while [ ! -f "$C/queue/done/$id.res" ]; do sleep 10; done
cat "$C/queue/done/$id.res"
grep -q '^LAND-GREEN' "$C/queue/done/$id.res"
