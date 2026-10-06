/* Closed two-owner Text cohort; public setup/leave/poll operations, with an
 * isolated destruction observer. Cache disposal is outside structural work. */
#define MINYAR_RC_TESTING 1
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_POLL_BUDGET 1
static void demand_destroy(const void *, unsigned);
#include MINYAR_RESEARCH_RUNTIME

static uintptr_t root_header, view_header;
static size_t root_destroyed, view_destroyed, total_work;
static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "Demand observer assertion: %s\n", message);
        exit(70);
    }
}
static void demand_destroy(const void *object, unsigned kind) {
    require(kind == RC_TEXT, "only Text destruction belongs to this cohort");
    if ((uintptr_t)object == root_header) root_destroyed++;
    else if ((uintptr_t)object == view_header) view_destroyed++;
    else require(0, "unexpected object identity");
    require(root_destroyed <= 1 && view_destroyed <= 1, "generation destroyed once");
}
static void state(const char *phase, size_t work) {
    printf("{\"phase\":\"%s\",\"work\":%zu,\"summed_work\":%zu,\"objects\":%zu,"
           "\"requested\":%zu,\"pending\":%zu,\"root_destroyed\":%zu,"
           "\"view_destroyed\":%zu,\"remaining_frame_slots\":%zu,"
           "\"frame_cached\":%u,\"cache_charge\":%zu,\"heap_allocations\":%zu}\n",
           phase, work, total_work, rc_object_count, rc_bytes, rc_pending_count,
           root_destroyed, view_destroyed,
           rc_bounded_frame_head ? rc_bounded_frame_head->local_count : 0,
           rc_free_frames != NULL, rc_bounded_cached_frame_bytes, rc_heap_allocation_count);
}
int main(int argc, char **argv) {
    require(argc == 2, "one owner-order argument");
    int reversed = atoi(argv[1]);
    require(reversed == 0 || reversed == 1, "owner order zero or one");
    require(!rc_frames && !rc_free_frames && !rc_pending_count && !rc_object_count &&
                !rc_bytes && !rc_bounded_cached_frame_bytes && !rc_heap_allocation_count,
            "fresh closure cohort without other owners or cache");
    minyar_rc_enter(2);
    MinyarText *root = copy_c_text("abcdefgh");
    MinyarText *view = minyar_text_slice(root, 1, 7);
    root_header = (uintptr_t)((RcObject *)root - 1);
    view_header = (uintptr_t)((RcObject *)view - 1);
    require(root != view && view->backing == root && view->bytes == root->bytes + 1,
            "proper view, neither full slice nor copied tiny slice");
    require(root->byte_length == 8 && view->byte_length == 6 &&
                !memcmp(root->bytes, "abcdefgh", 8) && !memcmp(view->bytes, "bcdefg", 6),
            "independent root/view byte contents");
    require(minyar_text_length(root) == 8 && minyar_text_length(view) == 6 &&
                !root->character_offsets && !view->character_offsets,
            "certified ASCII requires no index allocation");
    for (long long i = 0; i < 6; i++)
        require(minyar_text_character_at(view, i) == "bcdefg"[i], "independent scalar contents");
    minyar_rc_local_take(0, reversed ? (void *)view : (void *)root);
    minyar_rc_local_take(1, reversed ? (void *)root : (void *)view);
    require(((RcObject *)root - 1)->ownership == (16 | RC_TEXT) &&
                ((RcObject *)view - 1)->ownership == (8 | RC_TEXT), "exact producer owner transfer");
    require(rc_frames->written_count == 2 && rc_bounded_local_indices(rc_frames)[0] == 0 &&
                rc_bounded_local_indices(rc_frames)[1] == 1 && !rc_frames->temporary_count &&
                !rc_frames->temporary_head && !rc_pending_count, "same sparse indices and no temporaries");
    require(sizeof(MinyarText) + sizeof(RcObject) == 48 && sizeof(RcFrame) == 64 &&
                rc_bytes == 113 && rc_object_count == 2 && rc_heap_allocation_count == 5,
            "supported ABI allocation multiset");
    state("before-leave", 0);
    size_t before_objects = rc_object_count;
    minyar_rc_leave();
    size_t automatic = rc_bounded_last_work;
    require(automatic == 1 && before_objects - rc_object_count <= automatic,
            "automatic leave poll obeys K1 and destruction bound");
#ifndef MINYAR_RESEARCH_OMIT_LEAVE_WORK
    total_work += automatic;
#endif
    state("automatic-leave-poll", automatic);
    require(!rc_frames && rc_bounded_frame_head && rc_pending_count == 1 &&
                rc_bounded_frame_head->local_count == 1 && !root_destroyed &&
                view_destroyed == (size_t)!reversed && rc_object_count == (size_t)(reversed ? 2 : 1),
            "first reverse sparse owner visit");
    size_t polls = 0;
    while (rc_pending_count) {
        before_objects = rc_object_count;
        size_t work = minyar_rc_poll(1);
        require(work == 1 && before_objects - rc_object_count <= work && ++polls <= 4,
                "explicit poll work, destruction and bounded progress");
        total_work += work;
        state("explicit-poll", work);
    }
    require(root_destroyed == 1 && view_destroyed == 1 && !rc_object_count && !rc_bytes &&
                !rc_bounded_head && !rc_bounded_active && !rc_bounded_recent_head &&
                !rc_bounded_frame_head && !rc_bounded_chunk_head && rc_free_frames &&
                !rc_free_frames->previous && rc_heap_allocation_count == 2 &&
                rc_bounded_cached_frame_bytes == 96, "objects recovered with exact empty-frame cache");
    RcFrame *cached = rc_free_frames;
    rc_free_frames = NULL;
    rc_heap_deallocate(cached->locals);
    rc_heap_deallocate(cached);
    rc_bounded_cached_frame_bytes = 0;
    require(!rc_heap_allocation_count, "cache disposal recovers exact tracked allocations");
    state("cache-disposed-outside-work", 0);
    require(total_work == (size_t)(reversed ? 4 : 3), "include automatic leave work in total3/4");
    return 0;
}
