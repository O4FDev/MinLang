// Serial C peer for main.min: build N sales, six passes of three grouped aggregations.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { int64_t customer, product, region, month, quantity, price, discount; } Sale;
enum { PASSES = 6 };
static const int64_t MODULUS = 1000000007;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

int main(int argc, char **argv) {
    int64_t count = atoll(argv[1]);
    Sale *sales = malloc(sizeof(Sale) * (size_t)count);
    for (int64_t i = 0; i < count; ++i) {
        int64_t a = mix(i * 2), b = mix(i * 2 + 1);
        sales[i] = (Sale){a % 100000, (a >> 20) % 512, (a >> 32) % 16, (a >> 40) % 12, 1 + b % 9, 100 + (b >> 8) % 20000, (b >> 30) % 30};
    }
    int64_t digest = 0;
    for (int64_t pass = 0; pass < PASSES; ++pass) {
        int64_t minimum = 1 + pass % 3, skip = pass % 12, threshold = 100000 + pass * 10000, large = 0;
        int64_t revenue[192] = {0}, units[512] = {0};
        for (int64_t i = 0; i < count; ++i) {
            const Sale *s = &sales[i];
            int64_t net = s->price * s->quantity * (100 - s->discount) / 100;
            if (s->quantity >= minimum) revenue[s->region * 12 + s->month] += net;
            if (s->month != skip) units[s->product] += s->quantity;
            if (net > threshold) large++;
        }
        for (int k = 0; k < 192; ++k) digest = (digest * 31 + revenue[k]) % MODULUS;
        for (int k = 0; k < 512; ++k) digest = (digest * 31 + units[k]) % MODULUS;
        digest = (digest * 31 + large) % MODULUS;
        printf("pass %lld large %lld\n", (long long)pass, (long long)large);
    }
    printf("digest %lld\n", (long long)digest);
    free(sales);
    return 0;
}
