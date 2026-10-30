// C peer for main.min: split log fields, search messages, mask addresses,
// replace words, format output lines and summarise per service.
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *p; size_t n; } Slice;
typedef struct { Slice name, longest; long long lines, total_ms, timeouts, words; } Summary;
enum { SLOTS = 256 };
static Summary table[SLOTS];
static int used;

static int eq(Slice s, const char *literal, size_t n) { return s.n == n && memcmp(s.p, literal, n) == 0; }
static Summary *find_summary(Slice name) {
    unsigned h = 2166136261u;
    for (size_t i = 0; i < name.n; i++) { h ^= (unsigned char)name.p[i]; h *= 16777619u; }
    unsigned j = h & (SLOTS - 1);
    while (table[j].name.p) {
        if (table[j].name.n == name.n && memcmp(table[j].name.p, name.p, name.n) == 0) return &table[j];
        j = (j + 1) & (SLOTS - 1);
    }
    used++;
    table[j].name = name;
    table[j].longest = (Slice){"", 0};
    return &table[j];
}
static int compare(const void *x, const void *y) {
    const Summary *a = *(Summary *const *)x, *b = *(Summary *const *)y;
    size_t n = a->name.n < b->name.n ? a->name.n : b->name.n;
    int c = memcmp(a->name.p, b->name.p, n);
    return c ? c : (a->name.n > b->name.n) - (a->name.n < b->name.n);
}
static char *put(char *out, const char *p, size_t n) { memcpy(out, p, n); return out + n; }
static char *put_int(char *out, long long v) {
    char digits[24]; int n = 0;
    if (v < 0) { *out++ = '-'; v = -v; }
    do { digits[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *out++ = digits[--n];
    return out;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *text = malloc(size + 1); fread(text, 1, size, f); fclose(f); text[size] = '\n';
    long long lines = 0, malformed = 0, internal = 0, alerts = 0, timeouts = 0, replaced = 0, formatted_bytes = 0;
    static char samples[3][1024]; int sample_count = 0;
    static char formatted[1 << 16];
    const char *p = text, *limit = text + size;
    while (p < limit) {
        const char *end = memchr(p, '\n', limit + 1 - p);
        if (end == p) { p++; continue; }
        lines++;
        Slice field[5];
        const char *q = p;
        for (int k = 0; k < 5; k++) {
            const char *sep = k < 4 ? memmem(q, end - q, " | ", 3) : NULL;
            const char *stop = sep ? sep : end;
            field[k] = (Slice){q, (size_t)(stop - q)};
            q = sep ? sep + 3 : end;
        }
        p = end + 1;
        long long duration = 0;
        int valid = field[4].n > 0;
        for (size_t i = 0; i < field[4].n && valid; i++) {
            char c = field[4].p[i];
            if (c < '0' || c > '9') valid = 0; else duration = duration * 10 + (c - '0');
        }
        if (!valid) { malformed++; continue; }
        const char *tag = "[D]";
        if (eq(field[0], "ERROR", 5)) { tag = "[E]"; alerts++; }
        else if (eq(field[0], "WARN", 4)) { tag = "[W]"; alerts++; }
        else if (eq(field[0], "INFO", 4)) tag = "[I]";
        Slice service = field[1], address = field[2], message = field[3];
        if (address.n >= 12 && memcmp(address.p + address.n - 12, "@example.com", 12) == 0) internal++;
        int timed_out = memmem(message.p, message.n, "timeout", 7) != NULL;
        timeouts += timed_out;
        Summary *s = find_summary(service);
        s->lines++; s->total_ms += duration; s->timeouts += timed_out;
        for (size_t i = 0; i < message.n;) {
            size_t start = i;
            while (i < message.n && message.p[i] != ' ') i++;
            if (i > start) {
                s->words++;
                if (i - start > s->longest.n) s->longest = (Slice){message.p + start, i - start};
            }
            i++;
        }
        char *out = formatted;
        out = put(out, tag, 3); *out++ = ' ';
        if (service.n >= 4 && memcmp(service.p, "auth", 4) == 0) out = put(out, "security/", 9); else out = put(out, "app/", 4);
        out = put(out, service.p, service.n); *out++ = ' ';
        const char *at = memchr(address.p, '@', address.n);
        if (!at || at == address.p) out = put(out, "***", 3);
        else { *out++ = address.p[0]; out = put(out, "***", 3); out = put(out, at, address.p + address.n - at); }
        *out++ = ' '; out = put_int(out, duration); out = put(out, "ms: ", 4);
        const char *m = message.p, *m_end = message.p + message.n;
        for (;;) {
            const char *hit = memmem(m, m_end - m, "order", 5);
            if (!hit) break;
            out = put(out, m, hit - m); out = put(out, "ORDER", 5); m = hit + 5; replaced++;
        }
        out = put(out, m, m_end - m);
        size_t n = out - formatted;
        formatted_bytes += n;
        if (sample_count < 3) { memcpy(samples[sample_count], formatted, n); samples[sample_count][n] = 0; sample_count++; }
    }
    printf("lines %lld\nmalformed %lld\nalerts %lld\ninternal %lld\ntimeouts %lld\nreplaced %lld\nformatted bytes %lld\n",
           lines, malformed, alerts, internal, timeouts, replaced, formatted_bytes);
    for (int i = 0; i < sample_count; i++) puts(samples[i]);
    Summary **sorted = malloc(used * sizeof *sorted); int n = 0;
    for (int j = 0; j < SLOTS; j++) if (table[j].name.p) sorted[n++] = &table[j];
    qsort(sorted, n, sizeof *sorted, compare);
    for (int i = 0; i < n; i++) {
        Summary *s = sorted[i];
        printf("%.*s: %lld lines, avg %lld ms, %lld timeouts, %lld words, longest %.*s\n", (int)s->name.n, s->name.p,
               s->lines, s->total_ms / s->lines, s->timeouts, s->words, (int)s->longest.n, s->longest.p);
    }
    return 0;
}
