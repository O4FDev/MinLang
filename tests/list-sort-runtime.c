/* Independent insertion-sort oracle; the production algorithm is merge sort. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static unsigned long long seed = 0x836519acd;
static unsigned long long random_value(void) {
    seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
    return seed;
}
static long long bits(double value) { long long slot; memcpy(&slot, &value, 8); return slot; }
static int model_compare(long long a, long long b, int kind) {
    if (kind == 7) {
        double x, y; memcpy(&x, &a, 8); memcpy(&y, &b, 8);
        if (isnan(x)) return !isnan(y);
        if (isnan(y)) return -1;
        return (x > y) - (x < y);
    }
    if (kind == 2) {
        MinyarText *x = (void *)(uintptr_t)a, *y = (void *)(uintptr_t)b;
        long long i = 0;
        while (i < x->byte_length && i < y->byte_length) {
            if (x->bytes[i] != y->bytes[i]) return x->bytes[i] < y->bytes[i] ? -1 : 1;
            i++;
        }
        return (x->byte_length > y->byte_length) - (x->byte_length < y->byte_length);
    }
    return (a > b) - (a < b);
}
static void oracle(long long *values, size_t count, int kind) {
    for (size_t i = 1; i < count; i++) {
        long long value = values[i]; size_t j = i;
        while (j && model_compare(values[j-1], value, kind) > 0) {
            values[j] = values[j-1]; j--;
        }
        values[j] = value;
    }
}
static void natural_models(void) {
    const int kinds[] = {1, 3, 4, 7, 2};
    for (size_t k = 0; k < 5; k++) for (size_t n = 0; n < 130; n++) {
        int kind = kinds[k]; MinyarList *list = minyar_list_new();
        if (kind == 2) minyar_list_references(list);
        long long expected[130], original[130];
        for (size_t i = 0; i < n; i++) {
            long long value = (long long)(random_value() % 17) - 8;
            if (kind == 3) value = random_value() % 0x110000;
            if (kind == 4) value = random_value() % 2;
            if (kind == 7) {
                const double choices[] = {-INFINITY, -3.5, -0.0, 0.0, 4.5, INFINITY, NAN};
                value = bits(choices[random_value() % 7]);
                if (isnan(choices[(seed) % 7])) value ^= (long long)(i & 255);
            }
            if (kind == 2) {
                const char *choices[] = {"", "a", "aa", "z", "é", "😀", "a\0z"};
                size_t choice = random_value() % 7;
                MinyarText *text = minyar_native_copy_text((const unsigned char *)choices[choice], choice == 6 ? 3 : (long long)strlen(choices[choice]));
                value = (long long)(uintptr_t)text;
            }
            expected[i] = original[i] = value;
            minyar_list_add_take(list, value);
        }
        oracle(expected, n, kind);
        MinyarList *copy = minyar_list_sorted(list, kind, kind == 2);
        assert(copy != list && copy->length == (long long)n);
        assert(!n || !memcmp(copy->values, expected, n * 8));
        assert(!n || !memcmp(list->values, original, n * 8));
        MinyarList *alias = list; minyar_rc_retain(alias);
        minyar_list_sort(list, kind);
        assert(alias == list && (!n || !memcmp(alias->values, expected, n * 8)));
        if (kind == 2) for (size_t i = 0; i < n; i++)
            assert(!((MinyarText *)(uintptr_t)list->values[i])->character_offsets);
        minyar_rc_release(copy); minyar_rc_release(list); minyar_rc_release(alias);
    }
}
typedef struct { MinyarList *list; long long *original; size_t calls; int mutate; } State;
static long long compare(void *context, long long a, long long b) {
    MinyarRecord *state_record = context;
    State *state = (void *)(uintptr_t)minyar_record_get(state_record, 0);
    if (!state->mutate) assert(!memcmp(state->list->values, state->original, (size_t)state->list->length * 8));
    state->calls++;
    if (state->mutate == 1) minyar_list_set(state->list, 0, -999);
    if (state->mutate == 2) minyar_list_add(state->list, 42);
    return a % 7 < b % 7 ? LLONG_MIN : a % 7 > b % 7 ? LLONG_MAX : 0;
}
static void comparator_model(int mutate) {
    MinyarList *list = minyar_list_new(); long long original[257], expected[257];
    for (size_t i = 0; i < 257; i++) {
        original[i] = expected[i] = (long long)(random_value() % 1000);
        minyar_list_add(list, original[i]);
    }
    for (size_t i = 1; i < 257; i++) {
        long long value = expected[i]; size_t j = i;
        while (j && expected[j-1] % 7 > value % 7) { expected[j] = expected[j-1]; j--; }
        expected[j] = value;
    }
    State state = {list, original, 0, mutate};
    MinyarRecord *context = minyar_record_new_scalar(1);
    minyar_record_set_scalar(context, 0, (long long)(uintptr_t)&state);
    MinyarList *copy = minyar_list_sorted_by(list, context, compare, 0);
    assert(!memcmp(copy->values, expected, sizeof(expected)));
    assert(state.calls && state.calls < 257 * 9);
    minyar_list_sort_by(list, context, compare, 0);
    assert(!memcmp(list->values, expected, sizeof(expected)));
    minyar_rc_release(context); minyar_rc_release(copy); minyar_rc_release(list);
}
int main(int argc, char **argv) {
    if (argc > 1) { comparator_model(!strcmp(argv[1], "add") ? 2 : 1); return 99; }
    natural_models(); comparator_model(0);
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
    assert(rc_object_count == rc_immortal_object_count);
#endif
    puts("natural-models-alias-copy-float-text-comparator-stability-ok");
}
