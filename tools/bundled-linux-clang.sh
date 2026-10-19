#!/bin/sh
set -eu
minyar_bin=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LD_LIBRARY_PATH=$minyar_bin/../lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LD_LIBRARY_PATH
for minyar_argument in "$@"; do
    case "$minyar_argument" in
        -print-prog-name=ld.lld) printf '%s/ld.lld\n' "$minyar_bin"; exit 0 ;;
        -c|-S|-E|-M|-MM|-fsyntax-only|--version|-print-*|--print-*|-dumpmachine|-dumpversion)
            exec "$minyar_bin/../libexec/clang" "$@" ;;
    esac
done
exec "$minyar_bin/../libexec/clang" "--ld-path=$minyar_bin/ld.lld" "$@"
