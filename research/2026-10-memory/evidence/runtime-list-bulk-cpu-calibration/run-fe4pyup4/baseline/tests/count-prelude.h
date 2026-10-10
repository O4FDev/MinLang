/* Source-level append/copy work, separately from managed request/poll events. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int research_phase;
static size_t research_adds, research_takes, research_copies, research_copy_bytes;
static size_t research_retains, research_guard_pending;
static size_t events[512][5], event_count;
static void research_event(size_t kind, size_t a, size_t b, size_t c, size_t d) {
    if (!research_phase)
        return;
    assert(event_count < 512);
    size_t *event = events[event_count++];
    event[0] = kind;
    event[1] = a;
    event[2] = b;
    event[3] = c;
    event[4] = d;
}
static void *research_copy(void *target, const void *source, size_t size) {
    if (research_phase) {
        research_copies++;
        research_copy_bytes += size;
    }
    return memcpy(target, source, size);
}

#undef memcpy
#define memcpy research_copy
