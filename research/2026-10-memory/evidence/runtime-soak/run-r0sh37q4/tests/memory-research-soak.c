/* Sustained mixed payload/reuse test. Independent bounded arrays are the oracle;
 * this is loaded-host validation, not a benchmark or a generated-code test. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#define _POSIX_C_SOURCE 200809L
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <time.h>
#include <unistd.h>

enum { SLOTS = 32, LIMIT = 4096, LIST_LENGTH = 64, RING = 64 };
static unsigned long long epochs, api_calls, checks, polls, polled_units, recoveries;
static unsigned random_state, original_seed;
static int current_slot;
static struct { unsigned long long epoch; unsigned random; int slot, action; } ring[RING];
static size_t ring_count, requested_peak, charged_peak;
static double operation_wall_max;
#define API(expression) (api_calls++, (expression))
static void fail(const char *expression, int line) {
    fprintf(stderr, "Soak assertion failed at line %d: %s; seed=%u epoch=%llu slot=%d\n",
            line, expression, original_seed, epochs, current_slot);
    size_t count = ring_count < RING ? ring_count : RING;
    for (size_t i = 0; i < count; i++) {
        size_t index = (ring_count - count + i) % RING;
        fprintf(stderr, "trace epoch=%llu random=%u slot=%d action=%d\n",
                ring[index].epoch, ring[index].random, ring[index].slot, ring[index].action);
    }
    exit(70);
}
#define CHECK(expression) do { checks++; if (!(expression)) fail(#expression, __LINE__); } while (0)

static unsigned next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}
static double monotonic(void) {
    struct timespec value;
    CHECK(clock_gettime(CLOCK_MONOTONIC, &value) == 0);
    return value.tv_sec + value.tv_nsec / 1e9;
}
static size_t bounded_poll(size_t budget) {
    size_t before = rc_object_count;
    size_t work = API(minyar_rc_poll(budget));
    CHECK(work <= budget && before >= rc_object_count && before - rc_object_count <= work);
    polls++;
    polled_units += work;
    return work;
}
static struct Slot {
    MinyarText *text;
    MinyarBytes *bytes;
    MinyarList *list, *references;
    MinyarRecord *record;
    unsigned char text_oracle[LIMIT + 1], bytes_oracle[LIMIT];
    size_t text_length, bytes_length;
    long long list_oracle[LIST_LENGTH], scalar;
} slots[SLOTS];

/* This decoder reads the independently generated valid oracle, not runtime
 * character offsets. Payload generation never emits malformed UTF-8. */
static size_t decode(const unsigned char *bytes, size_t length, unsigned *scalars) {
    size_t count = 0;
    for (size_t i = 0; i < length;) {
        unsigned first = bytes[i++], value;
        size_t continuation;
        if (first < 128) { value = first; continuation = 0; }
        else if (first < 224) { value = first & 31; continuation = 1; }
        else if (first < 240) { value = first & 15; continuation = 2; }
        else { value = first & 7; continuation = 3; }
        CHECK(i + continuation <= length);
        for (size_t j = 0; j < continuation; j++) {
            CHECK((bytes[i] & 192) == 128);
            value = (value << 6) | (bytes[i++] & 63);
        }
        scalars[count++] = value;
    }
    return count;
}
static void verify_text(const MinyarText *text, const unsigned char *expected, size_t length) {
    CHECK(text->byte_length == (long long)length);
    CHECK(!memcmp(text->bytes, expected, length));
    unsigned scalars[LIMIT];
    size_t count = decode(expected, length, scalars);
    CHECK(API(minyar_text_length(text)) == (long long)count);
    for (size_t index = 0; index < count; index++)
        if (index < 3 || index + 3 >= count || index % 64 == 0)
            CHECK(API(minyar_text_character_at(text, (long long)index)) == scalars[index]);
}
static void verify(struct Slot *slot) {
    verify_text(slot->text, slot->text_oracle, slot->text_length);
    CHECK(API(minyar_bytes_length(slot->bytes)) == (long long)slot->bytes_length);
    CHECK(!memcmp(slot->bytes->bytes, slot->bytes_oracle, slot->bytes_length));
    CHECK(API(minyar_list_length(slot->list)) == LIST_LENGTH);
    for (long long index = 0; index < LIST_LENGTH; index++)
        CHECK(API(minyar_list_get(slot->list, index)) == slot->list_oracle[index]);
    CHECK(API(minyar_list_get(slot->references, 0)) == (long long)(uintptr_t)slot->text);
    CHECK(API(minyar_record_get(slot->record, 0)) == slot->scalar);
    CHECK(API(minyar_record_get(slot->record, 1)) == (long long)(uintptr_t)slot->text);
}
static void fresh_text(struct Slot *slot, unsigned choice) {
    size_t length = choice % 257;
    memset(slot->text_oracle, 'a' + choice % 26, length);
    if (choice & 1) {
        memcpy(slot->text_oracle + length, "é🙂", 6);
        length += 6;
    }
    slot->text_oracle[length] = 0;
    slot->text_length = length;
    slot->text = API(copy_c_text((const char *)slot->text_oracle));
}
static void initialize(void) {
    for (current_slot = 0; current_slot < SLOTS; current_slot++) {
        struct Slot *slot = &slots[current_slot];
        fresh_text(slot, next_random());
        slot->bytes = API(minyar_bytes_new(0));
        slot->bytes_length = 0;
        slot->list = API(minyar_list_new());
        for (long long index = 0; index < LIST_LENGTH; index++) {
            slot->list_oracle[index] = index;
            API(minyar_list_add(slot->list, index));
        }
        slot->references = API(minyar_list_new());
        API(minyar_list_references(slot->references));
        API(minyar_list_add(slot->references, (long long)(uintptr_t)slot->text));
        slot->record = API(minyar_record_new(2));
        slot->scalar = 0;
        API(minyar_record_set_scalar(slot->record, 0, 0));
        API(minyar_record_set_reference(slot->record, 1, (long long)(uintptr_t)slot->text));
        verify(slot);
    }
}
static void epoch(int mutant) {
    unsigned choice = next_random();
    current_slot = (int)(choice % SLOTS);
    struct Slot *slot = &slots[current_slot];
    ring[ring_count % RING].epoch = epochs;
    ring[ring_count % RING].random = choice;
    ring[ring_count % RING].slot = current_slot;
    ring[ring_count % RING].action = (int)((choice >> 8) % 4);
    ring_count++;
    API(minyar_rc_enter(9));
    API(minyar_rc_local(8, slot->text));
    API(minyar_rc_borrow(slot->text));
    API(minyar_rc_step());
    API(minyar_rc_leave());
    MinyarText *alias = slot->text;
    API(minyar_rc_retain(alias));
    unsigned char prior[LIMIT + 1];
    size_t prior_length = slot->text_length;
    memcpy(prior, slot->text_oracle, prior_length + 1);
    if (slot->text_length > LIMIT / 2 || (choice & 15) == 0) {
        API(minyar_rc_release(slot->text));
        fresh_text(slot, choice >> 8);
    } else if (choice & 16) {
        slot->text = API(minyar_join_text_take_left(slot->text, slot->text));
        memcpy(slot->text_oracle + prior_length, prior, prior_length);
        slot->text_length *= 2;
        slot->text_oracle[slot->text_length] = 0;
    } else {
        MinyarText *suffix = API(copy_c_text("!"));
        if (choice & 32) {
            MinyarText *joined = API(minyar_join_text(slot->text, suffix));
            API(minyar_rc_release(slot->text));
            slot->text = joined;
        } else {
            slot->text = API(minyar_join_text_take_left(slot->text, suffix));
        }
        API(minyar_rc_release(suffix));
        slot->text_oracle[slot->text_length++] = '!';
        slot->text_oracle[slot->text_length] = 0;
    }
    verify_text(alias, prior, prior_length);
    unsigned expected[LIMIT];
    size_t characters = decode(prior, prior_length, expected);
    MinyarText *view = API(minyar_text_slice(alias, 0, (long long)characters));
    API(minyar_rc_release(alias));
    verify_text(view, prior, prior_length);
    API(minyar_rc_release(view));
    API(minyar_list_set(slot->references, 0, (long long)(uintptr_t)slot->text));
    API(minyar_record_replace(slot->record, 1, (long long)(uintptr_t)slot->text, 0));
    size_t position = (choice >> 10) % LIST_LENGTH;
    slot->list_oracle[position] = (long long)choice - 2147483648LL;
    API(minyar_rc_retain(slot->list));
    MinyarList *list_alias = slot->list;
    API(minyar_list_set(list_alias, (long long)position, slot->list_oracle[position]));
    CHECK(API(minyar_list_get(slot->list, (long long)position)) == slot->list_oracle[position]);
    API(minyar_rc_release(list_alias));
    size_t length = (choice >> 12) % LIMIT;
    API(minyar_rc_retain(slot->bytes));
    MinyarBytes *bytes_alias = slot->bytes;
    API(minyar_bytes_resize(bytes_alias, (long long)length));
    if (length > slot->bytes_length)
        memset(slot->bytes_oracle + slot->bytes_length, 0, length - slot->bytes_length);
    slot->bytes_length = length;
    if (length) {
        position = (choice >> 5) % length;
        slot->bytes_oracle[position] = (unsigned char)choice;
        API(minyar_bytes_set(bytes_alias, (long long)position, (unsigned char)choice));
    }
    if (length >= 8) {
        unsigned long long value = ((unsigned long long)choice << 32) | next_random();
        API(minyar_bytes_set_int64(bytes_alias, 0, (long long)value));
        for (size_t index = 0; index < 8; index++)
            slot->bytes_oracle[index] = (unsigned char)(value >> (index * 8));
        CHECK((unsigned long long)API(minyar_bytes_get_int64(slot->bytes, 0)) == value);
    }
    API(minyar_rc_release(bytes_alias));
    slot->scalar = (long long)epochs;
    API(minyar_rc_retain(slot->record));
    API(minyar_record_set_scalar(slot->record, 0, slot->scalar));
    CHECK(API(minyar_record_get(slot->record, 0)) == slot->scalar);
    API(minyar_rc_release(slot->record));
    if (mutant && epochs == 512 && length)
        slot->bytes_oracle[0] ^= 1; /* Calibrates the independent payload oracle. */
    verify(slot);
    bounded_poll(MINYAR_RC_POLL_BUDGET);
    CHECK(rc_bytes <= 4 * 1024 * 1024);
    if (rc_bytes > requested_peak) requested_peak = rc_bytes;
#ifdef MINYAR_BOUNDED_HEAP
    CHECK(minyar_pool_used <= 8 * 1024 * 1024);
    if (minyar_pool_used > charged_peak) charged_peak = minyar_pool_used;
#endif
}
static void recover(void) {
    for (current_slot = 0; current_slot < SLOTS; current_slot++) {
        struct Slot *slot = &slots[current_slot];
        verify(slot);
        API(minyar_rc_release(slot->text));
        API(minyar_rc_release(slot->bytes));
        API(minyar_rc_release(slot->list));
        API(minyar_rc_release(slot->references));
        API(minyar_rc_release(slot->record));
    }
    size_t remaining = 0;
    while (rc_pending_count) {
        CHECK(bounded_poll(MINYAR_RC_POLL_BUDGET) > 0);
        CHECK(++remaining < 1000000);
    }
    CHECK(!rc_frames && !rc_object_count && !rc_bytes);
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes = 0;
#ifdef MINYAR_BOUNDED_HEAP
    CHECK(!minyar_pool_used);
#else
    CHECK(!rc_heap_allocation_count);
#endif
    recoveries++;
}
static void summary(double started, int final) {
    printf("{\"final\":%d,\"seed\":%u,\"elapsed_monotonic_seconds\":%.6f,"
           "\"epochs\":%llu,\"counted_public_api_calls\":%llu,\"assertions\":%llu,"
           "\"explicit_polls\":%llu,\"explicit_poll_units\":%llu,\"full_recoveries\":%llu,"
           "\"requested_peak\":%zu,\"charged_peak\":%zu,\"sampled_epoch_wall_max_seconds\":%.9f}\n",
           final, original_seed, monotonic() - started, epochs, api_calls, checks, polls,
           polled_units, recoveries, requested_peak, charged_peak, operation_wall_max);
}
int main(int argc, char **argv) {
    CHECK(argc == 4);
    double duration = strtod(argv[1], NULL);
    original_seed = random_state = (unsigned)strtoul(argv[2], NULL, 0);
    int mutant = atoi(argv[3]);
    CHECK(duration > 0 && random_state);
    setvbuf(stdout, NULL, _IONBF, 0);
    double started = monotonic(), next_summary = 60;
    initialize();
    while (monotonic() - started < duration) {
        clock_t cpu_start = clock();
        for (size_t index = 0; index < 256; index++) {
            double operation_start = 0;
            if (epochs % 1024 == 0) operation_start = monotonic();
            epoch(mutant);
            if (operation_start) {
                double elapsed = monotonic() - operation_start;
                if (elapsed > operation_wall_max) operation_wall_max = elapsed;
            }
            epochs++;
            if (epochs % 1024 == 0) {
                recover();
                initialize();
            }
        }
        double cpu = (double)(clock() - cpu_start) / CLOCKS_PER_SEC;
        double pause = cpu * (1.0 / 0.08 - 1.0);
        struct timespec delay = {(time_t)pause, (long)((pause - (time_t)pause) * 1e9)};
        CHECK(nanosleep(&delay, NULL) == 0);
        double elapsed = monotonic() - started;
        if (elapsed >= next_summary) {
            summary(started, 0);
            next_summary += 60;
        }
    }
    recover();
    summary(started, 1);
    return 0;
}
