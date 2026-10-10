/* Synthetic headers exercise arithmetic rejection without huge allocations.
 * Inspired by Zig ArrayList overflow tests; no invalid payload is accessed. */
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static void aliased_growth(int exhaust) {
    minyar_rc_enter(5);
    MinyarList *numbers = minyar_list_new(), *texts = minyar_list_new();
    minyar_rc_local_take(0, numbers);
    minyar_rc_local_take(1, texts);
    minyar_rc_local(2, numbers);
    minyar_rc_local(3, texts);
    MinyarList *number_alias = numbers, *text_alias = texts;
    minyar_list_references(texts);
    long long count = exhaust ? 100000 : 257;
    for (long long i = 0; i < count; ++i) {
        minyar_list_add(number_alias, i);
        MinyarText *text = minyar_integer_text(1000 + i);
        minyar_list_add_take(text_alias, (long long)(intptr_t)text);
        assert(numbers->length == i + 1 && texts->length == i + 1);
        for (long long j = 0; j <= i; ++j) {
            assert(minyar_list_get(numbers, j) == j);
            assert(minyar_list_get(number_alias, j) == j);
            MinyarText *actual = (MinyarText *)(intptr_t)minyar_list_get(texts, j);
            assert(actual == (MinyarText *)(intptr_t)minyar_list_get(text_alias, j));
            char expected[32];
            int length = snprintf(expected, sizeof(expected), "%lld", 1000 + j);
            assert(actual->byte_length == length);
            assert(!memcmp(actual->bytes, expected, (size_t)length));
        }
        if (exhaust) minyar_print_integer(i);
    }
    if (exhaust) abort(); /* A finite pool must reject this live growth. */
    MinyarText *held = (MinyarText *)(intptr_t)minyar_list_get(texts, 256);
    minyar_rc_local(4, held);
    minyar_list_set(number_alias, 0, 999);
    minyar_list_set_take(text_alias, 256, (long long)(intptr_t)minyar_integer_text(-1));
    assert(minyar_list_get(numbers, 0) == 999);
    MinyarText *replaced = (MinyarText *)(intptr_t)minyar_list_get(texts, 256);
    assert(replaced->byte_length == 2 && !memcmp(replaced->bytes, "-1", 2));
    assert(held->byte_length == 4 && !memcmp(held->bytes, "1256", 4));
    minyar_rc_leave();
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) minyar_rc_poll(1024);
#endif
}

int main(int argc, char **argv) {
    if (argc == 1) {
        aliased_growth(0);
        minyar_rc_enter(1);
        MinyarList *list = minyar_list_new();
        minyar_rc_local_take(0, list);
        for (long long i = 0; i < 4097; i++) {
            if (i % 2) minyar_list_add_take(list, i);
            else minyar_list_add(list, i);
        }
        assert(list->length == 4097 && list->capacity >= list->length);
        for (long long i = 0; i < list->length; i++) assert(minyar_list_get(list, i) == i);
        minyar_rc_leave();
#ifdef MINYAR_BOUNDED_RC
        while (rc_pending_count) minyar_rc_poll(1024);
#endif
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "exhaust")) {
        aliased_growth(1);
        return 99;
    }
    assert(argc == 3);
#if defined(MINYAR_BOUNDED_HEAP) && !defined(MINYAR_COMPILER_ARENA)
    const unsigned long long factor = 2;
#else
    const unsigned long long factor = 4;
#endif
    const long long capacities[] = {
        LLONG_MAX, LLONG_MAX / 4 + 1, LLONG_MAX / 4,
        LLONG_MAX / 2, LLONG_MAX / 2 + 1,
        (long long)(SIZE_MAX / sizeof(long long) / factor + 1)
    };
    int index = atoi(argv[2]);
    assert(index >= 0 && (size_t)index < sizeof(capacities) / sizeof(capacities[0]));
    MinyarList synthetic = {NULL, capacities[index], capacities[index]};
    if (!strcmp(argv[1], "add")) minyar_list_add(&synthetic, 7);
    else if (!strcmp(argv[1], "take")) minyar_list_add_take(&synthetic, 7);
    else {
        assert(!strcmp(argv[1], "appended") && index == 0);
        (void)minyar_list_appended(&synthetic, 7, 0, 0);
    }
    fputs("size guard did not reject synthetic List\n", stderr);
    return 99;
}
