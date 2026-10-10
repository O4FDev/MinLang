/* Instrument only the generated workload's final joins. Earlier construction
 * joins keep the normal policy so the test-only poll cannot alter its setup. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#define minyar_join_text_take_left research_join_take_left
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#undef minyar_join_text_take_left

MinyarText *minyar_join_text_take_left(MinyarText *left, const MinyarText *right) {
    int selected =
        left->byte_length == 32768 && (right->byte_length == 1 || right->byte_length == 32768);
    if (!selected)
        return research_join_take_left(left, right);
    size_t physical_before = ((RcObject *)left - 1)->ownership >> 3;
    uintptr_t old_header = (uintptr_t)left;
    uintptr_t old_backing = (uintptr_t)left->bytes;
    long long right_length = right->byte_length;
    size_t extra_work = 0;
#ifdef MINYAR_BOUNDED_RC
    size_t pending = rc_pending_count;
    if (getenv("MINYAR_RESEARCH_PRE_SERVICE") && rc_pending_count)
        extra_work = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
    size_t pending = 0;
#endif
    size_t physical_after = ((RcObject *)left - 1)->ownership >> 3;
    size_t before_bytes = rc_bytes;
    MinyarText *result = research_join_take_left(left, right);
    fprintf(stderr,
            "{\"left_bytes\":32768,\"right_bytes\":%lld,\"physical_before\":%zu,"
            "\"physical_after_service\":%zu,\"pending_tasks\":%zu,\"extra_work\":%zu,"
            "\"header_reused\":%d,\"backing_reused\":%d,\"requested_before\":%zu,"
            "\"requested_after\":%zu,\"result_capacity\":%zu}\n",
            right_length, physical_before, physical_after, pending, extra_work,
            (uintptr_t)result == old_header, (uintptr_t)result->bytes == old_backing, before_bytes,
            rc_bytes, ((RcData *)result->bytes - 1)->size);
    return result;
}
