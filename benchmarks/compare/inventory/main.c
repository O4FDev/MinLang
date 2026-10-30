// C peer for main.min: warehouses hold arrays of item structs by value; each
// item owns a small growable history array.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { CATEGORIES = 12, WAREHOUSES = 16 };
typedef struct { int64_t sku, category, quantity, price; int32_t *history; int32_t length, capacity; } Item;
typedef struct { Item *items; size_t length, capacity; int64_t *moves; size_t move_length, move_capacity; } Warehouse;
typedef struct { int64_t sku, value; } Ranked;

static int64_t state = 4242, next_sku = 0;
static int64_t next_random(void) { state = (state * 1103515245 + 12345) % 2147483648LL; return state / 16; }

static Item new_item(void) {
    Item item = {next_sku++, 0, 0, 0, NULL, 0, 0};
    item.category = next_random() % CATEGORIES;
    item.quantity = next_random() % 50;
    item.price = 100 + next_random() % 9900;
    return item;
}
static void add_item(Warehouse *w, Item item) {
    if (w->length == w->capacity) { w->capacity = w->capacity ? w->capacity * 2 : 64; w->items = realloc(w->items, w->capacity * sizeof(Item)); }
    w->items[w->length++] = item;
}
static void add_move(Warehouse *w, int64_t sku) {
    if (w->move_length == w->move_capacity) { w->move_capacity = w->move_capacity ? w->move_capacity * 2 : 64; w->moves = realloc(w->moves, w->move_capacity * sizeof(int64_t)); }
    w->moves[w->move_length++] = sku;
}
static void adjust(Item *item, int64_t delta) {
    item->quantity = item->quantity + delta > 0 ? item->quantity + delta : 0;
    if (item->length == item->capacity) { item->capacity = item->capacity ? item->capacity * 2 : 4; item->history = realloc(item->history, item->capacity * sizeof(int32_t)); }
    item->history[item->length++] = (int32_t)delta;
    if (item->length > 16) { memmove(item->history, item->history + item->length - 8, 8 * sizeof(int32_t)); item->length = 8; }
}
static Item take(Warehouse *w, size_t position) {
    Item item = w->items[position];
    w->items[position] = w->items[--w->length];
    return item;
}
static int64_t prune(Warehouse *w) {
    size_t kept = 0;
    for (size_t i = 0; i < w->length; i++) {
        if (w->items[i].quantity > 0) w->items[kept++] = w->items[i];
        else free(w->items[i].history);
    }
    int64_t pruned = (int64_t)(w->length - kept);
    w->length = kept;
    return pruned;
}
static int compare_ranked(const void *x, const void *y) {
    const Ranked *a = x, *b = y;
    if (a->value != b->value) return a->value < b->value ? 1 : -1;
    return (a->sku > b->sku) - (a->sku < b->sku);
}

int main(int argc, char **argv) {
    int64_t operations = argc > 1 ? atoll(argv[1]) : 0;
    static Warehouse warehouses[WAREHOUSES];
    for (int64_t i = 0; i < operations / 10; i++) add_item(&warehouses[i % WAREHOUSES], new_item());
    int64_t pruned = 0, sold = 0;
    for (int64_t i = 0; i < operations; i++) {
        Warehouse *w = &warehouses[next_random() % WAREHOUSES];
        int64_t kind = next_random() % 10;
        if (kind < 6) {
            if (w->length) { Item *item = &w->items[next_random() % w->length]; adjust(item, next_random() % 21 - 10); }
        } else if (kind < 8) {
            if (w->length) {
                Warehouse *destination = &warehouses[next_random() % WAREHOUSES];
                Item item = take(w, next_random() % w->length);
                add_item(destination, item);
                add_move(w, item.sku);
            }
        } else if (kind == 8) {
            add_item(w, new_item());
        } else if (w->length) {
            Item item = take(w, next_random() % w->length);
            sold += item.quantity;
            free(item.history);
        }
        if (i % 1024 == 1023) pruned += prune(w);
    }
    int64_t units[CATEGORIES] = {0}, values[CATEGORIES] = {0}, history_sum = 0, move_sum = 0;
    size_t total = 0;
    for (int w = 0; w < WAREHOUSES; w++) total += warehouses[w].length;
    Ranked *ranked = malloc((total + 1) * sizeof(Ranked)); size_t n = 0;
    for (int w = 0; w < WAREHOUSES; w++) {
        Warehouse *house = &warehouses[w];
        for (size_t m = 0; m < house->move_length; m++) move_sum = (move_sum * 31 + house->moves[m]) % 1000000007;
        for (size_t k = 0; k < house->length; k++) {
            const Item *item = &house->items[k];
            units[item->category] += item->quantity;
            values[item->category] += item->quantity * item->price;
            int64_t changes = item->length;
            for (int32_t h = 0; h < item->length; h++) changes += item->history[h];
            history_sum = (history_sum * 31 + changes + 1000) % 1000000007;
            ranked[n++] = (Ranked){item->sku, item->quantity * item->price};
        }
        printf("wh-%d %zu %zu\n", w, house->length, house->move_length);
    }
    for (int c = 0; c < CATEGORIES; c++) printf("category %d %lld %lld\n", c, (long long)units[c], (long long)values[c]);
    qsort(ranked, n, sizeof(Ranked), compare_ranked);
    int64_t top = 0;
    for (size_t i = 0; i < n && i < 100; i++) top = (top * 31 + ranked[i].sku) % 1000000007;
    printf("%zu %lld %lld %lld\n%lld %lld %lld\n", n, (long long)next_sku, (long long)pruned, (long long)sold,
           (long long)history_sum, (long long)move_sum, (long long)top);
    return 0;
}
