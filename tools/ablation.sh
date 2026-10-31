#!/bin/sh
# EXPERIMENTAL measurement switches ("ablation builds"; docs/testing.md).
# Never shipped, never a default: each switch turns off ONE language guarantee
# so its price can be measured. A program built with any of them may give wrong
# results or undefined behaviour on inputs the guarantee exists for.
#
# The launcher calls this only when the tree holds ablation.conf (or
# MINYAR_ABLATION_FILE names a file). Lines `MINYAR_ABLATE_<NAME>=1` select:
#   OVERFLOW   checked + - * and negation become `nsw` arithmetic (C semantics)
#   BOUNDS     inline List/Bytes position checks become always-true
#   UNICODE    text[i] / text.length use bytes (identical output on ASCII text)
#   RECLAIM    never free: the runtime's arena profile (bump allocation, no RC)
#   SCHEDULER  free immediately: the eager profile instead of bounded cleanup
#   THREADS    link the plain runtime although the program carries the
#              thread-runtime marker (link fails if it really needs threads)
#
#   ablation.sh switches FILE      print the selected names, space separated
#   ablation.sh runtime NAME...    print runtime #define lines
#   ablation.sh ir FILE.ll NAME... rewrite program IR in place
set -eu

has() {
    _wanted=$1; shift
    for _name in "$@"; do [ "$_name" = "$_wanted" ] && return 0; done
    return 1
}

case "${1-}" in
    switches)
        sed -n 's/^[[:space:]]*MINYAR_ABLATE_\([A-Z_]*\)=1[[:space:]]*$/\1/p' "$2" | sort -u | tr '\n' ' '
        ;;
    runtime)
        shift
        if has RECLAIM "$@"; then printf '#define MINYAR_COMPILER_ARENA 1\n'; fi
        ;;
    ir)
        shift; file=$1; shift
        script=
        if has OVERFLOW "$@"; then
            script="$script
/^  %checked\.[0-9]* = call { i64, i1 } @llvm\.s[a-z]*\.with\.overflow\.i64(/s/@llvm\.\(s[a-z]*\)\.with\.overflow\.i64(/@.minyar.ablate.\1(/"
        fi
        if has BOUNDS "$@"; then
            script="$script
s/^  %\([a-z]*\.\{0,1\}valid\) = icmp ult i64 %position, %length$/  %\1 = icmp eq i64 0, 0/"
        fi
        if has UNICODE "$@"; then
            script="$script
/^declare /!s/@minyar_text_character_at(/@.minyar.ablate.byte.at(/g
/^declare /!s/@minyar_text_length(/@.minyar.ablate.byte.length(/g"
        fi
        if has THREADS "$@"; then
            # Thread entry points the plain runtime lacks become weak stubs
            # that trap if a thread is ever started.
            script="$script
/^; minyar-thread-runtime: 1$/d
s/^declare \(.*\) @\(minyar_thread_[a-z_0-9]*\)(\([^)]*\)).*$/define weak \1 @\2(\3) {\\
  call void @llvm.trap()\\
  unreachable\\
}/
s/^declare \(.*\) @\(minyar_transfer_[a-z_0-9]*\)(\([^)]*\)).*$/define weak \1 @\2(\3) {\\
  call void @llvm.trap()\\
  unreachable\\
}/"
        fi
        [ -n "$script" ] || exit 0
        sed -e "$script" "$file" > "$file.ablated"
        if has THREADS "$@" && ! grep -q '^declare void @llvm.trap()' "$file.ablated"; then
            printf 'declare void @llvm.trap()\n' >> "$file.ablated"
        fi
        if has OVERFLOW "$@"; then
            for operation in sadd:add ssub:sub smul:mul; do
                cat >> "$file.ablated" <<EOF
define internal { i64, i1 } @.minyar.ablate.${operation%%:*}(i64 %a, i64 %b) alwaysinline {
  %r = ${operation#*:} nsw i64 %a, %b
  %p = insertvalue { i64, i1 } { i64 poison, i1 false }, i64 %r, 0
  ret { i64, i1 } %p
}
EOF
            done
        fi
        if has UNICODE "$@"; then
            # MinyarText = { bytes, byte_length, ... }; out of range keeps the
            # runtime's diagnostic.
            cat >> "$file.ablated" <<'EOF'
define internal i32 @.minyar.ablate.byte.at(ptr %text, i64 %position) alwaysinline {
entry:
  %length.pointer = getelementptr inbounds i8, ptr %text, i64 8
  %length = load i64, ptr %length.pointer
  %valid = icmp ult i64 %position, %length
  br i1 %valid, label %good, label %bad
good:
  %bytes = load ptr, ptr %text
  %slot = getelementptr inbounds i8, ptr %bytes, i64 %position
  %byte = load i8, ptr %slot
  %character = zext i8 %byte to i32
  ret i32 %character
bad:
  %stop = call i32 @minyar_text_character_at(ptr %text, i64 %position)
  ret i32 %stop
}
define internal i64 @.minyar.ablate.byte.length(ptr %text) alwaysinline {
  %length.pointer = getelementptr inbounds i8, ptr %text, i64 8
  %length = load i64, ptr %length.pointer
  ret i64 %length
}
EOF
        fi
        mv "$file.ablated" "$file"
        ;;
    *) echo "usage: ablation.sh switches FILE | runtime NAME... | ir FILE.ll NAME..." >&2; exit 2 ;;
esac
