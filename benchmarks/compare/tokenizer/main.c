// C peer for main.min: lex into a token array, then count kinds, rank identifiers, checksum.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { IDENT, KEYWORD, NUMBER, STRING, OPERATOR, COMMENT };
typedef struct { uint32_t start, width, line, extra; uint8_t kind; } Token; // extra: decoded string length
typedef struct { const char *name; uint32_t length, count; uint64_t hash; } Entry;

static Entry *table; static size_t capacity = 1 << 12, used;

static uint64_t hash_bytes(const char *p, size_t n) {
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 1099511628211ULL; }
    return h;
}
static void grow(void) {
    size_t old = capacity; Entry *previous = table;
    capacity *= 2; table = calloc(capacity, sizeof(Entry));
    for (size_t i = 0; i < old; i++) if (previous[i].name) {
        size_t j = previous[i].hash & (capacity - 1);
        while (table[j].name) j = (j + 1) & (capacity - 1);
        table[j] = previous[i];
    }
    free(previous);
}
static void count_identifier(const char *p, uint32_t n) {
    uint64_t h = hash_bytes(p, n);
    size_t j = h & (capacity - 1);
    while (table[j].name) {
        if (table[j].hash == h && table[j].length == n && memcmp(table[j].name, p, n) == 0) { table[j].count++; return; }
        j = (j + 1) & (capacity - 1);
    }
    table[j] = (Entry){p, n, 1, h};
    if (++used * 2 > capacity) grow();
}
static int compare(const void *x, const void *y) {
    const Entry *a = x, *b = y;
    if (a->count != b->count) return a->count < b->count ? 1 : -1;
    uint32_t n = a->length < b->length ? a->length : b->length;
    int c = memcmp(a->name, b->name, n);
    if (c) return c;
    return (int)a->length - (int)b->length;
}
static int is_letter(unsigned char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static int is_digit(unsigned char c) { return c >= '0' && c <= '9'; }
static int is_keyword(const char *p, size_t n) {
    switch (n) {
    case 2: return (p[0] == 'i' && (p[1] == 'f' || p[1] == 'n'));
    case 3: return (memcmp(p, "let", 3) == 0 || memcmp(p, "for", 3) == 0);
    case 4: return memcmp(p, "else", 4) == 0;
    case 5: return memcmp(p, "while", 5) == 0;
    case 6: return memcmp(p, "return", 6) == 0;
    case 8: return memcmp(p, "function", 8) == 0;
    default: return 0;
    }
}
static int two_char(char a, char b) {
    return (b == '=' && (a == '=' || a == '!' || a == '<' || a == '>')) || (a == '&' && b == '&') ||
           (a == '|' && b == '|') || (a == '-' && b == '>');
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); size_t size = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(size + 1); if (fread(src, 1, size, f) != size) return 1; fclose(f); src[size] = 0;
    size_t cap = size / 4 + 16, n = 0;
    Token *tokens = malloc(cap * sizeof(Token));
    uint32_t line = 1; size_t i = 0;
    while (i < size) {
        unsigned char c = (unsigned char)src[i];
        if (n == cap) { cap *= 2; tokens = realloc(tokens, cap * sizeof(Token)); }
        if (c == '\n') { line++; i++; }
        else if (c == ' ' || c == '\t' || c == '\r') i++;
        else if (is_letter(c)) {
            size_t start = i++;
            while (i < size && (is_letter((unsigned char)src[i]) || is_digit((unsigned char)src[i]))) i++;
            tokens[n++] = (Token){(uint32_t)start, (uint32_t)(i - start), line, 0, is_keyword(src + start, i - start) ? KEYWORD : IDENT};
        } else if (is_digit(c)) {
            size_t start = i++;
            while (i < size && is_digit((unsigned char)src[i])) i++;
            tokens[n++] = (Token){(uint32_t)start, (uint32_t)(i - start), line, 0, NUMBER};
        } else if (c == '"') {
            size_t start = i++; uint32_t decoded = 0;
            while (i < size && src[i] != '"') {
                if (src[i] == '\\' && i + 1 < size) i += 2; else i++;
                decoded++;
            }
            i++;
            tokens[n++] = (Token){(uint32_t)start, (uint32_t)(i - start), line, decoded, STRING};
        } else if (c == '/' && i + 1 < size && src[i + 1] == '/') {
            size_t start = i;
            const char *end = memchr(src + i, '\n', size - i);
            i = end ? (size_t)(end - src) : size;
            tokens[n++] = (Token){(uint32_t)start, (uint32_t)(i - start), line, 0, COMMENT};
        } else {
            uint32_t width = i + 1 < size && two_char(src[i], src[i + 1]) ? 2 : 1;
            tokens[n++] = (Token){(uint32_t)i, width, line, 0, OPERATOR};
            i += width;
        }
    }
    table = calloc(capacity, sizeof(Entry));
    long long counts[6] = {0}, number_sum = 0, string_bytes = 0, checksum = 0;
    for (size_t k = 0; k < n; k++) {
        const Token *t = &tokens[k];
        counts[t->kind]++;
        if (t->kind == IDENT) count_identifier(src + t->start, t->width);
        else if (t->kind == NUMBER) {
            long long v = 0;
            for (uint32_t d = 0; d < t->width; d++) v = v * 10 + (src[t->start + d] - '0');
            number_sum = (number_sum + v) % 1000000007;
        } else if (t->kind == STRING) string_bytes += t->extra;
        checksum = (checksum * 31 + t->kind * 1000 + t->width + t->line) % 1000000007;
    }
    Entry *entries = malloc((used + 1) * sizeof(Entry)); size_t m = 0;
    for (size_t k = 0; k < capacity; k++) if (table[k].name) entries[m++] = table[k];
    qsort(entries, m, sizeof(Entry), compare);
    static const char *names[] = {"identifier", "keyword", "number", "string", "operator", "comment"};
    printf("tokens %zu\n", n);
    for (int k = 0; k < 6; k++) printf("%s %lld\n", names[k], counts[k]);
    printf("number sum %lld\nstring bytes %lld\ndistinct identifiers %zu\n", number_sum, string_bytes, m);
    for (size_t k = 0; k < m && k < 10; k++) printf("%.*s %u\n", (int)entries[k].length, entries[k].name, entries[k].count);
    printf("checksum %lld\n", checksum);
    return 0;
}
