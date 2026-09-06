/* Minimal SanitizerCoverage sink for repeatable self-hosted compiler edge coverage. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static unsigned char *covered;
static uint64_t edge_count;

static void write_coverage(void) {
    const char *directory = getenv("MINYAR_SANCOV_DIR");
    char path[4096];
    FILE *output;
    if (!directory || !covered)
        return;
    if (snprintf(path, sizeof(path), "%s/%ld.edges", directory, (long)getpid()) >= (int)sizeof(path))
        return;
    output = fopen(path, "wb");
    if (!output)
        return;
    if (fwrite(&edge_count, sizeof(edge_count), 1, output) == 1)
        (void)fwrite(covered + 1, 1, (size_t)edge_count, output);
    (void)fclose(output);
}

void __sanitizer_cov_trace_pc_guard_init(uint32_t *start, uint32_t *stop) {
    uint32_t *guard;
    if (start == stop || *start)
        return;
    edge_count = (uint64_t)(stop - start);
    covered = calloc((size_t)edge_count + 1, 1);
    if (!covered)
        abort();
    for (guard = start; guard < stop; guard++)
        *guard = (uint32_t)(guard - start + 1);
    if (atexit(write_coverage) != 0)
        abort();
}

void __sanitizer_cov_trace_pc_guard(uint32_t *guard) {
    uint32_t id = *guard;
    if (id && id <= edge_count)
        covered[id] = 1;
}
