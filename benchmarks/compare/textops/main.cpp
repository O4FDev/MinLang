// C++ peer for main.min: split log fields, search messages, mask addresses,
// replace words, format output lines and summarise per service.
#include <algorithm>
#include <charconv>
#include <cstdio>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

struct Summary { long long lines = 0, total_ms = 0, timeouts = 0, words = 0; std::string_view longest; };

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    std::FILE *f = std::fopen(argv[1], "rb");
    std::fseek(f, 0, SEEK_END); long size = std::ftell(f); std::fseek(f, 0, SEEK_SET);
    std::vector<char> buffer(size);
    std::fread(buffer.data(), 1, size, f); std::fclose(f);
    std::string_view source(buffer.data(), size);
    std::unordered_map<std::string_view, Summary> summaries;
    long long lines = 0, malformed = 0, internal = 0, alerts = 0, timeouts = 0, replaced = 0, formatted_bytes = 0;
    std::vector<std::string> samples;
    std::string formatted;
    formatted.reserve(1024);
    size_t start = 0;
    while (start < source.size()) {
        size_t end = source.find('\n', start);
        if (end == std::string_view::npos) end = source.size();
        std::string_view line = source.substr(start, end - start);
        start = end + 1;
        if (line.empty()) continue;
        lines++;
        std::string_view fields[5];
        size_t p = 0;
        for (int k = 0; k < 5; k++) {
            size_t sep = k < 4 ? line.find(" | ", p) : std::string_view::npos;
            if (sep == std::string_view::npos) sep = line.size();
            fields[k] = line.substr(p, sep - p);
            p = sep + 3;
        }
        long long duration = 0;
        auto parsed = std::from_chars(fields[4].data(), fields[4].data() + fields[4].size(), duration);
        bool digits = !fields[4].empty() && fields[4].find_first_not_of("0123456789") == std::string_view::npos;
        if (!digits || parsed.ec != std::errc()) { malformed++; continue; }
        std::string_view tag = "[D]";
        if (fields[0] == "ERROR") { tag = "[E]"; alerts++; }
        else if (fields[0] == "WARN") { tag = "[W]"; alerts++; }
        else if (fields[0] == "INFO") tag = "[I]";
        std::string_view service = fields[1], address = fields[2], message = fields[3];
        if (address.ends_with("@example.com")) internal++;
        bool timed_out = message.find("timeout") != std::string_view::npos;
        timeouts += timed_out;
        Summary &s = summaries[service];
        s.lines++; s.total_ms += duration; s.timeouts += timed_out;
        for (size_t i = 0; i < message.size();) {
            size_t space = message.find(' ', i);
            if (space == std::string_view::npos) space = message.size();
            if (space > i) {
                s.words++;
                if (space - i > s.longest.size()) s.longest = message.substr(i, space - i);
            }
            i = space + 1;
        }
        formatted.clear();
        formatted += tag; formatted += ' ';
        formatted += service.starts_with("auth") ? "security/" : "app/";
        formatted += service; formatted += ' ';
        size_t at = address.find('@');
        if (at == std::string_view::npos || at == 0) formatted += "***";
        else { formatted += address[0]; formatted += "***"; formatted += address.substr(at); }
        formatted += ' ';
        char digits_buffer[24];
        formatted.append(digits_buffer, std::to_chars(digits_buffer, digits_buffer + 24, duration).ptr);
        formatted += "ms: ";
        size_t from = 0;
        for (size_t hit; (hit = message.find("order", from)) != std::string_view::npos; from = hit + 5) {
            formatted += message.substr(from, hit - from);
            formatted += "ORDER";
            replaced++;
        }
        formatted += message.substr(from);
        formatted_bytes += (long long)formatted.size();
        if (samples.size() < 3) samples.push_back(formatted);
    }
    std::printf("lines %lld\nmalformed %lld\nalerts %lld\ninternal %lld\ntimeouts %lld\nreplaced %lld\nformatted bytes %lld\n",
                lines, malformed, alerts, internal, timeouts, replaced, formatted_bytes);
    for (const std::string &sample : samples) std::printf("%s\n", sample.c_str());
    std::vector<std::pair<std::string_view, Summary>> sorted(summaries.begin(), summaries.end());
    std::sort(sorted.begin(), sorted.end(), [](const auto &a, const auto &b) { return a.first < b.first; });
    for (const auto &[name, s] : sorted)
        std::printf("%.*s: %lld lines, avg %lld ms, %lld timeouts, %lld words, longest %.*s\n", (int)name.size(), name.data(),
                    s.lines, s.total_ms / s.lines, s.timeouts, s.words, (int)s.longest.size(), s.longest.data());
    return 0;
}
