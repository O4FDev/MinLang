#define MINYAR_RC_TESTING 1
#define MINYAR_THREADED 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static MinyarBytes *detach_owner;

static void drop_detach_owner(void) {
    minyar_rc_release(detach_owner);
    rc_thread_domain_dispose();
    assert(rc_object_count == 0 && rc_bytes == 0);
}

int main(int argc, char **argv) {
    rc_thread_domain_init();
    if (argc == 2) {
        detach_owner = minyar_bytes_new(16);
        MinyarBytes *view = minyar_c_record_view(detach_owner, 0, 16);
        minyar_rc_release(view);
        if (strcmp(argv[1], "shrunk") == 0)
            minyar_bytes_resize(detach_owner, 0);
        assert(atexit(drop_detach_owner) == 0);
        minyar_frozen_bytes_take(detach_owner);
        return 2;
    }
    for (int iteration = 0; iteration < 1000; iteration++) {
        MinyarBytes *owner = minyar_bytes_new(64);
        uint64_t value = UINT64_MAX;
        memcpy((unsigned char *)owner->bytes + 24, &value, sizeof(value));
        MinyarBytes *outer = minyar_c_record_view(owner, 8, 40);
        MinyarBytes *inner = minyar_c_record_view(outer, 16, 8);
#ifndef MINYAR_COMPILER_ARENA
        assert(outer->backing == owner && inner->backing == owner);
        assert(((RcObject *)owner - 1)->ownership >> 3 == 3);
#endif
        assert(owner->character_length == -1 && outer->character_length == -1);
        const unsigned char *address = owner->bytes;
        assert(minyar_bytes_extend(owner, 0) == address + 64);
        minyar_bytes_resize(owner, 64);
        MinyarBytes *empty = minyar_bytes_new(0);
        minyar_bytes_append(owner, empty);
        minyar_rc_release(empty);
        assert(owner->bytes == address && owner->byte_length == 64);
        minyar_bytes_resize(owner, 32);
        assert(minyar_bytes_extend(owner, 0) == address + 32);
        assert(owner->bytes == address && owner->byte_length == 32);
        minyar_rc_release(owner);
        minyar_rc_release(outer);
        memcpy(&value, inner->bytes, sizeof(value));
        assert(value == UINT64_MAX);
        MinyarBytes *copy = minyar_c_record_copy(inner->bytes, 8);
        value = 42;
        memcpy((void *)copy->bytes, &value, sizeof(value));
        minyar_c_record_store(inner, 0, copy, 8);
        memcpy(&value, inner->bytes, sizeof(value));
        assert(value == 42);
        minyar_rc_release(inner);
        minyar_rc_release(copy);
        uint64_t external = 7;
        MinyarBytes *borrowed = minyar_c_record_at((long long)(uintptr_t)&external, 8);
        MinyarBytes *nested = minyar_c_record_view(borrowed, 0, 8);
#ifndef MINYAR_COMPILER_ARENA
        assert(nested->backing == &c_external_backing.text);
#endif
        minyar_rc_release(borrowed);
        value = 9;
        memcpy((void *)nested->bytes, &value, sizeof(value));
        minyar_rc_release(nested);
        assert(external == 9);
#ifndef MINYAR_COMPILER_ARENA
        rc_thread_domain_drain();
        assert(rc_object_count == 0 && rc_bytes == 0);
#endif
    }
    MinyarBytes *ordinary = minyar_bytes_new(0);
    minyar_bytes_resize(ordinary, 64);
    minyar_bytes_resize(ordinary, 0);
    minyar_bytes_resize(ordinary, 128);
    assert(ordinary->byte_length == 128 && ordinary->character_length >= 128);
    minyar_rc_release(ordinary);
    rc_thread_domain_dispose();
    assert(rc_object_count == 0 && rc_bytes == 0);
    puts("C-layout roots, nested views, borrowed addresses and ordinary Bytes passed");
    return 0;
}
