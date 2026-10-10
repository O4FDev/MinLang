/* Test-only system allocator instrumentation. Production sources are untouched.
 * Inspired by Zig FailingAllocator and Lua debug_realloc; original implementation.
 * Every successful resize moves, so a surviving interior pointer is observable.
 */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef union FaultHeader {
    max_align_t alignment;
    struct { size_t size; uint64_t magic; } value;
} FaultHeader;
#define FAULT_MAGIC UINT64_C(0x4d494e5941524641)
#define FAULT_SUFFIX_SIZE 16
#define FAULT_FRESH_BYTE 0xa5
#define FAULT_FREED_BYTE 0xdd
#define FAULT_SUFFIX_BYTE 0xe7
static size_t fault_allocations, fault_resizes, fault_moved, fault_fired;
static size_t fault_allocation_index, fault_resize_index;
static int fault_initialized, fault_explicit_exit;
typedef struct { size_t kind, size, live; } FaultEvent;
typedef struct { size_t required, events, allocations, resizes; } FaultPeak;
static FaultEvent *fault_events;
static FaultPeak *fault_peaks;
static size_t fault_event_count, fault_event_capacity, fault_peak_count, fault_peak_capacity;
static size_t fault_live_bytes, fault_peak_required, fault_byte_budget, fault_failed_required;
static int fault_budget_enabled;
static _Noreturn void fault_exit(int status);

static size_t fault_number(const char *name, int allow_zero) {
    const char *value = getenv(name);
    if (!value || !*value) return 0;
    char *end;
    errno = 0;
    unsigned long long parsed = strtoull(value, &end, 10);
    if (errno == ERANGE || *end || strspn(value, "0123456789") != strlen(value) || (!parsed && !allow_zero) || parsed > SIZE_MAX) {
        fputs("invalid allocation fault ordinal\n", stderr);
        exit(90);
    }
    return (size_t)parsed;
}

static size_t fault_index(const char *name) { return fault_number(name, 0); }

/* Bookkeeping storage is outside the target allocation budget and trace. */
static void *fault_grow_log(void *previous, size_t *capacity, size_t item_size) {
    if (*capacity > SIZE_MAX / 2 / item_size) abort();
    size_t next = *capacity ? *capacity * 2 : 64;
    void *result = realloc(previous, next * item_size);
    if (!result) abort();
    *capacity = next;
    return result;
}

static void fault_event(size_t kind, size_t size) {
    if (fault_event_count == fault_event_capacity)
        fault_events = fault_grow_log(fault_events, &fault_event_capacity, sizeof(*fault_events));
    fault_events[fault_event_count++] = (FaultEvent){kind, size, fault_live_bytes};
}

static void fault_init(void) {
    if (fault_initialized) return;
    fault_initialized = 1;
    fault_allocation_index = fault_index("MINYAR_FAIL_ALLOCATION");
    fault_resize_index = fault_index("MINYAR_FAIL_RESIZE");
    const char *budget = getenv("MINYAR_FAIL_BYTES");
    fault_budget_enabled = budget && *budget;
    fault_byte_budget = fault_number("MINYAR_FAIL_BYTES", 1);
}

static void *fault_raw_allocate(size_t size, size_t kind) {
    if (size > SIZE_MAX - sizeof(FaultHeader) - FAULT_SUFFIX_SIZE) return NULL;
    if (size > SIZE_MAX - fault_live_bytes) return NULL;
    fault_event(kind, size);
    size_t required = fault_live_bytes + size;
    if (required > fault_peak_required) {
        if (fault_peak_count == fault_peak_capacity)
            fault_peaks = fault_grow_log(fault_peaks, &fault_peak_capacity, sizeof(*fault_peaks));
        fault_peaks[fault_peak_count++] = (FaultPeak){required, fault_event_count, fault_allocations, fault_resizes};
        fault_peak_required = required;
    }
    if (fault_budget_enabled && required > fault_byte_budget) {
        fault_failed_required = required;
        fault_fired++;
        return NULL;
    }
    FaultHeader *header = malloc(sizeof(*header) + size + FAULT_SUFFIX_SIZE);
    if (!header) return NULL;
    header->value.size = size;
    header->value.magic = FAULT_MAGIC;
    memset(header + 1, FAULT_FRESH_BYTE, size);
    memset((unsigned char *)(header + 1) + size, FAULT_SUFFIX_BYTE, FAULT_SUFFIX_SIZE);
    fault_live_bytes = required;
    return header + 1;
}

static int fault_suffix_valid(FaultHeader *header) {
    assert(header->value.magic == FAULT_MAGIC);
    const unsigned char *suffix = (const unsigned char *)(header + 1) + header->value.size;
    for (size_t index = 0; index < FAULT_SUFFIX_SIZE; index++) {
        if (suffix[index] != FAULT_SUFFIX_BYTE) return 0;
    }
    return 1;
}

static void fault_check(FaultHeader *header) {
    if (!fault_suffix_valid(header)) {
        fputs("allocation suffix corrupted\n", stderr);
        fault_explicit_exit = 1;
        exit(94);
    }
}

static void *fault_malloc(size_t size) {
    fault_init();
    if (++fault_allocations == fault_allocation_index) {
        fault_fired++;
        return NULL;
    }
    return fault_raw_allocate(size, 1);
}

static void fault_free(void *pointer) {
    if (!pointer) return;
    FaultHeader *header = (FaultHeader *)pointer - 1;
    fault_check(header);
    fault_event(3, header->value.size);
    assert(header->value.size <= fault_live_bytes);
    fault_live_bytes -= header->value.size;
    /* Volatile stores keep native poisoning observable before real free. */
    volatile unsigned char *released = pointer;
    for (size_t index = 0; index < header->value.size; index++) released[index] = FAULT_FREED_BYTE;
    header->value.magic = 0;
    free(header); /* ASan poisons the old allocation, including its payload. */
}

static void *fault_realloc(void *pointer, size_t size) {
    if (!pointer) return fault_malloc(size);
    if (!size) { fault_free(pointer); return NULL; }
    fault_init();
    FaultHeader *old = (FaultHeader *)pointer - 1;
    fault_check(old);
    if (++fault_resizes == fault_resize_index) {
        fault_fired++;
        return NULL; /* Original allocation remains intact on refusal. */
    }
    void *replacement = fault_raw_allocate(size, 2);
    if (!replacement) return NULL;
    assert(replacement != pointer); /* Allocate before freeing to force movement. */
    memcpy(replacement, pointer, size < old->value.size ? size : old->value.size);
    fault_free(pointer);
    fault_moved++;
    return replacement;
}

static void *fault_calloc(size_t count, size_t size) {
    if (size && count > SIZE_MAX / size) return NULL;
    void *pointer = fault_malloc(count * size);
    if (pointer) memset(pointer, 0, count * size);
    return pointer;
}

#define malloc fault_malloc
#define calloc fault_calloc
#define realloc fault_realloc
#define free fault_free
#define exit fault_exit
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef exit

static _Noreturn void fault_exit(int status) {
    fault_explicit_exit = 1;
    exit(status);
}

__attribute__((destructor)) static void fault_report(void) {
    int corrupted = 0;
#ifdef MINYAR_COMPILER_ARENA
    /* Arenas intentionally survive to process exit, bypassing free/realloc. */
    MinyarArena *arenas[] = {&object_arena, &data_arena, &list_arena, &large_list_arena};
    for (size_t index = 0; index < sizeof(arenas) / sizeof(*arenas); index++) {
        for (MinyarArenaBlock *block = arenas[index]->block; block; block = block->next) {
            if (!fault_suffix_valid((FaultHeader *)block - 1)) corrupted = 1;
        }
    }
    if (corrupted) {
        fputs("allocation suffix corrupted\n", stderr);
        fault_explicit_exit = 1;
    }
#else
    if (!fault_explicit_exit) {
        assert(rc_frames == NULL);
        while (rc_pending_count) assert(minyar_rc_poll(32) > 0);
        assert(rc_object_count == rc_immortal_object_count);
    }
#endif
    const char *path = getenv("MINYAR_ALLOCATION_REPORT");
    if (path) {
        FILE *file = fopen(path, "wb");
        if (!file) abort();
        if (fprintf(file, "{\"allocations\":%zu,\"resizes\":%zu,\"moved\":%zu,"
                    "\"fired\":%zu,\"fatal_exit\":%d,\"live_bytes\":%zu,"
                    "\"peak_required\":%zu,\"failed_required\":%zu,\"events\":[",
                    fault_allocations, fault_resizes, fault_moved, fault_fired,
                    fault_explicit_exit, fault_live_bytes, fault_peak_required,
                    fault_failed_required) < 0) abort();
        for (size_t index = 0; index < fault_event_count; index++) {
            FaultEvent event = fault_events[index];
            if (fprintf(file, "%s[%zu,%zu,%zu]", index ? "," : "", event.kind, event.size, event.live) < 0) abort();
        }
        if (fputs("],\"peaks\":[", file) == EOF) abort();
        for (size_t index = 0; index < fault_peak_count; index++) {
            FaultPeak peak = fault_peaks[index];
            if (fprintf(file, "%s{\"required\":%zu,\"events\":%zu,\"allocations\":%zu,\"resizes\":%zu}",
                        index ? "," : "", peak.required, peak.events, peak.allocations, peak.resizes) < 0) abort();
        }
        if (fputs("]}\n", file) == EOF || fclose(file)) abort();
    }
    if (corrupted) {
        fflush(stderr);
        _Exit(94); /* Do not recursively call exit from an exit callback. */
    }
}

#ifdef MINYAR_FAULT_ARENA_SELF_TEST
int main(void) {
    MinyarArena *arenas[] = {&object_arena, &data_arena, &list_arena, &large_list_arena};
    for (size_t index = 0; index < sizeof(arenas) / sizeof(*arenas); index++) {
        arena_allocate(arenas[index], arenas[index]->block_size, _Alignof(max_align_t));
        arena_allocate(arenas[index], 1, _Alignof(max_align_t));
    }
    size_t corrupt = fault_index("MINYAR_FAULT_CORRUPT_ARENA");
    if (corrupt) {
        assert(corrupt <= 8);
        MinyarArenaBlock *block = arenas[(corrupt - 1) / 2]->block;
        if ((corrupt - 1) % 2) block = block->next;
        FaultHeader *header = (FaultHeader *)block - 1;
        ((unsigned char *)block)[header->value.size + FAULT_SUFFIX_SIZE - 1] = 0;
    }
    return 0;
}
#elif defined(MINYAR_FAULT_SELF_TEST)
int main(void) {
    unsigned char *pointer = fault_malloc(16);
    if (!pointer) return 91;
    for (size_t i = 0; i < 16; i++) assert(pointer[i] == FAULT_FRESH_BYTE);
    const char *corrupt = getenv("MINYAR_FAULT_CORRUPT_SUFFIX");
    if (corrupt) {
        /* Inside the wrapper's backing allocation, outside its payload. */
        size_t byte = fault_index("MINYAR_FAULT_CORRUPT_BYTE");
        assert(byte < FAULT_SUFFIX_SIZE);
        pointer[16 + byte] = 0;
        if (!strcmp(corrupt, "free")) fault_free(pointer);
        else if (!strcmp(corrupt, "resize")) (void)fault_realloc(pointer, 32);
        return 95; /* A missed canary must not look like a successful probe. */
    }
    memset(pointer, 0x5a, 16);
    unsigned char *moved = fault_realloc(pointer, 32);
    if (!moved) {
        for (size_t i = 0; i < 16; i++) assert(pointer[i] == 0x5a);
        fault_free(pointer);
        return 92;
    }
    for (size_t i = 0; i < 16; i++) assert(moved[i] == 0x5a);
    for (size_t i = 16; i < 32; i++) assert(moved[i] == FAULT_FRESH_BYTE);
    unsigned char *shrunk = fault_realloc(moved, 8);
    if (!shrunk) {
        for (size_t i = 0; i < 16; i++) assert(moved[i] == 0x5a);
        for (size_t i = 16; i < 32; i++) assert(moved[i] == FAULT_FRESH_BYTE);
        fault_free(moved);
        return 96;
    }
    for (size_t i = 0; i < 8; i++) assert(shrunk[i] == 0x5a);
    fault_free(shrunk);
    pointer = fault_calloc(8, 2);
    if (!pointer) return 93;
    for (size_t i = 0; i < 16; i++) assert(pointer[i] == 0);
    fault_free(pointer);
    return 0;
}
#endif
