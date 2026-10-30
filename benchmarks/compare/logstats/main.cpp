// C++ peer for main.min: parse CSV log lines and aggregate per service.
#include <algorithm>
#include <charconv>
#include <cstdio>
#include <string_view>
#include <unordered_map>
#include <vector>

struct Stats { long long count = 0, total = 0, slowest = 0, errors = 0; };

static long long to_int(std::string_view s) {
    long long v = 0;
    std::from_chars(s.data(), s.data() + s.size(), v);
    return v;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    std::FILE *f = std::fopen(argv[1], "rb");
    std::fseek(f, 0, SEEK_END); long size = std::ftell(f); std::fseek(f, 0, SEEK_SET);
    std::vector<char> buffer(size);
    std::fread(buffer.data(), 1, size, f); std::fclose(f);
    std::string_view text(buffer.data(), size);
    std::unordered_map<std::string_view, Stats> services;
    long long warnings = 0;
    size_t start = 0;
    while (start < text.size()) {
        size_t end = text.find('\n', start);
        if (end == std::string_view::npos) end = text.size();
        std::string_view line = text.substr(start, end - start);
        start = end + 1;
        if (line.empty()) continue;
        std::string_view fields[5];
        size_t p = 0;
        for (int k = 0; k < 5; k++) {
            size_t comma = line.find(',', p);
            if (comma == std::string_view::npos) comma = line.size();
            fields[k] = line.substr(p, comma - p);
            p = comma + 1;
        }
        long long latency = to_int(fields[3]), status = to_int(fields[4]);
        if (fields[1] == "WARN") warnings++;
        Stats &s = services[fields[2]];
        s.count++; s.total += latency;
        if (latency > s.slowest) s.slowest = latency;
        if (status >= 500) s.errors++;
    }
    std::vector<std::pair<std::string_view, Stats>> sorted(services.begin(), services.end());
    std::sort(sorted.begin(), sorted.end(), [](const auto &a, const auto &b) { return a.first < b.first; });
    std::printf("%lld\n", warnings);
    for (const auto &[name, s] : sorted)
        std::printf("%.*s %lld %lld %lld %lld\n", (int)name.size(), name.data(), s.count, s.total / s.count, s.slowest, s.errors);
    return 0;
}
