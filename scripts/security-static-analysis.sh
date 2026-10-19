#!/bin/sh
set -eu

compiler=${MINYAR_CLANG:-clang}
scratch=$(mktemp -d "${TMPDIR:-/tmp}/minyar-static-analysis.XXXXXX")
trap 'rm -rf "$scratch"' EXIT HUP INT TERM

set -- --analyze \
    -Xanalyzer -analyzer-checker=core,unix,security \
    -Xanalyzer -analyzer-disable-checker=security.insecureAPI.DeprecatedOrUnsafeBufferHandling \
    -std=c11 -D_GNU_SOURCE -DMINYAR_SYSTEM_HEAP=1 -isystem vendor -o /dev/null
if [ "$(uname -s)" = Darwin ]; then
    sdk=${SDKROOT:-$(xcrun --show-sdk-path)}
    set -- "$@" -isysroot "$sdk"
fi

checked=0
for source in \
    runtime/minyar_runtime.c \
    runtime/native/aes.c \
    runtime/native/deflate.c \
    runtime/native/files.c \
    runtime/native/net.c \
    runtime/native/quicinteropio.c \
    runtime/native/securecrypto.c \
    runtime/native/system.c \
    runtime/native/tlsverify.c \
    runtime/native/update.c \
    runtime/native/update_ed25519.c \
    runtime/native/update_monocypher.c \
    runtime/native/workers.c
do
    log="$scratch/diagnostics"
    if ! "$compiler" "$@" "$source" >"$log" 2>&1; then
        cat "$log" >&2
        echo "Clang analysis failed for $source" >&2
        exit 1
    fi
    if grep -Eq 'warning:|error:' "$log"; then
        cat "$log" >&2
        echo "Clang analysis found diagnostics in $source" >&2
        exit 1
    fi
    checked=$((checked + 1))
done

if [ "$(uname -s)" = Darwin ]; then
    source=runtime/native/http.m
    log="$scratch/diagnostics"
    if ! "$compiler" --analyze \
        -Xanalyzer -analyzer-checker=core,unix,security \
        -Xanalyzer -analyzer-disable-checker=security.insecureAPI.DeprecatedOrUnsafeBufferHandling \
        -fobjc-arc -fblocks -DMINYAR_SYSTEM_HEAP=1 -isystem vendor -isysroot "$sdk" \
        "$source" -o /dev/null >"$log" 2>&1; then
        cat "$log" >&2
        echo "Clang analysis failed for $source" >&2
        exit 1
    fi
    if grep -Eq 'warning:|error:' "$log"; then
        cat "$log" >&2
        echo "Clang analysis found diagnostics in $source" >&2
        exit 1
    fi
    checked=$((checked + 1))
fi

echo "Clang static analysis: $checked native sources clean"
