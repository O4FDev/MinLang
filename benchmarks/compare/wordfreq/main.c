// C peer for main.min: word frequencies over a text file, top 10 words.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *word; int length; long long count; unsigned long long hash; } Entry;
static Entry *table; static size_t capacity = 1 << 16, used;

static unsigned long long hash_bytes(const char *p, int n) {
    unsigned long long h = 1469598103934665603ULL;
    for (int i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 1099511628211ULL; }
    return h;
}
static void grow(void) {
    size_t old = capacity; Entry *previous = table;
    capacity *= 2; table = calloc(capacity, sizeof(Entry));
    for (size_t i = 0; i < old; i++) if (previous[i].word) {
        size_t j = previous[i].hash & (capacity - 1);
        while (table[j].word) j = (j + 1) & (capacity - 1);
        table[j] = previous[i];
    }
    free(previous);
}
static void count(const char *p, int n) {
    unsigned long long h = hash_bytes(p, n);
    size_t j = h & (capacity - 1);
    while (table[j].word) {
        if (table[j].hash == h && table[j].length == n && memcmp(table[j].word, p, n) == 0) { table[j].count++; return; }
        j = (j + 1) & (capacity - 1);
    }
    table[j] = (Entry){p, n, 1, h};
    if (++used * 2 > capacity) grow();
}
static int compare(const void *x, const void *y) {
    const Entry *a = x, *b = y;
    if (a->count != b->count) return a->count < b->count ? 1 : -1;
    int n = a->length < b->length ? a->length : b->length;
    int c = memcmp(a->word, b->word, n);
    if (c) return c;
    return a->length - b->length;
}
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *text = malloc(size + 1); fread(text, 1, size, f); fclose(f);
    table = calloc(capacity, sizeof(Entry));
    long long total = 0; long i = 0;
    while (i < size) {
        long start = i;
        while (i < size && text[i] != ' ' && text[i] != '\n') i++;
        if (i > start) { total++; count(text + start, (int)(i - start)); }
        i++;
    }
    Entry *entries = malloc(used * sizeof(Entry)); size_t n = 0;
    for (size_t k = 0; k < capacity; k++) if (table[k].word) entries[n++] = table[k];
    qsort(entries, n, sizeof(Entry), compare);
    printf("%lld\n%zu\n", total, n);
    for (int k = 0; k < 10; k++) printf("%.*s %lld\n", entries[k].length, entries[k].word, entries[k].count);
    return 0;
}
