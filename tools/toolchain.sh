#!/bin/sh
set -eu

llvm_version=23.1.2
tab=$(printf '\t')
cr=$(printf '\r')
newline='
'

fail() {
    printf 'minyar: %s\n' "$1" >&2
    exit 1
}

sanitize_path() {
    _search=${PATH-/bin:/usr/bin}:
    _safe=
    while [ -n "$_search" ]; do
        _directory=${_search%%:*}
        _search=${_search#*:}
        case $_directory in
            /*|[A-Za-z]:[\\/]*|\\\\*) _safe=$_safe${_safe:+:}$_directory ;;
        esac
    done
    PATH=${_safe:-/bin:/usr/bin}
    export PATH
}
sanitize_path

host_system() {
    if [ -n "${MINYAR_TEST_HOST_SYSTEM-}" ]; then printf '%s\n' "$MINYAR_TEST_HOST_SYSTEM"; return 0; fi
    uname -s 2>/dev/null || printf 'unknown\n'
}

find_command() {
    case $1 in
        '') return 1 ;;
        */*)
            if [ -f "$1" ] && [ -x "$1" ]; then printf '%s\n' "$1"; return 0; fi
            return 1 ;;
    esac
    _search=${PATH-/bin:/usr/bin}:
    while [ -n "$_search" ]; do
        _directory=${_search%%:*}
        _search=${_search#*:}
        case $_directory in
            /*|[A-Za-z]:[\\/]*|\\\\*) _candidate=$_directory/$1 ;;
            *) continue ;;
        esac
        if [ -f "$_candidate" ] && [ -x "$_candidate" ]; then printf '%s\n' "$_candidate"; return 0; fi
    done
    return 1
}

quote_word() {
    _value=$1
    _quoted=
    while :; do
        case $_value in
            *\'*) _quoted=$_quoted${_value%%\'*}"'\\''"; _value=${_value#*\'} ;;
            *) break ;;
        esac
    done
    _quoted="'$_quoted$_value'"
}

python_quote() {
    case $1 in
        '') _quoted="''" ;;
        *[!A-Za-z0-9_@%+=:,./-]*)
            _value=$1
            _quoted=
            while :; do
                case $_value in
                    *\'*) _quoted=$_quoted${_value%%\'*}"'\"'\"'"; _value=${_value#*\'} ;;
                    *) break ;;
                esac
            done
            _quoted="'$_quoted$_value'" ;;
        *) _quoted=$1 ;;
    esac
}

split_words() {
    _target=$1
    _rest=$2
    _label=$3
    _words=
    _word=
    _state=space
    _pending=0
    while [ -n "$_rest" ]; do
        _next=${_rest#?}
        _char=${_rest%"$_next"}
        _rest=$_next
        case $_state in
            single)
                if [ "$_char" = "'" ]; then _state=word; else _word=$_word$_char; fi ;;
            double)
                case $_char in
                    '"') _state=word ;;
                    \\)
                        [ -n "$_rest" ] || fail "$_label: No escaped character"
                        _next=${_rest#?}
                        _escaped=${_rest%"$_next"}
                        case $_escaped in
                            '"'|\\) _word=$_word$_escaped; _rest=$_next ;;
                            *) _word=$_word\\ ;;
                        esac ;;
                    *) _word=$_word$_char ;;
                esac ;;
            *)
                case $_char in
                    ' '|"$tab"|"$newline"|"$cr")
                        if [ "$_pending" = 1 ]; then
                            quote_word "$_word"
                            _words="$_words $_quoted"
                            _word=
                            _pending=0
                        fi ;;
                    \\)
                        [ -n "$_rest" ] || fail "$_label: No escaped character"
                        _next=${_rest#?}
                        _word=$_word${_rest%"$_next"}
                        _rest=$_next
                        _pending=1 ;;
                    "'") _state=single; _pending=1 ;;
                    '"') _state=double; _pending=1 ;;
                    *) _word=$_word$_char; _pending=1 ;;
                esac ;;
        esac
    done
    case $_state in single|double) fail "$_label: No closing quotation" ;; esac
    if [ "$_pending" = 1 ]; then
        quote_word "$_word"
        _words="$_words $_quoted"
    fi
    eval "$_target=\$_words"
}

version_of() {
    printf '%s\n' "$2" | sed -n "s/^\\(.*[^A-Za-z0-9_]\\)\\{0,1\\}$1 \\([0-9][0-9]*\\.[0-9][0-9]*\\.[0-9][0-9]*\\)\\([[:space:]].*\\)\\{0,1\\}\$/\\2/p" | sed -n 1p
}

pinned() {
    _kind=$1
    _command=$2
    if [ "$_kind" = compiler ]; then _label='clang version'; else _label=LLD; fi
    if ! _resolved=$(find_command "$_command"); then
        if [ "$_kind" = compiler ]; then
            fail "Minyar requires LLVM $llvm_version; Clang executable not found: $_command. Select it with MINYAR_CLANG or LLVM_CC."
        fi
        fail "Minyar requires LLVM $llvm_version; LLD executable not found: $_command"
    fi
    _status=0
    _output=$("$_resolved" --version 2>/dev/null) || _status=$?
    if [ "$_status" -ne 0 ] || [ "$(version_of "$_label" "$_output")" != "$llvm_version" ]; then
        if [ -n "$_output" ]; then
            _actual=$(printf '%s\n' "$_output" | sed -n 1p)
        else
            _actual=$("$_resolved" --version 2>&1 >/dev/null || :)
        fi
        if [ "$_kind" = compiler ]; then fail "Minyar requires LLVM $llvm_version; unsupported compiler $_command: $_actual"; fi
        fail "Minyar requires LLVM $llvm_version; unsupported linker $_command: $_actual"
    fi
    pinned_path=$_resolved
}

default_clang() {
    cached_clang=${HOME-}/.cache/minyar/toolchains/llvm-$llvm_version/bin/clang
    if [ -n "${MINYAR_BUNDLED_CLANG-}" ]; then printf '%s\n' "$MINYAR_BUNDLED_CLANG"
    elif [ -n "${HOME-}" ] && [ -x "$cached_clang" ]; then printf '%s\n' "$cached_clang"
    elif [ "$(host_system)" = Darwin ]; then printf '%s\n' clang
    else printf '%s\n' clang-23
    fi
}

sdkroot() {
    if [ "${SDKROOT+x}" = x ]; then printf '%s\n' "$SDKROOT"
    elif [ "$(host_system)" = Darwin ] && find_command xcrun >/dev/null; then
        xcrun --show-sdk-path 2>/dev/null || :
    fi
}

prepare_sdk() {
    if [ "${SDKROOT+x}" != x ]; then
        discovered_sdk=$(sdkroot)
        if [ -n "$discovered_sdk" ]; then SDKROOT=$discovered_sdk; export SDKROOT; fi
    fi
}

selected_clang() {
    if [ "${MINYAR_CLANG+x}" = x ]; then selected=$MINYAR_CLANG
    elif [ "${LLVM_CC+x}" = x ]; then selected=$LLVM_CC
    else selected=$(default_clang)
    fi
}

lto_flags() {
    _clang=$1
    shift
    lto="'-flto=thin'"
    _system=$(host_system)
    [ "$_system" != Darwin ] || return 0
    for _option in "$@"; do
        case $_option in -fuse-ld=*|--ld-path=*) return 0 ;; esac
    done
    case $_system in
        Linux)
            _linker=$("$_clang" -print-prog-name=ld.lld) || fail "Command '['$_clang', '-print-prog-name=ld.lld']' returned non-zero exit status $?."
            pinned linker "$_linker"
            quote_word "-fuse-ld=$pinned_path"
            lto="$lto $_quoted"
            return 0 ;;
        Windows*|MSYS*|MINGW*|CYGWIN*) _names='ld.lld.exe ld.lld'; _windows=1 ;;
        *) _names=ld.lld; _windows=0 ;;
    esac
    _found=$(find_command "$_clang") || _found=$_clang
    _count=0
    while [ -h "$_found" ] && [ "$_count" -lt 40 ]; do
        _link=$(readlink "$_found")
        case $_link in /*) _found=$_link ;; *) _found=$(dirname -- "$_found")/$_link ;; esac
        _count=$((_count + 1))
    done
    _directory=$(CDPATH= cd -- "$(dirname -- "$_found")" && pwd -P)
    for _name in $_names; do
        if [ -f "$_directory/$_name" ]; then
            if [ "$_windows" = 1 ]; then
                quote_word "--ld-path=$_directory/$_name"
                lto="$lto '-fuse-ld=lld' $_quoted"
            else
                quote_word "-fuse-ld=$_directory/$_name"
                lto="$lto $_quoted"
            fi
            return 0
        fi
    done
    for _name in $_names; do
        if find_command "$_name" >/dev/null; then lto="$lto '-fuse-ld=lld'"; return 0; fi
    done
}

toolchain() {
    selected_clang
    pinned compiler "$selected"
    printf '%s\n' "$pinned_path"
}

bootstrap() {
    prepare_sdk
    project=$1
    shift
    # Release toolchains are immutable. Never run Make or depend on build-host
    # paths/timestamps when using a precompiled distribution.
    if [ -f "$project/.minyar-distribution" ]; then
        for target in "$@"; do
            [ -f "$project/$target" ] || fail "release toolchain is missing $target; reinstall Minyar"
        done
        return 0
    fi
    targets=
    for target in "$@"; do
        quote_word "$target"
        targets="$targets $_quoted"
    done
    mkdir -p "$project/build"
    selected_clang
    pinned compiler "$selected"
    if [ -n "$selected" ]; then LLVM_CC=$selected; else LLVM_CC=$pinned_path; fi
    export LLVM_CC
    if [ "${CC+x}" != x ]; then CC=$LLVM_CC; export CC; fi
    if [ "${COMPILER_LTO_FLAGS+x}" != x ]; then
        split_words llvm_options "${LLVM_FLAGS--O2 -Wno-override-module}" LLVM_FLAGS
        eval "set -- $llvm_options"
        lto_flags "$LLVM_CC" "$@"
        eval "set -- $llvm_options $lto"
        lld=0
        threads=0
        for option in "$@"; do
            case $option in
                -fuse-ld=*|--ld-path=*)
                    case ${option#*=} in */lld|lld|*/ld.lld|ld.lld) lld=1 ;; esac ;;
            esac
            case $option in *--threads*) threads=1 ;; esac
        done
        if [ "$(host_system)" = Linux ] && [ "$lld" = 1 ] && [ "$threads" = 0 ]; then lto="$lto '-Wl,--threads=1'"; fi
        eval "set -- $lto"
        COMPILER_LTO_FLAGS=
        for option in "$@"; do
            python_quote "$option"
            COMPILER_LTO_FLAGS="$COMPILER_LTO_FLAGS${COMPILER_LTO_FLAGS:+ }$_quoted"
        done
        export COMPILER_LTO_FLAGS
    fi
    split_words make_options "${MINYAR_MAKE_FLAGS-}" MINYAR_MAKE_FLAGS
    eval "set -- $make_options $targets"
    lock=$project/build/bootstrap.lock
    if find_command lockf >/dev/null; then
        exec lockf -k "$lock" make -s -C "$project" "$@"
    elif find_command flock >/dev/null; then
        exec flock "$lock" make -s -C "$project" "$@"
    fi
    fail "first-use builds need flock (util-linux) or lockf to serialize shared artifacts"
}

doctor() {
    prepare_sdk
    selected_clang
    pinned compiler "$selected"
    clang=$pinned_path
    c_compiler=${CC-$clang}
    missing=
    prerequisites="make zsh"
    if [ "${MINYAR_PREBUILT-0}" = 1 ]; then prerequisites=; fi
    for name in $prerequisites "$c_compiler"; do
        find_command "$name" >/dev/null || missing="$missing${missing:+, }$name"
    done
    if [ -n "$missing" ]; then
        fail "missing prerequisites: $missing. Install the C compiler, Make, and zsh; see docs/toolchain.md."
    fi
    "$clang" --version | sed -n 1p
    work=$(mktemp -d "${TMPDIR:-/tmp}/minyar doctor XXXXXXXX")
    trap 'rm -rf -- "$work"' 0
    printf 'define i32 @main() {\n  %%slot = alloca ptr\n  store ptr null, ptr %%slot\n  %%value = load ptr, ptr %%slot\n  ret i32 0\n}\n' > "$work/probe.ll"
    printf '#include <stdint.h>\n#include <stdio.h>\n_Static_assert(sizeof(void *) == 8, "Minyar needs a 64-bit target");\n' > "$work/probe.c"
    split_words options "${MINYAR_CLANG_FLAGS--O2 -Wno-override-module}" MINYAR_CLANG_FLAGS
    eval "set -- $options"
    lto_flags "$clang" "$@"
    eval "set -- $options $lto"
    if ! "$clang" "$@" "$work/probe.ll" "$work/probe.c" -o "$work/probe" >/dev/null 2>"$work/errors"; then
        fail "the opaque IR / 64-bit C / LTO probe failed. Install matching Clang and lld (Linux), or Xcode command-line tools (macOS). Check MINYAR_CLANG_FLAGS.
$(cat "$work/errors")"
    fi
    "$work/probe" || fail 'the linked toolchain probe could not run on this Mac'
    printf 'Ready: 64-bit C headers, opaque LLVM pointers, and LTO linking verified.\n'
}

digest() {
    if find_command sha256sum >/dev/null; then sha256sum | sed 's/ .*//'
    elif find_command shasum >/dev/null; then shasum -a 256 | sed 's/ .*//'
    else openssl dgst -sha256 -r | sed 's/ .*//'
    fi
}

version() {
    project=$1
    LC_ALL=C
    export LC_ALL
    set -- "$project"/compiler/*.min
    if [ -f "$project/.minyar-distribution" ]; then
        distribution_platform=macos
        if [ -f "$project/distribution.platform" ]; then distribution_platform=$(cat "$project/distribution.platform"); fi
        if [ "$distribution_platform" = linux ]; then
            printf 'Minyar %s (Linux %s; requires glibc %s+)\n' "$(cat "$project/distribution.version")" "$(cat "$project/distribution.arch")" "$(cat "$project/distribution.libc")"
        else
            printf 'Minyar %s (macOS %s; requires macOS 14+)\n' "$(cat "$project/distribution.version")" "$(cat "$project/distribution.arch")"
        fi
    elif [ -f "$1" ]; then
        identity=$(for source in "$@"; do printf '%s\0' "${source##*/}"; cat "$source"; done | digest)
        printf 'Minyar development (source %.12s)\n' "$identity"
    else
        printf 'Minyar development\n'
    fi
    if [ -f "$project/build/minyarc" ]; then
        identity=$(digest < "$project/build/minyarc")
        printf 'cached compiler: %.12s\n' "$identity"
    else
        printf 'compiler builds on first use\n'
    fi
}

json_string() {
    _value=$1
    _json=
    while [ -n "$_value" ]; do
        _next=${_value#?}
        _char=${_value%"$_next"}
        _value=$_next
        case $_char in
            \\) _json="$_json\\\\" ;;
            '"') _json="$_json\\\"" ;;
            "$tab") _json="$_json\\t" ;;
            "$cr") _json="$_json\\r" ;;
            "$newline") _json="$_json\\n" ;;
            *) _json=$_json$_char ;;
        esac
    done
    _json="\"$_json\""
}

resolve_file() {
    _path=$1
    _count=0
    while [ -h "$_path" ] && [ "$_count" -lt 40 ]; do
        _link=$(readlink "$_path")
        case $_link in /*) _path=$_link ;; *) _path=$(dirname -- "$_path")/$_link ;; esac
        _count=$((_count + 1))
    done
    _directory=$(CDPATH= cd -- "$(dirname -- "$_path")" && pwd -P)
    resolved_file=${_directory%/}/${_path##*/}
}

nanoseconds() {
    _seconds=${1%%.*}
    case $1 in *.*) _fraction=${1#*.}000000000 ;; *) _fraction=000000000 ;; esac
    _fraction=$(printf '%.9s' "$_fraction" | sed 's/^0*//')
    echo $((_seconds * 1000000000 + ${_fraction:-0}))
}

modified_seconds() {
    stat -L -c %Y "$1" 2>/dev/null || stat -L -f %m "$1"
}

file_identity() {
    _name=$1
    _command=$2
    _found=$(find_command "$_command") || fail "$_name: compiler executable not found: $_command"
    resolve_file "$_found"
    _fields=$(stat -L -c '%d %i %s %.9Y %.9Z' "$resolved_file" 2>/dev/null || stat -L -f '%d %i %z %Fm %Fc' "$resolved_file") || fail "$_name: cannot inspect $resolved_file"
    set -f
    set -- $_fields
    set +f
    json_string "$_command"
    _quoted_command=$_json
    json_string "$resolved_file"
    identity="{
    \"changed_ns\": $(nanoseconds "$5"),
    \"command\": $_quoted_command,
    \"device\": $1,
    \"inode\": $2,
    \"modified_ns\": $(nanoseconds "$4"),
    \"path\": $_json,
    \"size\": $3
  }"
}

publish_stamp() {
    _target=$1
    _previous=0
    if [ -e "$_target" ]; then _previous=$(modified_seconds "$_target"); fi
    _now=$(date +%s)
    if [ "$_now" -gt "$_previous" ]; then _boundary=$((_now + 1)); else _boundary=$((_previous + 1)); fi
    stamp_temporary=$(mktemp "$_target.XXXXXXXX")
    trap 'rm -f -- "$stamp_temporary"' 0
    trap 'exit 1' HUP INT TERM
    printf '%s' "$2" > "$stamp_temporary"
    _attempts=0
    while :; do
        touch "$stamp_temporary"
        [ "$(modified_seconds "$stamp_temporary")" -lt "$_boundary" ] || break
        _attempts=$((_attempts + 1))
        [ "$_attempts" -le 60 ] || fail 'filesystem timestamp did not cross the required whole-second boundary'
        sleep 0.05
    done
    mv -f -- "$stamp_temporary" "$_target"
    trap - 0
}

stamp() {
    target=$1
    previous=
    if [ -f "$target" ]; then previous=$(cat "$target"; printf x); previous=${previous%x}; fi
    default_clang=$(default_clang)
    file_identity CC "${CC-cc}"
    cc_identity=$identity
    llvm_command=${LLVM_CC-$default_clang}
    file_identity LLVM_CC "$llvm_command"
    llvm_identity=$identity
    version_line="  \"llvm_version\": \"$llvm_version\""
    case $previous in
        *"\"llvm_cc\": $llvm_identity"*"$version_line"*) ;;
        *) pinned compiler "$llvm_command" ;;
    esac
    linker_identity=null
    split_words options "${LLVM_FLAGS-} ${COMPILER_LTO_FLAGS-}" options
    eval "set -- $options"
    lto=0
    for option in "$@"; do case $option in -flto*) lto=1 ;; esac; done
    if [ "$(host_system)" = Linux ] && [ "$lto" = 1 ]; then
        selected=
        for option in "$@"; do case $option in --ld-path=*) selected=${option#*=} ;; esac; done
        if [ -z "$selected" ]; then
            selected=lld
            for option in "$@"; do case $option in -fuse-ld=*) selected=${option#*=} ;; esac; done
        fi
        case $selected in
            lld) selected=$("$llvm_command" -print-prog-name=ld.lld) || fail "Command '['$llvm_command', '-print-prog-name=ld.lld']' returned non-zero exit status $?." ;;
            /*) ;;
            *) selected=$(find_command "$selected" || find_command "ld.$selected" || printf '%s\n' "$selected") ;;
        esac
        file_identity LLD "$selected"
        linker_identity=$identity
        case $previous in
            *"\"linker\": $linker_identity"*"$version_line"*) ;;
            *) pinned linker "$selected" ;;
        esac
    fi
    flags=
    for name in BOUNDED_FLAGS CFLAGS COMPILER_LTO_FLAGS COMPILER_RUNTIME_FLAGS CPPFLAGS LDLIBS LLVM_FLAGS PROGRAM_RUNTIME_FLAGS SANITIZER_FLAGS; do
        eval "value=\${$name-}"
        json_string "$value"
        flags="$flags${flags:+,$newline}    \"$name\": $_json"
    done
    content="{
  \"cc\": $cc_identity,
  \"flags\": {
$flags
  },
  \"linker\": $linker_identity,
  \"llvm_cc\": $llvm_identity,
$version_line
}
"
    [ "$content" != "$previous" ] || return 0
    mkdir -p "$(dirname -- "$target")"
    publish_stamp "$target" "$content"
}

host_path() {
    _value=$1
    case $_value in
        [A-Za-z]:[\\/]*|\\\\*)
            case $(host_system) in MSYS*|MINGW*|CYGWIN*) _value=$(cygpath -u "$_value") ;; esac ;;
    esac
    case $_value in
        //[!/]*|//) _root=//; _rest=${_value#//} ;;
        /*) _root=/; _rest=${_value#"${_value%%[!/]*}"} ;;
        *) _root=; _rest=$_value ;;
    esac
    _parts=
    _old_ifs=$IFS
    IFS=/
    set -f
    for _part in $_rest; do
        case $_part in ''|.) ;; *) _parts="$_parts${_parts:+/}$_part" ;; esac
    done
    set +f
    IFS=$_old_ifs
    host_value=$_root$_parts
    [ -n "$host_value" ] || host_value=.
}

host_directory() {
    host_path "$1"
    case $_parts in
        '') ;;
        */*) host_value=$_root${_parts%/*} ;;
        *) host_value=${_root:-.} ;;
    esac
}

command=${1-}
[ "$#" -eq 0 ] || shift
usage='usage: toolchain.sh toolchain | doctor | version PROJECT | stamp TARGET | bootstrap PROJECT TARGET...'
case $command:$# in
    stamp:1) stamp "$1" ;;
    host-path:1) host_path "$1"; printf '%s\n' "$host_value" ;;
    host-directory:1) host_directory "$1"; printf '%s\n' "$host_value" ;;
    toolchain:0) toolchain ;;
    default-clang:0) default_clang ;;
    sdkroot:0) sdkroot ;;
    doctor:0) doctor ;;
    version:1) version "$1" ;;
    bootstrap:*)
        [ "$#" -ge 2 ] || fail "$usage"
        bootstrap "$@" ;;
    *) fail "$usage" ;;
esac
