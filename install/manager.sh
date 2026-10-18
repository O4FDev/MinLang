#!/bin/sh
# Managed by Minyar toolchains (v1)
set -eu
minyar_home=${MINYAR_HOME:-${HOME:?HOME must be set}/.minyar}
if [ -d "$minyar_home" ]; then minyar_home=$(CDPATH= cd -- "$minyar_home" && pwd -P); fi
MINYAR_HOME=$minyar_home
export MINYAR_HOME
die() { printf 'minyar: %s\n' "$*" >&2; exit 1; }
valid_version() {
    [ "${#1}" -le 80 ] || return 1
    case "$1" in ''|*[!0-9A-Za-z.+-]*|*..*) return 1 ;; esac
    awk -v version="$1" 'BEGIN { exit !(version ~ /^[0-9]+\.[0-9]+\.[0-9]+([+-][0-9A-Za-z.-]+)?$/) }'
}
installed() {
    valid_version "$1" && [ ! -L "$minyar_home/toolchains/$1" ] && [ -f "$minyar_home/toolchains/$1/.minyar-toolchain" ] && [ "$(cat -- "$minyar_home/toolchains/$1/.minyar-toolchain")" = "$1" ] && [ -x "$minyar_home/toolchains/$1/minyar" ]
}
default_version() {
    [ -f "$minyar_home/default" ] || die 'no default toolchain is installed; run the verified Minyar installer first'
    default=$(cat -- "$minyar_home/default")
    installed "$default" || die "default toolchain is unavailable: $default; reinstall it with minyar toolchain install $default"
}
installer() {
    if [ -z "${MINYAR_DIST_URL:-}" ] && [ -f "$minyar_home/server" ]; then
        MINYAR_DIST_URL=$(cat -- "$minyar_home/server")
        export MINYAR_DIST_URL
    fi
    if [ -f "$minyar_home/release-key.pub" ]; then
        MINYAR_TRUSTED_KEY=$minyar_home/release-key.pub
        export MINYAR_TRUSTED_KEY
    fi
    if [ -f "$minyar_home/default" ]; then
        default_version
        installer_path=$minyar_home/toolchains/$default/install/install.sh
    else
        installer_path=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)/install.sh
    fi
    [ -f "$installer_path" ] || die 'the installed toolchain is missing its verified installer; reinstall Minyar'
}
select_version() {
    selected=${MINYAR_TOOLCHAIN:-}
    reason=MINYAR_TOOLCHAIN
    if [ -z "$selected" ]; then
        directory=$(pwd -P)
        while :; do
            if [ -f "$directory/minyar-toolchain" ]; then
                selected=$(cat -- "$directory/minyar-toolchain")
                reason=$directory/minyar-toolchain
                break
            fi
            [ "$directory" != / ] || break
            directory=${directory%/*}
            [ -n "$directory" ] || directory=/
        done
    fi
    if [ -z "$selected" ]; then default_version; selected=$default; reason=default; fi
    valid_version "$selected" || die "$reason must contain one toolchain version, for example 0.1.0"
    installed "$selected" || die "this project needs toolchain $selected; run minyar toolchain install $selected"
}
case "${1-}" in
    toolchain)
        shift
        case "${1-}" in
            list)
                [ "$#" -eq 1 ] || die 'usage: minyar toolchain list'
                found=0
                for path in "$minyar_home"/toolchains/*; do
                    version=${path##*/}
                    if installed "$version"; then
                        suffix=
                        if [ -f "$minyar_home/default" ] && [ "$(cat -- "$minyar_home/default")" = "$version" ]; then suffix=' (default)'; fi
                        printf '%s%s\n' "$version" "$suffix"
                        found=1
                    fi
                done
                [ "$found" -eq 1 ] || printf 'No toolchains installed.\n'
                exit 0 ;;
            current)
                [ "$#" -eq 1 ] || die 'usage: minyar toolchain current'
                select_version
                printf '%s (%s)\n' "$selected" "$reason"
                exit 0 ;;
            install)
                [ "$#" -eq 2 ] && valid_version "$2" || die 'usage: minyar toolchain install VERSION'
                if installed "$2"; then printf 'Installed  Minyar %s (already available)\n' "$2"; exit 0; fi
                installer
                exec sh "$installer_path" --version "$2" --no-default ;;
            default)
                [ "$#" -eq 2 ] && installed "$2" || die 'usage: minyar toolchain default INSTALLED_VERSION'
                [ ! -L "$minyar_home/default" ] || die 'refusing to replace a symlinked default file'
                printf '%s\n' "$2" > "$minyar_home/.default-$$"
                mv -f -- "$minyar_home/.default-$$" "$minyar_home/default"
                printf 'Default  Minyar %s\n' "$2"
                exit 0 ;;
            *) die 'usage: minyar toolchain install VERSION | list | current | default VERSION' ;;
        esac ;;
    self)
        [ "$#" -eq 2 ] && [ "$2" = update ] || die 'usage: minyar self update'
        installer
        exec sh "$installer_path" ;;
esac
select_version
MINYAR_TOOLCHAIN_ACTIVE=$selected
export MINYAR_TOOLCHAIN_ACTIVE
exec "$minyar_home/toolchains/$selected/minyar" "$@"
