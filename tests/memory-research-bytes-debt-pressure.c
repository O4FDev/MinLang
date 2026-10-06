/* Debt created after an idle capacity choice can distinguish policies that
 * skip a later growth service point. The final request is public fileExists. */
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
    MinyarBytes *bytes = minyar_bytes_new(0);
    for (int i = 0; i < 16; i++)
        minyar_bytes_add(bytes, i * 7);
    RcData *data = (RcData *)bytes->bytes - 1;
    assert(pool_allocated_order(data) == 0 && !(pool_offset(data) & 63));
    MinyarRecord *debt = minyar_record_new(64);
    assert(pool_block_size(pool_allocated_order((RcObject *)debt - 1)) == 1024);
    enum { MAX_FILLERS = MINYAR_BOUNDED_HEAP_BYTES / MINYAR_POOL_MINIMUM };
    void *fillers[MAX_FILLERS];
    size_t count = 0;
    void *next;
    while ((next = minyar_pool_try_allocate(32))) {
        assert(count < MAX_FILLERS);
        fillers[count++] = next;
    }
    assert(minyar_pool_used == MINYAR_POOL_BYTES);
    size_t released = 0;
    for (size_t i = 0; i < count; i++) {
        if (pool_offset(fillers[i]) == pool_offset(data) + 32) {
            minyar_pool_deallocate(fillers[i]);
            fillers[i] = NULL;
            released++;
        }
    }
    assert(released == 1 && minyar_pool_used == MINYAR_POOL_BYTES - 32);
    rc_drop(debt);
    for (int field = 0; field < 64; field++)
        assert(minyar_rc_poll(1) == 1);
    assert(rc_pending_count == 1 && rc_bounded_active == (RcObject *)debt - 1);
    assert(rc_bounded_cursor == 64);
    printf("before append: length=%lld capacity=%lld pending=%zu pool_used=%zu\n",
           bytes->byte_length, bytes->character_length, rc_pending_count, minyar_pool_used);
    minyar_bytes_add(bytes, 171);
    for (int i = 0; i < 16; i++)
        assert(minyar_bytes_get(bytes, i) == i * 7);
    assert(minyar_bytes_get(bytes, 16) == 171);
    printf("before fileExists: capacity=%lld pending=%zu objects=%zu pool_used=%zu\n",
           bytes->character_length, rc_pending_count, rc_object_count, minyar_pool_used);

    static unsigned char path_bytes[1024];
    memset(path_bytes, 'x', sizeof(path_bytes) - 1);
    static struct {
        RcObject owner;
        MinyarText text;
    } path = {{RC_TEXT}, {path_bytes, 1023, 1023, NULL, NULL}};
    /* A nonexistent overlong component fails fopen normally. Converting its
     * existing Text to a C path needs exactly one raw 1024-byte pool block. */
    assert(!minyar_file_exists(&path.text));
    minyar_rc_release(bytes);
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    for (size_t i = 0; i < count; i++)
        minyar_pool_deallocate(fillers[i]);
    assert(!rc_object_count && !rc_bytes && !minyar_pool_used);
    puts("public fileExists succeeds and complete pool recovery verified");
    return 0;
}
