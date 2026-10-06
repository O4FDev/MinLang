/* Count-only causal experiment. Both policies use the same instrumented copy;
 * this is not a benchmark, production candidate or general budget theorem. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int research_active;
static size_t research_service_calls, research_offered, research_queued, research_immediate;
static size_t research_destroyed, research_object_allocations, research_data_allocations;
static size_t research_data_resizes, research_requested_peak;
static void research_note_storage(void);
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RESEARCH_INSTRUMENTED
#error Use this fixture only with the research runner's instrumented copy.
#endif
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#include "memory-research-credit-relocation.h"

static void research_note_storage(void) {
    if (research_active && rc_bytes > research_requested_peak)
        research_requested_peak = rc_bytes;
}

static void clear(void) {
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    assert(!rc_frames && !rc_object_count && !rc_bytes);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_BOUNDED_HEAP
    assert(!minyar_pool_used);
#else
    assert(!rc_heap_allocation_count);
#endif
}

static void experiment(const char *label, int relocated, long long slots, int live_alias,
                       int view_alias, int self, int grow, int unicode, int unrelated_debt) {
    size_t length = unicode ? 6 : 32768;
    size_t capacity = grow ? length + 1 : self ? 131072 : 65536;
    unsigned char *storage = rc_allocate_data(capacity);
    if (unicode)
        memcpy(storage, "é🙂", 7);
    else {
        memset(storage, 'x', length);
        storage[length] = 0;
    }
    MinyarText *left = new_text(storage, (long long)length, unicode ? -1 : (long long)length);
    if (unicode)
        assert(minyar_text_length(left) == 2);
    MinyarText *right = self ? left : copy_c_text("!");
    MinyarText *view = view_alias ? minyar_text_slice(left, 0, (long long)length / 2) : NULL;
    if (live_alias)
        minyar_rc_retain(left);
    if (slots) {
        minyar_rc_enter(slots);
        minyar_rc_local(0, left);
        for (long long index = 1; index < slots; index++)
            minyar_rc_local_take(index, copy_c_text("retired"));
        minyar_rc_leave();
    }
    if (unrelated_debt)
        rc_drop(minyar_record_new(MINYAR_RC_POLL_BUDGET + 1));
    size_t physical = ((RcObject *)left - 1)->ownership >> 3;
    assert(physical == (size_t)(1 + live_alias + view_alias + !!slots));
    size_t pending = rc_pending_count, before = rc_bytes;
    uintptr_t old_header = (uintptr_t)left, old_backing = (uintptr_t)left->bytes;
    research_service_calls = research_offered = research_queued = research_immediate = 0;
    research_destroyed = research_object_allocations = research_data_allocations = 0;
    research_data_resizes = 0;
    research_requested_peak = before;
#ifdef MINYAR_BOUNDED_HEAP
    minyar_pool_high_water = minyar_pool_used;
#endif
    research_active = 1;
    MinyarText *result = research_credit_join(left, right, relocated);
    research_active = 0;
    size_t after = rc_bytes;
#ifdef MINYAR_BOUNDED_HEAP
    size_t charge_peak = minyar_pool_high_water;
#else
    size_t charge_peak = 0;
#endif
    int reused = (uintptr_t)result == old_header;
    assert(result->byte_length == (long long)(length * (self ? 2 : 1) + (self ? 0 : 1)));
    assert(research_destroyed <= research_queued + research_immediate);
    assert(research_offered + research_immediate <= 3 * MINYAR_RC_POLL_BUDGET);
    if (!slots && unrelated_debt) {
        assert(reused);
        assert(research_service_calls == (size_t)grow);
    } else if (live_alias || view_alias || slots > 3 * MINYAR_RC_POLL_BUDGET) {
        assert(!reused);
    } else {
        assert(reused == relocated);
    }
    if (live_alias) {
        assert(left->byte_length == (long long)length);
        for (size_t index = 0; index < length; index++)
            assert(left->bytes[index] == 'x');
    }
    if (view_alias) {
        assert(view->byte_length == (long long)length / 2);
        for (long long index = 0; index < view->byte_length; index++)
            assert(view->bytes[index] == 'x');
    }
    if (unicode) {
        assert(minyar_text_length(result) == 3);
        assert(minyar_text_character_at(result, 0) == 0xe9);
        assert(minyar_text_character_at(result, 1) == 0x1f642);
        assert(minyar_text_character_at(result, 2) == '!');
    } else {
        for (size_t index = 0; index < length; index++)
            assert(result->bytes[index] == 'x');
        if (self) {
            for (size_t index = length; index < length * 2; index++)
                assert(result->bytes[index] == 'x');
        } else {
            assert(result->bytes[length] == '!');
        }
    }
    printf("{\"case\":\"%s\",\"relocated\":%d,\"budget\":%u,\"physical_before\":%zu,"
           "\"pending_before\":%zu,\"header_reused\":%d,\"backing_reused\":%d,"
           "\"service_hooks\":%zu,\"offered_units\":%zu,\"queued_units\":%zu,"
           "\"immediate_units\":%zu,\"destructions\":%zu,\"object_allocations\":%zu,"
           "\"data_allocations\":%zu,\"data_resizes\":%zu,\"requested_before\":%zu,"
           "\"requested_after\":%zu,\"requested_peak\":%zu,\"pool_peak\":%zu,"
           "\"result_capacity\":%zu,\"copied_prefix_bytes\":%zu}\n",
           label, relocated, MINYAR_RC_POLL_BUDGET, physical, pending, reused,
           (uintptr_t)result->bytes == old_backing, research_service_calls, research_offered,
           research_queued, research_immediate, research_destroyed, research_object_allocations,
           research_data_allocations, research_data_resizes, before, after, research_requested_peak,
           charge_peak, ((RcData *)result->bytes - 1)->size, reused ? 0 : length);
    if (live_alias)
        minyar_rc_release(left);
    if (view_alias)
        minyar_rc_release(view);
    minyar_rc_release(result);
    if (!self)
        minyar_rc_release(right);
    clear();
}

int main(int argc, char **argv) {
    assert(argc == 2 && (!strcmp(argv[1], "baseline") || !strcmp(argv[1], "relocated")));
    int relocated = !strcmp(argv[1], "relocated");
    long long near = MINYAR_RC_POLL_BUDGET + 1, far = 4 * MINYAR_RC_POLL_BUDGET + 1;
    experiment("near-owner", relocated, near, 0, 0, 0, 0, 0, 0);
    experiment("far-owner", relocated, far, 0, 0, 0, 0, 0, 0);
    experiment("live-alias", relocated, near, 1, 0, 0, 0, 0, 0);
    experiment("live-view", relocated, near, 0, 1, 0, 0, 0, 0);
    experiment("self-rhs", relocated, near, 0, 0, 1, 0, 0, 0);
    experiment("reconciled-growth", relocated, near, 0, 0, 0, 1, 0, 0);
    experiment("indexed-unicode", relocated, near, 0, 0, 0, 0, 1, 0);
    experiment("already-unique-spare", relocated, 0, 0, 0, 0, 0, 0, 1);
    experiment("already-unique-grown", relocated, 0, 0, 0, 0, 1, 0, 1);
    return 0;
}
