/* Reserve one output-sized region except a retired object in its upper half
 * and one independent result-header slot. Original geometric growth can use
 * the lower free region while paying cleanup; direct reservation cannot. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES 65536
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#include <assert.h>

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    const long long length = MINYAR_RC_POLL_BUDGET == 1 ? 127 : 511;
    const size_t target = MINYAR_RC_POLL_BUDGET == 1 ? 2048 : 8192;
    const size_t base = 32768;
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, i * 37);
    enum { MAX_FILLERS = MINYAR_BOUNDED_HEAP_BYTES / MINYAR_POOL_MINIMUM };
    void *fillers[MAX_FILLERS];
    size_t count = 0;
    void *next;
    while ((next = minyar_pool_try_allocate(32))) {
        assert(count < MAX_FILLERS);
        fillers[count++] = next;
    }
    assert(minyar_pool_used == MINYAR_POOL_BYTES);
    size_t header_hole = SIZE_MAX;
    for (size_t i = 0; i < count; i++) {
        size_t offset = pool_offset(fillers[i]);
        if (offset >= base && offset < base + target) {
            minyar_pool_deallocate(fillers[i]);
            fillers[i] = NULL;
        } else if (offset == MINYAR_POOL_BYTES - 32) {
            header_hole = i;
        }
    }
    assert(header_hole != SIZE_MAX);
    long long fields = 2 * MINYAR_RC_POLL_BUDGET;
    size_t requested = sizeof(RcObject) + sizeof(MinyarRecord) + (size_t)fields * 9;
    size_t debt_block = 32;
    while (debt_block < requested)
        debt_block *= 2;
    void *guard = minyar_pool_allocate(debt_block);
    assert(pool_offset(guard) == base);
    MinyarRecord *debt = minyar_record_new(fields);
    assert(pool_offset((RcObject *)debt - 1) == base + debt_block);
    minyar_pool_deallocate(guard);
    minyar_pool_deallocate(fillers[header_hole]);
    fillers[header_hole] = NULL;
    rc_drop(debt);
    assert(rc_pending_count == 1);
    printf("before: budget=%u fields=%lld pending=%zu pool_used=%zu target=%zu\n",
           MINYAR_RC_POLL_BUDGET, fields, rc_pending_count, minyar_pool_used, target);
    MinyarList *result = minyar_list_appended(source, 313, 0, 0);
    assert(result->length == length + 1 && result->values[length] == 313);
    for (long long i = 0; i < length; i++)
        assert(result->values[i] == source->values[i]);
    printf("success: pending=%zu pool_used=%zu capacity=%lld\n", rc_pending_count, minyar_pool_used,
           result->capacity);
    minyar_rc_release(source);
    minyar_rc_release(result);
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    for (size_t i = 0; i < count; i++)
        minyar_pool_deallocate(fillers[i]);
    assert(rc_object_count == 0 && rc_bytes == 0 && minyar_pool_used == 0);
    puts("contents and complete pool recovery verified");
    return 0;
}
