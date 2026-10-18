#!/bin/sh
# This file is shipped as install.sh at the root of a binary distribution.
set -eu
PATH="${PATH:-/usr/bin:/bin}:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
minyar_source=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
minyar_prefix=${HOME:?HOME must be set}/.local
minyar_modify_path=1
minyar_check=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix) [ "$#" -ge 2 ] || { echo '--prefix requires a directory' >&2; exit 2; }; minyar_prefix=$2; shift 2 ;;
        --no-modify-path) minyar_modify_path=0; shift ;;
        --check) minyar_check=1; shift ;;
        --help|-h) echo 'usage: sh install.sh [--prefix DIRECTORY] [--no-modify-path] [--check]'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
sh "$minyar_source/tools/macos-platform.sh" "$minyar_source"
case "$minyar_prefix" in /*) ;; *) minyar_prefix=$PWD/$minyar_prefix ;; esac
# Shell startup files are line-oriented; reject control characters in the prefix.
minyar_cr=$(printf '\r')
case "$minyar_prefix" in *'
'*|*"$minyar_cr"*) echo 'installation paths must not contain newlines' >&2; exit 2 ;; esac
minyar_sdk=${SDKROOT-}
if [ -z "$minyar_sdk" ]; then minyar_sdk=$(/usr/bin/xcrun --show-sdk-path 2>/dev/null || :); fi
if [ ! -f "$minyar_sdk/usr/include/stdio.h" ] || [ ! -d "$minyar_sdk/System/Library/Frameworks" ]; then
    printf '%s\n' 'Minyar needs the Apple macOS SDK. Install the Command Line Tools, then run this installer again.' >&2
    if [ "$minyar_check" = 0 ]; then /usr/bin/xcode-select --install || :; fi
    printf '%s\n' 'If developer tools are already installed, check SDKROOT, DEVELOPER_DIR and xcode-select --print-path.' >&2
    exit 2
fi
SDKROOT=$minyar_sdk
export SDKROOT
"$minyar_source/minyar" --doctor
if [ "$minyar_check" = 1 ]; then exit 0; fi
# Prove the ordinary project workflow before publishing or changing the shell.
minyar_work=$(mktemp -d "${TMPDIR:-/tmp}/minyar-install.XXXXXXXX")
trap 'rm -rf -- "$minyar_work"' 0
trap 'exit 1' HUP INT TERM
"$minyar_source/minyar" new "$minyar_work/hello"
(cd "$minyar_work/hello" && "$minyar_source/minyar" run && "$minyar_source/minyar" test && "$minyar_source/minyar" build --release)
"$minyar_source/build/tooling/tools/install-cli" --source "$minyar_source" --prefix "$minyar_prefix"
if [ "$minyar_modify_path" = 1 ]; then
    # Quote literal paths, including spaces and apostrophes, for POSIX shells.
    minyar_quoted=$(printf '%s' "$minyar_prefix/bin" | sed "s/'/'\\\\''/g")
    minyar_env="$minyar_prefix/lib/minyar/env"
    minyar_env_staged=$(mktemp "$minyar_env.XXXXXXXX")
    printf 'export PATH='"'"'%s'"'"':"$PATH"\n' "$minyar_quoted" > "$minyar_env_staged"
    mv -f "$minyar_env_staged" "$minyar_env"
    minyar_env_quoted=$(printf '%s' "$minyar_env" | sed "s/'/'\\\\''/g")
    minyar_line=". '$minyar_env_quoted' # Minyar PATH"
    case "${SHELL-}" in
        */zsh) minyar_profile=${ZDOTDIR:-$HOME}/.zshrc ;;
        */bash) minyar_profile=$HOME/.bash_profile ;;
        *) minyar_profile= ;;
    esac
    if [ -n "$minyar_profile" ]; then
        mkdir -p "$(dirname -- "$minyar_profile")"
        if [ ! -f "$minyar_profile" ] || ! grep -Fqx "$minyar_line" "$minyar_profile"; then
            printf '\n%s\n' "$minyar_line" >> "$minyar_profile"
        fi
    fi
    if [ -n "$minyar_profile" ]; then
        printf 'Ready. Open a new terminal, or run:\n  . '\''%s'\''\n' "$minyar_env_quoted"
    else
        printf 'Ready. Add %s/bin to your shell PATH. POSIX shells can run:\n  . '\''%s'\''\n' "$minyar_prefix" "$minyar_env_quoted"
    fi
else
    printf 'Ready. Add %s/bin to PATH.\n' "$minyar_prefix"
fi
