/* Isolated observation helpers, included after the copied runtime. */
static void research_begin(void) {
    research_adds = research_takes = research_copies = research_copy_bytes = 0;
    research_retains = research_guard_pending = event_count = 0;
    research_phase = 1;
}
static void research_emit(void) {
    printf("{\"kind\":\"events\",\"guard_pending\":%zu,\"add_entries\":%zu,"
           "\"take_entries\":%zu,\"copy_entries\":%zu,\"copy_bytes\":%zu,\"events\":[",
           research_guard_pending, research_adds, research_takes, research_copies,
           research_copy_bytes);
    for (size_t i = 0; i < event_count; i++)
        printf("%s[%zu,%zu,%zu,%zu,%zu]", i ? "," : "", events[i][0], events[i][1], events[i][2],
               events[i][3], events[i][4]);
    puts("]}");
}
#ifdef MINYAR_BOUNDED_HEAP
static size_t research_offset(const void *pointer) {
    return pointer ? pool_offset(pointer) : SIZE_MAX;
}
static void research_list(const MinyarList *list) {
    printf("[%zu,%zu,%lld,%lld,%zu,%zu,[", research_offset(list), ((RcObject *)list - 1)->ownership,
           list->length, list->capacity, research_offset(list->values),
           list->values ? ((RcData *)list->values - 1)->size : 0);
    for (long long i = 0; i < list->length; i++)
        printf("%s%lld", i ? "," : "", list->values[i]);
    printf("]]");
}
static void research_frames(RcFrame *frame) {
    printf("[");
    size_t count = 0;
    while (frame) {
        assert(count < 8);
        printf("%s[%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu]", count ? "," : "", research_offset(frame),
               research_offset(frame->previous), research_offset(frame->locals), frame->local_count,
               frame->local_capacity, frame->written_count, frame->temporary_count,
               research_offset(frame->temporary_head), research_offset(frame->temporary_tail));
        frame = frame->previous;
        count++;
    }
    printf("]");
}
static void research_state(const char *label, const MinyarList *source, const MinyarList *result) {
    assert(!rc_pending_count && !rc_bounded_head && !rc_bounded_tail && !rc_bounded_active &&
           !rc_bounded_recent_head && !rc_bounded_recent_tail && !rc_bounded_frame_head &&
           !rc_bounded_frame_tail && !rc_bounded_chunk_head && !rc_bounded_chunk_tail);
    printf("{\"kind\":\"state\",\"label\":\"%s\",\"used\":%zu,\"mask\":%zu,"
           "\"high_water\":%zu,\"allocation_count\":%zu,\"requested\":%zu,\"objects\":%zu,"
           "\"rc\":[%zu,%u,%u,%zu,%zu],\"map\":\"",
           label, minyar_pool_used, minyar_pool_mask, minyar_pool_high_water,
           minyar_pool_allocation_count, rc_bytes, rc_object_count, rc_bounded_cursor,
           rc_bounded_recent_turn, rc_bounded_next_queue, rc_bounded_cached_frame_bytes,
           rc_bounded_last_work);
    for (size_t i = 0; i < MINYAR_POOL_BYTES / MINYAR_POOL_MINIMUM; i++)
        printf("%02x", minyar_pool_map[i]);
    printf("\",\"free\":[");
    for (unsigned order = 0; order <= minyar_pool_max_order; order++) {
        printf("%s[", order ? "," : "");
        PoolLink *head = minyar_pool_free[order];
        size_t count = 0;
        while (head) {
            assert(count < MINYAR_POOL_BYTES / MINYAR_POOL_MINIMUM);
            PoolLink link = pool_read_link(head);
            printf("%s[%zu,%zu,%zu]", count ? "," : "", research_offset(head),
                   research_offset(link.previous), research_offset(link.next));
            head = link.next;
            count++;
        }
        printf("]");
    }
    printf("],\"active_frames\":");
    research_frames(rc_frames);
    printf(",\"cached_frames\":");
    research_frames(rc_free_frames);
    printf(",\"source\":");
    research_list(source);
    printf(",\"result\":");
    research_list(result);
    puts("}");
}
static void research_pressure(const MinyarList *source, const MinyarList *result, void **fillers,
                              size_t count) {
    research_emit();
    research_state("after-append", source, result);
    size_t freed = 0;
    for (size_t i = 0; i < count && freed < 4; i++) {
        if (fillers[i]) {
            minyar_pool_deallocate(fillers[i]);
            fillers[i] = NULL;
            freed++;
        }
    }
    assert(freed == 4);
    research_state("after-four-filler-frees", source, result);
    static const size_t requests[] = {1, 31, 32, 33, 63, 64, 127, 128};
    void *continuation[sizeof(requests) / sizeof(*requests)];
    size_t admitted = 0, refused = 0;
    for (size_t i = 0; i < sizeof(requests) / sizeof(*requests); i++) {
        continuation[i] = minyar_pool_try_allocate(requests[i]);
        if (continuation[i])
            admitted++;
        else
            refused++;
        printf("{\"kind\":\"request\",\"bytes\":%zu,\"offset\":%zu}\n", requests[i],
               research_offset(continuation[i]));
        research_state("after-request", source, result);
    }
    assert(admitted && refused);
    for (size_t i = 0; i < sizeof(requests) / sizeof(*requests); i++)
        minyar_pool_deallocate(continuation[i]);
    research_state("after-continuation-frees", source, result);
}
#endif
