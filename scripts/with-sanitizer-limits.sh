#!/bin/zsh
set -eu

# ASan deliberately reserves a huge sparse virtual address range, so applying
# an address-space ulimit would prevent it from starting. CPU, file size, low
# priority, and single-job Make execution still apply.
cpu_seconds=${MINYAR_MAX_CPU_SECONDS:-240}
memory_mib=${MINYAR_MAX_MEMORY_MIB:-768}
file_blocks=${MINYAR_MAX_FILE_BLOCKS:-262144}
priority=${MINYAR_NICE_PRIORITY:-15}

ulimit -t "$cpu_seconds"
ulimit -f "$file_blocks"

if [ -x /usr/sbin/taskpolicy ]; then
    # Older macOS releases support scheduling policy but lack the memory cap.
    # Probe separately so an unsupported option cannot prevent the command.
    memory_policy=()
    if /usr/sbin/taskpolicy -m "$memory_mib" /usr/bin/true 2>/dev/null; then
        memory_policy=(-m "$memory_mib")
    fi
    if [ "${MINYAR_INTERACTIVE_BOOTSTRAP:-0}" = 1 ]; then
        exec /usr/sbin/taskpolicy "${memory_policy[@]}" nice -n "$priority" "$@"
    fi
    exec /usr/sbin/taskpolicy -b -c background "${memory_policy[@]}" nice -n "$priority" "$@"
fi
if command -v nice >/dev/null 2>&1; then
    exec nice -n "$priority" "$@"
fi
exec "$@"
