#!/bin/sh
# start.sh RUN_DIR [GOAL]: lay out an overnight run (docs/overnight-runs.md). Creates RUN_DIR with the charter, the
# queue, locks, logs, reports, the train worktree and thin wrappers (heavy, light, land.sh, tick.sh) that lanes call
# as $C/heavy etc. Prints the two commands that start the base gate and the train. Settings come from the
# environment: MINYAR_RUN_BRANCH (v2), MINYAR_GATE_VM (rpcgate), MINYAR_HEAVY_SLOTS, MINYAR_LIGHT_SLOTS (3 each),
# MINYAR_RUN_SDKROOT / MINYAR_RUN_MACOSX_DEPLOYMENT_TARGET / MINYAR_RUN_LINK_PARTITIONS for local macOS builds.
set -eu
run=${1:?usage: start.sh RUN_DIR [GOAL]}; goal=${2:-see the lane briefs.}
tools=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd); repo=$(git -C "$tools" rev-parse --show-toplevel)
branch=${MINYAR_RUN_BRANCH:-v2}
[ -e "$run/env" ] && { echo "start.sh: $run already holds a run" >&2; exit 2; }
mkdir -p "$run/queue/done" "$run/locks" "$run/logs" "$run/reports" "$run/gate"
run=$(CDPATH= cd -- "$run" && pwd)
{
    echo "MINYAR_RUN_DIR=$run"; echo "MINYAR_RUN_REPO=$repo"; echo "MINYAR_RUN_BRANCH=$branch"
    echo "MINYAR_GATE_VM=${MINYAR_GATE_VM:-rpcgate}"
    for key in MINYAR_HEAVY_SLOTS MINYAR_LIGHT_SLOTS MINYAR_RUN_SDKROOT MINYAR_RUN_MACOSX_DEPLOYMENT_TARGET MINYAR_RUN_LINK_PARTITIONS; do
        eval "value=\${$key-}"; [ -n "$value" ] && echo "$key=$value"
    done
} > "$run/env"
for tool in heavy light land.sh tick.sh; do
    printf '#!/bin/sh\nset -a; . "%s/env"; set +a\nexec "%s/%s" "$@"\n' "$run" "$tools" "$tool" > "$run/$tool"
    chmod +x "$run/$tool"
done
git -C "$repo" worktree add -q --detach "$run/train" "$branch"
: > "$run/LANDED"; : > "$run/reports/cross-lane.md"
sed -e "s|@RUN_NAME@|$(basename "$run")|; s|@RUN_DIR@|$run|; s|@REPO@|$repo|; s|@BRANCH@|$branch|g" \
    -e "s|@GOAL@|$goal|; s|@END@|the time in your brief|; s|@FIRST_LAND@|the time in your brief|; s|@LAST_LAND@|the time in your brief|" \
    "$tools/charter-template.md" > "$run/CHARTER.md"
cat <<MSG
Run laid out in $run. Edit $run/CHARTER.md (goal, end and landing times), then:
  python3 $tools/train.py $run --base              # gate $branch once: base.fail, base.ready
  nohup python3 $tools/train.py $run > $run/logs/train.out 2>&1 &
Lanes: C=$run; \$C/heavy, \$C/light, \$C/land.sh LANE. Orchestrator: \$C/tick.sh.
MSG
