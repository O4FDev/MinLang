/* Original guarded-end runtime probe inspired by Go issue15002.
 * Links an existing runtime object; does not rebuild production runtime sources. */
#if defined(__linux__)
#define _GNU_SOURCE 1
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

typedef struct { long long *values, length, capacity; } MinyarList;
typedef struct MinyarText {
    const unsigned char *bytes;
    long long byte_length, character_length;
    void *character_offsets;
    struct MinyarText *backing;
} MinyarText;
extern long long minyar_list_get(const MinyarList *, long long);
extern int minyar_text_character_at(MinyarText *, long long);
static volatile long long dynamic_zero;

int main(int argc, char **argv) {
    assert(argc == 4);
    long page = sysconf(_SC_PAGESIZE);
    assert(page > 0);
    unsigned char *mapping = mmap(NULL, (size_t)page * 2, PROT_READ | PROT_WRITE,
                                 MAP_PRIVATE | MAP_ANON, -1, 0);
    assert(mapping != MAP_FAILED);
    assert(mprotect(mapping + page, (size_t)page, PROT_NONE) == 0);
    int count = atoi(argv[2]);
    assert(count == 2 || count == 4 || count == 8);
    long long start = !strcmp(argv[3], "dynamic") ? dynamic_zero : 0;
    if (!strcmp(argv[1], "list")) {
        long long *last = (long long *)(mapping + page - sizeof(long long));
        *last = 42;
        MinyarList list = {last, 1, 1};
        assert(minyar_list_get(&list, start) == 42);
        for (int i = 1; i < count; i++) (void)minyar_list_get(&list, start + i);
    } else {
        assert(!strcmp(argv[1], "text"));
        mapping[page - 1] = 'A';
        MinyarText text = {mapping + page - 1, 1, 1, NULL, NULL};
        assert(minyar_text_character_at(&text, start) == 'A');
        for (int i = 1; i < count; i++) (void)minyar_text_character_at(&text, start + i);
    }
    fputs("guarded-end access unexpectedly returned\n", stderr);
    return 99;
}
