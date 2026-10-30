// Serial C++ peer for main.min: build N sales, six passes of three grouped aggregations.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

struct Sale { int64_t customer, product, region, month, quantity, price, discount; };
constexpr int PASSES = 6;
constexpr int64_t MODULUS = 1000000007;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = int64_t(uint64_t(value) * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = int64_t(uint64_t(value) + uint64_t(round));
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

int main(int, char **argv) {
    int64_t count = std::atoll(argv[1]);
    std::vector<Sale> sales;
    sales.reserve(size_t(count));
    for (int64_t i = 0; i < count; ++i) {
        int64_t a = mix(i * 2), b = mix(i * 2 + 1);
        sales.push_back({a % 100000, (a >> 20) % 512, (a >> 32) % 16, (a >> 40) % 12, 1 + b % 9, 100 + (b >> 8) % 20000, (b >> 30) % 30});
    }
    int64_t digest = 0;
    for (int64_t pass = 0; pass < PASSES; ++pass) {
        int64_t minimum = 1 + pass % 3, skip = pass % 12, threshold = 100000 + pass * 10000, large = 0;
        std::array<int64_t, 192> revenue{};
        std::array<int64_t, 512> units{};
        for (const Sale &s : sales) {
            int64_t net = s.price * s.quantity * (100 - s.discount) / 100;
            if (s.quantity >= minimum) revenue[size_t(s.region * 12 + s.month)] += net;
            if (s.month != skip) units[size_t(s.product)] += s.quantity;
            if (net > threshold) large++;
        }
        for (int64_t v : revenue) digest = (digest * 31 + v) % MODULUS;
        for (int64_t v : units) digest = (digest * 31 + v) % MODULUS;
        digest = (digest * 31 + large) % MODULUS;
        std::printf("pass %lld large %lld\n", (long long)pass, (long long)large);
    }
    std::printf("digest %lld\n", (long long)digest);
}
