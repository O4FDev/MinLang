#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include "../runtime/minyar_thread_buffers.h"
#include <assert.h>
static void assert_native_empty(void) {
    rc_thread_domain_drain();
    assert(!atomic_load(&rc_thread_native_bytes));
    assert(!atomic_load(&rc_thread_native_allocations));
    assert(!atomic_load(&rc_thread_transit_bytes));
    assert(!atomic_load(&rc_thread_transit_allocations));
}
static void aliases_and_capacity(void) {
    MinyarBytes *bytes = minyar_bytes_new(0);
    minyar_bytes_add(bytes, 42); /* Capacity 16, length 1. */
    MinyarBytes *alias = bytes;
    minyar_rc_retain(alias);
    MinyarRecord *record = minyar_record_new(1);
    minyar_record_set_reference(record, 0, (long long)(uintptr_t)bytes);
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    minyar_list_add(list, (long long)(uintptr_t)bytes);
    RcThreadLeaf *small = minyar_bytes_channel_new(15, 1);
    const unsigned char *payload = bytes->bytes;
    assert(!minyar_bytes_channel_try_send(small, bytes));
    assert(!minyar_bytes_channel_send(small, bytes)); /* Oversize cannot wait forever. */
    assert(bytes->bytes == payload && alias->byte_length == 1);
    minyar_rc_release(small);
    RcThreadLeaf *channel = minyar_bytes_channel_new(16, 1);
    size_t charge = sizeof(RcData) + ((RcData *)payload - 1)->size;
    size_t before = rc_bytes;
    assert(minyar_bytes_channel_try_send(channel, bytes));
    assert(rc_bytes == before - charge + sizeof(RcData) + 1);
    assert(atomic_load(&rc_thread_transit_bytes) == charge);
    assert(alias->byte_length == 0 && bytes->character_length == 0);
    assert(((MinyarBytes *)(uintptr_t)minyar_record_get(record, 0))->byte_length == 0);
    assert(((MinyarBytes *)(uintptr_t)minyar_list_get(list, 0))->byte_length == 0);
    minyar_bytes_add(bytes, 99); /* Reuse cannot alter detached payload. */
    assert(!minyar_bytes_channel_try_send(channel, bytes));
    MinyarBytes *destination = minyar_bytes_new(2);
    MinyarBytes *destination_alias = destination;
    minyar_rc_retain(destination_alias);
    assert(minyar_bytes_channel_try_receive(channel, destination) == 1);
    assert(destination->bytes == payload && destination_alias->byte_length == 1);
    assert(minyar_bytes_get(destination, 0) == 42);
    assert(!atomic_load(&rc_thread_transit_bytes));
    assert(minyar_bytes_channel_try_receive(channel, destination) == 0);
    assert(destination->bytes == payload);
    minyar_bytes_channel_close(channel);
    assert(!minyar_bytes_channel_try_send(channel, bytes));
    assert(bytes->byte_length == 1 && minyar_bytes_get(bytes, 0) == 99);
    assert(minyar_bytes_channel_try_receive(channel, destination) == 2);
    assert(!minyar_bytes_channel_receive(channel, destination));
    assert(destination->bytes == payload);
    minyar_rc_release(channel);
    minyar_rc_release(destination_alias);
    minyar_rc_release(destination);
    minyar_rc_release(alias);
    minyar_rc_release(list);
    minyar_rc_release(record);
    minyar_rc_release(bytes);
    assert_native_empty();

    bytes = minyar_bytes_new(0);
    channel = minyar_bytes_channel_new(0, 2);
    destination = minyar_bytes_new(5);
    assert(minyar_bytes_channel_try_send(channel, bytes));
    assert(minyar_bytes_channel_try_send(channel, bytes));
    assert(!minyar_bytes_channel_try_send(channel, bytes));
    minyar_bytes_channel_close(channel);
    assert(minyar_bytes_channel_try_receive(channel, destination) == 1);
    assert(destination->byte_length == 0);
    assert(minyar_bytes_channel_try_receive(channel, destination) == 1);
    assert(minyar_bytes_channel_try_receive(channel, destination) == 2);
    minyar_rc_release(channel);
    minyar_rc_release(destination);
    minyar_rc_release(bytes);
    assert_native_empty();

    bytes = minyar_bytes_new(8);
    alias = bytes;
    minyar_rc_retain(alias);
    payload = bytes->bytes;
    RcThreadLeaf *frozen = minyar_frozen_bytes_take(bytes);
    assert(((RcData *)payload - 1) == rc_frozen(frozen)->buffer.data);
    assert(alias->byte_length == 0);
    MinyarBytes *copy = minyar_frozen_bytes_local_copy(frozen);
    assert(copy->bytes != payload && copy->byte_length == 8);
    minyar_rc_release(frozen);
    minyar_rc_release(copy);
    minyar_rc_release(alias);
    minyar_rc_release(bytes);
    assert_native_empty();
}

int main(void) {
    rc_thread_domain_init();
    aliases_and_capacity();
    rc_thread_domain_dispose();
    assert(!rc_object_count && !rc_bytes);
    puts("native frozen buffer and bounded channel ownership passed");
}
