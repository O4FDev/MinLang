// C peer for main.min: records in an array, filtered, grouped and ranked.
#include <stdio.h>
#include <stdlib.h>

typedef struct { long long id, customer, region, price, quantity, discount; } Order;
typedef struct { long long id, total; } Ranked;
static int compare(const void *x, const void *y) {
    const Ranked *a = x, *b = y;
    if (a->total != b->total) return a->total < b->total ? 1 : -1;
    return a->id < b->id ? -1 : a->id > b->id;
}
int main(int argc, char **argv) {
    long long count = argc > 1 ? atoll(argv[1]) : 0, seed = 12345;
    Order *orders = malloc((size_t)count * sizeof(Order));
    for (long long i = 0; i < count; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        long long price = 100 + (seed / 64) % 9900;
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        orders[i] = (Order){i, (seed / 16) % 50000, (seed / 8) % 16, price, 1 + (seed / 256) % 7, (seed / 7) % 500};
    }
    long long checksum = 0;
    for (long long pass = 0; pass < 20; pass++) {
        long long regions[16] = {0}, large = 0;
        for (long long i = 0; i < count; i++) {
            const Order *o = &orders[i];
            long long total = o->price * o->quantity - o->discount;
            if (total > 5000 + pass * 100) { regions[o->region] += total; large++; }
        }
        for (int r = 0; r < 16; r++) checksum = (checksum * 31 + regions[r]) % 1000000007;
        checksum = (checksum + large) % 1000000007;
    }
    Ranked *ranked = malloc((size_t)count * sizeof(Ranked)); long long n = 0;
    for (long long i = 0; i < count; i++) if (orders[i].customer % 10 == 0)
        ranked[n++] = (Ranked){orders[i].id, orders[i].price * orders[i].quantity - orders[i].discount};
    qsort(ranked, (size_t)n, sizeof(Ranked), compare);
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + ranked[i].id) % 1000000007;
    printf("%lld\n%lld\n", n, checksum);
    return 0;
}
