/* Ownership/scheduler kernel probes. Private detachment creates the model's
 * queue state; explicit polls check actual destruction and task accounting. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

#ifndef MINYAR_BOUNDED_RC
#error These probes require incremental ownership.
#endif

static size_t poll_one(void) {
    size_t before = rc_object_count;
    size_t units = minyar_rc_poll(1);
    assert(units <= 1 && before - rc_object_count <= units);
    return units;
}

static void clear(void) {
    while (rc_pending_count)
        assert(poll_one() == 1);
    assert(!rc_frames && !rc_object_count && !rc_bytes);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
}

static MinyarText *make_view(void) {
    MinyarText *root = copy_c_text("αβγδεζηθ");
    MinyarText *view = minyar_text_slice(root, 1, 7);
    ensure_text_index(view);
    minyar_rc_release(root);
    assert(view->backing && minyar_text_character_at(view, 0) == 0x3b2);
    return view;
}

static void partial_chunk_view(void) {
    minyar_rc_enter(0);
    MinyarText *view = make_view();
    RcObject *root = (RcObject *)view->backing - 1;
    minyar_rc_keep(view);
    rc_bounded_retire_temporaries(rc_frames);
    assert(rc_pending_count == 1 && rc_object_count == 2);
    assert(rc_bounded_chunk_head->count == 1);
    assert(!rc_bounded_recent_head && !rc_bounded_head && !rc_bounded_active);
    assert(poll_one() == 1);
    assert(rc_pending_count == 2 && rc_object_count == 1);
    assert(!rc_bounded_chunk_head->count && rc_bounded_recent_head == root);
    assert(!(root->ownership >> 3));
    assert(poll_one() == 1);
    assert(rc_pending_count == 1 && !rc_object_count && !rc_bytes);
    assert(!rc_bounded_chunk_head->count);
    assert(poll_one() == 1);
    assert(!rc_pending_count && !rc_bounded_chunk_head);
    minyar_rc_leave();
    clear();
    puts("partial chunk/view: tasks 1->2->1->0, two separate destructions");
}

static void moved_sparse_slot(void) {
    minyar_rc_enter(3);
    MinyarText *caller = make_view();
    minyar_rc_local_take(0, caller);
    minyar_rc_local_move(0);
    assert(rc_frames->written_count == 1 && !rc_bounded_local_value(rc_frames, 0));
    size_t before = rc_object_count;
    minyar_rc_leave();
    assert(before == rc_object_count && rc_object_count == 2);
    while (rc_pending_count)
        assert(poll_one() == 1);
    assert(((RcObject *)caller - 1)->ownership >> 3 == 1);
    assert(minyar_text_character_at(caller, 4) == 0x3b6);
    before = rc_object_count;
    minyar_rc_release(caller);
    assert(before - rc_object_count <= rc_bounded_last_work);
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    clear();
    puts("moved sparse owner: null visit preserves caller and view root");
}

static void cached_capacity_cycle(void) {
    const long long declared[] = {9, 2, 9};
    RcFrame *cached = NULL;
    for (size_t step = 0; step < sizeof(declared) / sizeof(*declared); step++) {
        minyar_rc_enter(declared[step]);
        if (cached)
            assert(rc_frames == cached);
        assert(rc_frames->local_capacity == 9);
        minyar_rc_local_take(declared[step] - 1, make_view());
        assert(rc_frames->written_count == 1);
        cached = rc_frames;
        minyar_rc_leave();
        while (rc_pending_count)
            assert(poll_one() == 1);
        assert(!rc_object_count && !rc_bytes && rc_free_frames == cached);
    }
    clear();
    puts("cached capacity 9->2->9: stale sparse slots remain inert");
}

static void record_cursor_boundary(void) {
    static struct {
        RcObject owner;
        MinyarText text;
    } literal = {{RC_TEXT}, {(const unsigned char *)"immortal", 8, 8, NULL, NULL}};
    MinyarRecord *older = minyar_record_new(1000);
    MinyarRecord *record = minyar_record_new(130);
    for (long long field = 0; field < 130; field++) {
        if (field % 17 == 0)
            minyar_record_set_reference(record, field, (long long)(uintptr_t)&literal.text);
        else
            minyar_record_set_scalar(record, field, field * 37);
    }
    rc_drop(older);
    assert(poll_one() == 1);
    /* Prior probes deliberately preserve scheduler history. The newly queued
     * record needs 131 visits; its first turn determines one extra old visit. */
    size_t expected_polls = rc_bounded_recent_turn ? 261 : 262;
    rc_drop(record);
    int crossed = 0;
    size_t polls = 0;
    unsigned char *map = (unsigned char *)(record->values + record->length);
    while (rc_object_count == 2) {
        for (int field = 0; field < 130; field++)
            assert((map[field] & 1) == (field % 17 == 0));
        size_t cursor = rc_bounded_saved_cursor((RcObject *)record - 1);
        assert(cursor <= 130);
        if (cursor == 128)
            crossed = 1;
        assert(poll_one() == 1);
        assert(++polls <= 262);
    }
    assert(crossed && polls == expected_polls && rc_pending_count == 1);
    assert(rc_bounded_active == (RcObject *)older - 1);
    clear();
    assert(literal.owner.ownership == RC_TEXT);
    puts("recent record cursor crosses 127/128 with scalar/reference map flags intact");
}

int main(void) {
    partial_chunk_view();
    moved_sparse_slot();
    cached_capacity_cycle();
    record_cursor_boundary();
    return 0;
}
