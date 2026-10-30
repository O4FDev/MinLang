// C++ peer for main.min: word frequencies over a text file, top 10 words.
#include <algorithm>
#include <cstdio>
#include <string_view>
#include <unordered_map>
#include <vector>

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    std::FILE *f = std::fopen(argv[1], "rb");
    std::fseek(f, 0, SEEK_END); long size = std::ftell(f); std::fseek(f, 0, SEEK_SET);
    std::vector<char> buffer(size);
    std::fread(buffer.data(), 1, size, f); std::fclose(f);
    const char *text = buffer.data();
    std::unordered_map<std::string_view, long long> counts;
    counts.reserve(1 << 16);
    long long total = 0;
    long i = 0;
    while (i < size) {
        long start = i;
        while (i < size && text[i] != ' ' && text[i] != '\n') i++;
        if (i > start) { total++; counts[std::string_view(text + start, i - start)]++; }
        i++;
    }
    std::vector<std::pair<std::string_view, long long>> entries(counts.begin(), counts.end());
    std::sort(entries.begin(), entries.end(), [](const auto &a, const auto &b) {
        return a.second != b.second ? a.second > b.second : a.first < b.first;
    });
    std::printf("%lld\n%zu\n", total, entries.size());
    for (int k = 0; k < 10; k++)
        std::printf("%.*s %lld\n", (int)entries[k].first.size(), entries[k].first.data(), entries[k].second);
    return 0;
}
