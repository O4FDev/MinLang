#!/bin/sh
set -eu
minyar_bin=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Ship a matching linker and debug-symbol tool. Apple's installed linker can be
# too old to read the LLVM bitcode even when its SDK is otherwise usable.
MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-14.0}
export MACOSX_DEPLOYMENT_TARGET
for minyar_argument in "$@"; do
    case "$minyar_argument" in
        -c|-S|-E|-M|-MM|-fsyntax-only|--version|-print-*|--print-*|-dumpmachine|-dumpversion)
            exec "$minyar_bin/clang.bin" "$@" ;;
    esac
done
exec "$minyar_bin/clang.bin" "--ld-path=$minyar_bin/ld64.lld" "$@"
