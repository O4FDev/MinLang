/* Runtime failure entry points must stop before any invalid operation. */
#include "../runtime/minyar_runtime.c"
#include <assert.h>

#ifdef MINYAR_TEST_EXPLICIT_TRAPS
extern void minyar_fail_integer_overflow(void);
extern void minyar_fail_integer_division(long long right);
#endif

int main(int argc, char **argv) {
    assert(argc >= 2);
    if (!strcmp(argv[1], "valid")) {
        const long long values[] = {LLONG_MIN, LLONG_MIN + 1, -1, 0, 1, LLONG_MAX};
        minyar_check_integer_overflow(0);
        for (size_t left = 0; left < sizeof(values) / sizeof(*values); left++) {
            for (size_t right = 0; right < sizeof(values) / sizeof(*values); right++) {
                if (values[right] && !(values[left] == LLONG_MIN && values[right] == -1))
                    minyar_check_integer_division(values[left], values[right]);
            }
        }
        puts("valid checks return");
        return 0;
    }
    if (!strcmp(argv[1], "growth")) {
        assert(argc == 3);
        /* Synthetic metadata reaches the arithmetic boundary without asking
         * the host to allocate exabytes first. No elements are accessed. */
        long long capacity = strtoll(argv[2], NULL, 10);
        MinyarList list = {NULL, capacity, capacity};
        list_grow(&list);
    } else if (!strcmp(argv[1], "overflow")) {
        minyar_check_integer_overflow(1);
    } else if (!strcmp(argv[1], "zero")) {
        minyar_check_integer_division(LLONG_MIN, 0);
    } else if (!strcmp(argv[1], "division")) {
        minyar_check_integer_division(LLONG_MIN, -1);
#ifdef MINYAR_TEST_EXPLICIT_TRAPS
    } else if (!strcmp(argv[1], "fail-overflow")) {
        minyar_fail_integer_overflow();
    } else if (!strcmp(argv[1], "fail-zero")) {
        minyar_fail_integer_division(0);
    } else if (!strcmp(argv[1], "fail-division")) {
        minyar_fail_integer_division(-1);
#endif
    } else {
        return 8;
    }
    fputs("a failure entry point returned\n", stderr);
    return 9;
}
