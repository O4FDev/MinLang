/* Count actual object destruction independently of the reported work counter. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#include <assert.h>

static void bounded(size_t before) {
    assert(rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    assert(before - rc_object_count <= rc_bounded_last_work);
}
static void drain(void) {
    while (rc_pending_count) {
        size_t before = rc_object_count;
        assert(minyar_rc_poll(1) == 1);
        assert(before - rc_object_count <= 1);
    }
}
static MinyarText *view(void) {
    MinyarText *root = copy_c_text("αβγδεζηθ");
    MinyarText *result = minyar_text_slice(root, 1, 7);
    ensure_text_index(result);
    assert(result->backing == root && !root->backing);
    minyar_rc_release(root);
    return result;
}
static void clear(void) {
    drain();
    assert(!rc_frames && !rc_object_count && !rc_bytes);
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames;
        rc_free_frames = f->previous;
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
}
int main(void) {
    MinyarText *v = view();
    size_t before = rc_object_count;
    minyar_rc_release(v); bounded(before);
    if (MINYAR_RC_POLL_BUDGET == 1) {
        assert(rc_object_count == 1 && rc_pending_count == 1);
        assert(rc_bounded_last_work == 1);
    }
    clear();

    /* Nested slices flatten to the owning root; a live alias must survive. */
    v = view();
    MinyarText *alias = minyar_text_slice(v, 1, 4);
    assert(alias->backing == v->backing);
    before = rc_object_count;
    minyar_rc_release(v); bounded(before);
    assert(minyar_text_length(alias) == 3);
    before = rc_object_count;
    minyar_rc_release(alias); bounded(before); clear();

    MinyarList *list = minyar_list_new(); minyar_list_references(list);
    minyar_list_add_take(list, (long long)(uintptr_t)view());
    before = rc_object_count;
    minyar_list_set_take(list, 0, 0); bounded(before);
    minyar_rc_release(list); clear();

    minyar_rc_enter(1);
    minyar_rc_local_take(0, view());
    before = rc_object_count;
    minyar_rc_local_take(0, NULL); bounded(before);
    minyar_rc_leave(); clear();

    minyar_rc_enter(3);
    for (int i = 0; i < 3; i++) minyar_rc_local_take(i, view());
    for (int i = 0; i < 17; i++) minyar_rc_keep(view());
    before = rc_object_count;
    minyar_rc_step(); bounded(before);
    before = rc_object_count;
    minyar_rc_leave(); bounded(before); clear();

    uint64_t header[8], storage[2];
    minyar_rc_enter_stack_v1(header, storage, 1);
    minyar_rc_local_take(0, view());
    before = rc_object_count;
    minyar_rc_leave_stack_v1(header); bounded(before); clear();

    /* Both recent and captured objects can be fieldless Text tasks. */
    MinyarRecord *older = minyar_record_new(64);
    v = view(); alias = view();
    rc_drop(older);
    assert(minyar_rc_poll(1) == 1);
    assert(rc_bounded_active == (RcObject *)older - 1);
    assert(rc_drop(v) == 1 && rc_drop(alias) == 1);
    drain(); clear();
    puts("Text-view release, aliases, replacement, frame/chunk/stack retirement obey actual destruction budgets");
}
