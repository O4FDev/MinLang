/* Generated-language observer uses the unchanged policy. The first print
 * drains already-detached debt to distinguish queued owners from live views. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stddef.h>
static size_t research_index_calls, research_index_input_bytes;
#define minyar_text_slice research_original_slice
#define minyar_print_integer research_original_print_integer
#define main research_matrix_main
#include "memory-research-credit-relocation.c"
#include "../runtime/minyar_stack_frames.h"
#undef main
#undef minyar_text_slice
#undef minyar_print_integer
static size_t observed_slices, observed_views, observed_copies, root_length, root_capacity;
static size_t print_count;

MinyarText *minyar_text_slice(MinyarText *source, long long start, long long end) {
    if (!observed_slices) {
        research_object_allocations = research_data_allocations = research_service_calls = 0;
        research_offered = research_queued = research_immediate = research_destroyed = 0;
        root_length = (size_t)source->byte_length;
        root_capacity = ((RcData *)source->bytes - 1)->size;
    }
    research_active = 1;
    MinyarText *result = research_original_slice(source, start, end);
    research_active = 0;
    observed_slices++;
    if (result->backing) observed_views++; else observed_copies++;
    return result;
}
void minyar_print_integer(long long value) {
    if (!print_count++) {
        size_t before = rc_bytes, pending = rc_pending_count, drained = 0;
        while (rc_pending_count) drained += minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        fprintf(stderr, "{\"phase\":\"first-print\",\"slices\":%zu,\"views\":%zu,\"copies\":%zu,"
                "\"root_length\":%zu,\"root_capacity\":%zu,\"slice_object_allocations\":%zu,"
                "\"slice_data_allocations\":%zu,\"slice_service_hooks\":%zu,\"slice_offered_units\":%zu,"
                "\"pending_tasks_before_observer_drain\":%zu,\"observer_drain_units\":%zu,"
                "\"requested_before_observer_drain\":%zu,\"requested_after_observer_drain\":%zu,"
                "\"objects_after_observer_drain\":%zu}\n",
                observed_slices, observed_views, observed_copies, root_length, root_capacity,
                research_object_allocations, research_data_allocations, research_service_calls,
                research_offered, pending, drained, before, rc_bytes, rc_object_count);
    }
    research_original_print_integer(value);
}
__attribute__((destructor)) static void recovery(void) {
    clear();
    fprintf(stderr, "{\"phase\":\"final-recovery\",\"objects\":0,\"requested_bytes\":0}\n");
}
