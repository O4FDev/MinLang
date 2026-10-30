// C++ peer for main.min: Collatz step sum and hash histogram over 4 std::threads,
// chunks of indices interleaved across threads, per-thread partial results.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

constexpr int THREADS = 4, BUCKETS = 16;
constexpr int64_t CHUNK = 4096;

static int32_t collatz_steps(uint64_t value) {
    int32_t n = 0;
    while (value != 1) { value = (value & 1) ? 3 * value + 1 : value >> 1; n++; }
    return n;
}

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 4; round++) {
        value ^= value >> 31;
        value = static_cast<int64_t>(static_cast<uint64_t>(value) * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = static_cast<int64_t>(static_cast<uint64_t>(value) + static_cast<uint64_t>(round));
    }
    return value;
}

template <class Body> static void interleaved(int64_t n, Body body) {
    std::vector<std::thread> threads;
    for (int t = 0; t < THREADS; t++)
        threads.emplace_back([=] {
            for (int64_t first = t * CHUNK; first < n; first += THREADS * CHUNK) body(t, first, std::min(first + CHUNK, n));
        });
    for (auto &thread : threads) thread.join();
}

int main(int argc, char **argv) {
    int64_t count = std::atoll(argv[1]);
    std::vector<int32_t> steps(static_cast<size_t>(count));
    std::array<int64_t, THREADS> partial{};
    interleaved(count, [&](int t, int64_t first, int64_t last) {
        int64_t sum = 0;
        for (int64_t i = first; i < last; i++) { steps[i] = collatz_steps(static_cast<uint64_t>(i) + 1); sum += steps[i]; }
        partial[t] += sum;
    });
    int64_t total = 0;
    for (int64_t p : partial) total += p;
    int64_t longest = 0, longest_start = 1;
    for (int64_t i = 0; i < count; i++) if (steps[i] > longest) { longest = steps[i]; longest_start = i + 1; }
    std::printf("steps %lld\nlongest %lld %lld\n", (long long)total, (long long)longest_start, (long long)longest);
    int64_t samples = count * 8;
    std::array<std::array<int64_t, BUCKETS>, THREADS> bins{};
    interleaved(samples, [&](int t, int64_t first, int64_t last) {
        std::array<int64_t, BUCKETS> local{};
        for (int64_t s = first; s < last; s++) local[(mix(s) >> 11) & 15]++;
        for (int b = 0; b < BUCKETS; b++) bins[t][b] += local[b];
    });
    for (int b = 0; b < BUCKETS; b++) {
        int64_t sum = 0;
        for (auto &per : bins) sum += per[b];
        std::printf("bucket %d %lld\n", b, (long long)sum);
    }
    return 0;
}
