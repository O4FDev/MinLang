// C++ peer for main.min: unordered_map degrees and node indices, adjacency
// vectors of indices, BFS and a FIFO cache.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <unordered_map>
#include <vector>

struct Mix {
    size_t operator()(int64_t key) const noexcept { uint64_t h = (uint64_t)key * 0x9E3779B97F4A7C15ULL; return h ^ (h >> 29); }
};
using Map = std::unordered_map<int64_t, int64_t, Mix>;

static int64_t state = 99;
static int64_t next_random() { state = (state * 1103515245 + 12345) % 2147483648LL; return state / 16; }
static int64_t node_key(int64_t index) { return index * 7919 + 13; }

int main(int argc, char **argv) {
    const int64_t edges = argc > 1 ? std::atoll(argv[1]) : 0, nodes = edges / 4 + 1;
    Map degrees, index;
    degrees.reserve(nodes); index.reserve(nodes);
    std::vector<std::vector<int32_t>> lists;
    lists.reserve(nodes);
    int64_t removed = 0, start = 0;
    auto node_index = [&](int64_t key) {
        auto [it, inserted] = index.try_emplace(key, (int64_t)lists.size());
        if (inserted) lists.emplace_back();
        return it->second;
    };
    for (int64_t i = 0; i < edges; i++) {
        int64_t a = node_key(next_random() % nodes);
        int64_t b = node_key(next_random() % nodes);
        if (i == 0) start = a;
        degrees[a]++;
        degrees[b]++;
        int64_t la = node_index(a), lb = node_index(b);
        lists[la].push_back((int32_t)lb);
        lists[lb].push_back((int32_t)la);
        if (i % 7 == 0 && degrees.erase(node_key(next_random() % nodes))) removed++;
    }
    std::vector<std::pair<int64_t, int64_t>> sorted(degrees.begin(), degrees.end());
    std::sort(sorted.begin(), sorted.end());
    int64_t checksum = 0, busiest = 0;
    for (auto [key, degree] : sorted) {
        checksum = (checksum * 31 + key + degree) % 1000000007;
        busiest = std::max(busiest, degree);
    }
    std::printf("%zu %zu %lld\n%lld %lld\n", degrees.size(), index.size(), (long long)removed, (long long)checksum, (long long)busiest);

    std::vector<uint8_t> visited(lists.size());
    std::vector<int32_t> frontier{(int32_t)index[start]}, next;
    visited[frontier[0]] = 1;
    int64_t reached = 1, depth = 0, depth_sum = 0;
    while (!frontier.empty()) {
        next.clear();
        for (int32_t node : frontier) {
            depth_sum += depth;
            for (int32_t to : lists[node])
                if (!visited[to]) { visited[to] = 1; next.push_back(to); reached++; }
        }
        frontier.swap(next);
        depth++;
    }
    std::printf("%lld %lld %lld\n", (long long)reached, (long long)depth_sum, (long long)depth);

    const size_t capacity = nodes / 8 + 1;
    Map cache;
    cache.reserve(capacity + 1);
    std::vector<int64_t> arrivals;
    size_t oldest = 0;
    int64_t hits = 0, misses = 0, value_sum = 0;
    for (int64_t request = 0; request < edges; request++) {
        int64_t x = next_random() % nodes;
        int64_t y = next_random() % nodes;
        int64_t key = node_key(std::min(x, y));
        auto [it, inserted] = cache.try_emplace(key, 0);
        if (!inserted) { hits++; value_sum += it->second; continue; }
        misses++;
        it->second = key * 3 % 1000;
        value_sum += it->second;
        arrivals.push_back(key);
        if (cache.size() > capacity) cache.erase(arrivals[oldest++]);
    }
    std::printf("%lld %lld %lld %zu\n", (long long)hits, (long long)misses, (long long)value_sum, cache.size());
    return 0;
}
