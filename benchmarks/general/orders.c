// C reference for orders.min: same output.
#include <stdio.h>
#include <stdlib.h>

typedef struct { long long id, customer, region, price, quantity, discount; } Order;
typedef struct { long long id, total; } Ranked;
static int compare(const void *x, const void *y) {
    const Ranked *a = x, *b = y;
    if (a->total != b->total) return a->total < b->total ? 1 : -1;
    return a->id < b->id ? -1 : a->id > b->id;
}
int main(void) {
    long long count = 1000000, seed = 12345;
    Order *orders = NULL; long long length = 0, capacity = 0;
    for (long long i = 0; i < count; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        long long price = 100 + (seed / 64) % 9900;
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        if (length == capacity) { capacity = capacity ? capacity * 2 : 16; orders = realloc(orders, capacity * sizeof(Order)); }
        orders[length++] = (Order){i, (seed / 16) % 50000, (seed / 8) % 16, price, 1 + (seed / 256) % 7, (seed / 7) % 500};
    }
    long long checksum = 0;
    for (long long pass = 0; pass < 20; pass++) {
        long long regions[16] = {0}, large = 0;
        for (long long i = 0; i < length; i++) {
            Order *o = &orders[i];
            long long total = o->price * o->quantity - o->discount;
            if (total > 5000 + pass * 100) { regions[o->region] += total; large++; }
        }
        for (int r = 0; r < 16; r++) checksum = (checksum * 31 + regions[r]) % 1000000007;
        checksum = (checksum + large) % 1000000007;
    }
    Ranked *ranked = malloc(length * sizeof(Ranked)); long long n = 0;
    for (long long i = 0; i < length; i++) if (orders[i].customer % 10 == 0)
        ranked[n++] = (Ranked){orders[i].id, orders[i].price * orders[i].quantity - orders[i].discount};
    qsort(ranked, n, sizeof(Ranked), compare);
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + ranked[i].id) % 1000000007;
    printf("%lld\n%lld\n", n, checksum);
    return 0;
}
