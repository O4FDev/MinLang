/* Public-ABI ownership replay. The snapshot-only destructor hook observes;
 * it neither allocates nor calls the runtime or changes the queue schedule. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define MINYAR_RC_TESTING 1
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { MAX_OBJECTS = 8192, MAX_ARGS = 256 };
enum { POINTER_SLOTS = 32768 };
static void *addresses[MAX_OBJECTS], *roots[64];
static size_t pointer_generations[POINTER_SLOTS];
static unsigned kinds[MAX_OBJECTS];
static unsigned char freed[MAX_OBJECTS], expected_live[MAX_OBJECTS];
static size_t generations, destructions, observed_reuse, step_number;

static size_t pointer_slot(void *pointer) {
    size_t slot = ((uintptr_t)pointer >> 4) * UINT64_C(11400714819323198485) & (POINTER_SLOTS - 1);
    while (pointer_generations[slot] && addresses[pointer_generations[slot]] != pointer)
        slot = (slot + 1) & (POINTER_SLOTS - 1);
    return slot;
}

static void research_on_free(void *pointer) {
    size_t id = pointer_generations[pointer_slot(pointer)];
    if (id && !freed[id]) {
        if (expected_live[id]) {
            fprintf(stderr, "LIVE FREE generation=%zu operation=%zu\n", id, step_number);
            abort();
        }
        freed[id] = 1;
        destructions++;
        return;
    }
    fputs("FREE OF UNKNOWN OR ALREADY FREED GENERATION\n", stderr);
    abort();
}

#ifndef MINYAR_RESEARCH_RUNTIME
#error This fixture requires an isolated, explicitly instrumented runtime snapshot.
#endif
#include MINYAR_RESEARCH_RUNTIME

static void *value(size_t id) {
    assert(id <= generations && (!id || !freed[id]));
    return addresses[id];
}

static size_t identity(void *pointer) {
    if (!pointer) return 0;
    size_t id = pointer_generations[pointer_slot(pointer)];
    if (id && !freed[id]) return id;
    fputs("LIVE PAYLOAD REFERENCES FREED OR UNKNOWN GENERATION\n", stderr);
    abort();
}

static uint64_t mix(uint64_t hash, uint64_t item) {
    return (hash ^ item) * UINT64_C(1099511628211);
}

static uint64_t payload_digest(void) {
    uint64_t hash = UINT64_C(1469598103934665603);
    for (size_t id = 1; id <= generations; id++) {
        if (!expected_live[id]) continue;
        assert(!freed[id]);
        hash = mix(hash, id);
        hash = mix(hash, kinds[id]);
        if (kinds[id] == 3) {
            MinyarList *list = value(id);
            assert(list->length >= 0 && list->length <= 129);
            hash = mix(hash, (uint64_t)list->length);
            for (long long i = 0; i < list->length; i++)
                hash = mix(hash, identity((void *)(uintptr_t)minyar_list_get(list, i)));
        } else {
            MinyarRecord *record = value(id);
            assert(record->length > 0 && record->length <= 130);
            hash = mix(hash, (uint64_t)record->length);
            hash = mix(hash, (uint64_t)minyar_record_get(record, 0));
            for (long long i = 1; i < record->length; i++)
                hash = mix(hash, identity((void *)(uintptr_t)minyar_record_get(record, i)));
        }
    }
    return hash;
}

static size_t poll_checked(size_t requested) {
#ifdef MINYAR_BOUNDED_RC
    size_t before = destructions;
    size_t work = minyar_rc_poll(requested);
    assert(work <= requested && work <= MINYAR_RC_POLL_BUDGET);
    assert(destructions - before <= work);
    return work;
#else
    (void)requested;
    return 0; /* Eager release already drains ownership work. */
#endif
}

static void clear_frame_cache(void) {
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
#else
        free(frame->locals);
        free(frame->temporaries);
        free(frame);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_cached_frame_bytes = 0;
#else
    free(rc_pending);
    rc_pending = NULL;
    rc_pending_capacity = 0;
#endif
}

int main(int argc, char **argv) {
    assert(argc == 3);
    FILE *trace = fopen(argv[1], "r"), *observations = fopen(argv[2], "w");
    assert(trace && observations);
    size_t peak_live = 0, peak_retained = 0, polls = 0, poll_work = 0;
    unsigned opcode;
    while (fscanf(trace, "%u", &opcode) == 1) {
        step_number++;
        size_t count;
        uint64_t args[MAX_ARGS];
        assert(fscanf(trace, "%zu", &count) == 1 && count <= MAX_ARGS);
        for (size_t i = 0; i < count; i++) {
            unsigned long long parsed;
            assert(fscanf(trace, "%llu", &parsed) == 1);
            args[i] = (uint64_t)parsed;
        }
        size_t live_count;
        assert(fscanf(trace, "%zu", &live_count) == 1 && live_count < MAX_OBJECTS);
        memset(expected_live, 0, sizeof(expected_live));
        for (size_t i = 0; i < live_count; i++) {
            size_t id;
            assert(fscanf(trace, "%zu", &id) == 1 && id && id < MAX_OBJECTS);
            assert(!expected_live[id]);
            expected_live[id] = 1;
        }
        unsigned long long expected_digest;
        assert(fscanf(trace, "%llu", &expected_digest) == 1);
        switch (opcode) {
        case 1: { /* new */
            assert(count >= 3);
            unsigned kind = (unsigned)args[0];
            size_t id = (size_t)args[1], slot = (size_t)args[2];
            assert(id == generations + 1 && id < MAX_OBJECTS && slot < 64 && !roots[slot]);
            void *object;
            if (kind == 3) {
                object = minyar_list_new();
            } else {
                assert(kind == 1 || kind == 2);
                object = kind == 1 ? minyar_record_new_scalar(1) : minyar_record_new((long long)count - 2);
            }
            size_t pointer_index = pointer_slot(object), previous = pointer_generations[pointer_index];
            if (previous) {
                assert(freed[previous]);
                observed_reuse++;
            }
            generations = id;
            addresses[id] = roots[slot] = object;
            pointer_generations[pointer_index] = id;
            kinds[id] = kind;
            if (kind == 3) {
                minyar_list_references(object);
                for (size_t i = 3; i < count; i++)
                    minyar_list_add(object, (long long)(uintptr_t)value((size_t)args[i]));
            } else {
                minyar_record_set_scalar(object, 0, (long long)id * 1009 + 17);
                for (size_t i = 3; i < count; i++)
                    minyar_record_set_reference(object, (long long)i - 2, (long long)(uintptr_t)value((size_t)args[i]));
            }
            break;
        }
        case 2: /* alias */
            roots[args[1]] = value((size_t)args[0]);
            minyar_rc_retain(roots[args[1]]);
            break;
        case 3: { /* drop */
            void *previous = roots[args[0]];
            roots[args[0]] = NULL;
            minyar_rc_release(previous);
            break;
        }
        case 4: minyar_rc_enter((long long)args[0]); break;
        case 5: minyar_rc_local((long long)args[0], value((size_t)args[1])); break;
        case 6: {
            void *previous = roots[args[1]];
            roots[args[1]] = NULL;
            minyar_rc_local_take((long long)args[0], previous);
            break;
        }
        case 7:
#ifdef MINYAR_BOUNDED_RC
            roots[args[1]] = rc_bounded_local_value(rc_frames, (size_t)args[0]);
#else
            roots[args[1]] = rc_frames->locals[args[0]];
#endif
            minyar_rc_local_move((long long)args[0]);
            break;
        case 8: minyar_rc_borrow(value((size_t)args[0])); break;
        case 9: {
            void *previous = roots[args[0]];
            roots[args[0]] = NULL;
            minyar_rc_keep(previous);
            break;
        }
        case 10: minyar_rc_step(); break;
        case 11: minyar_rc_leave(); break;
        case 12:
            if (kinds[args[0]] == 3)
                minyar_list_set(value((size_t)args[0]), (long long)args[1], (long long)(uintptr_t)value((size_t)args[2]));
            else
                minyar_record_replace(value((size_t)args[0]), (long long)args[1] + 1, (long long)(uintptr_t)value((size_t)args[2]), 0);
            break;
        case 13:
            minyar_list_add(value((size_t)args[0]), (long long)(uintptr_t)value((size_t)args[1]));
            break;
        case 14:
            polls++;
            poll_work += poll_checked((size_t)args[0]);
            break;
        default: assert(0);
        }
        assert(generations - destructions == rc_object_count);
        assert(payload_digest() == (uint64_t)expected_digest);
        size_t retained = 0;
        fprintf(observations, "%zu live", step_number);
        for (size_t id = 1; id <= generations; id++)
            if (expected_live[id]) fprintf(observations, " %zu", id);
        fputs(" retained", observations);
        for (size_t id = 1; id <= generations; id++)
            if (!expected_live[id] && !freed[id]) {
                retained++;
                fprintf(observations, " %zu", id);
            }
        fputc('\n', observations);
        if (live_count > peak_live) peak_live = live_count;
        if (retained > peak_retained) peak_retained = retained;
    }
    assert(feof(trace) && !ferror(trace));
    for (size_t id = 1; id <= generations; id++) assert(!expected_live[id]);
    assert(!rc_frames);
    size_t drain_polls = 0, drain_work = 0;
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) {
        assert(drain_polls++ < 1000000);
        size_t work = poll_checked(SIZE_MAX);
        assert(work > 0);
        drain_work += work;
    }
#endif
    assert(generations == destructions && !rc_object_count && !rc_bytes);
    clear_frame_cache();
#ifdef MINYAR_BOUNDED_RC
#ifdef MINYAR_SYSTEM_HEAP
    assert(!rc_heap_allocation_count);
#else
    assert(!minyar_pool_used);
#endif
#endif
    assert(fclose(trace) == 0 && fclose(observations) == 0);
    printf("{\"operations\":%zu,\"objects\":%zu,\"destructions\":%zu,\"peak_live\":%zu,\"peak_retained\":%zu,\"address_reuses\":%zu,\"explicit_polls\":%zu,\"explicit_poll_work\":%zu,\"drain_polls\":%zu,\"drain_work\":%zu}\n",
           step_number, generations, destructions, peak_live, peak_retained, observed_reuse, polls, poll_work, drain_polls, drain_work);
    return 0;
}
