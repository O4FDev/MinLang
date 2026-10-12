/* Actual shared backing, transfer ledgers, blocked operations and exit tests.
 * Only test-native shares/coordination cross C threads; shells always local. */
#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>
#include "thread-test-host.h"

static RcTestGate readers;
static const unsigned char *expected_payload;
static RcFrozenBytes *expected_control;
static long long reader(long long seed, void *frozen_pointer, void *channel) {
    (void)channel;
    RcThreadLeaf *frozen = frozen_pointer;
    assert(rc_frozen(frozen) == expected_control);
    assert((const unsigned char *)(rc_frozen(frozen)->buffer.data + 1) == expected_payload);
    rc_test_gate_arrive(&readers);
    minyar_rc_enter(2);
    MinyarText *literal = minyar_thread_text_literal(&(MinyarText){
        .bytes = (const unsigned char *)"λ🐈", .byte_length = 6});
    minyar_rc_local_take(0, literal);
    assert(minyar_text_length(literal) == 2);
    MinyarText *view = minyar_text_slice(literal, 1, 2);
    minyar_rc_local_take(1, view);
    assert(minyar_text_length(view) == 1);
    assert(minyar_text_character_at(view, 0) == 0x1f408);
    MinyarText *integer = minyar_integer_text(7);
    minyar_rc_release(integer);
    (void)minyar_character_text('x');
#ifdef MINYAR_TEST_CYCLES
    MinyarRecord *cycle = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(cycle, 0, (long long)(uintptr_t)cycle);
    minyar_record_set_reference_traced(cycle, 1, (long long)(uintptr_t)frozen);
    minyar_rc_release(cycle);
#endif
    long long sum = seed;
    for (unsigned round = 0; round < 1000; round++)
        for (long long i = 0; i < minyar_frozen_bytes_length(frozen); i++)
            sum += minyar_frozen_bytes_get_uint8(frozen, i);
    minyar_rc_leave();
    return sum;
}
static void assert_native_empty(void) {
    rc_thread_domain_drain();
    assert(!atomic_load(&rc_thread_native_bytes));
    assert(!atomic_load(&rc_thread_native_allocations));
    assert(!atomic_load(&rc_thread_transit_bytes));
    assert(!atomic_load(&rc_thread_transit_allocations));
}
static void sharing(void) {
    MinyarBytes *b = minyar_bytes_new(8);
    minyar_bytes_set_int64(b, 0, 42);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    assert(b->byte_length == 8);
    assert(minyar_frozen_bytes_get_int64(f, 0) == 42);
    expected_control = rc_frozen(f);
    expected_payload = (const unsigned char *)(expected_control->buffer.data + 1);
    assert(expected_payload != b->bytes);
    minyar_bytes_set(b, 0, 7);
    RcThreadLeaf *channel = minyar_bytes_channel_new(64, 2);
    rc_test_gate_init(&readers, 4);
    RcThreadLeaf *threads[4];
    size_t destroyed = atomic_load(&rc_thread_frozen_destructions);
    for (int i = 0; i < 4; i++) threads[i] = minyar_thread_spawn(reader, i, f, channel);
    minyar_rc_release(f);
    minyar_rc_release(b);
    for (int i = 0; i < 4; i++) {
        assert(minyar_thread_join(threads[i]) == i + 42000);
        assert(minyar_thread_join(threads[i]) == i + 42000);
        minyar_rc_release(threads[i]);
    }
    minyar_thread_join_children();
    assert(atomic_load(&rc_thread_frozen_destructions) == destroyed + 1);
    minyar_rc_release(channel);
    rc_test_gate_dispose(&readers);
    assert_native_empty();
}
static RcFrozenBytes *created;
static void creator(void *unused) {
    (void)unused;
    rc_thread_domain_init();
    MinyarBytes *bytes = minyar_bytes_new(8);
    minyar_bytes_set_int64(bytes, 0, 42);
    const unsigned char *payload = bytes->bytes;
    RcThreadLeaf *f = minyar_frozen_bytes_take(bytes);
    created = f->control;
    assert((const unsigned char *)(created->buffer.data + 1) == payload);
    rc_thread_control_retain(created); /* Native handoff share; no foreign RC. */
    minyar_rc_release(f);
    minyar_rc_release(bytes);
    rc_thread_domain_dispose();
}
static void creator_exit(void) {
    rc_test_join(rc_test_start(creator, NULL)); /* Creator OS thread has exited. */
    RcThreadLeaf *f = rc_thread_wrap(created);
    expected_control = created;
    expected_payload = (const unsigned char *)(created->buffer.data + 1);
    RcThreadLeaf *channel = minyar_bytes_channel_new(0, 1);
    rc_test_gate_init(&readers, 4);
    RcThreadLeaf *threads[4];
    size_t destroyed = atomic_load(&rc_thread_frozen_destructions);
    for (int i = 0; i < 4; i++) threads[i] = minyar_thread_spawn(reader, i, f, channel);
    minyar_rc_release(f);
    for (int i = 0; i < 4; i++) {
        assert(minyar_thread_join(threads[i]) == i + 42000);
        minyar_rc_release(threads[i]);
    }
    minyar_thread_join_children();
    assert(atomic_load(&rc_thread_frozen_destructions) == destroyed + 1);
    minyar_rc_release(channel);
    rc_test_gate_dispose(&readers);
    assert_native_empty();
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

enum { MESSAGES = 1000, PRODUCERS = 2 };
static _Atomic unsigned seen[MESSAGES * PRODUCERS];
static long long producer(long long seed, void *frozen, void *channel) {
    (void)frozen;
    for (int i = 0; i < MESSAGES; i++) {
        MinyarBytes *b = minyar_bytes_new(8);
        minyar_bytes_set_int64(b, 0, seed * MESSAGES + i);
        assert(minyar_bytes_channel_send(channel, b));
        assert(b->byte_length == 0);
        minyar_rc_release(b);
    }
    return MESSAGES;
}
static long long consumer(long long seed, void *frozen, void *channel) {
    (void)seed; (void)frozen;
    MinyarBytes *b = minyar_bytes_new(0);
    long long count = 0;
    while (minyar_bytes_channel_receive(channel, b)) {
        long long message = minyar_bytes_get_int64(b, 0);
        assert(message >= 0 && message < MESSAGES * PRODUCERS);
        assert(atomic_fetch_add(&seen[message], 1) == 0);
        count++;
    }
    minyar_rc_release(b);
    return count;
}
static void backpressure(void) {
    MinyarBytes *empty = minyar_bytes_new(0);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(empty);
    RcThreadLeaf *c = minyar_bytes_channel_new(16, 2);
    RcThreadLeaf *p[2], *r[2];
    for (unsigned i = 0; i < MESSAGES * PRODUCERS; i++) atomic_store(&seen[i], 0);
    for (int i = 0; i < 2; i++) r[i] = minyar_thread_spawn(consumer, 0, f, c);
    for (int i = 0; i < 2; i++) p[i] = minyar_thread_spawn(producer, i, f, c);
    for (int i = 0; i < 2; i++) assert(minyar_thread_join(p[i]) == MESSAGES);
    minyar_bytes_channel_close(c);
    assert(minyar_thread_join(r[0]) + minyar_thread_join(r[1]) == MESSAGES * PRODUCERS);
    for (unsigned i = 0; i < MESSAGES * PRODUCERS; i++) assert(atomic_load(&seen[i]) == 1);
    for (int i = 0; i < 2; i++) { minyar_rc_release(p[i]); minyar_rc_release(r[i]); }
    minyar_rc_release(f);
    minyar_rc_release(c);
    minyar_rc_release(empty);
    minyar_thread_join_children();
    assert_native_empty();
}
static long long no_work(long long seed, void *frozen, void *channel) {
    (void)frozen; (void)channel;
    return seed;
}
static long long self_join(long long seed, void *frozen, void *channel) {
    (void)seed; (void)frozen; (void)channel;
    RcThreadLeaf *self = rc_thread_wrap(rc_thread_current);
    rc_thread_control_retain(rc_thread_current);
    long long output = 123;
    assert(minyar_thread_try_join(self, &output) == 1 && output == 123);
    MinyarRecord *r = minyar_thread_join_result(self);
    assert(minyar_record_get(r, 0) == 1 && minyar_record_get(r, 1) == 0);
    minyar_rc_release(r);
    minyar_rc_release(self);
    return 17;
}
static void failures_and_results(void) {
    MinyarBytes *b = minyar_bytes_new(0);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    RcThreadLeaf *c = minyar_bytes_channel_new(0, 1);
    void *output = b;
    size_t native_before = atomic_load(&rc_thread_native_bytes);
    size_t frozen_before = atomic_load(&rc_frozen(f)->owner.strong);
    rc_thread_test_fail_start = 1;
    assert(minyar_thread_try_spawn(no_work, 0, f, c, &output) == 2 && output == b);
    MinyarRecord *failed = minyar_thread_spawn_result(no_work, 0, f, c);
    assert(minyar_record_get(failed, 0) == 2 && !minyar_record_get(failed, 1));
    minyar_rc_release(failed);
    assert(atomic_load(&rc_thread_native_bytes) == native_before);
    assert(atomic_load(&rc_frozen(f)->owner.strong) == frozen_before);
    rc_thread_test_fail_start = 0;
    MinyarRecord *started = minyar_thread_spawn_result(self_join, 0, f, c);
    assert(minyar_record_get(started, 0) == 0);
    RcThreadLeaf *thread = minyar_thread_start_result_value(started);
    minyar_rc_release(started);
    long long unchanged = 313;
    rc_thread_test_fail_join = 1;
    assert(minyar_thread_try_join(thread, &unchanged) == 2 && unchanged == 313);
    MinyarRecord *join_failed = minyar_thread_join_result(thread);
    assert(minyar_thread_result_code(join_failed) == 2);
    minyar_rc_release(join_failed);
    rc_thread_test_fail_join = 0;
    MinyarRecord *joined = minyar_thread_join_result(thread);
    assert(minyar_record_get(joined, 0) == 0 && minyar_record_get(joined, 1) == 17);
    minyar_rc_release(joined);
    minyar_rc_release(thread);
    /* Dropped wrappers retain neither a detached frame nor a running hazard. */
    thread = minyar_thread_spawn(no_work, 91, f, c);
    minyar_rc_release(thread);
    minyar_thread_join_children();
    minyar_rc_release(c);
    minyar_rc_release(f);
    minyar_rc_release(b);
    assert_native_empty();
}
static long long nested(long long seed, void *frozen, void *channel) {
    RcThreadLeaf *child = minyar_thread_spawn(no_work, seed + 1, frozen, channel);
    minyar_rc_release(child);
    return seed;
}
static void descendants(void) {
    MinyarBytes *b = minyar_bytes_new(0);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    RcThreadLeaf *c = minyar_bytes_channel_new(0, 1);
    size_t before = atomic_load(&rc_thread_domain_exits);
    RcThreadLeaf *t = minyar_thread_spawn(nested, 29, f, c);
    assert(minyar_thread_join(t) == 29);
    assert(atomic_load(&rc_thread_domain_exits) == before + 2);
    minyar_rc_release(t);
    minyar_thread_join_children();
    minyar_rc_release(c); minyar_rc_release(f); minyar_rc_release(b);
    assert_native_empty();
}

static long long frozen_publisher(long long seed, void *input, void *channel) {
    (void)input;
    MinyarBytes *b = minyar_bytes_new(8);
    minyar_bytes_set_int64(b, 0, seed);
    expected_payload = b->bytes;
    RcThreadLeaf *f = minyar_frozen_bytes_take(b);
    expected_control = f->control;
    assert(minyar_frozen_channel_send(channel, f));
    assert(b->byte_length == 0);
    minyar_rc_release(f);
    minyar_rc_release(b);
    return seed;
}
static void frozen_forwarding(void) {
    MinyarBytes *empty = minyar_bytes_new(0);
    RcThreadLeaf *seed = minyar_frozen_bytes_copy(empty);
    RcThreadLeaf *c = minyar_frozen_channel_new(8, 1);
    MinyarRecord *r = minyar_frozen_channel_try_receive(c);
    assert(minyar_frozen_result_code(r) == 1);
    minyar_rc_release(r);
    RcThreadLeaf *creator_thread = minyar_thread_spawn(frozen_publisher, 42, seed, c);
    assert(minyar_thread_join(creator_thread) == 42);
    minyar_rc_release(creator_thread);
    minyar_thread_join_children(); /* Creator is fully joined before any reader. */
    r = minyar_frozen_channel_receive(c);
    assert(minyar_frozen_result_code(r) == 0);
    RcThreadLeaf *f = minyar_frozen_result_value(r);
    minyar_rc_release(r); /* Owned getter must protect f. */
    assert(rc_frozen(f) == expected_control);
    assert((const unsigned char *)(rc_frozen(f)->buffer.data + 1) == expected_payload);
    rc_test_gate_init(&readers, 4);
    RcThreadLeaf *threads[4];
    for (int i = 0; i < 4; i++) threads[i] = minyar_thread_spawn(reader, i, f, c);
    minyar_rc_release(f);
    for (int i = 0; i < 4; i++) {
        assert(minyar_thread_join(threads[i]) == i + 42000);
        minyar_rc_release(threads[i]);
    }
    minyar_thread_join_children();
    rc_test_gate_dispose(&readers);
    /* Duplicate shares fill capacity/count without mutating source aliases. */
    assert(minyar_frozen_channel_try_send(c, seed));
    assert(!minyar_frozen_channel_try_send(c, seed));
    minyar_frozen_channel_close(c);
    assert(!minyar_frozen_channel_try_send(c, seed));
    r = minyar_frozen_channel_try_receive(c);
    assert(minyar_frozen_result_code(r) == 0);
    f = minyar_frozen_result_value(r);
    assert(rc_frozen(f) == rc_frozen(seed));
    minyar_rc_release(f);
    minyar_rc_release(r);
    r = minyar_frozen_channel_receive(c);
    assert(minyar_frozen_result_code(r) == 2);
    minyar_rc_release(r);
    minyar_rc_release(c);
    minyar_rc_release(seed);
    minyar_rc_release(empty);
    assert_native_empty();
}
static long long bytes_publisher(long long seed, void *input, void *channel) {
    (void)input;
    MinyarBytes *b = minyar_bytes_new(8);
    minyar_bytes_set_int64(b, 0, seed);
    expected_payload = b->bytes;
    assert(minyar_bytes_channel_send(channel, b));
    minyar_rc_release(b);
    return seed;
}
static void queued_creator_exit(void) {
    MinyarBytes *b = minyar_bytes_new(0);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    RcThreadLeaf *c = minyar_bytes_channel_new(8, 1);
    RcThreadLeaf *t = minyar_thread_spawn(bytes_publisher, 72, f, c);
    assert(minyar_thread_join(t) == 72);
    minyar_rc_release(t);
    minyar_thread_join_children();
    assert(atomic_load(&rc_thread_transit_allocations) == 1);
    assert(minyar_bytes_channel_receive(c, b));
    assert(b->bytes == expected_payload && minyar_bytes_get_int64(b, 0) == 72);
    assert(!atomic_load(&rc_thread_transit_allocations));
    assert(minyar_bytes_channel_try_send(c, b));
    minyar_bytes_channel_close(c);
    minyar_rc_release(c); /* Unread message frees raw prefixed allocation. */
    minyar_rc_release(f); minyar_rc_release(b);
    assert_native_empty();
}
static long long closed_waiter(long long send, void *input, void *channel) {
    (void)input;
    RcBytesChannel *c = ((RcThreadLeaf *)channel)->control;
    if (c->transport == RC_CHANNEL_FROZEN) {
        if (send) assert(!minyar_frozen_channel_send(channel, input));
        else {
            MinyarRecord *r = minyar_frozen_channel_receive(channel);
            assert(minyar_frozen_result_code(r) == 2);
            minyar_rc_release(r);
        }
    } else {
        MinyarBytes *b = minyar_bytes_new(8);
        const unsigned char *payload = b->bytes;
        if (send) assert(!minyar_bytes_channel_send(channel, b));
        else assert(!minyar_bytes_channel_receive(channel, b));
        assert(b->bytes == payload && b->byte_length == 8);
        minyar_rc_release(b);
    }
    return 1;
}
static void wait_for_channel_waiter(RcThreadLeaf *channel) {
    RcBytesChannel *c = channel->control;
    rc_thread_mutex_lock(&c->mutex);
    while (!c->waiters) rc_thread_condition_wait(&c->changed, &c->mutex);
    rc_thread_mutex_unlock(&c->mutex);
}
static void closure_waiters(void) {
    for (int frozen = 0; frozen < 2; frozen++) for (int send = 0; send < 2; send++) {
        MinyarBytes *b = minyar_bytes_new(8);
        RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
        RcThreadLeaf *c = frozen ? minyar_frozen_channel_new(8, 1) : minyar_bytes_channel_new(8, 1);
        if (send) {
            if (frozen) assert(minyar_frozen_channel_try_send(c, f));
            else assert(minyar_bytes_channel_try_send(c, b));
        }
        RcThreadLeaf *t = minyar_thread_spawn(closed_waiter, send, f, c);
        wait_for_channel_waiter(c);
        assert(atomic_load(&((RcBytesChannel *)c->control)->owner.strong) >= 3);
        minyar_rc_release(t); /* Running + registry shares survive dropped handle. */
        if (frozen) minyar_frozen_channel_close(c);
        else minyar_bytes_channel_close(c);
        minyar_rc_release(c); minyar_rc_release(f); minyar_rc_release(b);
        minyar_thread_join_children();
        assert_native_empty();
    }
}
static RcTestGate held_worker, joiners_started;
static _Atomic unsigned joined_waiters;
static long long held_entry(long long seed, void *frozen, void *channel) {
    (void)frozen; (void)channel;
    rc_test_gate_arrive(&held_worker);
    return seed;
}
static void join_waiter(void *native) {
    rc_thread_domain_init();
    RcThreadLeaf *t = rc_thread_wrap(native); /* Pre-retained native share. */
    rc_test_gate_arrive(&joiners_started);
    assert(minyar_thread_join(t) == 51);
    minyar_rc_release(t);
    rc_thread_domain_dispose();
    atomic_fetch_add(&joined_waiters, 1);
}
static void multiple_joiners(void) {
    MinyarBytes *b = minyar_bytes_new(0);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    RcThreadLeaf *c = minyar_bytes_channel_new(0, 1);
    rc_test_gate_init(&held_worker, 2);
    rc_test_gate_init(&joiners_started, 4);
    size_t joins = atomic_load(&rc_thread_native_joins);
    RcThreadLeaf *t = minyar_thread_spawn(held_entry, 51, f, c);
    RcManagedThread *native = t->control;
    RcTestThread waiters[4];
    atomic_store(&joined_waiters, 0);
    for (unsigned i = 0; i < 4; i++) {
        rc_thread_control_retain(native);
        waiters[i] = rc_test_start(join_waiter, native);
    }
    minyar_rc_release(t);
    rc_test_gate_arrive(&held_worker);
    for (unsigned i = 0; i < 4; i++) rc_test_join(waiters[i]);
    assert(atomic_load(&joined_waiters) == 4);
    assert(atomic_load(&rc_thread_native_joins) == joins + 1);
    minyar_thread_join_children();
    assert(atomic_load(&rc_thread_native_joins) == joins + 1);
    rc_test_gate_dispose(&held_worker);
    rc_test_gate_dispose(&joiners_started);
    minyar_rc_release(c); minyar_rc_release(f); minyar_rc_release(b);
    assert_native_empty();
}
static void fatal_case(const char *name) {
    if (!strcmp(name, "allocation")) {
        rc_thread_test_fail_allocation_after = 0;
        (void)minyar_bytes_channel_new(0, 1);
        return;
    }
    if (!strcmp(name, "capacity")) { (void)minyar_bytes_channel_new(-1, 1); return; }
    MinyarBytes *b = minyar_bytes_new(1);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    if (!strcmp(name, "allocation-packet")) {
        RcThreadLeaf *c = minyar_bytes_channel_new(0, 1);
        rc_thread_test_fail_allocation_after = 1;
        (void)minyar_thread_spawn(no_work, 0, f, c);
        return;
    }
    if (!strcmp(name, "allocation-detach")) {
        rc_thread_test_fail_allocation_after = 0;
        (void)minyar_frozen_bytes_take(b);
        return;
    }
    if (!strcmp(name, "bounds")) { (void)minyar_frozen_bytes_get_uint8(f, -1); return; }
    if (!strcmp(name, "bounds64")) { (void)minyar_frozen_bytes_get_int64(f, 0); return; }
    MinyarRecord *r = minyar_record_new(2);
    minyar_record_set(r, 0, 2);
    if (!strcmp(name, "start-result")) { (void)minyar_thread_start_result_value(r); return; }
    if (!strcmp(name, "join-result")) { (void)minyar_thread_join_result_value(r); return; }
    if (!strcmp(name, "frozen-result")) { (void)minyar_frozen_result_value(r); return; }
    abort();
}
int main(int count, char **arguments) {
    if (count == 2) { fatal_case(arguments[1]); return 99; }
    sharing();
    creator_exit();
    aliases_and_capacity();
    backpressure();
    failures_and_results();
    descendants();
    frozen_forwarding();
    queued_creator_exit();
    closure_waiters();
    multiple_joiners();
    rc_thread_domain_dispose();
    assert(rc_object_count == 0 && rc_bytes == 0);
#ifdef MINYAR_BOUNDED_RC
    assert(rc_heap_allocation_count == 0);
#endif
    puts("thread sharing, creator exit, transfers, closure, joins, Result and cleanup passed");
}
