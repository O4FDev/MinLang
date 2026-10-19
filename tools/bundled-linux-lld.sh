#!/bin/sh
set -eu
minyar_bin=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LD_LIBRARY_PATH=$minyar_bin/../lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LD_LIBRARY_PATH
exec "$minyar_bin/../libexec/ld.lld" "$@"
