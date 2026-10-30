// C peer for main.min: open-addressed Integer hash tables for degrees,
// adjacency (key -> node index -> growable array of indices), BFS and a FIFO cache.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EMPTY INT64_MIN
typedef struct { int64_t *keys, *values; size_t mask, used; } Table;

static uint64_t mix(int64_t key) { uint64_t h = (uint64_t)key * 0x9E3779B97F4A7C15ULL; return h ^ (h >> 29); }
static void table_init(Table *t, size_t capacity) {
    t->mask = capacity - 1; t->used = 0;
    t->keys = malloc(capacity * sizeof(int64_t)); t->values = malloc(capacity * sizeof(int64_t));
    for (size_t i = 0; i < capacity; i++) t->keys[i] = EMPTY;
}
static size_t table_slot(const Table *t, int64_t key) {
    size_t j = mix(key) & t->mask;
    while (t->keys[j] != EMPTY && t->keys[j] != key) j = (j + 1) & t->mask;
    return j;
}
static void table_grow(Table *t) {
    Table old = *t;
    table_init(t, (old.mask + 1) * 2);
    for (size_t i = 0; i <= old.mask; i++) if (old.keys[i] != EMPTY) {
        size_t j = table_slot(t, old.keys[i]);
        t->keys[j] = old.keys[i]; t->values[j] = old.values[i]; t->used++;
    }
    free(old.keys); free(old.values);
}
// Returns the value slot for key, inserting `fresh` when absent.
static int64_t *table_upsert(Table *t, int64_t key, int64_t fresh, int *inserted) {
    size_t j = table_slot(t, key);
    *inserted = t->keys[j] == EMPTY;
    if (*inserted) {
        if ((t->used + 1) * 4 > (t->mask + 1) * 3) { table_grow(t); j = table_slot(t, key); }
        t->keys[j] = key; t->values[j] = fresh; t->used++;
    }
    return &t->values[j];
}
static int64_t *table_find(const Table *t, int64_t key) {
    size_t j = table_slot(t, key);
    return t->keys[j] == EMPTY ? NULL : &t->values[j];
}
static int table_remove(Table *t, int64_t key) {
    size_t j = table_slot(t, key);
    if (t->keys[j] == EMPTY) return 0;
    t->keys[j] = EMPTY; t->used--;
    // Backward-shift deletion keeps probe chains intact without tombstones.
    for (size_t k = (j + 1) & t->mask; t->keys[k] != EMPTY; k = (k + 1) & t->mask) {
        size_t home = mix(t->keys[k]) & t->mask;
        if (((k - home) & t->mask) >= ((k - j) & t->mask)) {
            t->keys[j] = t->keys[k]; t->values[j] = t->values[k]; t->keys[k] = EMPTY; j = k;
        }
    }
    return 1;
}

typedef struct { int64_t *items; int32_t length, capacity; } Vec;
static void vec_push(Vec *v, int64_t x) {
    if (v->length == v->capacity) { v->capacity = v->capacity ? v->capacity * 2 : 4; v->items = realloc(v->items, v->capacity * sizeof(int64_t)); }
    v->items[v->length++] = x;
}
static int compare_keys(const void *a, const void *b) { int64_t x = *(const int64_t *)a, y = *(const int64_t *)b; return (x > y) - (x < y); }

static int64_t state = 99;
static int64_t next_random(void) { state = (state * 1103515245 + 12345) % 2147483648LL; return state / 16; }
static int64_t node_key(int64_t index) { return index * 7919 + 13; }

int main(int argc, char **argv) {
    int64_t edges = argc > 1 ? atoll(argv[1]) : 0, nodes = edges / 4 + 1;
    Table degrees, index; table_init(&degrees, 1024); table_init(&index, 1024);
    Vec *lists = calloc((size_t)nodes + 1, sizeof(Vec));
    int64_t list_count = 0, removed = 0, start = 0; int inserted;
    for (int64_t i = 0; i < edges; i++) {
        int64_t a = node_key(next_random() % nodes), b = node_key(next_random() % nodes);
        if (i == 0) start = a;
        ++*table_upsert(&degrees, a, 0, &inserted);
        ++*table_upsert(&degrees, b, 0, &inserted);
        // Adjacency holds node indices, so the search never hashes again.
        int64_t la = *table_upsert(&index, a, list_count, &inserted); list_count += inserted;
        int64_t lb = *table_upsert(&index, b, list_count, &inserted); list_count += inserted;
        vec_push(&lists[la], lb); vec_push(&lists[lb], la);
        if (i % 7 == 0 && table_remove(&degrees, node_key(next_random() % nodes))) removed++;
    }
    int64_t *keys = malloc(degrees.used * sizeof(int64_t)); size_t n = 0;
    for (size_t j = 0; j <= degrees.mask; j++) if (degrees.keys[j] != EMPTY) keys[n++] = degrees.keys[j];
    qsort(keys, n, sizeof(int64_t), compare_keys);
    int64_t checksum = 0, busiest = 0;
    for (size_t k = 0; k < n; k++) {
        int64_t degree = *table_find(&degrees, keys[k]);
        checksum = (checksum * 31 + keys[k] + degree) % 1000000007;
        if (degree > busiest) busiest = degree;
    }
    printf("%zu %zu %lld\n%lld %lld\n", degrees.used, index.used, (long long)removed, (long long)checksum, (long long)busiest);

    uint8_t *visited = calloc((size_t)list_count, 1);
    int64_t *frontier = malloc(list_count * sizeof(int64_t)), *next = malloc(list_count * sizeof(int64_t));
    int64_t first = *table_find(&index, start), frontier_length = 1, reached = 1, depth = 0, depth_sum = 0;
    frontier[0] = first; visited[first] = 1;
    while (frontier_length > 0) {
        int64_t next_length = 0;
        for (int64_t f = 0; f < frontier_length; f++) {
            depth_sum += depth;
            const Vec *v = &lists[frontier[f]];
            for (int32_t e = 0; e < v->length; e++) {
                int64_t to = v->items[e];
                if (!visited[to]) { visited[to] = 1; next[next_length++] = to; reached++; }
            }
        }
        int64_t *t = frontier; frontier = next; next = t; frontier_length = next_length; depth++;
    }
    printf("%lld %lld %lld\n", (long long)reached, (long long)depth_sum, (long long)depth);

    int64_t capacity = nodes / 8 + 1, oldest = 0, arrivals_length = 0, hits = 0, misses = 0, value_sum = 0;
    int64_t *arrivals = malloc((size_t)edges * sizeof(int64_t));
    Table cache; table_init(&cache, 1024);
    for (int64_t request = 0; request < edges; request++) {
        int64_t x = next_random() % nodes, y = next_random() % nodes, key = node_key(x < y ? x : y);
        int64_t *slot = table_upsert(&cache, key, 0, &inserted);
        if (!inserted) { hits++; value_sum += *slot; continue; }
        misses++;
        *slot = key * 3 % 1000; value_sum += *slot;
        arrivals[arrivals_length++] = key;
        if ((int64_t)cache.used > capacity) table_remove(&cache, arrivals[oldest++]);
    }
    printf("%lld %lld %lld %zu\n", (long long)hits, (long long)misses, (long long)value_sum, cache.used);
    return 0;
}
