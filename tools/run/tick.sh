#!/bin/sh
# tick.sh: one screen of run state for the orchestrator: load, run branch, landings, lane STATUS lines, top CPU.
C=${MINYAR_RUN_DIR:?set MINYAR_RUN_DIR}; . "$C/env"; cd "$MINYAR_RUN_REPO" || exit 1
echo "== $(date '+%H:%M') load $(uptime | sed 's/.*averages*: //') free-disk $(df -h / | awk 'END{print $4}')"
echo "== $MINYAR_RUN_BRANCH $(git rev-parse --short "$MINYAR_RUN_BRANCH") origin $(git rev-parse --short "origin/$MINYAR_RUN_BRANCH") landed $(wc -l < "$C/LANDED" 2>/dev/null)"
tail -5 "$C/LANDED" 2>/dev/null; tail -3 "$C/logs/train.log" 2>/dev/null | cut -c1-160
echo "== queue: $(ls "$C"/queue/*.req 2>/dev/null | wc -l | tr -d ' ') waiting"
echo "== reports (mtime, lines, STATUS)"
for f in "$C"/reports/*.md; do [ -f "$f" ] && printf '%s %s %4s  %s\n' "$(date -r "$f" +%H:%M)" "$(basename "$f" .md)" "$(wc -l < "$f" | tr -d ' ')" "$(grep -m1 '^STATUS' "$f" | cut -c1-140)"; done
echo "== top cpu"; ps -Ao pcpu,rss,etime,comm -r 2>/dev/null | head -8
