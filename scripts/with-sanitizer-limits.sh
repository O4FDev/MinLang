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
    exec /usr/sbin/taskpolicy -b -c background -m "$memory_mib" nice -n "$priority" "$@"
fi
if command -v nice >/dev/null 2>&1; then
    exec nice -n "$priority" "$@"
fi
exec "$@"
