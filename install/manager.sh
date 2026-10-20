#!/bin/sh
# Managed by Minyar toolchains (v1)
set -eu
minyar_home=${MINYAR_HOME:-${HOME:?HOME must be set}/.minyar}
if [ -d "$minyar_home" ]; then minyar_home=$(CDPATH= cd -- "$minyar_home" && pwd -P); fi
MINYAR_HOME=$minyar_home
export MINYAR_HOME
lock=
die() { printf 'minyar: %s\n' "$*" >&2; exit 1; }
cleanup() { [ -z "$lock" ] || rmdir -- "$lock" 2>/dev/null || :; }
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
valid_version() {
    [ "${#1}" -le 80 ] || return 1
    case "$1" in ''|*[!0-9A-Za-z.+-]*|*..*) return 1 ;; esac
    awk -v version="$1" 'BEGIN { exit !(version ~ /^[0-9]+\.[0-9]+\.[0-9]+([+-][0-9A-Za-z.-]+)?$/) }'
}
version_less_than() {
    LC_ALL=C awk -v left="$1" -v right="$2" '
        function number_compare(a, b, aa, bb) {
            aa = a; bb = b
            sub(/^0+/, "", aa); sub(/^0+/, "", bb)
            if (aa == "") aa = "0"
            if (bb == "") bb = "0"
            if (length(aa) != length(bb)) return length(aa) < length(bb) ? -1 : 1
            if (aa == bb) return 0
            return ("x" aa < "x" bb) ? -1 : 1
        }
        function identifier_compare(a, b, a_number, b_number) {
            a_number = a ~ /^[0-9]+$/
            b_number = b ~ /^[0-9]+$/
            if (a_number && b_number) return number_compare(a, b)
            if (a_number != b_number) return a_number ? -1 : 1
            if (a == b) return 0
            return ("x" a < "x" b) ? -1 : 1
        }
        function version_compare(a, b, a_core, b_core, a_pre, b_pre, a_count, b_count, count, i, result) {
            sub(/\+.*/, "", a); sub(/\+.*/, "", b)
            a_core = a; b_core = b
            sub(/-.*/, "", a_core); sub(/-.*/, "", b_core)
            split(a_core, left_core, "."); split(b_core, right_core, ".")
            for (i = 1; i <= 3; i++) {
                result = number_compare(left_core[i], right_core[i])
                if (result != 0) return result
            }
            a_pre = index(a, "-") ? substr(a, index(a, "-") + 1) : ""
            b_pre = index(b, "-") ? substr(b, index(b, "-") + 1) : ""
            if (a_pre == "" || b_pre == "") {
                if (a_pre == b_pre) return 0
                return a_pre == "" ? 1 : -1
            }
            a_count = split(a_pre, left_pre, "."); b_count = split(b_pre, right_pre, ".")
            count = a_count < b_count ? a_count : b_count
            for (i = 1; i <= count; i++) {
                result = identifier_compare(left_pre[i], right_pre[i])
                if (result != 0) return result
            }
            if (a_count == b_count) return 0
            return a_count < b_count ? -1 : 1
        }
        BEGIN { exit version_compare(left, right) < 0 ? 0 : 1 }
    '
}
installed() {
    valid_version "$1" && [ ! -L "$minyar_home/toolchains/$1" ] && [ -f "$minyar_home/toolchains/$1/.minyar-toolchain" ] && [ "$(cat -- "$minyar_home/toolchains/$1/.minyar-toolchain")" = "$1" ] && [ -x "$minyar_home/toolchains/$1/minyar" ]
}
default_version() {
    [ -f "$minyar_home/default" ] || die 'no default toolchain is installed; run the verified Minyar installer first'
    default=$(cat -- "$minyar_home/default")
    installed "$default" || die "default toolchain is unavailable: $default; reinstall it with minyar toolchain install $default"
}
floor_version() {
    floor=
    if [ -e "$minyar_home/update-floor" ] || [ -L "$minyar_home/update-floor" ]; then
        [ ! -L "$minyar_home/update-floor" ] && [ -f "$minyar_home/update-floor" ] || die 'the automatic update floor must be a regular file'
        floor=$(cat -- "$minyar_home/update-floor")
        valid_version "$floor" || die 'the automatic update floor contains an invalid version'
        installed "$floor" || die "automatic update floor toolchain is unavailable: $floor; reinstall Minyar $floor from a verified installer"
    elif [ -f "$minyar_home/default" ]; then
        default_version
        floor=$default
    fi
}
raise_floor() {
    floor_version
    if [ -z "$floor" ] || version_less_than "$floor" "$1"; then floor=$1; fi
    printf '%s\n' "$floor" > "$minyar_home/.update-floor-$$"
    mv -f -- "$minyar_home/.update-floor-$$" "$minyar_home/update-floor"
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
    floor_version
    if [ -n "$floor" ]; then
        installer_path=$minyar_home/toolchains/$floor/install/install.sh
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
                mkdir -- "$minyar_home/.install-lock" 2>/dev/null || die 'another toolchain installation is running; repeat this command when it finishes'
                lock=$minyar_home/.install-lock
                raise_floor "$2"
                printf '%s\n' "$2" > "$minyar_home/.default-$$"
                mv -f -- "$minyar_home/.default-$$" "$minyar_home/default"
                rmdir -- "$lock"
                lock=
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
