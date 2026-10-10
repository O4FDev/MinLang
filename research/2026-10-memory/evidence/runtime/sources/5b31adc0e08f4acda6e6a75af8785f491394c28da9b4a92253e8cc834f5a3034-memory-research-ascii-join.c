/* Counter oracles for a copied, explicitly instrumented runtime. This fixture
 * measures lazy-index input and allocation/service calls, not operation time. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef MINYAR_RESEARCH_INSTRUMENTED
#error Use the research runner's instrumented runtime snapshot.
#endif
static size_t research_index_builds, research_index_input_bytes;
static size_t research_service_calls, research_service_work;
static size_t allocation_calls, resize_calls;
#ifndef MINYAR_BOUNDED_HEAP
static void *research_allocate(size_t size) {
    allocation_calls++;
    return malloc(size);
}
static void *research_resize(void *pointer, size_t size) {
    resize_calls++;
    return realloc(pointer, size);
}
#define malloc research_allocate
#define realloc research_resize
#endif
#define MINYAR_RC_TESTING 1
#ifndef MINYAR_RESEARCH_RUNTIME
#define MINYAR_RESEARCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include MINYAR_RESEARCH_RUNTIME
#undef malloc
#undef realloc

static void reset_metrics(void) {
    research_index_builds = research_index_input_bytes = 0;
    research_service_calls = research_service_work = 0;
    allocation_calls = resize_calls = 0;
}

static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
#endif
    assert(!rc_object_count && !rc_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#elif defined(MINYAR_BOUNDED_HEAP)
    assert(!minyar_pool_used);
#endif
}

static void borrowed_case(const char *label, long long bytes, int prime, int unicode, int debt,
                          int self, int query, int require_metadata) {
    MinyarText *left;
    long long characters;
    if (unicode) {
        left = copy_c_text("é🙂");
        characters = 2;
    } else {
        unsigned char *buffer = new_bytes(bytes);
        memset(buffer, 'a', (size_t)bytes);
        for (long long i = 16; i < bytes; i += 17)
            buffer[i] = 0; /* Embedded NUL is an ASCII scalar too. */
        buffer[bytes] = 0;
        left = new_text(buffer, bytes, -1);
        characters = bytes;
    }
    MinyarText *right = self ? left : copy_c_text("!");
    if (prime)
        assert(minyar_text_length(left) == characters);
    if (!self)
        assert(minyar_text_length(right) == 1);
#ifdef MINYAR_BOUNDED_RC
    if (debt)
        rc_drop(minyar_record_new(4 * MINYAR_RC_POLL_BUDGET + 1));
#else
    assert(!debt);
#endif
    reset_metrics();
    size_t before_objects = rc_object_count;
    MinyarText *result = minyar_join_text(left, right);
    assert(result != left && result != right && rc_object_count == before_objects + 1);
    assert(result->byte_length == left->byte_length + right->byte_length);
    assert(!memcmp(result->bytes, left->bytes, (size_t)left->byte_length));
    assert(!memcmp(result->bytes + left->byte_length, right->bytes, (size_t)right->byte_length));
    size_t join_hooks = research_service_calls, join_work = research_service_work;
    size_t join_allocations = allocation_calls, join_resizes = resize_calls;
#ifndef MINYAR_BOUNDED_HEAP
    assert(join_allocations == 2 && !join_resizes);
#endif
#ifdef MINYAR_BOUNDED_RC
    assert(join_hooks == 2);
    assert(join_work == (debt ? 2 * MINYAR_RC_POLL_BUDGET : 0));
#else
    assert(!join_hooks && !join_work);
#endif
    if (query) {
        assert(minyar_text_length(result) == characters * (self ? 2 : 1) + (self ? 0 : 1));
        assert(minyar_text_character_at(result, 0) == (unicode ? 0xe9 : 'a'));
        if (unicode)
            assert(minyar_text_character_at(result, 1) == 0x1f642);
    }
    printf("{\"case\":\"%s\",\"index_builds\":%zu,\"index_input_bytes\":%zu,"
           "\"join_allocations\":%zu,\"join_resizes\":%zu,\"join_service_hooks\":%zu,"
           "\"join_service_units\":%zu,\"query_service_hooks\":%zu}\n",
           label, research_index_builds, research_index_input_bytes, join_allocations, join_resizes,
           join_hooks, join_work, research_service_calls - join_hooks);
    if (!query)
        assert(!research_index_builds);
    else if (unicode || !prime)
        assert(research_index_builds == 1);
    else if (require_metadata)
        assert(!research_index_builds && "certified ASCII joins must avoid lazy-index scans");
    if (!unicode)
        assert(research_service_calls == join_hooks && research_service_work == join_work);
    if (!self)
        minyar_rc_release(right);
    minyar_rc_release(left);
    minyar_rc_release(result);
    drain();
}

static void consuming_control(void) {
    unsigned char *bytes = new_bytes(63);
    memcpy(bytes, "abc", 4);
    MinyarText *left = new_text(bytes, 3, 3);
    MinyarText *right = minyar_character_text('!');
    reset_metrics();
    MinyarText *joined = minyar_join_text_take_left(left, right);
    assert(joined == left && minyar_text_length(joined) == 4);
    assert(!research_index_builds && !research_service_calls && !allocation_calls && !resize_calls);
    assert(!memcmp(joined->bytes, "abc!", 4));
    minyar_rc_release(joined);
    drain();
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc == 2 && !strcmp(argv[1], "--invalid-utf8")) {
        MinyarText *left = copy_c_text("\xc3(");
        MinyarText *right = minyar_character_text('!');
        MinyarText *result = minyar_join_text(left, right);
        minyar_text_length(result);
        assert(0 && "unknown malformed UTF-8 must still trap");
    }
    int require = argc == 2 && !strcmp(argv[1], "--require-known-ascii");
    borrowed_case("known-long-ascii", 65536, 1, 0, 0, 0, 1, require);
    borrowed_case("known-short-ascii", 7, 1, 0, 0, 0, 1, require);
    borrowed_case("known-no-query", 65536, 1, 0, 0, 0, 0, require);
    borrowed_case("unknown-ascii", 65536, 0, 0, 0, 0, 1, require);
    borrowed_case("known-unicode", 0, 1, 1, 0, 0, 1, require);
    borrowed_case("known-self-ascii", 65536, 1, 0, 0, 1, 1, require);
#ifdef MINYAR_BOUNDED_RC
    borrowed_case("known-ascii-pending-debt", 65536, 1, 0, 1, 0, 1, require);
#endif
    consuming_control();
    return 0;
}
