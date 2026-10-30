// C reference for sortrows.min: same output (stable merge sort over pointers, like the Minyar List).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { long long id, score; const char *name; } Row;
typedef int (*Compare)(const Row *, const Row *);
static int by_score(const Row *a, const Row *b) {
    if (a->score != b->score) return b->score > a->score ? 1 : -1;
    int c = strcmp(a->name, b->name);
    if (c) return c;
    return a->id < b->id ? -1 : a->id > b->id;
}
static int by_id(const Row *a, const Row *b) { return a->id < b->id ? -1 : a->id > b->id; }
static void merge(Row **v, size_t n, Row **scratch, Compare compare) {
    if (n < 2) return;
    size_t left = n / 2;
    merge(v, left, scratch, compare); merge(v + left, n - left, scratch, compare);
    if (compare(v[left - 1], v[left]) <= 0) return;
    memcpy(scratch, v, left * sizeof *v);
    size_t l = 0, r = left, o = 0;
    while (l < left && r < n) v[o++] = compare(scratch[l], v[r]) <= 0 ? scratch[l++] : v[r++];
    memcpy(v + o, scratch + l, (left - l) * sizeof *v);
}
int main(void) {
    static const char *names[] = {"ada", "bob", "cy", "dee", "eve", "fay", "gus", "hal"};
    size_t n = 400000; long long seed = 7;
    Row **rows = malloc(n * sizeof *rows), **scratch = malloc(n * sizeof *rows);
    for (size_t i = 0; i < n; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        rows[i] = malloc(sizeof(Row));
        *rows[i] = (Row){(long long)i, (seed / 1024) % 1000, names[(seed / 16) % 8]};
    }
    for (int round = 0; round < 3; round++) { merge(rows, n, scratch, by_score); merge(rows, n, scratch, by_id); }
    long long checksum = 0;
    for (size_t i = 0; i < n; i++) checksum = (checksum * 31 + rows[i]->score) % 1000000007;
    merge(rows, n, scratch, by_score);
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + rows[i]->id) % 1000000007;
    printf("%lld\n", checksum);
    return 0;
}
