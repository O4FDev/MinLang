#!/bin/zsh
set -eu

# Keep compiler development from monopolising a workstation. Children inherit
# these limits, so fuzzers and mutation tests cannot escape the same envelope.
cpu_seconds=${MINYAR_MAX_CPU_SECONDS:-240}
memory_mib=${MINYAR_MAX_MEMORY_MIB:-768}
file_blocks=${MINYAR_MAX_FILE_BLOCKS:-262144}
priority=${MINYAR_NICE_PRIORITY:-15}

if ! ulimit -t "$cpu_seconds" 2>/dev/null; then
    echo "Minyar test runner could not apply its CPU-time limit" >&2
    exit 2
fi
if ! ulimit -f "$file_blocks" 2>/dev/null; then
    echo "Minyar test runner could not apply its output-file limit" >&2
    exit 2
fi

if [ -x /usr/sbin/taskpolicy ]; then
    exec /usr/sbin/taskpolicy -b -c background -m "$memory_mib" nice -n "$priority" "$@"
fi
if command -v nice >/dev/null 2>&1; then
    memory_kb=$((memory_mib * 1024))
    ulimit -v "$memory_kb" 2>/dev/null || {
        echo "Minyar test runner could not apply its memory limit" >&2
        exit 2
    }
    exec nice -n "$priority" "$@"
fi
echo "Minyar test runner needs taskpolicy or nice plus a memory ulimit" >&2
exit 2
