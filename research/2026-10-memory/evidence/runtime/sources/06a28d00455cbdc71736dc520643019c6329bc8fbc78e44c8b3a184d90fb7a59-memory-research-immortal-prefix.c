/* Quantify task count versus remaining field work after List promotion.
 * The immutable prefix contains no mortal ownership edges. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

#ifndef MINYAR_BOUNDED_RC
#error This fixture measures incremental retirement.
#endif

static struct {
    RcObject owner;
    MinyarText text;
} literal = {{RC_TEXT}, {(const unsigned char *)"immutable", 9, 9, NULL, NULL}};

static void experiment(long long prefix, int promote) {
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    for (long long i = 0; i < prefix; i++)
        minyar_list_add(list, i % 2 ? 0 : (long long)(uintptr_t)&literal.text);
    assert((((RcObject *)list - 1)->ownership & 7) == RC_REFERENCES_IMMORTAL);
    if (promote) {
        unsigned char *bytes = new_bytes(32768);
        memset(bytes, 'x', 32768);
        bytes[32768] = 0;
        minyar_list_add_take(list, (long long)(uintptr_t)new_text(bytes, 32768, 32768));
        assert((((RcObject *)list - 1)->ownership & 7) == RC_REFERENCES);
    }
    size_t requested_before = rc_bytes;
    minyar_rc_release(list);
    size_t initial_work = rc_bounded_last_work;
    size_t tasks_after_release = rc_pending_count;
    size_t retained_after_release = rc_bytes;
    size_t work = initial_work, polls = 0;
    while (rc_pending_count) {
        size_t objects = rc_object_count;
        size_t units = minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(units > 0 && units <= MINYAR_RC_POLL_BUDGET);
        assert(objects - rc_object_count <= units);
        work += units;
        polls++;
    }
    assert(work == (size_t)(promote ? prefix + 2 : 1));
    assert(!rc_object_count && !rc_bytes && literal.owner.ownership == RC_TEXT);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
    printf("{\"prefix_fields\":%lld,\"promoted\":%d,\"tasks_after_release\":%zu,"
           "\"requested_before\":%zu,\"retained_after_release\":%zu,"
           "\"total_work\":%zu,\"followup_polls\":%zu}\n",
           prefix, promote, tasks_after_release, requested_before, retained_after_release, work,
           polls);
}

int main(void) {
    const long long lengths[] = {0, 7, 63, 1023, 16383, 65534};
    for (size_t i = 0; i < sizeof(lengths) / sizeof(*lengths); i++) {
        experiment(lengths[i], 0);
        experiment(lengths[i], 1);
    }
    return 0;
}
