/* Count-only observer; counter hooks exist only in an isolated runtime copy.
 * Shadow cache aliases own no references because the original cache is immortal.
 * No timing/RSS claim: instrumentation has its own static pointer registry. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
static int research_active;
static size_t research_calls, research_formats, research_headers, research_data;
static size_t research_allocated_bytes, research_hooks, research_offered, research_work;
static size_t research_destroyed;
#define MINYAR_RC_TESTING 1
#define minyar_integer_text research_original_integer_text
#define minyar_print_integer research_original_print_integer
#define minyar_print_text research_original_print_text
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#undef minyar_integer_text
#undef minyar_print_integer
#undef minyar_print_text

static MinyarText *tracked_cache[32768];
static MinyarText *saved_status[2];
static size_t phase, printed_frames;

MinyarText *minyar_integer_text(long long value) {
    assert(!research_active);
    research_active = 1;
    research_calls++;
    MinyarText *text = research_original_integer_text(value);
    research_active = 0;
    if ((unsigned long long)value < MINYAR_INTEGER_TEXT_CACHE_LIMIT) {
        assert((((RcObject *)text - 1)->ownership >> 3) == 0);
        if (tracked_cache[value])
            assert(tracked_cache[value] == text);
        tracked_cache[value] = text;
    }
    return text;
}

void minyar_print_text(const MinyarText *text) {
    if (phase < 2 && !printed_frames)
        saved_status[phase] = (MinyarText *)text;
    if (phase < 2)
        printed_frames++;
    research_original_print_text(text);
}

static size_t validate_cache(size_t *requested) {
    size_t count = 0;
    *requested = 0;
    for (size_t value = 0; value < 32768; value++) {
        MinyarText *text = tracked_cache[value];
        if (!text)
            continue;
        char expected[32];
        int length = snprintf(expected, sizeof(expected), "%zu", value);
        assert(text->byte_length == length && !memcmp(text->bytes, expected, (size_t)length));
        assert(text->character_length == length && !text->character_offsets && !text->backing);
        *requested += sizeof(RcObject) + sizeof(MinyarText) + sizeof(RcData) + (size_t)length + 1;
        count++;
    }
    return count;
}

static size_t status_bytes(MinyarText *text) {
    assert(text && !text->backing && !text->character_offsets);
    return sizeof(RcObject) + sizeof(MinyarText) + sizeof(RcData) +
           ((RcData *)text->bytes - 1)->size;
}

void minyar_print_integer(long long marker) {
    assert(marker >= 1 && marker <= 3 && (size_t)marker == phase + 1);
    if (marker <= 2)
        assert(printed_frames == MINYAR_RESEARCH_HUD_FRAMES);
    size_t drain_work = 0;
    while (rc_pending_count)
        drain_work += minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    size_t expected_bytes, cached = validate_cache(&expected_bytes);
    size_t alias_count = marker <= 2 ? (size_t)marker : 0;
    for (size_t i = 0; i < alias_count; i++)
        expected_bytes += status_bytes(saved_status[i]);
    assert(rc_immortal_object_count == cached);
    assert(rc_object_count == cached + alias_count && rc_bytes == expected_bytes);
    assert(research_headers == research_formats && research_data == research_formats);
    assert(research_hooks == 2 * research_formats);
    assert(research_offered == research_hooks * MINYAR_RC_POLL_BUDGET);
    assert(research_work <= research_offered && research_destroyed <= research_work);
    fprintf(stderr,
            "{\"phase\":%lld,\"calls\":%zu,\"formats\":%zu,\"headers\":%zu,"
            "\"data\":%zu,\"allocated_requested_bytes\":%zu,\"hooks\":%zu,"
            "\"offered\":%zu,\"actual_work\":%zu,\"destructions\":%zu,"
            "\"observer_drain_work\":%zu,\"cached_objects\":%zu,"
            "\"objects\":%zu,\"requested_bytes\":%zu,\"alias_objects\":%zu,"
            "\"cache_table_bytes\":%zu,\"observer_registry_bytes\":%zu,"
            "\"object_header_size\":%zu,\"text_size\":%zu,\"data_header_size\":%zu}\n",
            marker, research_calls, research_formats, research_headers, research_data,
            research_allocated_bytes, research_hooks, research_offered, research_work,
            research_destroyed, drain_work, cached, rc_object_count, rc_bytes, alias_count,
            (size_t)MINYAR_INTEGER_TEXT_CACHE_LIMIT * sizeof(MinyarText *), sizeof(tracked_cache),
            sizeof(RcObject), sizeof(MinyarText), sizeof(RcData));
    research_calls = research_formats = research_headers = research_data = 0;
    research_allocated_bytes = research_hooks = research_offered = research_work =
        research_destroyed = 0;
    printed_frames = 0;
    phase++;
    research_original_print_integer(marker);
}

__attribute__((destructor)) static void final_recovery(void) {
    assert(phase == 3 && !rc_frames);
    while (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
    size_t bytes, cached = validate_cache(&bytes);
    assert(rc_object_count == cached && rc_immortal_object_count == cached && rc_bytes == bytes);
    assert(rc_heap_allocation_count == 2 * cached);
    fprintf(stderr,
            "{\"phase\":\"final\",\"cached_objects\":%zu,\"requested_bytes\":%zu,"
            "\"heap_allocations\":%zu,\"intentional_permanent_cache\":true}\n",
            cached, bytes, rc_heap_allocation_count);
}
