/* Isolated compiler phase observations, never linked into production artifacts. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#ifndef PEER_PROFILE_PHASES
#define PEER_PROFILE_PHASES 12
#endif

typedef struct {
    uint64_t calls;
    uint64_t inclusive;
    uint64_t exclusive;
} Phase;

typedef struct {
    int id;
    uint64_t start;
    uint64_t children;
} Frame;

static Phase phases[PEER_PROFILE_PHASES];
static Frame frames[4096];
static unsigned depth;
static int initialized;

static uint64_t cpu_nanoseconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &now) != 0) {
        perror("phase profiler clock");
        exit(70);
    }
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}

static void report(void) {
    fprintf(stderr, "peer-profile {\"schema\":1,\"complete\":%s,\"phases\":[",
            depth == 0 ? "true" : "false");
    for (unsigned index = 0; index < PEER_PROFILE_PHASES; ++index) {
        fprintf(stderr,
                "%s{\"id\":%u,\"calls\":%" PRIu64 ",\"inclusive_ns\":%" PRIu64
                ",\"exclusive_ns\":%" PRIu64 "}",
                index ? "," : "", index, phases[index].calls, phases[index].inclusive,
                phases[index].exclusive);
    }
    fprintf(stderr, "]}\n");
}

void peer_profile_enter(int id) {
    assert(id >= 0 && id < PEER_PROFILE_PHASES);
    assert(depth < sizeof(frames) / sizeof(frames[0]));
    if (!initialized) {
        if (atexit(report) != 0) {
            fprintf(stderr, "phase profiler could not register evidence writer\n");
            exit(70);
        }
        initialized = 1;
    }
    frames[depth++] = (Frame){id, cpu_nanoseconds(), 0};
    phases[id].calls++;
}

void peer_profile_leave(int id) {
    uint64_t end = cpu_nanoseconds();
    assert(depth > 0 && frames[depth - 1].id == id);
    Frame frame = frames[--depth];
    assert(end >= frame.start);
    uint64_t elapsed = end - frame.start;
    assert(elapsed >= frame.children);
    phases[id].inclusive += elapsed;
    phases[id].exclusive += elapsed - frame.children;
    if (depth) {
        frames[depth - 1].children += elapsed;
    }
}
