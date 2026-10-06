/* Retained counterexample, now a regression for separately budgeted root cleanup.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#define MINYAR_RC_POLL_BUDGET 1
#include "../../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    MinyarText *root = copy_c_text("abcdef");
    MinyarText *view = minyar_text_slice(root, 1, 5);
    assert(view != root && view->backing == root);
    minyar_rc_release(root);
    assert(rc_object_count == 2);
    minyar_rc_release(view);
    size_t reported = rc_bounded_last_work;
    size_t remaining = rc_object_count;
    while (rc_pending_count) assert(minyar_rc_poll(1) == 1);
    printf("{\"budget\":%u,\"reported_work\":%zu,\"remaining_after_release\":%zu,\"final_objects\":%zu,\"final_bytes\":%zu}\n",
           MINYAR_RC_POLL_BUDGET, reported, remaining, rc_object_count, rc_bytes);
    assert(!rc_object_count && !rc_bytes && !rc_heap_allocation_count);
    /* A nonzero result marks a contract violation, not a memory leak. */
    assert(reported == 1 && remaining == 1);
    return reported > MINYAR_RC_POLL_BUDGET ? 1 : 0;
}
