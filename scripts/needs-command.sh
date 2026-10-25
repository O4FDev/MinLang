#!/bin/sh
# needs-command.sh TOOL TARGET WHY COMMAND... — run COMMAND only when TOOL is on PATH.
# Without TOOL, print one SKIP line naming the target, the missing tool and why it is needed, and succeed, so a lab
# that drives a real third-party server skips instead of failing on hosts that lack that server.
# MINYAR_REQUIRE_LAB_TOOLS=1 turns the skip into a failure (hosts that are expected to run every lab).
set -eu
tool=$1 target=$2 why=$3
shift 3
if command -v "$tool" >/dev/null 2>&1; then exec "$@"; fi
if [ "${MINYAR_REQUIRE_LAB_TOOLS:-0}" = 1 ]; then
    echo "FAIL $target: $tool is not on PATH and MINYAR_REQUIRE_LAB_TOOLS=1; $why" >&2
    exit 1
fi
echo "SKIP $target: $tool is not on PATH; $why"
