// Serial C peer for main.min: sort N 40-bit keys with one quicksort (median of
// three, insertion sort below 16 keys) and print the same summary.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

static void insertion(int64_t *keys, int64_t low, int64_t high) {
    for (int64_t i = low + 1; i < high; ++i) {
        int64_t key = keys[i], j = i - 1;
        while (j >= low && keys[j] > key) { keys[j + 1] = keys[j]; --j; }
        keys[j + 1] = key;
    }
}

static int64_t min64(int64_t a, int64_t b) { return a < b ? a : b; }
static int64_t max64(int64_t a, int64_t b) { return a > b ? a : b; }

static void quicksort(int64_t *keys, int64_t first, int64_t after) {
    while (after - first > 16) {
        int64_t middle = first + (after - first) / 2;
        int64_t a = keys[first], b = keys[middle], c = keys[after - 1];
        int64_t pivot = max64(min64(a, b), min64(max64(a, b), c));
        int64_t i = first, j = after - 1;
        while (i <= j) {
            while (keys[i] < pivot) ++i;
            while (keys[j] > pivot) --j;
            if (i <= j) { int64_t t = keys[i]; keys[i] = keys[j]; keys[j] = t; ++i; --j; }
        }
        if (j + 1 - first < after - i) { quicksort(keys, first, j + 1); first = i; }
        else { quicksort(keys, i, after); after = j + 1; }
    }
    insertion(keys, first, after);
}

int main(int argc, char **argv) {
    int64_t count = atoll(argv[1]);
    int64_t *keys = malloc(sizeof(int64_t) * (size_t)count);
    for (int64_t i = 0; i < count; ++i) keys[i] = mix(i) & 0xFFFFFFFFFFLL;
    quicksort(keys, 0, count);
    uint64_t checksum = 0;
    int64_t disorder = 0;
    for (int64_t i = 0; i < count; ++i) {
        checksum += (uint64_t)keys[i] * (uint64_t)(i + 1);
        if (i > 0 && keys[i - 1] > keys[i]) ++disorder;
    }
    printf("count %lld disorder %lld\n", (long long)count, (long long)disorder);
    printf("first %lld middle %lld last %lld\n", (long long)keys[0], (long long)keys[count / 2], (long long)keys[count - 1]);
    printf("checksum %lld\n", (long long)(int64_t)checksum);
    free(keys);
    return 0;
}
