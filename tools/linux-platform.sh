#!/bin/sh
# Diagnose the platform before starting any packaged ELF executable.
set -eu
minyar_root=$1
minyar_fail() { printf 'minyar: %s\n' "$1" >&2; exit 1; }
[ "$(uname -s)" = Linux ] || minyar_fail 'this distribution requires Linux'
minyar_arch=$(uname -m)
case "$minyar_arch" in aarch64) minyar_arch=arm64 ;; amd64) minyar_arch=x86_64 ;; esac
minyar_packaged_arch=$(cat "$minyar_root/distribution.arch")
[ "$minyar_arch" = "$minyar_packaged_arch" ] || minyar_fail "download the $minyar_arch distribution; this one is for $minyar_packaged_arch"
minyar_required=$(cat "$minyar_root/distribution.libc")
minyar_libc=$(getconf GNU_LIBC_VERSION 2>/dev/null) || minyar_fail 'this distribution requires glibc; musl Linux needs a separate toolchain'
case "$minyar_libc" in 'glibc '*) minyar_libc=${minyar_libc#glibc } ;; *) minyar_fail 'cannot identify the installed glibc version' ;; esac
awk -v required="$minyar_required" -v actual="$minyar_libc" 'BEGIN {
    if (required !~ /^[0-9]+\.[0-9]+$/ || actual !~ /^[0-9]+\.[0-9]+$/) exit 2
    split(required, r, "."); split(actual, a, ".")
    exit !(a[1] > r[1] || (a[1] == r[1] && a[2] >= r[2]))
}' || minyar_fail "this distribution requires glibc $minyar_required or newer (found $minyar_libc)"
if ! "$minyar_root/toolchain/bin/clang" --version >/dev/null; then
    minyar_fail 'bundled LLVM cannot start; on Ubuntu 24.04 install its runtime prerequisites:
  sudo apt install build-essential libffi8 libedit2 libz3-4 zlib1g libzstd1 libxml2
Then repeat this command. Other Linux releases need the runtime libraries listed in docs/linux-distribution.md.'
fi
