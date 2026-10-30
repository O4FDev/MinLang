// C++ peer for main.min: frame and parse requests as string_views, route, and build responses.
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

using namespace std::literals;

static bool space(char c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
static std::string_view trim(std::string_view s) {
    while (!s.empty() && space(s.front())) s.remove_prefix(1);
    while (!s.empty() && space(s.back())) s.remove_suffix(1);
    return s;
}
static bool iequals(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); i++) {
        char c = a[i];
        if (c >= 'A' && c <= 'Z') c = char(c + 32);
        if (c != b[i]) return false;
    }
    return true;
}
static std::optional<int64_t> parse_integer(std::string_view s) {
    s = trim(s);
    bool plus = !s.empty() && s[0] == '+';
    if (plus) s.remove_prefix(1);
    if (s.empty() || s[0] == '+' || (plus && s[0] == '-')) return std::nullopt;
    int64_t v = 0;
    auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), v);
    if (ec != std::errc() || ptr != s.data() + s.size()) return std::nullopt;
    return v;
}
static void append(std::string &out, int64_t v) {
    char buffer[24];
    auto r = std::to_chars(buffer, buffer + sizeof buffer, v);
    out.append(buffer, r.ptr);
}
static std::string_view reason(int status) {
    switch (status) {
    case 200: return "OK";
    case 201: return "Created";
    case 400: return "Bad Request";
    case 404: return "Not Found";
    case 405: return "Method Not Allowed";
    default: return "Length Required";
    }
}

int main(int, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string src((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::string_view rest(src);
    auto next_line = [&]() {
        size_t crlf = rest.find("\r\n");
        std::string_view line = rest.substr(0, crlf);
        rest = crlf == std::string_view::npos ? std::string_view() : rest.substr(crlf + 2);
        return line;
    };
    long long requests = 0, response_bytes = 0, checksum = 0, created = 0, counts[6] = {};
    static constexpr int codes[6] = {200, 201, 400, 404, 405, 411};
    std::vector<std::string> samples;
    std::string body, out;
    while (!rest.empty()) {
        std::string_view line = next_line();
        if (line.empty()) break;
        std::string_view parts[3];
        int part_count = 0;
        for (std::string_view s = line;;) {
            size_t sp = s.find(' ');
            if (part_count < 3) parts[part_count] = s.substr(0, sp);
            part_count++;
            if (sp == std::string_view::npos) break;
            s = s.substr(sp + 1);
        }
        bool valid = part_count == 3;
        std::optional<std::string_view> host, length, request_id, connection;
        while (!rest.empty()) {
            std::string_view header = next_line();
            if (header.empty()) break;
            size_t colon = header.find(':');
            if (colon == std::string_view::npos || colon == 0) continue;
            std::string_view name = header.substr(0, colon), value = trim(header.substr(colon + 1));
            if (iequals(name, "host")) host = value;
            else if (iequals(name, "content-length")) length = value;
            else if (iequals(name, "x-request-id")) request_id = value;
            else if (iequals(name, "connection")) connection = value;
        }
        int64_t body_length = 0;
        bool bad_length = false;
        if (length) {
            if (auto n = parse_integer(*length)) { body_length = *n; rest.remove_prefix(size_t(body_length)); }
            else bad_length = true;
        }
        int status;
        long long location = 0;
        auto fail = [&](int code, std::string_view message) { status = code; body = "{\"error\":\""; body += message; body += "\"}"; };
        if (!valid) fail(400, "bad request line");
        else if (bad_length) fail(400, "bad content length");
        else if (!host) fail(400, "missing host");
        else {
            std::string_view method = parts[0], path = parts[1], query;
            if (size_t mark = path.find('?'); mark != std::string_view::npos) { query = path.substr(mark + 1); path = path.substr(0, mark); }
            if (path.starts_with("/users/")) {
                auto id = parse_integer(path.substr(7));
                if (method != "GET") fail(405, "method not allowed");
                else if (id && *id >= 0 && *id < 50000) {
                    status = 200;
                    body = "{\"id\":"; append(body, *id); body += ",\"name\":\"user-"; append(body, *id);
                    body += "\",\"tier\":"; append(body, *id % 5); body += "}";
                } else fail(404, "no such user");
            } else if (path == "/search") {
                if (method != "GET") fail(405, "method not allowed");
                else {
                    std::optional<std::string_view> term;
                    int64_t limit = 10;
                    for (std::string_view q = query; !query.empty();) {
                        size_t amp = q.find('&');
                        std::string_view pair = q.substr(0, amp);
                        size_t eq = pair.find('=');
                        std::string_view key = pair.substr(0, eq), value = eq == std::string_view::npos ? ""sv : pair.substr(eq + 1);
                        if (key == "q") term = value;
                        else if (key == "limit") limit = parse_integer(value).value_or(10);
                        if (amp == std::string_view::npos) break;
                        q = q.substr(amp + 1);
                    }
                    if (!term) fail(400, "missing q");
                    else {
                        status = 200;
                        body = "{\"query\":\""; body += *term; body += "\",\"limit\":"; append(body, limit); body += ",\"results\":[";
                        for (int64_t k = 0; k < limit && k < 5; k++) {
                            if (k) body += ',';
                            body += '"'; body += *term; body += '-'; append(body, k); body += '"';
                        }
                        body += "]}";
                    }
                }
            } else if (path == "/items") {
                if (method != "POST") fail(405, "method not allowed");
                else if (!length) fail(411, "length required");
                else { status = 201; location = ++created; body = "{\"created\":true,\"bytes\":"; append(body, body_length); body += "}"; }
            } else fail(404, "not found");
        }
        out = "HTTP/1.1 "; append(out, status); out += ' '; out += reason(status);
        out += "\r\nContent-Type: application/json\r\nContent-Length: "; append(out, int64_t(body.size())); out += "\r\n";
        if (request_id) { out += "X-Request-Id: "; out += *request_id; out += "\r\n"; }
        if (location) { out += "Location: /items/"; append(out, location); out += "\r\n"; }
        out += "Connection: "; out += connection && *connection == "close" ? "close"sv : "keep-alive"sv; out += "\r\n\r\n"; out += body;
        requests++;
        for (int k = 0; k < 6; k++) if (codes[k] == status) counts[k]++;
        response_bytes += (long long)out.size();
        checksum = (checksum * 131 + (long long)out.size() * 7 + status) % 1000000007;
        if (samples.size() < 3) samples.push_back(out);
    }
    std::printf("requests %lld\n", requests);
    for (int k = 0; k < 6; k++) std::printf("status %d %lld\n", codes[k], counts[k]);
    std::printf("response bytes %lld\nitems created %lld\nchecksum %lld\n", response_bytes, created, checksum);
    for (const auto &s : samples) std::printf("%s\n", s.c_str());
    std::printf("%s\n", out.c_str());
}
