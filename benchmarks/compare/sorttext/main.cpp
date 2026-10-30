// C++ peer for main.min: std::sort of string_views, Integers and (key, value) records.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <vector>

struct Item { std::string_view key; int64_t value; };

static int64_t checksum(const std::vector<int64_t> &values) {
    int64_t total = 0;
    for (int64_t v : values) total = (total * 31 + v) % 1000000007;
    return total;
}

int main(int argc, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::vector<std::string_view> words;
    std::vector<int64_t> numbers;
    std::vector<Item> items;
    std::string_view rest(text);
    while (!rest.empty()) {
        std::size_t eol = rest.find('\n');
        std::string_view line = rest.substr(0, eol);
        rest = eol == std::string_view::npos ? std::string_view() : rest.substr(eol + 1);
        if (line.empty()) continue;
        std::size_t space = line.find(' ');
        std::string_view key = line.substr(0, space);
        int64_t value = 0;
        for (char d : line.substr(space + 1)) value = value * 10 + (d - '0');
        words.push_back(key);
        numbers.push_back(value);
        items.push_back({key, value});
    }
    const std::size_t n = words.size();
    std::vector<std::string_view> sortedWords = words;
    std::sort(sortedWords.begin(), sortedWords.end());
    std::size_t distinct = 0;
    std::vector<int64_t> scratch(n);
    for (std::size_t i = 0; i < n; i++) {
        if (i == 0 || sortedWords[i] != sortedWords[i - 1]) distinct++;
        scratch[i] = int64_t(sortedWords[i].size());
    }
    std::printf("words %zu distinct %zu checksum %lld\n", n, distinct, (long long)checksum(scratch));
    for (std::size_t i = 0; i < 3; i++) std::printf("%.*s\n", int(sortedWords[i].size()), sortedWords[i].data());
    for (std::size_t i = n - 3; i < n; i++) std::printf("%.*s\n", int(sortedWords[i].size()), sortedWords[i].data());
    std::sort(numbers.begin(), numbers.end());
    std::printf("numbers min %lld median %lld max %lld checksum %lld\n", (long long)numbers[0], (long long)numbers[n / 2],
                (long long)numbers[n - 1], (long long)checksum(numbers));
    std::sort(items.begin(), items.end(), [](const Item &a, const Item &b) {
        if (a.key != b.key) return a.key < b.key;
        return a.value > b.value;
    });
    for (std::size_t i = 0; i < n; i++) scratch[i] = items[i].value;
    std::printf("items checksum %lld\n", (long long)checksum(scratch));
    for (std::size_t i = 0; i < 3; i++) std::printf("%.*s %lld\n", int(items[i].key.size()), items[i].key.data(), (long long)items[i].value);
    return 0;
}
