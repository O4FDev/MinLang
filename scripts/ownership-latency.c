/* Diagnostic fixture: separately time construction and deterministic cleanup.
 * Compile with MINYAR_RUNTIME_SOURCE naming either runtime snapshot. */
#define _POSIX_C_SOURCE 200809L
#include <time.h>
#define MINYAR_RC_TESTING
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>

static double milliseconds(void) {
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return now.tv_sec * 1000.0 + now.tv_nsec / 1000000.0;
}

int main(int argc, char **argv) {
    assert(argc == 3);
    long long count = strtoll(argv[2], NULL, 10);
    assert(count > 0 && count <= 800000);
    double start = milliseconds();
    void *root = NULL;
    if (strcmp(argv[1], "chain") == 0) {
        for (long long i = 0; i < count; i++) {
            void *next = minyar_record_new(1);
            minyar_record_set_take(next, 0, (long long)(intptr_t)root);
            root = next;
        }
    } else {
        MinyarList *values = minyar_list_new();
        minyar_list_references(values);
        root = values;
        if (strcmp(argv[1], "shared") == 0) {
            void *leaf = minyar_record_new_scalar(1);
            minyar_record_set(leaf, 0, 7);
            for (long long i = 0; i < count; i++)
                minyar_list_add(values, (long long)(intptr_t)leaf);
            minyar_rc_release(leaf);
        } else {
            assert(strcmp(argv[1], "wide") == 0);
            for (long long i = 0; i < count; i++) {
                void *leaf = minyar_record_new_scalar(2);
                minyar_record_set(leaf, 0, i);
                minyar_record_set(leaf, 1, i + 1);
                minyar_list_add_take(values, (long long)(intptr_t)leaf);
            }
        }
    }
    double built = milliseconds();
    size_t live_bytes = rc_bytes, live_objects = rc_object_count;
    minyar_rc_release(root);
    double released = milliseconds();
    assert(rc_bytes == 0 && rc_object_count == 0 && rc_pending_count == 0);
    printf("{\"build_ms\":%.6f,\"release_ms\":%.6f,\"live_bytes\":%zu,"
           "\"live_objects\":%zu,\"queue_capacity\":%zu}\n",
           built - start, released - built, live_bytes, live_objects, rc_pending_capacity);
}
