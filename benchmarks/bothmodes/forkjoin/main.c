// Serial C peer for main.min: build a random expression tree, evaluate it eight times.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { PASSES = 8 };
static const int64_t MODULUS = 2147483647;
static int64_t *left, *right, *size, nodes, splits;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

static int64_t build(int64_t leaves) {
    int64_t node = nodes++;
    left[node] = right[node] = -1;
    size[node] = 1;
    if (leaves == 1) return node;
    int64_t split = 1 + mix(splits++) % (leaves - 1);
    int64_t l = build(split), r = build(leaves - split);
    left[node] = l; right[node] = r;
    size[node] = 1 + size[l] + size[r];
    return node;
}

static int64_t combine(int64_t node, int64_t a, int64_t b) {
    int64_t op = mix(node) % 4, value;
    if (op == 0) value = (a + b) % MODULUS;
    else if (op == 1) value = a * b % MODULUS;
    else if (op == 2) value = (a ^ b) % MODULUS;
    else value = a > b ? a : b;
    return (value + mix(value + node) % 1024) % MODULUS;
}

static int64_t evaluate(int64_t node, int64_t pass) {
    if (left[node] < 0) return mix(node + pass * 1000003) % MODULUS;
    int64_t a = evaluate(left[node], pass), b = evaluate(right[node], pass);
    return combine(node, a, b);
}

int main(int argc, char **argv) {
    int64_t leaves = atoll(argv[1]);
    left = malloc(sizeof(int64_t) * (size_t)(2 * leaves));
    right = malloc(sizeof(int64_t) * (size_t)(2 * leaves));
    size = malloc(sizeof(int64_t) * (size_t)(2 * leaves));
    int64_t root = build(leaves);
    printf("nodes %lld\n", (long long)nodes);
    int64_t digest = 0;
    for (int64_t pass = 0; pass < PASSES; ++pass) {
        int64_t value = evaluate(root, pass);
        printf("pass %lld %lld\n", (long long)pass, (long long)value);
        digest = (digest * 31 + value) % MODULUS;
    }
    printf("digest %lld\n", (long long)digest);
    return 0;
}
