// Serial C++ peer for main.min: sort N 40-bit keys with std::sort and print the same summary.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

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
    std::vector<int64_t> keys(static_cast<size_t>(count));
    for (int64_t i = 0; i < count; ++i) keys[size_t(i)] = mix(i) & 0xFFFFFFFFFFLL;
    std::sort(keys.begin(), keys.end());
    uint64_t checksum = 0;
    int64_t disorder = 0;
    for (int64_t i = 0; i < count; ++i) {
        checksum += uint64_t(keys[size_t(i)]) * uint64_t(i + 1);
        if (i > 0 && keys[size_t(i - 1)] > keys[size_t(i)]) ++disorder;
    }
    std::printf("count %lld disorder %lld\n", (long long)count, (long long)disorder);
    std::printf("first %lld middle %lld last %lld\n", (long long)keys[0], (long long)keys[size_t(count / 2)], (long long)keys[size_t(count - 1)]);
    std::printf("checksum %lld\n", (long long)int64_t(checksum));
}
