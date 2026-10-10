/* Baseline-only view-retention and Boolean formatting counts; no policy change. */
static size_t research_index_calls, research_index_input_bytes;
#define main research_matrix_main
#include "memory-research-credit-relocation.c"
#undef main

static void reset_metrics(void) {
    research_service_calls = research_offered = research_queued = research_immediate = 0;
    research_object_allocations = research_data_allocations = research_data_resizes = 0;
    research_destroyed = research_index_calls = research_index_input_bytes = 0;
}
static void slices(size_t length, size_t token, size_t count, int geometric, int nested) {
    size_t capacity = length + 1;
    if (geometric) {
        capacity = 2;
        while (capacity <= length) capacity *= 2;
    }
    unsigned char *bytes = rc_allocate_data(capacity);
    memset(bytes, 'x', length);
    bytes[length] = 0;
    MinyarText *root = new_text(bytes, (long long)length, (long long)length);
    MinyarText *source = nested ? minyar_text_slice(root, 0, (long long)length / 2) : root;
    MinyarText *tokens[32];
    assert(count <= 32 && token <= (size_t)source->byte_length);
    size_t before = rc_bytes;
    reset_metrics();
    research_active = 1;
    for (size_t index = 0; index < count; index++)
        tokens[index] = minyar_text_slice(source, 0, (long long)token);
    research_active = 0;
    int copied = length > 4096 && token * 8 < length;
    for (size_t index = 0; index < count; index++) {
        assert(!!tokens[index]->backing == !copied);
        if (!copied) assert(tokens[index]->backing == root);
        assert(minyar_text_length(tokens[index]) == (long long)token);
        for (size_t byte = 0; byte < token; byte++) assert(tokens[index]->bytes[byte] == 'x');
    }
    assert(research_object_allocations == count && research_data_allocations == (copied ? count : 0));
    size_t hooks = research_service_calls, offered = research_offered, allocation_bytes = rc_bytes - before;
    if (nested) minyar_rc_release(source);
    minyar_rc_release(root);
    while (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
    size_t retained = rc_bytes;
#ifdef MINYAR_BOUNDED_HEAP
    size_t charge = minyar_pool_used;
#else
    size_t charge = 0;
#endif
    printf("{\"family\":\"slice\",\"budget\":%u,\"root_length\":%zu,\"root_capacity\":%zu,"
           "\"token_length\":%zu,\"survivors\":%zu,\"nested\":%d,\"copied\":%d,"
           "\"object_allocations\":%zu,\"data_allocations\":%zu,\"slice_requested_delta\":%zu,"
           "\"requested_retained_after_root_drop_and_drain\":%zu,\"pool_charge_retained\":%zu,"
           "\"service_hooks\":%zu,\"offered_units\":%zu,\"inferred_copied_payload_bytes\":%zu}\n",
           MINYAR_RC_POLL_BUDGET, length, capacity, token, count, nested, copied,
           research_object_allocations, research_data_allocations, allocation_bytes,
           retained, charge, hooks, offered, copied ? token * count : 0);
    for (size_t index = 0; index < count; index++) minyar_rc_release(tokens[index]);
    clear();
}
static void boolean_format(int value, int query, int literal) {
    struct { RcObject owner; MinyarText text; } constant =
        {{RC_TEXT}, {(const unsigned char *)(value ? "true" : "false"), value ? 4 : 5,
                    value ? 4 : 5, NULL, NULL}};
    reset_metrics();
    research_active = 1;
    for (int index = 0; index < 1000; index++) {
        MinyarText *text = literal ? &constant.text : minyar_boolean_text(value);
        assert(text->byte_length == (value ? 4 : 5));
        assert(!memcmp(text->bytes, value ? "true" : "false", (size_t)text->byte_length));
        if (query) assert(minyar_text_length(text) == (value ? 4 : 5));
        minyar_rc_release(text);
    }
    research_active = 0;
    assert(research_object_allocations == (size_t)(literal ? 0 : 1000));
    assert(research_data_allocations == (size_t)(literal ? 0 : 1000));
    assert(research_index_calls == (size_t)(query && !literal ? 1000 : 0));
    printf("{\"family\":\"boolean\",\"budget\":%u,\"value\":%d,\"query\":%d,\"literal_control\":%d,"
           "\"iterations\":1000,\"object_allocations\":%zu,\"data_allocations\":%zu,"
           "\"service_hooks\":%zu,\"offered_units\":%zu,\"queued_units\":%zu,\"immediate_units\":%zu,"
           "\"index_calls\":%zu,\"index_input_bytes\":%zu}\n",
           MINYAR_RC_POLL_BUDGET, value, query, literal, research_object_allocations,
           research_data_allocations, research_service_calls, research_offered, research_queued,
           research_immediate, research_index_calls, research_index_input_bytes);
    clear();
}
int main(int argc, char **argv) {
    assert(argc == 2 && !strcmp(argv[1], "probe"));
    const size_t lengths[] = {4096, 4097, 8192};
    for (size_t index = 0; index < 3; index++)
        for (int offset = -1; offset <= 1; offset++)
            for (int geometric = 0; geometric < 2; geometric++)
                for (size_t count = 1; count <= 32; count *= 32)
                    slices(lengths[index], lengths[index] / 8 + offset, count, geometric, 0);
    for (size_t index = 1; index < 3; index++)
        for (int offset = 0; offset <= 1; offset++)
            slices(lengths[index], lengths[index] / 8 + offset, 1, 0, 1);
    for (int value = 0; value < 2; value++)
        for (int query = 0; query < 2; query++)
            for (int literal = 0; literal < 2; literal++)
                boolean_format(value, query, literal);
    return 0;
}
