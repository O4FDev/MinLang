// C++ peer for main.min: std::sort of row structs by value. Every comparator is
// a total order (id breaks ties), so stability does not change the result.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string_view>
#include <vector>

struct Row { int64_t id, score; std::string_view name; };

int main(int argc, char **argv) {
    static constexpr std::string_view names[] = {"ada", "bob", "cy", "dee", "eve", "fay", "gus", "hal"};
    const std::size_t n = argc > 1 ? std::strtoul(argv[1], nullptr, 10) : 0;
    int64_t seed = 7;
    std::vector<Row> rows;
    rows.reserve(n);
    for (std::size_t i = 0; i < n; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        rows.push_back({int64_t(i), (seed / 1024) % 1000, names[(seed / 16) % 8]});
    }
    auto byScore = [](const Row &a, const Row &b) {
        if (a.score != b.score) return a.score > b.score;
        if (a.name != b.name) return a.name < b.name;
        return a.id < b.id;
    };
    auto byId = [](const Row &a, const Row &b) { return a.id < b.id; };
    for (int round = 0; round < 3; round++) {
        std::sort(rows.begin(), rows.end(), byScore);
        std::sort(rows.begin(), rows.end(), byId);
    }
    int64_t checksum = 0;
    for (const Row &r : rows) checksum = (checksum * 31 + r.score) % 1000000007;
    std::sort(rows.begin(), rows.end(), byScore);
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + rows[i].id) % 1000000007;
    std::printf("%lld\n", (long long)checksum);
    return 0;
}
