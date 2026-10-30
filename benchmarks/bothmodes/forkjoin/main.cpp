// Serial C++ peer for main.min: build a random expression tree, evaluate it eight times.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

constexpr int PASSES = 8;
constexpr int64_t MODULUS = 2147483647;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = int64_t(uint64_t(value) * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = int64_t(uint64_t(value) + uint64_t(round));
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

struct Tree {
    std::vector<int64_t> left, right, size;
    int64_t splits = 0;
    int64_t build(int64_t leaves) {
        int64_t node = int64_t(left.size());
        left.push_back(-1); right.push_back(-1); size.push_back(1);
        if (leaves == 1) return node;
        int64_t split = 1 + mix(splits++) % (leaves - 1);
        int64_t l = build(split), r = build(leaves - split);
        left[size_t(node)] = l; right[size_t(node)] = r;
        size[size_t(node)] = 1 + size[size_t(l)] + size[size_t(r)];
        return node;
    }
    static int64_t combine(int64_t node, int64_t a, int64_t b) {
        int64_t value;
        switch (mix(node) % 4) {
        case 0: value = (a + b) % MODULUS; break;
        case 1: value = a * b % MODULUS; break;
        case 2: value = (a ^ b) % MODULUS; break;
        default: value = std::max(a, b);
        }
        return (value + mix(value + node) % 1024) % MODULUS;
    }
    int64_t evaluate(int64_t node, int64_t pass) const {
        if (left[size_t(node)] < 0) return mix(node + pass * 1000003) % MODULUS;
        int64_t a = evaluate(left[size_t(node)], pass), b = evaluate(right[size_t(node)], pass);
        return combine(node, a, b);
    }
};

int main(int, char **argv) {
    int64_t leaves = std::atoll(argv[1]);
    Tree tree;
    tree.left.reserve(size_t(2 * leaves)); tree.right.reserve(size_t(2 * leaves)); tree.size.reserve(size_t(2 * leaves));
    int64_t root = tree.build(leaves);
    std::printf("nodes %lld\n", (long long)tree.left.size());
    int64_t digest = 0;
    for (int64_t pass = 0; pass < PASSES; ++pass) {
        int64_t value = tree.evaluate(root, pass);
        std::printf("pass %lld %lld\n", (long long)pass, (long long)value);
        digest = (digest * 31 + value) % MODULUS;
    }
    std::printf("digest %lld\n", (long long)digest);
}
