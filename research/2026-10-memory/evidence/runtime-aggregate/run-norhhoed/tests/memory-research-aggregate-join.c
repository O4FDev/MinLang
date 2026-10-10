/* Generated lexer-fragment count observer, only against an instrumented snapshot. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stddef.h>
#ifndef MINYAR_RESEARCH_INSTRUMENTED
#error Use the aggregate-join research runner.
#endif
static int research_phase;
static size_t research_objects, research_data, research_data_bytes, research_copy_calls;
static size_t research_copy_bytes, research_indexes, research_index_bytes;
static size_t research_joins, research_sizing_parts, research_copy_parts;
static size_t research_certified_parts, research_uncertified_parts;
static size_t research_characters, research_ascii, research_nonascii;
static size_t research_hooks, research_offered, research_queued_work;
#define MINYAR_RC_TESTING 1
#define minyar_print_integer research_original_print_integer
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#undef minyar_print_integer
#include <assert.h>

static void report_phase(void) {
    if (!research_phase)
        return;
    fprintf(stderr,
            "{\"phase\":%d,\"object_payload_requests\":%zu,\"data_requests\":%zu,"
            "\"data_payload_request_bytes\":%zu,\"copy_calls\":%zu,\"copy_bytes\":%zu,"
            "\"index_builds\":%zu,\"index_input_bytes\":%zu,\"aggregate_joins\":%zu,"
            "\"sizing_parts\":%zu,\"copy_parts\":%zu,\"certified_ascii_parts\":%zu,"
            "\"uncertified_parts\":%zu,\"character_calls\":%zu,"
            "\"ascii_character_calls\":%zu,\"nonascii_character_calls\":%zu,"
            "\"service_hooks\":%zu,\"offered_queued_units\":%zu,\"actual_queued_units\":%zu}\n",
            research_phase, research_objects, research_data, research_data_bytes,
            research_copy_calls, research_copy_bytes, research_indexes, research_index_bytes,
            research_joins, research_sizing_parts, research_copy_parts, research_certified_parts,
            research_uncertified_parts, research_characters, research_ascii, research_nonascii,
            research_hooks, research_offered, research_queued_work);
    assert(research_queued_work <= research_offered);
    research_objects = research_data = research_data_bytes = research_copy_calls = 0;
    research_copy_bytes = research_indexes = research_index_bytes = research_joins = 0;
    research_sizing_parts = research_copy_parts = research_characters = research_ascii = 0;
    research_certified_parts = research_uncertified_parts = 0;
    research_nonascii = research_hooks = research_offered = research_queued_work = 0;
}

void minyar_print_integer(long long value) {
    if (value <= -10001 && value >= -10006) {
        int next = (int)(-value - 10000);
        assert(next == research_phase + 1);
        report_phase();
        research_phase = next == 6 ? 0 : next;
    }
    research_original_print_integer(value);
}

#ifdef MINYAR_COMPILER_ARENA
static size_t used(MinyarArena *arena) {
    size_t total = 0;
    for (MinyarArenaBlock *block = arena->block; block; block = block->next)
        total += block->used;
    return total;
}
#endif

__attribute__((destructor)) static void final_state(void) {
    assert(!research_phase);
#ifdef MINYAR_COMPILER_ARENA
    fprintf(stderr,
            "{\"phase\":\"final\",\"profile\":\"compiler-arena\","
            "\"process_lifetime_arena_used_bytes\":%zu,\"managed_recovery_applicable\":false}\n",
            used(&object_arena) + used(&data_arena) + used(&list_arena) + used(&large_list_arena));
#else
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    assert(!rc_frames);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
    assert(!rc_object_count && !rc_bytes && !rc_heap_allocation_count);
    fprintf(stderr, "{\"phase\":\"final\",\"profile\":\"system\",\"objects\":0,"
                    "\"requested_bytes\":0,\"heap_allocations\":0}\n");
#endif
}
