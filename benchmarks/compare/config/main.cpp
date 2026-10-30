// C++ peer for main.min: parse into nested unordered_maps of string_views, then query.
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <variant>
#include <vector>

struct Fnv {
    size_t operator()(std::string_view s) const noexcept {
        uint64_t h = 1469598103934665603ULL;
        for (unsigned char c : s) { h ^= c; h *= 1099511628211ULL; }
        return h;
    }
};
using Value = std::variant<int64_t, bool, std::string_view, std::vector<int64_t>>;
using Section = std::unordered_map<std::string_view, Value, Fnv>;

static bool space(char c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
static std::string_view trim(std::string_view s) {
    while (!s.empty() && space(s.front())) s.remove_prefix(1);
    while (!s.empty() && space(s.back())) s.remove_suffix(1);
    return s;
}
static std::optional<int64_t> parse_integer(std::string_view s, std::string &error) {
    size_t i = 0;
    bool negative = false;
    if (!s.empty() && (s[0] == '-' || s[0] == '+')) { negative = s[0] == '-'; i = 1; }
    int64_t v = 0;
    bool ok = i < s.size();
    for (; ok && i < s.size(); i++) {
        if (s[i] < '0' || s[i] > '9' || __builtin_mul_overflow(v, 10, &v) || __builtin_add_overflow(v, s[i] - '0', &v)) ok = false;
    }
    if (ok) return negative ? -v : v;
    error = "invalid integer '" + std::string(s) + "'";
    return std::nullopt;
}
static std::optional<Value> parse_value(std::string_view raw, std::string &error) {
    std::string_view v = trim(raw);
    if (!v.empty() && v[0] == '"') {
        size_t close = v.find('"', 1);
        if (close == std::string_view::npos) { error = "unterminated string"; return std::nullopt; }
        std::string_view rest = trim(v.substr(close + 1));
        if (!rest.empty() && rest[0] != '#') { error = "unexpected text after string"; return std::nullopt; }
        return Value(v.substr(1, close - 1));
    }
    if (size_t comment = v.find('#'); comment != std::string_view::npos) v = trim(v.substr(0, comment));
    if (!v.empty() && v[0] == '[') {
        if (v.size() < 2 || v.back() != ']') { error = "unterminated list"; return std::nullopt; }
        std::string_view inner = trim(v.substr(1, v.size() - 2));
        std::vector<int64_t> items;
        while (!inner.empty()) {
            size_t comma = inner.find(',');
            auto number = parse_integer(trim(inner.substr(0, comma)), error);
            if (!number) return std::nullopt;
            items.push_back(*number);
            if (comma == std::string_view::npos) break;
            inner = inner.substr(comma + 1);
            if (inner.empty()) { if (!parse_integer(inner, error)) return std::nullopt; }
        }
        return Value(std::move(items));
    }
    if (v == "true") return Value(true);
    if (v == "false") return Value(false);
    if (!v.empty() && (v[0] == '-' || (v[0] >= '0' && v[0] <= '9'))) {
        auto number = parse_integer(v, error);
        if (!number) return std::nullopt;
        return Value(*number);
    }
    error = "unknown value '" + std::string(v) + "'";
    return std::nullopt;
}

template <class T> static const T *lookup(const Section &section, std::string_view key) {
    auto it = section.find(key);
    return it == section.end() ? nullptr : std::get_if<T>(&it->second);
}

int main(int, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string src((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::unordered_map<std::string_view, Section, Fnv> sections;
    std::vector<std::string> errors;
    long long error_count = 0, line_number = 0;
    Section *current = nullptr;
    std::string_view all(src);
    std::string error;
    size_t start = 0;
    auto report = [&](std::string_view problem) {
        if (errors.size() < 8) errors.push_back("line " + std::to_string(line_number) + ": " + std::string(problem));
        error_count++;
    };
    while (start <= all.size()) {
        size_t nl = all.find('\n', start);
        if (nl == std::string_view::npos) nl = all.size();
        std::string_view line = trim(all.substr(start, nl - start));
        start = nl + 1;
        line_number++;
        if (line.empty() || line[0] == '#') continue;
        if (line[0] == '[') {
            if (line.size() < 2 || line.back() != ']') { report("unterminated section header"); continue; }
            current = &sections[trim(line.substr(1, line.size() - 2))];
            continue;
        }
        size_t eq = line.find('=');
        if (eq == std::string_view::npos) { report("expected '=' after a key"); continue; }
        std::string_view key = trim(line.substr(0, eq));
        if (key.empty()) { report("missing key"); continue; }
        if (!current) { report("entry outside a section"); continue; }
        auto value = parse_value(line.substr(eq + 1), error);
        if (!value) { report(error); continue; }
        (*current)[key] = std::move(*value);
    }
    size_t entries = 0;
    for (const auto &[name, section] : sections) entries += section.size();
    std::printf("sections %zu\nentries %zu\nerrors %lld\n", sections.size(), entries, error_count);
    for (const auto &e : errors) std::puts(e.c_str());
    long long queries = (long long)sections.size() * 3, space_ = (long long)sections.size() + (long long)sections.size() / 10 + 1;
    long long missing_sections = 0, missing_keys = 0, port_sum = 0, enabled = 0, name_bytes = 0, weight_sum = 0, weight_count = 0, timeout_sum = 0;
    std::string name;
    for (long long q = 0; q < queries; q++) {
        name = "service.";
        name += std::to_string((q * 7919) % space_);
        auto it = sections.find(name);
        if (it == sections.end()) { missing_sections++; continue; }
        const Section &s = it->second;
        if (auto v = lookup<int64_t>(s, "port")) port_sum += *v; else missing_keys++;
        if (auto v = lookup<bool>(s, "enabled")) enabled += *v; else missing_keys++;
        if (auto v = lookup<std::string_view>(s, "name")) name_bytes += (long long)v->size(); else missing_keys++;
        if (auto v = lookup<std::vector<int64_t>>(s, "weights")) {
            weight_count += (long long)v->size();
            for (int64_t item : *v) weight_sum += item;
        } else missing_keys++;
        auto timeout = lookup<int64_t>(s, "timeout");
        timeout_sum += timeout ? *timeout : 30;
    }
    std::printf("queries %lld\nmissing sections %lld\nmissing keys %lld\nport sum %lld\nenabled %lld\nname bytes %lld\nweights %lld %lld\ntimeout sum %lld\n",
                queries, missing_sections, missing_keys, port_sum, enabled, name_bytes, weight_count, weight_sum, timeout_sum);
}
