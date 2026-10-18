#!/bin/sh
# Check without executing a Mach-O binary, so unsupported Macs get a useful error.
set -eu
minyar_root=$1
minyar_fail() { printf 'minyar: %s\n' "$1" >&2; exit 1; }
[ "$(/usr/bin/uname -s)" = Darwin ] || minyar_fail 'this distribution requires macOS'
minyar_os=$(/usr/bin/sw_vers -productVersion)
minyar_major=${minyar_os%%.*}
case "$minyar_major" in ''|*[!0-9]*) minyar_fail "cannot identify macOS version: $minyar_os" ;; esac
[ "$minyar_major" -ge 14 ] || minyar_fail "this distribution requires macOS 14 or newer (found $minyar_os)"
minyar_arch=$(/usr/bin/uname -m)
if [ "$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || :)" = 1 ]; then minyar_arch=arm64; fi
minyar_packaged_arch=$(cat "$minyar_root/distribution.arch")
[ "$minyar_arch" = "$minyar_packaged_arch" ] || minyar_fail "download the $minyar_arch distribution; this one is for $minyar_packaged_arch"
