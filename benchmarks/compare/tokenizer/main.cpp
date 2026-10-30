// C++ peer for main.min: lex into a token vector, then count kinds, rank identifiers, checksum.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

enum Kind : uint8_t { IDENT, KEYWORD, NUMBER, STRING, OPERATOR, COMMENT };
struct Token { uint32_t start, width, line, extra; Kind kind; };

struct Fnv {
    size_t operator()(std::string_view s) const noexcept {
        uint64_t h = 1469598103934665603ULL;
        for (unsigned char c : s) { h ^= c; h *= 1099511628211ULL; }
        return h;
    }
};

static bool is_letter(unsigned char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static bool is_digit(unsigned char c) { return c >= '0' && c <= '9'; }
static bool is_keyword(std::string_view w) {
    static constexpr std::string_view keywords[] = {"let", "if", "else", "while", "return", "function", "for", "in"};
    return std::find(std::begin(keywords), std::end(keywords), w) != std::end(keywords);
}
static bool two_char(char a, char b) {
    return (b == '=' && (a == '=' || a == '!' || a == '<' || a == '>')) || (a == '&' && b == '&') ||
           (a == '|' && b == '|') || (a == '-' && b == '>');
}

int main(int, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string src((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    const size_t size = src.size();
    std::vector<Token> tokens;
    tokens.reserve(size / 4);
    uint32_t line = 1;
    size_t i = 0;
    while (i < size) {
        unsigned char c = src[i];
        if (c == '\n') { line++; i++; }
        else if (c == ' ' || c == '\t' || c == '\r') i++;
        else if (is_letter(c)) {
            size_t start = i++;
            while (i < size && (is_letter(src[i]) || is_digit(src[i]))) i++;
            tokens.push_back({uint32_t(start), uint32_t(i - start), line, 0,
                              is_keyword(std::string_view(src).substr(start, i - start)) ? KEYWORD : IDENT});
        } else if (is_digit(c)) {
            size_t start = i++;
            while (i < size && is_digit(src[i])) i++;
            tokens.push_back({uint32_t(start), uint32_t(i - start), line, 0, NUMBER});
        } else if (c == '"') {
            size_t start = i++;
            uint32_t decoded = 0;
            while (i < size && src[i] != '"') { i += (src[i] == '\\' && i + 1 < size) ? 2 : 1; decoded++; }
            i++;
            tokens.push_back({uint32_t(start), uint32_t(i - start), line, decoded, STRING});
        } else if (c == '/' && i + 1 < size && src[i + 1] == '/') {
            size_t start = i;
            size_t end = src.find('\n', i);
            i = end == std::string::npos ? size : end;
            tokens.push_back({uint32_t(start), uint32_t(i - start), line, 0, COMMENT});
        } else {
            uint32_t width = i + 1 < size && two_char(src[i], src[i + 1]) ? 2 : 1;
            tokens.push_back({uint32_t(i), width, line, 0, OPERATOR});
            i += width;
        }
    }
    std::unordered_map<std::string_view, uint32_t, Fnv> identifiers;
    identifiers.reserve(4096);
    long long counts[6] = {}, number_sum = 0, string_bytes = 0, checksum = 0;
    std::string_view view(src);
    for (const Token &t : tokens) {
        counts[t.kind]++;
        if (t.kind == IDENT) identifiers[view.substr(t.start, t.width)]++;
        else if (t.kind == NUMBER) {
            long long v = 0;
            for (uint32_t d = 0; d < t.width; d++) v = v * 10 + (src[t.start + d] - '0');
            number_sum = (number_sum + v) % 1000000007;
        } else if (t.kind == STRING) string_bytes += t.extra;
        checksum = (checksum * 31 + t.kind * 1000 + t.width + t.line) % 1000000007;
    }
    std::vector<std::pair<std::string_view, uint32_t>> entries(identifiers.begin(), identifiers.end());
    std::sort(entries.begin(), entries.end(), [](const auto &a, const auto &b) {
        return a.second != b.second ? a.second > b.second : a.first < b.first;
    });
    static const char *names[] = {"identifier", "keyword", "number", "string", "operator", "comment"};
    std::printf("tokens %zu\n", tokens.size());
    for (int k = 0; k < 6; k++) std::printf("%s %lld\n", names[k], counts[k]);
    std::printf("number sum %lld\nstring bytes %lld\ndistinct identifiers %zu\n", number_sum, string_bytes, entries.size());
    for (size_t k = 0; k < entries.size() && k < 10; k++)
        std::printf("%.*s %u\n", int(entries[k].first.size()), entries[k].first.data(), entries[k].second);
    std::printf("checksum %lld\n", checksum);
}
