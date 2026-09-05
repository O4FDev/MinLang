/* Capacity correctness: a modest scalar List must fit the selected finite
 * heap; headers must not double every rounded backing allocation. */
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES (8u * 1024u * 1024u)
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

int main(void) {
    MinyarList *values = minyar_list_new();
    for (long long i = 0; i < 300000; i++) minyar_list_add(values, i * 3);
    for (long long i = 0; i < values->length; i++) assert(values->values[i] == i * 3);
    size_t backing_size = sizeof(RcData) + (size_t)values->capacity * sizeof(long long);
    assert((backing_size & (backing_size - 1)) == 0);
    assert(values->capacity == 524287);
    minyar_rc_release(values);
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET));
    assert(rc_object_count == 0 && rc_bytes == 0 && minyar_pool_used == 0);
    puts("bounded List capacity, contents and complete recovery verified");
}
