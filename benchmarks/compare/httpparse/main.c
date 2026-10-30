// C peer for main.min: frame and parse requests in place, route, and format responses.
#define _GNU_SOURCE // memmem
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

typedef struct { const char *p; size_t n; } Str;

static int space(char c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
static Str trim(Str s) {
    while (s.n && space(s.p[0])) { s.p++; s.n--; }
    while (s.n && space(s.p[s.n - 1])) s.n--;
    return s;
}
static int is(Str s, const char *lit) { size_t n = strlen(lit); return s.n == n && memcmp(s.p, lit, n) == 0; }
static int named(Str s, const char *lit) { size_t n = strlen(lit); return s.n == n && strncasecmp(s.p, lit, n) == 0; }
static int parse_integer(Str s, int64_t *out) {
    s = trim(s);
    size_t i = 0; int negative = 0;
    if (s.n && (s.p[0] == '-' || s.p[0] == '+')) { negative = s.p[0] == '-'; i = 1; }
    if (i == s.n) return 0;
    int64_t v = 0;
    for (; i < s.n; i++) {
        if (s.p[i] < '0' || s.p[i] > '9') return 0;
        if (__builtin_mul_overflow(v, 10, &v) || __builtin_add_overflow(v, s.p[i] - '0', &v)) return 0;
    }
    *out = negative ? -v : v;
    return 1;
}
static const char *reason(int status) {
    switch (status) {
    case 200: return "OK";
    case 201: return "Created";
    case 400: return "Bad Request";
    case 404: return "Not Found";
    case 405: return "Method Not Allowed";
    default: return "Length Required";
    }
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); size_t size = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(size + 1); if (fread(src, 1, size, f) != size) return 1; fclose(f); src[size] = 0;
    const char *p = src, *end = src + size;
    long long requests = 0, response_bytes = 0, checksum = 0, created = 0, counts[6] = {0};
    static const int codes[6] = {200, 201, 400, 404, 405, 411};
    char samples[3][512]; int sample_count = 0;
    char body[256], out[1024];
    int out_length = 0;
    for (;;) {
        const char *crlf = memmem(p, (size_t)(end - p), "\r\n", 2);
        const char *eol = crlf ? crlf : end;
        if (eol == p) break;
        Str line = {p, (size_t)(eol - p)};
        p = crlf ? crlf + 2 : end;
        Str parts[3]; int part_count = 0;
        for (const char *s = line.p, *stop = line.p + line.n;;) {
            const char *sp = memchr(s, ' ', (size_t)(stop - s));
            if (part_count < 3) parts[part_count] = (Str){s, (size_t)((sp ? sp : stop) - s)};
            part_count++;
            if (!sp) break;
            s = sp + 1;
        }
        int valid = part_count == 3;
        Str host = {0}, length = {0}, request_id = {0}, connection = {0};
        int has_host = 0, has_length = 0, has_id = 0, has_connection = 0;
        while (p < end) {
            crlf = memmem(p, (size_t)(end - p), "\r\n", 2);
            eol = crlf ? crlf : end;
            Str header = {p, (size_t)(eol - p)};
            p = crlf ? crlf + 2 : end;
            if (!header.n) break;
            const char *colon = memchr(header.p, ':', header.n);
            if (!colon || colon == header.p) continue;
            Str name = {header.p, (size_t)(colon - header.p)};
            Str value = trim((Str){colon + 1, (size_t)(header.p + header.n - colon - 1)});
            if (named(name, "host")) { host = value; has_host = 1; }
            else if (named(name, "content-length")) { length = value; has_length = 1; }
            else if (named(name, "x-request-id")) { request_id = value; has_id = 1; }
            else if (named(name, "connection")) { connection = value; has_connection = 1; }
        }
        (void)host;
        int64_t body_length = 0; int bad_length = 0;
        if (has_length) {
            if (parse_integer(length, &body_length)) p += body_length;
            else bad_length = 1;
        }
        int status; int body_n; long long location = 0;
        if (!valid) { status = 400; body_n = snprintf(body, sizeof body, "{\"error\":\"bad request line\"}"); }
        else if (bad_length) { status = 400; body_n = snprintf(body, sizeof body, "{\"error\":\"bad content length\"}"); }
        else if (!has_host) { status = 400; body_n = snprintf(body, sizeof body, "{\"error\":\"missing host\"}"); }
        else {
            Str method = parts[0], path = parts[1], query = {"", 0};
            const char *mark = memchr(path.p, '?', path.n);
            if (mark) { query = (Str){mark + 1, (size_t)(path.p + path.n - mark - 1)}; path.n = (size_t)(mark - path.p); }
            if (path.n >= 7 && memcmp(path.p, "/users/", 7) == 0) {
                int64_t id;
                if (!is(method, "GET")) { status = 405; body_n = snprintf(body, sizeof body, "{\"error\":\"method not allowed\"}"); }
                else if (parse_integer((Str){path.p + 7, path.n - 7}, &id) && id >= 0 && id < 50000) {
                    status = 200;
                    body_n = snprintf(body, sizeof body, "{\"id\":%lld,\"name\":\"user-%lld\",\"tier\":%lld}", (long long)id, (long long)id, (long long)(id % 5));
                } else { status = 404; body_n = snprintf(body, sizeof body, "{\"error\":\"no such user\"}"); }
            } else if (is(path, "/search")) {
                if (!is(method, "GET")) { status = 405; body_n = snprintf(body, sizeof body, "{\"error\":\"method not allowed\"}"); }
                else {
                    Str term = {0}; int has_term = 0; int64_t limit = 10;
                    const char *q = query.p, *qend = query.p + query.n;
                    while (query.n) {
                        const char *amp = memchr(q, '&', (size_t)(qend - q));
                        const char *stop = amp ? amp : qend;
                        const char *eq = memchr(q, '=', (size_t)(stop - q));
                        Str key = {q, (size_t)((eq ? eq : stop) - q)};
                        Str value = eq ? (Str){eq + 1, (size_t)(stop - eq - 1)} : (Str){"", 0};
                        if (is(key, "q")) { term = value; has_term = 1; }
                        else if (is(key, "limit")) { if (!parse_integer(value, &limit)) limit = 10; }
                        if (!amp) break;
                        q = amp + 1;
                    }
                    if (!has_term) { status = 400; body_n = snprintf(body, sizeof body, "{\"error\":\"missing q\"}"); }
                    else {
                        status = 200;
                        body_n = snprintf(body, sizeof body, "{\"query\":\"%.*s\",\"limit\":%lld,\"results\":[", (int)term.n, term.p, (long long)limit);
                        for (int64_t k = 0; k < limit && k < 5; k++)
                            body_n += snprintf(body + body_n, sizeof body - (size_t)body_n, k ? ",\"%.*s-%lld\"" : "\"%.*s-%lld\"", (int)term.n, term.p, (long long)k);
                        body_n += snprintf(body + body_n, sizeof body - (size_t)body_n, "]}");
                    }
                }
            } else if (is(path, "/items")) {
                if (!is(method, "POST")) { status = 405; body_n = snprintf(body, sizeof body, "{\"error\":\"method not allowed\"}"); }
                else if (!has_length) { status = 411; body_n = snprintf(body, sizeof body, "{\"error\":\"length required\"}"); }
                else { status = 201; location = ++created; body_n = snprintf(body, sizeof body, "{\"created\":true,\"bytes\":%lld}", (long long)body_length); }
            } else { status = 404; body_n = snprintf(body, sizeof body, "{\"error\":\"not found\"}"); }
        }
        out_length = snprintf(out, sizeof out, "HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\n", status, reason(status), body_n);
        if (has_id) out_length += snprintf(out + out_length, sizeof out - (size_t)out_length, "X-Request-Id: %.*s\r\n", (int)request_id.n, request_id.p);
        if (location) out_length += snprintf(out + out_length, sizeof out - (size_t)out_length, "Location: /items/%lld\r\n", location);
        out_length += snprintf(out + out_length, sizeof out - (size_t)out_length, "Connection: %s\r\n\r\n%s",
                               has_connection && is(connection, "close") ? "close" : "keep-alive", body);
        requests++;
        for (int k = 0; k < 6; k++) if (codes[k] == status) counts[k]++;
        response_bytes += out_length;
        checksum = (checksum * 131 + (long long)out_length * 7 + status) % 1000000007;
        if (sample_count < 3) memcpy(samples[sample_count++], out, (size_t)out_length + 1);
        if (p >= end) break;
    }
    printf("requests %lld\n", requests);
    for (int k = 0; k < 6; k++) printf("status %d %lld\n", codes[k], counts[k]);
    printf("response bytes %lld\nitems created %lld\nchecksum %lld\n", response_bytes, created, checksum);
    for (int k = 0; k < sample_count; k++) puts(samples[k]);
    puts(out);
    return 0;
}
