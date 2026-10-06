/* Isolated test instrumentation, using the existing fault-wrapper implementation.
 * Does not replace any compiler or production runtime artifact. */
#include "allocation-fault-runtime.c"

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "allocate")) {
        unsigned char *a = fault_malloc(4);
        unsigned char *b = fault_malloc(4);
        assert(a && b && a != b);
        memset(a, 0x12, 4);
        memset(b, 0x34, 4);
        void *c = fault_malloc(4);
        assert(!c && fault_allocations == 3 && fault_fired == 1);
        for (size_t i = 0; i < 4; i++) assert(a[i] == 0x12 && b[i] == 0x34);
        assert(fault_live_bytes == 8);
        fault_free(a);
        fault_free(b);
        assert(fault_live_bytes == 0);
    } else if (!strcmp(argv[1], "resize")) {
        unsigned char *a = fault_malloc(8);
        assert(a);
        memset(a, 0x56, 8);
        unsigned char *b = fault_realloc(a, 6);
        assert(b && fault_moved == 1);
        unsigned char *c = fault_realloc(b, 4);
        assert(!c && fault_resizes == 2 && fault_fired == 1);
        for (size_t i = 0; i < 6; i++) assert(b[i] == 0x56);
        assert(fault_live_bytes == 6);
        /* Minyar's wrapper has one resize API and a single-failure ordinal.
         * Rearm it for the second upstream resize/remap refusal. A distinct
         * successful allocation proves resize and allocation limits differ. */
        unsigned char *independent = fault_malloc(3);
        assert(independent && fault_allocations == 2);
        memset(independent, 0x78, 3);
        fault_resize_index = 3;
        c = fault_realloc(b, 4);
        assert(!c && fault_resizes == 3 && fault_fired == 2);
        for (size_t i = 0; i < 6; i++) assert(b[i] == 0x56);
        for (size_t i = 0; i < 3; i++) assert(independent[i] == 0x78);
        assert(fault_live_bytes == 9);
        fault_free(independent);
        fault_free(b);
        assert(fault_live_bytes == 0);
    } else {
        assert(!strcmp(argv[1], "move"));
        unsigned char *a = fault_malloc(2);
        unsigned char *b = fault_malloc(2);
        assert(a && b && a != b);
        a[0] = 1; a[1] = 2;
        b[0] = 3; b[1] = 4;
        unsigned char *c = fault_realloc(a, 4);
        assert(c && c != a && c != b && fault_moved == 1);
        assert(c[0] == 1 && c[1] == 2 && b[0] == 3 && b[1] == 4);
        c[2] = 5; c[3] = 6;
        assert(b[0] == 3 && b[1] == 4);
        fault_free(b);
        fault_free(c);
        assert(fault_live_bytes == 0);
    }
    return 0;
}
