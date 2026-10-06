/* Generated Minyar handles setup and events; this C harness controls arrivals. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#include <mach/mach_time.h>
#endif
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <inttypes.h>
#include <time.h>
#ifdef EVENT_DIAGNOSTIC
#define MINYAR_RC_TESTING 1
#endif
#include "../../runtime/minyar_runtime.c"
#ifdef EVENT_DIAGNOSTIC
#define minyar_rc_enter_stack_v1 event_real_stack_enter
#endif
#include "../../runtime/minyar_stack_frames.h"
#ifdef EVENT_DIAGNOSTIC
#undef minyar_rc_enter_stack_v1
static size_t stack_admissions;
void minyar_rc_enter_stack_v1(void *header, void *storage, long long locals) {
    event_real_stack_enter(header, storage, locals);
    if ((void *)rc_frames == header) stack_admissions++;
}
#endif
#ifdef NDEBUG
#error Assertions are required.
#endif
extern MinyarList *eventSetup(long long width);
extern MinyarList *eventValues(void);
extern long long eventApply(MinyarList *, MinyarList *, long long, long long, long long, long long);

enum { CYCLES = 4, SHOCK_EVERY = 256 };
typedef struct {
    uint64_t arrival, start, service, response;
    long long result, managed, live, owners;
    size_t pending;
} Event;
typedef struct {
    size_t before, after, polls;
    uint64_t start, duration, overrun;
    long long managed, live, owners;
} Recovery;
#ifdef __APPLE__
static mach_timebase_info_data_t timebase;
#endif
static uint64_t now_ns(void) {
#ifdef __APPLE__
    return (uint64_t)(((__uint128_t)mach_absolute_time() * timebase.numer) / timebase.denom);
#else
    struct timespec t; assert(!clock_gettime(CLOCK_MONOTONIC, &t));
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
#endif
}
static void wait_until(uint64_t deadline) { while (now_ns() < deadline) {} }
static size_t parse(const char *s, size_t low, size_t high) {
    char *end; unsigned long long value = strtoull(s, &end, 10);
    assert(*s && *s != '-' && !*end && value >= low && value <= high);
    return (size_t)value;
}
static size_t drain(void) {
    size_t polls = 0;
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) { assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET)); polls++; }
#endif
    return polls;
}

#ifdef EVENT_DIAGNOSTIC
static void **seen, **pending;
static size_t scan_capacity, scan_count;
static void push(void *value) {
    if (!value) return;
    RcObject *o = (RcObject *)value - 1;
    if (!(o->ownership >> 3)) return; /* Immortal, never charged to rc_bytes. */
    size_t slot = ((uintptr_t)value >> 3) * (size_t)UINT64_C(11400714819323198485) & (scan_capacity - 1);
    while (seen[slot] && seen[slot] != value) slot = (slot + 1) & (scan_capacity - 1);
    if (seen[slot]) return;
    assert(scan_count < scan_capacity / 2);
    seen[slot] = value; pending[scan_count++] = value;
}
static size_t data_bytes(void *value) {
    return value ? sizeof(RcData) + ((RcData *)value - 1)->size : 0;
}
/* A source-reachability traversal independent of the collector's retirement
 * queues and counters. Run only between events, with no active generated frame. */
static size_t live_bytes(MinyarList *snapshots, MinyarList *values) {
    memset(seen, 0, scan_capacity * sizeof(*seen)); scan_count = 0;
    push(snapshots); push(values);
    size_t bytes = 0;
    for (size_t i = 0; i < scan_count; i++) {
        void *value = pending[i]; RcObject *o = (RcObject *)value - 1;
        unsigned kind = o->ownership & 7;
        bytes += sizeof(*o);
        if (kind == RC_TEXT) {
            MinyarText *text = value;
            bytes += sizeof(*text) + data_bytes(text->character_offsets);
            if (text->backing) push(text->backing);
            else bytes += data_bytes((void *)text->bytes);
        } else if (kind == RC_LIST || kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL) {
            MinyarList *list = value;
            bytes += sizeof(*list) + data_bytes(list->values);
            if (kind != RC_LIST) for (long long j = 0; j < list->length; j++)
                push((void *)(uintptr_t)list->values[j]);
        } else {
            assert(kind == RC_RECORD || kind == RC_SCALAR_RECORD);
            MinyarRecord *record = value;
            bytes += sizeof(*record) + (size_t)record->length * (sizeof(long long) + (kind == RC_RECORD));
            if (kind == RC_RECORD) {
                unsigned char *map = (unsigned char *)(record->values + record->length);
                for (long long j = 0; j < record->length; j++) if (map[j] & 1)
                    push((void *)(uintptr_t)record->values[j]);
            }
        }
    }
    assert(bytes <= rc_bytes);
    return bytes;
}
static size_t owner_bytes(void) {
    assert(!rc_frames);
    size_t bytes = 0;
    for (RcFrame *f = rc_free_frames; f; f = f->previous) {
        bytes += sizeof(*f) + f->local_capacity * sizeof(void *);
#ifdef MINYAR_BOUNDED_RC
        bytes += f->local_capacity * sizeof(size_t);
#else
        bytes += f->temporary_capacity * sizeof(void *);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    for (RcFrame *f = rc_bounded_frame_head; f; f = f->previous)
        bytes += sizeof(*f) + f->local_capacity * (sizeof(void *) + sizeof(size_t));
    for (RcTemporaryChunk *c = rc_bounded_chunk_head; c; c = c->next) bytes += sizeof(*c);
#else
    bytes += rc_pending_capacity * sizeof(*rc_pending);
#endif
    return bytes;
}
#endif

static void accounting(Event *e, MinyarList *snapshots, MinyarList *values) {
    e->pending = rc_pending_count;
    e->managed = e->live = e->owners = -1;
#ifdef EVENT_DIAGNOSTIC
    e->managed = (long long)rc_bytes;
    e->live = (long long)live_bytes(snapshots, values);
    e->owners = (long long)owner_bytes();
#else
    (void)snapshots; (void)values;
#endif
}
static void clear_caches(void) {
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames; rc_free_frames = f->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
#else
        free(f->locals); free(f->temporaries); free(f);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_cached_frame_bytes = 0;
#else
    free(rc_pending);
#endif
}
int main(int argc, char **argv) {
    assert(argc == 9);
    size_t count = parse(argv[1], 128, 1000000), width = parse(argv[2], 4, 8192);
    size_t seed = parse(argv[3], 1, 1000000000), spacing = parse(argv[4], 0, 1000000);
    size_t burst = parse(argv[5], 1, 16), per_cycle = count / CYCLES;
    assert(count % CYCLES == 0 && per_cycle % burst == 0);
    Event *events = calloc(count, sizeof(*events)); assert(events);
    long long *expected = malloc(count * sizeof(*expected)); assert(expected);
    FILE *oracle = fopen(argv[6], "r"); assert(oracle);
    for (size_t i = 0; i < count; i++) assert(fscanf(oracle, "%lld", &expected[i]) == 1);
    long long extra; assert(fscanf(oracle, "%lld", &extra) == EOF); assert(!fclose(oracle));
    Recovery recovery[CYCLES] = {{0}};
#ifdef __APPLE__
    assert(!mach_timebase_info(&timebase));
#endif
#ifdef EVENT_DIAGNOSTIC
    scan_capacity = 1;
    while (scan_capacity < width * 128 + 8192) scan_capacity *= 2;
    seen = calloc(scan_capacity, sizeof(*seen)); pending = malloc(scan_capacity * sizeof(*pending));
    assert(seen && pending);
    assert(spacing == 0 && burst == 1);
#endif
    MinyarList *snapshots = eventSetup((long long)width), *values = eventValues();
    drain();
    uint64_t quiet = spacing ? UINT64_C(10000000) : 0, clock_min = UINT64_MAX;
#ifndef EVENT_DIAGNOSTIC
    for (size_t i = 0; i < 10000; i++) {
        uint64_t t = now_ns(), delta = now_ns() - t;
        if (delta && delta < clock_min) clock_min = delta;
    }
#endif
    uint64_t origin = 0, total_service = 0, finish = 0;
#ifndef EVENT_DIAGNOSTIC
    origin = now_ns();
#endif
    for (size_t cycle = 0; cycle < CYCLES; cycle++) {
        uint64_t base = cycle * (per_cycle * spacing + quiet);
        for (size_t j = 0; j < per_cycle; j++) {
            size_t i = cycle * per_cycle + j;
            Event *e = &events[i];
            e->arrival = base + (j / burst) * burst * spacing;
#ifndef EVENT_DIAGNOSTIC
            if (spacing) wait_until(origin + e->arrival);
            e->start = now_ns() - origin;
#endif
            e->result = eventApply(snapshots, values, (long long)width, (long long)i,
                                   (long long)seed, SHOCK_EVERY);
#ifndef EVENT_DIAGNOSTIC
            finish = now_ns() - origin;
            e->service = finish - e->start;
            e->response = spacing ? finish - e->arrival : e->service;
            total_service += e->service;
#endif
            assert(e->result == expected[i]);
            accounting(e, snapshots, values);
        }
        Recovery *r = &recovery[cycle];
        r->before = rc_pending_count;
#ifdef EVENT_DIAGNOSTIC
        r->polls = drain();
#else
        uint64_t boundary = origin + base + per_cycle * spacing;
        uint64_t deadline = boundary + quiet;
        if (spacing) wait_until(boundary);
        uint64_t start = now_ns(); r->start = start - origin;
#ifdef MINYAR_BOUNDED_RC
        while (rc_pending_count && (!spacing || now_ns() < deadline)) {
            assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET)); r->polls++;
        }
#endif
        uint64_t end = now_ns(); r->duration = end - start;
        r->overrun = spacing && end > deadline ? end - deadline : 0;
        if (spacing) wait_until(deadline);
#endif
        r->after = rc_pending_count;
        Event state = {0}; accounting(&state, snapshots, values);
        r->managed = state.managed; r->live = state.live; r->owners = state.owners;
    }
    size_t final_pending = rc_pending_count;
    minyar_rc_release(snapshots); minyar_rc_release(values); drain(); clear_caches();
    uint64_t lifecycle = 0;
    long long final_bytes = -1, admissions = -1;
#ifdef EVENT_DIAGNOSTIC
    final_bytes = (long long)rc_bytes; admissions = (long long)stack_admissions;
    assert(!rc_bytes && !rc_object_count && !rc_frames && !rc_pending_count);
#ifdef MINYAR_BOUNDED_RC
    assert(!rc_heap_allocation_count);
#endif
    free(seen); free(pending);
#else
    lifecycle = now_ns() - origin;
#endif
    FILE *out = fopen(argv[7], "w"); assert(out);
    fprintf(out, "event,cycle,kind,arrival_ns,start_ns,service_ns,response_ns,result,pending,managed_bytes,live_bytes,owner_bytes\n");
    for (size_t i = 0; i < count; i++) {
        Event *e = &events[i];
        fprintf(out, "%zu,%zu,%s,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%lld,%zu,%lld,%lld,%lld\n",
            i, i / per_cycle, i % SHOCK_EVERY ? "ordinary" : "rebuild", e->arrival,
            e->start, e->service, e->response, e->result, e->pending, e->managed, e->live, e->owners);
    }
    assert(!fclose(out));
    out = fopen(argv[8], "w"); assert(out);
    fprintf(out, "cycle,pending_before,pending_after,polls,start_ns,duration_ns,overrun_ns,managed_bytes,live_bytes,owner_bytes\n");
    for (size_t i = 0; i < CYCLES; i++) {
        Recovery *r = &recovery[i];
        fprintf(out, "%zu,%zu,%zu,%zu,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%lld,%lld,%lld\n",
                i, r->before, r->after, r->polls, r->start, r->duration, r->overrun, r->managed, r->live, r->owners);
    }
    assert(!fclose(out));
    printf("{\"events\":%zu,\"width\":%zu,\"seed\":%zu,\"spacing_ns\":%zu,\"burst\":%zu,"
           "\"total_service_ns\":%" PRIu64 ",\"lifecycle_ns\":%" PRIu64 ",\"pending_before_teardown\":%zu,"
           "\"final_bytes\":%lld,\"stack_admissions\":%lld,\"clock_positive_min_ns\":%" PRIu64 "}\n",
           count, width, seed, spacing, burst, total_service, lifecycle, final_pending,
           final_bytes, admissions, clock_min == UINT64_MAX ? 0 : clock_min);
    free(events); free(expected);
    return 0;
}
