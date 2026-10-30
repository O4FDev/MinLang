// C peer for main.min: parse CSV log lines and aggregate per service.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *name; int length; long long count, total, slowest, errors; } Stats;
enum { SLOTS = 1024 };
static Stats table[SLOTS]; static int used;

static unsigned hash_bytes(const char *p, int n) {
    unsigned h = 2166136261u;
    for (int i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 16777619u; }
    return h;
}
static Stats *find(const char *p, int n) {
    unsigned j = hash_bytes(p, n) & (SLOTS - 1);
    while (table[j].name) {
        if (table[j].length == n && memcmp(table[j].name, p, n) == 0) return &table[j];
        j = (j + 1) & (SLOTS - 1);
    }
    used++;
    table[j].name = p; table[j].length = n;
    return &table[j];
}
static long long parse_int(const char *p, const char *end) {
    long long v = 0; int negative = p < end && *p == '-';
    for (p += negative; p < end; p++) v = v * 10 + (*p - '0');
    return negative ? -v : v;
}
static int compare(const void *x, const void *y) {
    const Stats *a = *(Stats *const *)x, *b = *(Stats *const *)y;
    int n = a->length < b->length ? a->length : b->length, c = memcmp(a->name, b->name, n);
    return c ? c : a->length - b->length;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *text = malloc(size + 1); fread(text, 1, size, f); fclose(f); text[size] = '\n';
    const char *p = text, *limit = text + size;
    long long warnings = 0;
    while (p < limit) {
        const char *end = memchr(p, '\n', limit + 1 - p);
        if (end == p) { p++; continue; }
        const char *field[5], *stop[5];
        for (int k = 0; k < 5; k++) {
            field[k] = p;
            while (p < end && *p != ',') p++;
            stop[k] = p; if (p < end) p++;
        }
        long long latency = parse_int(field[3], stop[3]), status = parse_int(field[4], stop[4]);
        if (stop[1] - field[1] == 4 && memcmp(field[1], "WARN", 4) == 0) warnings++;
        Stats *s = find(field[2], (int)(stop[2] - field[2]));
        s->count++; s->total += latency;
        if (latency > s->slowest) s->slowest = latency;
        if (status >= 500) s->errors++;
        p = end + 1;
    }
    Stats **sorted = malloc(used * sizeof *sorted); int n = 0;
    for (int j = 0; j < SLOTS; j++) if (table[j].name) sorted[n++] = &table[j];
    qsort(sorted, n, sizeof *sorted, compare);
    printf("%lld\n", warnings);
    for (int i = 0; i < n; i++)
        printf("%.*s %lld %lld %lld %lld\n", sorted[i]->length, sorted[i]->name, sorted[i]->count,
               sorted[i]->total / sorted[i]->count, sorted[i]->slowest, sorted[i]->errors);
    return 0;
}
