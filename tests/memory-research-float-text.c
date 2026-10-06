/* Public Float-to-Text allocation/lifetime baseline, not formatter timing. */
#include <stddef.h>
#define MINYAR_RC_TESTING 1
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_POLL_BUDGET 32
static size_t observed_objects, observed_data, observed_object_bytes, observed_data_bytes;
static size_t observed_hooks, observed_offered, observed_polls, observed_work;
static void float_allocation(unsigned, size_t);
static void float_service(size_t, size_t);
static void float_poll(size_t);
#include MINYAR_RESEARCH_RUNTIME

static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "Float Text observer assertion: %s\n", message);
        exit(70);
    }
}
static void float_allocation(unsigned object, size_t requested) {
    if (object) {
        observed_objects++;
        observed_object_bytes += requested;
    } else {
#ifndef MINYAR_RESEARCH_OMIT_DATA_EVENT
        observed_data++;
        observed_data_bytes += requested;
#else
        (void)requested;
#endif
    }
}
static void float_service(size_t budget, size_t pending) {
    observed_hooks++;
    observed_offered += budget;
    require(pending == 0, "this baseline has no queued cleanup debt");
}
static void float_poll(size_t work) {
    observed_polls++;
    observed_work += work;
    require(work <= MINYAR_RC_POLL_BUDGET, "public poll work bounded");
}
static void verify(MinyarText *text, const char *expected) {
    size_t length = strlen(expected);
    require(text->byte_length == (long long)length &&
                text->character_length == (long long)length &&
                !text->character_offsets && !text->backing &&
                !memcmp(text->bytes, expected, length) && text->bytes[length] == 0,
            "exact spelling, sentinel and certified ASCII metadata");
    require(minyar_text_length(text) == (long long)length,
            "public scalar length matches independent string");
    for (size_t position = 0; position < length; position++)
        require(minyar_text_character_at(text, (long long)position) == expected[position],
                "public Character contents match independent string");
}
int main(void) {
    static const struct { uint64_t bits; const char *expected; } cases[] = {
        {UINT64_C(0x0000000000000000), "0.0"},
        {UINT64_C(0x8000000000000000), "-0.0"},
        {UINT64_C(0x3ff4000000000000), "1.25"},
        {UINT64_C(0x3fb999999999999a), "0.1"},
        {UINT64_C(0x0000000000000001), "5.0e-324"},
        {UINT64_C(0x7fefffffffffffff), "1.7976931348623157e+308"},
        {UINT64_C(0xffefffffffffffff), "-1.7976931348623157e+308"},
        {UINT64_C(0x7ff0000000000000), "Infinity"},
        {UINT64_C(0xfff0000000000000), "-Infinity"},
        {UINT64_C(0x7ff8000000000000), "NaN"},
    };
    require(sizeof(double) == 8 && sizeof(MinyarText) + sizeof(RcObject) == 48 &&
                sizeof(RcData) == 8, "supported binary64 and Text ABI");
    for (size_t index = 0; index < sizeof(cases) / sizeof(cases[0]); index++) {
        require(!rc_object_count && !rc_bytes && !rc_pending_count && !rc_heap_allocation_count,
                "fresh quiescent case");
        observed_objects = observed_data = observed_object_bytes = observed_data_bytes = 0;
        observed_hooks = observed_offered = observed_polls = observed_work = 0;
        double value;
        memcpy(&value, &cases[index].bits, sizeof(value));
        MinyarText *text = minyar_float_text(value);
        size_t objects = observed_objects, data = observed_data;
        size_t object_bytes = observed_object_bytes, data_bytes = observed_data_bytes;
        size_t hooks = observed_hooks, offered = observed_offered, polls = observed_polls;
        size_t requested = rc_bytes;
        verify(text, cases[index].expected);
        require(rc_object_count == 1 && rc_heap_allocation_count == 2 &&
                    requested == strlen(cases[index].expected) + 57,
                "one object and one exact backing request");
        minyar_rc_retain(text);
        minyar_rc_release(text);
        require(rc_object_count == 1 && rc_bytes == requested,
                "surviving alias protects the same allocation");
        MinyarText *pressure = minyar_float_text(42.0);
        verify(pressure, "42.0");
        verify(text, cases[index].expected);
        minyar_rc_release(pressure);
        minyar_rc_release(text);
        require(!rc_object_count && !rc_bytes && !rc_pending_count &&
                    !rc_heap_allocation_count && !rc_frames && !rc_free_frames,
                "all objects, requested bytes and tracked allocations recover");
        printf("{\"case\":%zu,\"bits\":\"%016llx\",\"text\":\"%s\","
               "\"object_allocations\":%zu,\"data_allocations\":%zu,"
               "\"object_requested\":%zu,\"data_requested\":%zu,"
               "\"total_requested\":%zu,\"allocation_hooks\":%zu,"
               "\"allocation_offered\":%zu,\"allocation_public_polls\":%zu,"
               "\"lifecycle_hooks\":%zu,\"lifecycle_offered\":%zu,"
               "\"lifecycle_public_polls\":%zu,\"queued_work\":%zu,"
               "\"objects_after\":%zu,\"requested_after\":%zu,\"heap_after\":%zu}\n",
               index, (unsigned long long)cases[index].bits, cases[index].expected,
               objects, data, object_bytes, data_bytes, requested, hooks, offered, polls,
               observed_hooks, observed_offered, observed_polls, observed_work,
               rc_object_count, rc_bytes, rc_heap_allocation_count);
        /* Validate the observer after complete recovery, including the red control. */
        require(objects == 1 && data == 1 && object_bytes == 48 &&
                    data_bytes == strlen(cases[index].expected) + 9,
                "public conversion observes both managed allocation edges");
        require(hooks == 2 && offered == 64 && polls == 0 &&
                    observed_hooks == 7 && observed_offered == 222 &&
                    observed_polls == 0 && observed_work == 0,
                "construction and alias lifecycle helper events match exact idle schedule");
    }
    return 0;
}
