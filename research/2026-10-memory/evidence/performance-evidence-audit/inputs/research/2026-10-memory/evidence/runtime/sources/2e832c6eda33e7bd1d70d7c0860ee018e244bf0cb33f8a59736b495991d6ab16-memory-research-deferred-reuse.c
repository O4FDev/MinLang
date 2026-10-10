/* Experimental comparison: a normal join versus explicit bounded service.
 * No runtime mechanism is changed. Logical owners are modeled independently. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static MinyarText *make_text(void) {
    enum { LENGTH = 32768, CAPACITY = 131072 };
    unsigned char *bytes = rc_allocate_data(CAPACITY);
    memset(bytes, 'x', LENGTH);
    bytes[LENGTH] = 0;
    return new_text(bytes, LENGTH, LENGTH);
}

static size_t service(size_t budget) {
#ifdef MINYAR_BOUNDED_RC
    size_t before = rc_object_count;
    size_t work = minyar_rc_poll(budget);
    assert(work <= budget && work <= MINYAR_RC_POLL_BUDGET);
    assert(before - rc_object_count <= work);
    return work;
#else
    (void)budget;
    return 0;
#endif
}

static void clear(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        service(1);
#endif
    assert(rc_object_count == 0 && rc_bytes == 0 && !rc_frames);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
#else
        free(frame->locals);
        free(frame->temporaries);
        free(frame);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_cached_frame_bytes = 0;
#endif
#ifdef MINYAR_SYSTEM_HEAP
    assert(rc_heap_allocation_count == 0);
#elif defined(MINYAR_BOUNDED_HEAP)
    assert(minyar_pool_used == 0);
#endif
}

static void experiment(const char *name, int pre_service, int live_alias, int view_alias,
                       int self_join, int deep_backlog, long long base_width) {
    MinyarText *left = make_text();
    MinyarText *right = self_join ? left : copy_c_text("!");
    MinyarText *view = view_alias ? minyar_text_slice(left, 0, 16384) : NULL;
    if (live_alias)
        minyar_rc_retain(left);
    const long long width = deep_backlog ? base_width * 2 - 1 : base_width;
    minyar_rc_enter(width);
    minyar_rc_local(0, left);
    for (long long i = 1; i < width; i++)
        minyar_rc_local_take(i, copy_c_text("retired"));
    minyar_rc_leave();
    size_t physical_before = ((RcObject *)left - 1)->ownership >> 3;
    size_t logical_owners = 1 + (size_t)live_alias + (size_t)view_alias;
    assert(physical_before >= logical_owners);
    size_t service_work = 0;
#ifdef MINYAR_BOUNDED_RC
    size_t pending_before = rc_pending_count;
    assert(physical_before == logical_owners + 1);
    if (pre_service)
        service_work = service(MINYAR_RC_POLL_BUDGET);
#else
    size_t pending_before = 0;
    assert(physical_before == logical_owners);
#endif
    size_t physical_after_service = ((RcObject *)left - 1)->ownership >> 3;
    size_t bytes_before_join = rc_bytes;
#ifdef MINYAR_BOUNDED_HEAP
    size_t pool_before = minyar_pool_used;
    minyar_pool_high_water = minyar_pool_used;
#else
    size_t pool_before = 0;
#endif
    MinyarText *result = minyar_join_text_take_left(left, right);
    int reused = result == left;
    long long expected_length = self_join ? 65536 : 32769;
    assert(result->byte_length == expected_length);
    for (long long i = 0; i < 32768; i++)
        assert(result->bytes[i] == 'x');
    if (self_join) {
        for (long long i = 32768; i < 65536; i++)
            assert(result->bytes[i] == 'x');
    } else {
        assert(result->bytes[32768] == '!');
    }
    if (live_alias || view_alias)
        assert(!reused);
    if (live_alias)
        assert(left->byte_length == 32768 && left->bytes[32767] == 'x');
    if (view_alias)
        assert(view->byte_length == 16384 && view->bytes[16383] == 'x');
#ifdef MINYAR_BOUNDED_HEAP
    size_t pool_peak = minyar_pool_high_water;
#else
    size_t pool_peak = 0;
#endif
    printf("{\"case\":\"%s\",\"pre_service\":%d,\"frame_slots\":%lld,\"logical_owners\":%zu,"
           "\"physical_before\":%zu,\"physical_after_service\":%zu,\"pending_tasks\":%zu,"
           "\"reused\":%d,\"copied_prefix_bytes\":%d,\"bytes_before_join\":%zu,\"bytes_after_"
           "join\":%zu,\"extra_service_work\":%zu,\"logical_payload_bytes\":32769,"
           "\"backing_capacity_bytes\":131072,\"pool_before_join\":%zu,\"pool_join_peak\":%zu}\n",
           name, pre_service, width, logical_owners, physical_before, physical_after_service,
           pending_before, reused, reused ? 0 : 32768, bytes_before_join, rc_bytes, service_work,
           pool_before, pool_peak);
    if (live_alias)
        minyar_rc_release(left);
    if (view_alias)
        minyar_rc_release(view);
    minyar_rc_release(result);
    if (!self_join)
        minyar_rc_release(right);
    clear();
}

int main(int argc, char **argv) {
    int pre_service = argc >= 2 && !strcmp(argv[1], "pre-service");
    long long width = argc == 3 ? strtoll(argv[2], NULL, 10) : 33;
    if (width < 33 || width > 256)
        return 2;
    experiment("retired-alias", pre_service, 0, 0, 0, 0, width);
    experiment("live-alias", pre_service, 1, 0, 0, 0, width);
    experiment("live-view", pre_service, 0, 1, 0, 0, width);
    experiment("self-borrow", pre_service, 0, 0, 1, 0, width);
    experiment("deep-retired-backlog", pre_service, 0, 0, 0, 1, width);
    return 0;
}
