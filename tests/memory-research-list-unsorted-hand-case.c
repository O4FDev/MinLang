/* One separately authorized unsorted-list correspondence check.
 * Snapshots exclude telemetry, uninitialized spare storage and sanitizer state.
 * Raw continuation requests never inspect or resize uninitialized storage. */
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES 4096
#define MINYAR_RC_POLL_BUDGET 32
#define MINYAR_RC_TESTING 1
static void hand_snapshot(const char *, const void *, const void *);
#include MINYAR_RESEARCH_RUNTIME
#include <assert.h>

static void *filler;
static void *blockers[24];
static size_t blocker_sizes[24];
static size_t blocker_count;
static unsigned long long normalized(const void *p) {
    return p ? (unsigned long long)pool_offset(p) + 1 : 0;
}
static void list_snapshot(const MinyarList *list) {
    if (!list) { printf("null"); return; }
    printf("{\"header\":%llu,\"ownership\":%zu,\"values\":%llu,\"length\":%lld,"
           "\"capacity\":%lld,\"data_size\":%zu,\"initialized\":[",
           normalized((RcObject *)list - 1), ((RcObject *)list - 1)->ownership,
           normalized(list->values), list->length, list->capacity,
           list->values ? ((RcData *)list->values - 1)->size : 0);
    for (long long i = 0; i < list->length; i++)
        printf("%s%lld", i ? "," : "", list->values[i]);
    printf("]}");
}
static void hand_snapshot(const char *phase, const void *source, const void *result) {
    printf("{\"phase\":\"%s\",\"decision\":{\"map\":[", phase);
    for (size_t i = 0; i < MINYAR_POOL_MAP_BYTES; i++)
        printf("%s%u", i ? "," : "", minyar_pool_map[i]);
    printf("],\"lists\":[");
    for (unsigned order = 0; order < MINYAR_POOL_ORDERS; order++) {
        printf("%s[", order ? "," : "");
        size_t count = 0;
        PoolLink *previous = NULL;
        for (PoolLink *p = minyar_pool_free[order]; p;) {
            PoolLink link = pool_read_link(p);
            assert(link.previous == previous && ++count <= MINYAR_POOL_MAP_BYTES);
            printf("%s[%llu,%llu,%llu]", count > 1 ? "," : "", normalized(p),
                   normalized(link.previous), normalized(link.next));
            previous = p;
            p = link.next;
        }
        printf("]");
    }
    printf("],\"mask\":%zu,\"used\":%zu,\"max_order\":%u,\"source\":",
           minyar_pool_mask, minyar_pool_used, minyar_pool_max_order);
    list_snapshot(source);
    printf(",\"result\":");
    list_snapshot(result);
    printf(",\"filler\":{\"base\":%llu,\"bytes\":[", normalized(filler));
    if (filler) for (size_t i = 0; i < 32; i++) {
        assert(((unsigned char *)filler)[i] == 0x5a);
        printf("%s%u", i ? "," : "", ((unsigned char *)filler)[i]);
    }
    printf("]},\"initialized_raw_blockers\":[");
    size_t emitted = 0;
    for (size_t i = 0; i < blocker_count; i++) {
        if (!blockers[i]) continue;
        printf("%s{\"base\":%llu,\"size\":%zu,\"bytes\":[", emitted++ ? "," : "",
               normalized(blockers[i]), blocker_sizes[i]);
        for (size_t j = 0; j < blocker_sizes[i]; j++) {
            unsigned char value = ((unsigned char *)blockers[i])[j];
            assert(value == 0x5a);
            printf("%s%u", j ? "," : "", value);
        }
        printf("]}");
    }
    printf("],\"scheduler\":[%zu,%llu,%llu,%llu,%zu,%llu,%llu,%u,%llu,%llu,"
           "%llu,%llu,%u,%llu,%llu,%zu],\"accounting\":[%zu,%zu,%zu]},"
           "\"telemetry\":{\"high_water\":%zu,\"allocations\":%zu,\"last_steps\":%zu,"
           "\"max_steps\":%zu,\"last_work\":%zu}}\n",
           rc_pending_count, normalized(rc_bounded_head), normalized(rc_bounded_tail),
           normalized(rc_bounded_active), rc_bounded_cursor, normalized(rc_bounded_recent_head),
           normalized(rc_bounded_recent_tail), rc_bounded_recent_turn,
           normalized(rc_bounded_frame_head), normalized(rc_bounded_frame_tail),
           normalized(rc_bounded_chunk_head), normalized(rc_bounded_chunk_tail),
           rc_bounded_next_queue, normalized(rc_frames), normalized(rc_free_frames),
           rc_bounded_cached_frame_bytes, rc_object_count, rc_bytes, rc_immortal_object_count,
           minyar_pool_high_water, minyar_pool_allocation_count, minyar_pool_last_steps,
           minyar_pool_max_steps, rc_bounded_last_work);
}
int main(int argc, char **argv) {
    assert(argc == 2 && strtoll(argv[1], NULL, 10) == 15);
    MinyarList *source = minyar_list_new();
    assert(pool_offset((RcObject *)source - 1) == 0);
    const size_t offsets[] = {32,64,96,128,192,256,384,512,640,768,800,832,864,
                              896,960,1024,1536,2048,2304,2560,2816,3072};
    const size_t sizes[] = {32,32,32,64,64,128,128,128,128,32,32,32,32,
                            64,64,512,512,256,256,256,256,1024};
    blocker_count = sizeof(offsets) / sizeof(offsets[0]);
    assert(blocker_count <= 24);
    for (size_t i = 0; i < blocker_count; i++) {
        blocker_sizes[i] = sizes[i];
        if (offsets[i] == 512) {
            source->values = rc_allocate_data(120);
            source->capacity = 15;
            assert(pool_offset((RcData *)source->values - 1) == 512);
        } else {
            blockers[i] = minyar_pool_allocate(sizes[i]);
            assert(pool_offset(blockers[i]) == offsets[i]);
            memset(blockers[i], 0x5a, sizes[i]);
        }
    }
    assert(minyar_pool_used == 4096);
    /* Reverse insertion creates unsorted lists. The final two frees coalesce
     * 64/96; smaller-class free heads remain preferred for the real header. */
    const size_t free_offsets[] = {800,864,896,128,640,256,2048,2560,1024,3072,64,96};
    for (size_t j = 0; j < sizeof(free_offsets) / sizeof(free_offsets[0]); j++) {
        size_t i = 0;
        while (i < blocker_count && offsets[i] != free_offsets[j]) i++;
        assert(i < blocker_count && blockers[i]);
        minyar_pool_deallocate(blockers[i]);
        blockers[i] = NULL;
    }
    for (long long i = 0; i < 15; i++) minyar_list_add(source, i);
    assert(rc_pending_count == 0);
    /* Matched latent scheduler residues, separate from allocator history. */
    rc_bounded_recent_turn = 1;
    rc_bounded_next_queue = 2;
    hand_snapshot("pre-append", source, NULL);
    MinyarList *result = minyar_list_appended(source, 919, 0, 0);
    assert(result->length == 16 && result->capacity == 31);
    assert(pool_offset((RcData *)result->values - 1) == 2560);
    for (long long i = 0; i < 15; i++) assert(result->values[i] == i);
    assert(result->values[15] == 919 && rc_pending_count == 0);
    assert(minyar_pool_used == 1824);
    hand_snapshot("post-append", source, result);
    const size_t requests[] = {32, 64, 128, 4096};
    void *probes[4];
    for (size_t i = 0; i < 4; i++) {
        probes[i] = minyar_pool_try_allocate(requests[i]);
        printf("{\"request\":%zu,\"response\":%llu}\n", requests[i], normalized(probes[i]));
        hand_snapshot("continuation-allocation", source, result);
    }
    assert(!probes[3]);
    for (size_t i = 4; i; i--) {
        minyar_pool_deallocate(probes[i - 1]);
        hand_snapshot("continuation-free", source, result);
    }
    minyar_rc_release(result);
    minyar_rc_release(source);
    while (rc_pending_count) minyar_rc_poll(32);
    for (size_t i = 0; i < blocker_count; i++) {
        minyar_pool_deallocate(blockers[i]);
        blockers[i] = NULL;
    }
    assert(rc_object_count == 0 && rc_bytes == 0 && minyar_pool_used == 0);
    hand_snapshot("recovered", NULL, NULL);
    return 0;
}
