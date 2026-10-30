// C peer for main.min: sort row structs by value with qsort. Every comparator
// is a total order (id breaks ties), so stability does not change the result.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { long long id, score; const char *name; } Row;

static int by_score(const void *x, const void *y) {
    const Row *a = x, *b = y;
    if (a->score != b->score) return b->score > a->score ? 1 : -1;
    int c = strcmp(a->name, b->name);
    if (c) return c;
    return a->id < b->id ? -1 : a->id > b->id;
}
static int by_id(const void *x, const void *y) {
    const Row *a = x, *b = y;
    return a->id < b->id ? -1 : a->id > b->id;
}

int main(int argc, char **argv) {
    static const char *names[] = {"ada", "bob", "cy", "dee", "eve", "fay", "gus", "hal"};
    size_t n = argc > 1 ? strtoul(argv[1], NULL, 10) : 0;
    long long seed = 7;
    Row *rows = malloc(n * sizeof *rows);
    for (size_t i = 0; i < n; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        rows[i] = (Row){(long long)i, (seed / 1024) % 1000, names[(seed / 16) % 8]};
    }
    for (int round = 0; round < 3; round++) {
        qsort(rows, n, sizeof *rows, by_score);
        qsort(rows, n, sizeof *rows, by_id);
    }
    long long checksum = 0;
    for (size_t i = 0; i < n; i++) checksum = (checksum * 31 + rows[i].score) % 1000000007;
    qsort(rows, n, sizeof *rows, by_score);
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + rows[i].id) % 1000000007;
    printf("%lld\n", checksum);
    return 0;
}
