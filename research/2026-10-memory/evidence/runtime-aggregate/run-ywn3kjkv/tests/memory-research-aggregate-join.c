/* Generated lexer-fragment count observer, only against an instrumented snapshot. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stddef.h>
#include <assert.h>
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
static size_t research_events[512][5], research_event_count;
static void research_event(size_t kind, size_t a, size_t b, size_t c, size_t d) {
    if (!research_phase)
        return;
    assert(research_event_count < 512);
    size_t *event = research_events[research_event_count++];
    event[0] = kind;
    event[1] = a;
    event[2] = b;
    event[3] = c;
    event[4] = d;
}
#define MINYAR_RC_TESTING 1
#define minyar_print_integer research_original_print_integer
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#undef minyar_print_integer

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
            "\"service_hooks\":%zu,\"offered_queued_units\":%zu,\"actual_queued_units\":%zu,"
            "\"events\":[",
            research_phase, research_objects, research_data, research_data_bytes,
            research_copy_calls, research_copy_bytes, research_indexes, research_index_bytes,
            research_joins, research_sizing_parts, research_copy_parts, research_certified_parts,
            research_uncertified_parts, research_characters, research_ascii, research_nonascii,
            research_hooks, research_offered, research_queued_work);
    for (size_t index = 0; index < research_event_count; index++) {
        size_t *event = research_events[index];
        fprintf(stderr, "%s[%zu,%zu,%zu,%zu,%zu]", index ? "," : "", event[0], event[1], event[2],
                event[3], event[4]);
    }
    fputs("]}\n", stderr);
    assert(research_queued_work <= research_offered);
    research_objects = research_data = research_data_bytes = research_copy_calls = 0;
    research_copy_bytes = research_indexes = research_index_bytes = research_joins = 0;
    research_sizing_parts = research_copy_parts = research_characters = research_ascii = 0;
    research_certified_parts = research_uncertified_parts = 0;
    research_nonascii = research_hooks = research_offered = research_queued_work = 0;
    research_event_count = 0;
}

#ifdef MINYAR_RESEARCH_NATIVE_CONTROLS
/* Public join with a deterministic private retirement boundary. Setup itself
 * remains outside the measured call; no scheduler policy is modified. */
static struct {
    RcObject owner;
    MinyarText text;
} immortal = {{RC_TEXT}, {(const unsigned char *)"a", 1, 1, NULL, NULL}};

int main(int argc, char **argv) {
    assert(argc == 2);
    int invalid = !strcmp(argv[1], "invalid");
    MinyarList *parts = minyar_list_new();
    minyar_list_references(parts);
    MinyarText *unknown = NULL;
    if (invalid) {
        unsigned char *bytes = new_bytes(1);
        bytes[0] = 0xff;
        bytes[1] = 0;
        unknown = new_text(bytes, 1, -1);
        minyar_list_add_take(parts, (long long)(intptr_t)unknown);
    } else {
        minyar_list_add(parts, (long long)(intptr_t)&immortal.text);
        minyar_list_add(parts, (long long)(intptr_t)&immortal.text);
        MinyarRecord *debt = minyar_record_new(97);
        if (!strcmp(argv[1], "object")) {
            rc_drop(debt);
        } else if (!strcmp(argv[1], "frame")) {
            minyar_rc_enter(97);
            minyar_rc_local_take(0, debt);
            for (long long index = 1; index < 97; index++)
                minyar_rc_local_take(index, &immortal.text);
            RcFrame *frame = rc_frames;
            rc_frames = frame->previous;
            frame->local_count = frame->written_count;
            frame->previous = NULL;
            rc_bounded_frame_head = rc_bounded_frame_tail = frame;
            rc_pending_count++;
        } else {
            assert(!strcmp(argv[1], "chunk"));
            minyar_rc_enter(0);
            for (size_t index = 0; index < 97; index++)
                minyar_rc_borrow(debt);
            rc_drop(debt);
            rc_bounded_retire_temporaries(rc_frames);
        }
        assert(rc_pending_count);
    }
    research_phase = 2;
    MinyarText *result = minyar_join_texts(parts);
    assert(result->character_offsets == NULL);
    assert(result->byte_length == (invalid ? 1 : 2));
    if (invalid) {
        assert(result->character_length == -1);
        report_phase();
        research_phase = 0;
        minyar_text_length(result);
        abort();
    }
#ifdef MINYAR_RESEARCH_CANDIDATE
    assert(result->character_length == 2);
#else
    assert(result->character_length == -1);
#endif
    assert(!memcmp(result->bytes, "aa", 2));
    assert(minyar_text_length(result) == 2);
    assert(minyar_text_character_at(result, 0) == 'a');
    assert(minyar_text_character_at(result, 1) == 'a');
    report_phase();
    research_phase = 0;
    minyar_rc_release(result);
    minyar_rc_release(parts);
    while (rc_pending_count)
        minyar_rc_poll(32);
    if (rc_frames)
        minyar_rc_leave();
    while (rc_pending_count)
        minyar_rc_poll(32);
    puts("native aggregate contents, metadata and debt recovery verified");
    return 0;
}
#endif

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
