// C++ peer for main.min: a general JSON DOM parser (string_views into the
// input; decoded strings owned by a deque), the same query, and a compact
// serialiser with the same escaping as json.quote.
#include <algorithm>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

enum class Kind : uint8_t { Null, False, True, Number, String, Array, Object };
struct Value {
    Kind kind = Kind::Null;
    int64_t number = 0;
    std::string_view text;
    std::vector<Value> items;
    std::vector<std::string_view> keys;
};

[[noreturn]] static void invalid(const char *why) { std::printf("invalid input: %s\n", why); std::exit(1); }

class Parser {
public:
    explicit Parser(std::string_view source) : p(source.data()), end(source.data() + source.size()) {}
    Value document() {
        Value v = value(0);
        space();
        if (p != end) invalid("unexpected trailing input");
        return v;
    }
private:
    const char *p, *end;
    std::deque<std::string> decoded;
    void space() { while (p < end && (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t')) p++; }
    static unsigned hex4(const char *s) {
        unsigned v = 0;
        for (int i = 0; i < 4; i++) {
            char c = s[i]; v <<= 4;
            if (c >= '0' && c <= '9') v |= c - '0'; else if (c >= 'a' && c <= 'f') v |= c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') v |= c - 'A' + 10; else invalid("bad unicode escape");
        }
        return v;
    }
    static void utf8(std::string &o, unsigned c) {
        if (c < 0x80) o += (char)c;
        else if (c < 0x800) { o += (char)(0xC0 | c >> 6); o += (char)(0x80 | (c & 63)); }
        else if (c < 0x10000) { o += (char)(0xE0 | c >> 12); o += (char)(0x80 | (c >> 6 & 63)); o += (char)(0x80 | (c & 63)); }
        else { o += (char)(0xF0 | c >> 18); o += (char)(0x80 | (c >> 12 & 63)); o += (char)(0x80 | (c >> 6 & 63)); o += (char)(0x80 | (c & 63)); }
    }
    std::string_view string() {
        const char *start = ++p, *s = p;
        while (s < end && *s != '"' && *s != '\\') { if ((unsigned char)*s < 32) invalid("control in string"); s++; }
        if (s < end && *s == '"') { p = s + 1; return {start, (size_t)(s - start)}; }
        std::string &o = decoded.emplace_back(start, s);
        while (s < end && *s != '"') {
            unsigned char c = (unsigned char)*s;
            if (c < 32) invalid("control in string");
            if (c != '\\') { o += (char)c; s++; continue; }
            if (s + 1 >= end) invalid("unfinished escape");
            switch (s[1]) {
            case '"': o += '"'; break; case '\\': o += '\\'; break; case '/': o += '/'; break;
            case 'b': o += '\b'; break; case 'f': o += '\f'; break; case 'n': o += '\n'; break;
            case 'r': o += '\r'; break; case 't': o += '\t'; break;
            case 'u': {
                if (end - s < 6) invalid("short unicode escape");
                unsigned u = hex4(s + 2); s += 4;
                if (u >= 0xD800 && u < 0xDC00 && end - s >= 8 && s[2] == '\\' && s[3] == 'u') {
                    unsigned low = hex4(s + 4);
                    if (low >= 0xDC00 && low < 0xE000) { u = 0x10000 + ((u - 0xD800) << 10) + (low - 0xDC00); s += 6; }
                }
                utf8(o, u); break;
            }
            default: invalid("unknown escape");
            }
            s += 2;
        }
        if (s >= end) invalid("unterminated string");
        p = s + 1;
        return o;
    }
    bool literal(std::string_view word) {
        if ((size_t)(end - p) >= word.size() && std::memcmp(p, word.data(), word.size()) == 0) { p += word.size(); return true; }
        return false;
    }
    Value value(int depth) {
        if (depth > 512) invalid("nesting too deep");
        space();
        if (p >= end) invalid("unexpected end");
        Value v;
        char c = *p;
        if (c == '{') {
            p++; v.kind = Kind::Object; space();
            if (p < end && *p == '}') { p++; return v; }
            for (;;) {
                space();
                if (p >= end || *p != '"') invalid("expected member name");
                v.keys.push_back(string()); space();
                if (p >= end || *p != ':') invalid("expected ':'");
                p++; v.items.push_back(value(depth + 1)); space();
                if (p < end && *p == ',') { p++; continue; }
                if (p < end && *p == '}') { p++; return v; }
                invalid("expected ',' or '}'");
            }
        }
        if (c == '[') {
            p++; v.kind = Kind::Array; space();
            if (p < end && *p == ']') { p++; return v; }
            for (;;) {
                v.items.push_back(value(depth + 1)); space();
                if (p < end && *p == ',') { p++; continue; }
                if (p < end && *p == ']') { p++; return v; }
                invalid("expected ',' or ']'");
            }
        }
        if (c == '"') { v.kind = Kind::String; v.text = string(); return v; }
        if (literal("true")) { v.kind = Kind::True; return v; }
        if (literal("false")) { v.kind = Kind::False; return v; }
        if (literal("null")) return v;
        if (c == '-' || (c >= '0' && c <= '9')) {
            const char *start = p;
            if (*p == '-') p++;
            const char *digits = p;
            while (p < end && *p >= '0' && *p <= '9') p++;
            if (p == digits || (p - digits > 1 && *digits == '0') || p - digits > 18) invalid("bad number");
            if (p < end && (*p == '.' || *p == 'e' || *p == 'E')) invalid("expected an integer");
            std::from_chars(start, p, v.number);
            v.kind = Kind::Number;
            return v;
        }
        invalid("unexpected character");
    }
};

static const Value &get(const Value &v, std::string_view name) {
    if (v.kind != Kind::Object) invalid("expected a JSON object");
    for (size_t i = 0; i < v.keys.size(); i++) if (v.keys[i] == name) return v.items[i];
    invalid("missing member");
}
static int64_t integer(const Value &v) { if (v.kind != Kind::Number) invalid("expected a JSON integer"); return v.number; }
static std::string_view text(const Value &v) { if (v.kind != Kind::String) invalid("expected a JSON string"); return v.text; }
static const std::vector<Value> &array(const Value &v) { if (v.kind != Kind::Array) invalid("expected a JSON array"); return v.items; }

static void quote(std::string &o, std::string_view s) {
    static const char hex[] = "0123456789abcdef";
    o += '"';
    for (unsigned char c : s) {
        if (c >= 32 && c != '"' && c != '\\') { o += (char)c; continue; }
        o += '\\';
        switch (c) {
        case '"': o += '"'; break; case '\\': o += '\\'; break; case '\n': o += 'n'; break;
        case '\t': o += 't'; break; case '\r': o += 'r'; break; case 8: o += 'b'; break; case 12: o += 'f'; break;
        default: o += "u00"; o += hex[c >> 4]; o += hex[c & 15];
        }
    }
    o += '"';
}
static void number(std::string &o, int64_t v) { char buf[24]; o.append(buf, std::to_chars(buf, buf + sizeof buf, v).ptr); }

struct CityStats { int64_t users = 0, active = 0, spent = 0, oldest = 0, top_spent = -1; std::string_view top; };

int main(int argc, char **argv) {
    std::ifstream file(argv[1], std::ios::binary);
    std::string source((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    Parser parser(source);
    const Value root = parser.document();
    std::unordered_map<std::string_view, CityStats> cities;
    std::unordered_map<std::string_view, int64_t> tag_counts;
    int64_t active = 0, checksum = 0, geo_sum = 0;
    std::vector<std::string> spenders;
    for (const Value &user : array(root)) {
        const Value &address = get(user, "address");
        const std::vector<Value> &geo = array(get(address, "geo"));
        std::vector<std::string_view> tags;
        for (const Value &tag : array(get(user, "tags"))) tags.push_back(text(tag));
        int64_t spent = 0;
        for (const Value &order : array(get(user, "orders"))) spent += integer(get(order, "qty")) * integer(get(order, "price"));
        const int64_t id = integer(get(user, "id"));
        const std::string_view name = text(get(user, "name")), city = text(get(address, "city")), zip_text = text(get(address, "zip"));
        const Value &flag = get(user, "active");
        if (flag.kind != Kind::True && flag.kind != Kind::False) invalid("expected a JSON boolean");
        const int64_t age = integer(get(user, "age")), score = integer(get(user, "score"));
        if (geo.size() < 2) invalid("short geo");
        int64_t zip = 0;
        std::from_chars(zip_text.data(), zip_text.data() + zip_text.size(), zip);
        CityStats &stats = cities[city];
        stats.users++;
        stats.spent += spent;
        stats.oldest = std::max(stats.oldest, age);
        if (spent > stats.top_spent) { stats.top_spent = spent; stats.top = name; }
        checksum = (checksum * 31 + (int64_t)name.size() + age + score + 5000 + zip) % 1000000007;
        geo_sum += integer(geo[0]) + integer(geo[1]);
        if (flag.kind != Kind::True) continue;
        active++;
        stats.active++;
        for (std::string_view tag : tags) tag_counts[tag]++;
        if (spent > 600000) {
            std::string &s = spenders.emplace_back("{\"id\":");
            number(s, id); s += ",\"name\":"; quote(s, name); s += ",\"city\":"; quote(s, city);
            s += ",\"spent\":"; number(s, spent); s += ",\"tags\":[";
            for (size_t t = 0; t < tags.size(); t++) { if (t) s += ','; quote(s, tags[t]); }
            s += "]}";
        }
    }
    std::vector<std::string_view> city_names, tag_names;
    for (auto &[name, _] : cities) city_names.push_back(name);
    for (auto &[name, _] : tag_counts) tag_names.push_back(name);
    std::sort(city_names.begin(), city_names.end());
    std::sort(tag_names.begin(), tag_names.end());
    std::vector<std::string> city_lines;
    for (std::string_view city : city_names) {
        const CityStats &s = cities[city];
        std::string &o = city_lines.emplace_back("{\"city\":");
        quote(o, city);
        o += ",\"users\":"; number(o, s.users); o += ",\"active\":"; number(o, s.active);
        o += ",\"spent\":"; number(o, s.spent); o += ",\"oldest\":"; number(o, s.oldest);
        o += ",\"top\":"; quote(o, s.top); o += ",\"topSpent\":"; number(o, s.top_spent); o += '}';
    }
    std::string output = "{\"cities\":[";
    for (size_t c = 0; c < city_lines.size(); c++) { if (c) output += ','; output += city_lines[c]; }
    output += "],\"tags\":{";
    for (size_t t = 0; t < tag_names.size(); t++) { if (t) output += ','; quote(output, tag_names[t]); output += ':'; number(output, tag_counts[tag_names[t]]); }
    output += "},\"spenders\":[";
    for (size_t k = 0; k < spenders.size(); k++) { if (k) output += ','; output += spenders[k]; }
    output += "]}";
    uint64_t hash = 14695981039346656037ULL;
    for (unsigned char c : output) { hash ^= c; hash *= 1099511628211ULL; }
    std::printf("%zu %lld\n%lld %lld\n%zu\n%zu %lld\n", root.items.size(), (long long)active, (long long)checksum, (long long)geo_sum,
                spenders.size(), output.size(), (long long)hash);
    for (const std::string &line : city_lines) { std::fwrite(line.data(), 1, line.size(), stdout); std::fputc('\n', stdout); }
    return 0;
}
