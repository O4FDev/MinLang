/* Source-level append/copy work, separately from managed request/poll events. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int research_phase;
static size_t research_adds, research_takes, research_copies, research_copy_bytes;
static size_t research_retains, research_guard_pending;
static size_t events[512][5], event_count;
static void research_event(size_t kind, size_t a, size_t b, size_t c, size_t d) {
    if (!research_phase)
        return;
    assert(event_count < 512);
    size_t *event = events[event_count++];
    event[0] = kind;
    event[1] = a;
    event[2] = b;
    event[3] = c;
    event[4] = d;
}
static void *research_copy(void *target, const void *source, size_t size) {
    if (research_phase) {
        research_copies++;
        research_copy_bytes += size;
    }
    return memcpy(target, source, size);
}
#undef memcpy /* Darwin headers may provide a fortified macro. */
#define memcpy research_copy
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#undef memcpy

static struct {
    RcObject owner;
    MinyarText text;
} immortal = {{RC_TEXT}, {(const unsigned char *)"a", 1, 1, NULL, NULL}};

static void reset_observer(void) {
    research_adds = research_takes = research_copies = research_copy_bytes = 0;
    research_retains = research_guard_pending = event_count = 0;
    research_phase = 1;
}
static void recover(void) {
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    if (rc_frames)
        minyar_rc_leave();
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
    assert(!rc_frames && !rc_object_count && !rc_bytes);
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
}
static long long expected_value(long long index) {
    static const uint64_t edges[] = {UINT64_C(0x8000000000000000),
                                     UINT64_C(0x7fffffffffffffff),
                                     UINT64_MAX,
                                     0,
                                     1,
                                     UINT64_C(0x10ffff),
                                     UINT64_C(0x3fe0000000000000),
                                     UINT64_C(0xbff0000000000000)};
    uint64_t bits = edges[(size_t)index % 8];
    if (index >= 8)
        bits ^= (uint64_t)index * UINT64_C(0x9e3779b97f4a7c15);
    long long value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}
static void emit(const char *mode, long long length, int take, long long capacity, size_t pending,
                 size_t objects, size_t bytes) {
    printf("{\"mode\":\"%s\",\"length\":%lld,\"take\":%d,\"capacity\":%lld,"
           "\"guard_pending\":%zu,\"add_entries\":%zu,\"take_entries\":%zu,"
           "\"copy_entries\":%zu,\"copy_bytes\":%zu,\"retain_entries\":%zu,"
           "\"post_pending\":%zu,\"post_objects\":%zu,\"post_requested\":%zu,\"events\":[",
           mode, length, take, capacity, research_guard_pending, research_adds, research_takes,
           research_copies, research_copy_bytes, research_retains, pending, objects, bytes);
    for (size_t i = 0; i < event_count; i++)
        printf("%s[%zu,%zu,%zu,%zu,%zu]", i ? "," : "", events[i][0], events[i][1], events[i][2],
               events[i][3], events[i][4]);
    puts("],\"recovered\":true}");
}
static void debt(const char *mode) {
    size_t slots = 4 * MINYAR_RC_POLL_BUDGET + 2;
    if (!strcmp(mode, "object")) {
        rc_drop(minyar_record_new((long long)slots));
    } else if (!strcmp(mode, "frame")) {
        minyar_rc_enter((long long)slots);
        for (size_t i = 0; i < slots; i++)
            minyar_rc_local_take((long long)i, &immortal.text);
        minyar_rc_leave();
    } else if (!strcmp(mode, "chunk")) {
        minyar_rc_enter(0);
        MinyarText *value = copy_c_text("chunk owner");
        for (size_t i = 0; i < slots; i++)
            minyar_rc_borrow(value);
        minyar_rc_release(value);
        minyar_rc_step();
    } else
        assert(!strcmp(mode, "idle"));
    assert(!strcmp(mode, "idle") || rc_pending_count);
}
static void scalar(const char *mode, long long length, int take, int require_bulk) {
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < length; i++)
        minyar_list_add(source, expected_value(i));
    assert(length || !source->values);
    minyar_rc_retain(source);
    debt(mode);
    reset_observer();
    MinyarList *result = minyar_list_appended(source, LLONG_MIN, 0, take);
    research_phase = 0;
    assert(result != source && result->length == length + 1 && source->length == length);
    for (long long i = 0; i < length; i++) {
        assert(source->values[i] == expected_value(i));
        assert(result->values[i] == expected_value(i));
    }
    assert(result->values[length] == LLONG_MIN);
    assert(((RcObject *)source - 1)->ownership >> 3 == 2);
    long long capacity = result->capacity;
    size_t pending = rc_pending_count, objects = rc_object_count, bytes = rc_bytes;
    if (strcmp(mode, "idle"))
        assert(research_guard_pending);
    minyar_rc_release(source);
    for (long long i = 0; i < length; i++)
        assert(source->values[i] == expected_value(i));
    minyar_rc_release(source);
    minyar_rc_release(result);
    recover();
    emit(mode, length, take, capacity, pending, objects, bytes);
    if (require_bulk && (research_adds != 1 || research_copies != 1 || research_copy_bytes != 16)) {
        fputs("Expected n2 scalar prefix to use one bulk copy and only the unchanged tail append; "
              "semantics and recovery passed.\n",
              stderr);
        exit(70);
    }
}
static void references(int take) {
    MinyarText *mortal = copy_c_text("mortal");
    MinyarList *source = minyar_list_new();
    minyar_list_references(source);
    long long words[] = {(long long)(uintptr_t)mortal, 0, (long long)(uintptr_t)&immortal.text,
                         (long long)(uintptr_t)mortal};
    for (size_t i = 0; i < 4; i++)
        minyar_list_add(source, words[i]);
    minyar_rc_retain(source);
    if (take)
        minyar_rc_retain(mortal);
    reset_observer();
    MinyarList *result = minyar_list_appended(source, (long long)(uintptr_t)mortal, 1, take);
    research_phase = 0;
    assert(result != source && result->length == 5 && source->length == 4);
    assert(((RcObject *)mortal - 1)->ownership >> 3 == 6);
    assert(immortal.owner.ownership == RC_TEXT);
    for (size_t i = 0; i < 4; i++)
        assert(result->values[i] == words[i] && source->values[i] == words[i]);
    assert(result->values[4] == words[0]);
    long long capacity = result->capacity;
    size_t pending = rc_pending_count, objects = rc_object_count, bytes = rc_bytes;
    minyar_rc_release(source);
    minyar_rc_release(source);
    minyar_rc_release(mortal);
    while (rc_pending_count)
        assert(minyar_rc_poll(1) == 1);
    assert(((RcObject *)mortal - 1)->ownership >> 3 == 3);
    assert(mortal->byte_length == 6 && !memcmp(mortal->bytes, "mortal", 6));
    minyar_rc_release(result);
    recover();
    emit("references", 4, take, capacity, pending, objects, bytes);
}
int main(int argc, char **argv) {
    assert(argc == 1 || (argc == 2 && !strcmp(argv[1], "--require-bulk")));
    if (argc == 2) {
        scalar("idle", 2, 0, 1);
        return 0;
    }
    static const long long lengths[] = {0, 1, 2, 3, 7, 15, 31, 32, 1023, 1024, 4095, 4096, 8193};
    for (size_t i = 0; i < sizeof(lengths) / sizeof(*lengths); i++)
        for (int take = 0; take < 2; take++)
            scalar("idle", lengths[i], take, 0);
    const char *modes[] = {"object", "frame", "chunk"};
    for (size_t i = 0; i < 3; i++)
        for (int take = 0; take < 2; take++)
            scalar(modes[i], 31, take, 0);
    for (int take = 0; take < 2; take++)
        references(take);
    return 0;
}
