/* Instrumented correctness endurance. CPU pacing is not a speed measurement. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static const void *watched_prefix;
static size_t watched_bytes, observed_prefix_copies;
static void *observed_memcpy(void *target, const void *source, size_t length) {
#ifndef MINYAR_RESEARCH_HIDE_PREFIX_COPY
    if (watched_prefix && source == watched_prefix && length == watched_bytes)
        observed_prefix_copies++;
#endif
    return memcpy(target, source, length);
}
#define MINYAR_RC_TESTING 1
#define memcpy observed_memcpy
#include "../runtime/minyar_runtime.c"
#undef memcpy

static uint64_t seed, epochs, recoveries, eligible, empty_eligible, fallbacks, copied;
static uint64_t ascii_joins, unknown_joins, unicode_joins;
static size_t requested_sample_max;
static int oracle_fault;
static struct {
    uint64_t epoch;
    size_t length;
    unsigned debt, text_mode;
} ring[64];

static void failure(const char *condition, unsigned line) {
    fprintf(stderr, "FAILED line %u: %s\n", line, condition);
    uint64_t first = epochs > 63 ? epochs - 63 : 0;
    for (uint64_t position = first; position <= epochs; position++) {
        size_t index = (size_t)(position % 64);
        fprintf(stderr, "{\"epoch\":%llu,\"length\":%zu,\"debt\":%u,\"text_mode\":%u}\n",
                (unsigned long long)ring[index].epoch, ring[index].length, ring[index].debt,
                ring[index].text_mode);
    }
    exit(90);
}
#define CHECK(condition)                                                                           \
    do {                                                                                           \
        if (!(condition))                                                                          \
            failure(#condition, __LINE__);                                                         \
    } while (0)

static double clock_seconds(clockid_t clock) {
    struct timespec value;
    CHECK(clock_gettime(clock, &value) == 0);
    return (double)value.tv_sec + (double)value.tv_nsec / 1e9;
}

static void drain(void) {
    size_t polls = 0;
    while (rc_pending_count) {
        size_t before = rc_object_count;
        size_t work = minyar_rc_poll(32);
        CHECK(work > 0 && work <= 32 && before - rc_object_count <= work);
        CHECK(++polls <= 1000000);
    }
}

static void recover(void) {
    drain();
    CHECK(!rc_frames && !rc_free_frames);
    CHECK(!rc_object_count && !rc_bytes && !rc_heap_allocation_count);
    recoveries++;
}

static uint64_t word(size_t position) {
    return (seed ^ (epochs * UINT64_C(0xd6e8feb86659fd93))) +
           (uint64_t)position * UINT64_C(0x9e3779b97f4a7c15);
}

static void scalar_epoch(size_t length, unsigned debt) {
    drain();
    MinyarList *source = minyar_list_new();
    for (size_t position = 0; position < length; position++) {
        uint64_t bits = word(position);
        long long value;
        memcpy(&value, &bits, sizeof(value));
        minyar_list_add(source, value);
    }
    minyar_rc_retain(source); /* A real surviving alias while the result is built. */
    CHECK(!rc_pending_count);
    if (debt) {
        rc_drop(minyar_record_new(4 * MINYAR_RC_POLL_BUDGET + 2));
        CHECK(rc_pending_count);
        fallbacks++;
    } else {
        eligible++;
        empty_eligible += length == 0;
    }
    watched_prefix = source->values;
    watched_bytes = length * sizeof(*source->values);
    observed_prefix_copies = 0;
    MinyarList *result = minyar_list_appended(source, -313, 0, 0);
    watched_prefix = NULL;
    CHECK(result != source && result->length == (long long)length + 1);
    CHECK(observed_prefix_copies == (!debt && length != 0));
    copied += observed_prefix_copies;
    CHECK(result->values[length] == -313);
    for (size_t position = 0; position < length; position++) {
        uint64_t bits;
        memcpy(&bits, &result->values[position], sizeof(bits));
        uint64_t expected = word(position);
        if (oracle_fault && epochs == 512 && position == 0)
            expected ^= 1; /* Corrupt only the independent oracle, not runtime data. */
        CHECK(bits == expected && result->values[position] == source->values[position]);
    }
    if (length) {
        long long saved = source->values[0];
        minyar_list_set(result, 0, 0);
        CHECK(source->values[0] == saved);
        minyar_list_set(result, 0, saved);
        minyar_list_set(source, 0, 7);
        CHECK(result->values[0] == saved);
    }
    minyar_rc_release(source);
    CHECK(source->length == (long long)length);
    minyar_rc_release(source);
    drain();
    for (size_t position = 0; position < length; position++) {
        uint64_t bits;
        memcpy(&bits, &result->values[position], sizeof(bits));
        CHECK(bits == word(position));
    }
    CHECK(result->values[length] == -313);
    minyar_rc_release(result);
}

static MinyarText *text(const unsigned char *bytes, size_t length, long long certificate) {
    unsigned char *storage = new_bytes((long long)length);
    memcpy(storage, bytes, length);
    storage[length] = 0;
    return new_text(storage, (long long)length, certificate);
}

static void text_epoch(unsigned mode) {
    static const unsigned char ascii[] = {'a', 0, 'b'};
    static const unsigned char unicode[] = {0xc3, 0xa9, 0xf0, 0x9f, 0x99, 0x82};
    const unsigned char *bytes = mode == 2 ? unicode : ascii;
    size_t length = mode == 2 ? sizeof(unicode) : sizeof(ascii);
    MinyarText *source = text(bytes, length, mode == 0 ? (long long)length : -1);
    if (mode == 2)
        CHECK(minyar_text_length(source) == 2); /* Already indexed Unicode stays uncertified. */
    minyar_rc_retain(source);
    MinyarText *empty = text(ascii, 0, 0);
    MinyarList *parts = minyar_list_new();
    minyar_list_references(parts);
    minyar_list_add(parts, (long long)(intptr_t)empty);
    minyar_list_add(parts, (long long)(intptr_t)source);
    MinyarText *joined = minyar_join_texts(parts);
    CHECK(joined != source && joined->byte_length == (long long)length);
    CHECK(joined->character_length == (mode == 0 ? (long long)length : -1));
    CHECK(!joined->character_offsets && !memcmp(joined->bytes, bytes, length));
    CHECK(minyar_text_length(joined) == (mode == 2 ? 2 : 3));
    CHECK(minyar_text_character_at(joined, 0) == (mode == 2 ? 0xe9 : 'a'));
    CHECK(minyar_text_character_at(joined, 1) == (mode == 2 ? 0x1f642 : 0));
    if (mode != 2)
        CHECK(minyar_text_character_at(joined, 2) == 'b');
    MinyarText *slice = minyar_text_slice(joined, 0, 1);
    CHECK(minyar_text_length(slice) == 1);
    CHECK(minyar_text_character_at(slice, 0) == (mode == 2 ? 0xe9 : 'a'));
    CHECK(!memcmp(source->bytes, bytes, length));
    ascii_joins += mode == 0;
    unknown_joins += mode == 1;
    unicode_joins += mode == 2;
    minyar_rc_release(slice);
    minyar_rc_release(joined);
    minyar_rc_release(parts);
    minyar_rc_release(empty);
    minyar_rc_release(source);
    CHECK(source->byte_length == (long long)length && !memcmp(source->bytes, bytes, length));
    minyar_rc_release(source);
}

static void summary(double started, int final) {
    printf("{\"final\":%d,\"seed\":%llu,\"elapsed_native_seconds\":%.9f,\"epochs\":%llu,"
           "\"recoveries\":%llu,\"eligible_scalar\":%llu,\"eligible_empty\":%llu,"
           "\"observed_nonempty_prefix_copies\":%llu,\"pending_debt_fallbacks\":%llu,"
           "\"certified_ascii_joins\":%llu,\"unknown_ascii_joins\":%llu,\"unicode_joins\":%llu,"
           "\"completed_epoch_requested_sample_max\":%zu,\"total_process_cpu_seconds\":%.9f}\n",
           final, (unsigned long long)seed, clock_seconds(CLOCK_MONOTONIC) - started,
           (unsigned long long)epochs, (unsigned long long)recoveries, (unsigned long long)eligible,
           (unsigned long long)empty_eligible, (unsigned long long)copied,
           (unsigned long long)fallbacks, (unsigned long long)ascii_joins,
           (unsigned long long)unknown_joins, (unsigned long long)unicode_joins,
           requested_sample_max, clock_seconds(CLOCK_PROCESS_CPUTIME_ID));
    fflush(stdout);
}

int main(int argc, char **argv) {
    CHECK(argc == 3 || argc == 4);
    double duration = strtod(argv[1], NULL);
    CHECK(duration > 0 && duration <= 1800);
    seed = strtoull(argv[2], NULL, 16);
    oracle_fault = argc == 4 && !strcmp(argv[3], "--oracle-red");
    static const size_t lengths[] = {0, 2, 31, 32, 1024, 8193};
    double started = clock_seconds(CLOCK_MONOTONIC), next_summary = started + 60;
    summary(started, 0);
    while (clock_seconds(CLOCK_MONOTONIC) - started < duration) {
        double batch_wall = clock_seconds(CLOCK_MONOTONIC);
        double batch_cpu = clock_seconds(CLOCK_PROCESS_CPUTIME_ID);
        for (unsigned iteration = 0; iteration < 16; iteration++) {
            size_t length = lengths[epochs % 6];
            unsigned debt = epochs % 17 == 0, mode = (unsigned)(epochs % 3);
            ring[epochs % 64].epoch = epochs;
            ring[epochs % 64].length = length;
            ring[epochs % 64].debt = debt;
            ring[epochs % 64].text_mode = mode;
            scalar_epoch(length, debt);
            text_epoch(mode);
            CHECK(rc_object_count <= 16 && !rc_frames && !rc_free_frames);
            if (rc_bytes > requested_sample_max)
                requested_sample_max = rc_bytes;
            CHECK(rc_bytes <= 4 * 1024 * 1024);
            epochs++;
            if (epochs % 128 == 0)
                recover();
        }
        double target = (clock_seconds(CLOCK_PROCESS_CPUTIME_ID) - batch_cpu) / .05;
        double remaining = target - (clock_seconds(CLOCK_MONOTONIC) - batch_wall);
        if (remaining > 0) {
            struct timespec pause = {(time_t)remaining,
                                     (long)((remaining - (time_t)remaining) * 1e9)};
            int status;
            do {
                status = nanosleep(&pause, &pause);
            } while (status < 0 && errno == EINTR);
            CHECK(status == 0);
        }
        if (clock_seconds(CLOCK_MONOTONIC) >= next_summary) {
            summary(started, 0);
            next_summary += 60;
        }
    }
    recover();
    CHECK(copied + empty_eligible == eligible);
    CHECK(eligible + fallbacks == epochs);
    CHECK(ascii_joins + unknown_joins + unicode_joins == epochs);
    summary(started, 1);
    return 0;
}
