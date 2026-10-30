// C peer for main.min: parse into flat hash tables keyed by section and key, then query.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *p; size_t n; } Str;
enum { NONE, INTEGER, BOOLEAN, TEXT, LIST };
typedef struct { uint8_t type; int64_t number; Str text; size_t first, count; } Value;
typedef struct { Str name; uint64_t hash; uint32_t id; uint8_t used; } Section;
typedef struct { Str key; uint64_t hash; uint32_t section; uint8_t used; Value value; } Entry;

static Section *sections; static size_t section_capacity = 1024, section_count;
static Entry *entries; static size_t entry_capacity = 4096, entry_count;
static int64_t *items; static size_t item_count, item_capacity = 4096;

static uint64_t hash_bytes(const char *p, size_t n, uint64_t h) {
    for (size_t i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 1099511628211ULL; }
    return h;
}
static int space(char c) { return c == ' ' || (c >= '\t' && c <= '\r'); }
static Str trim(Str s) {
    while (s.n && space(s.p[0])) { s.p++; s.n--; }
    while (s.n && space(s.p[s.n - 1])) s.n--;
    return s;
}
static int equals(Str a, const char *b, size_t n) { return a.n == n && memcmp(a.p, b, n) == 0; }

static long section_find(const char *p, size_t n, uint64_t h) {
    size_t j = h & (section_capacity - 1);
    while (sections[j].used) {
        if (sections[j].hash == h && sections[j].name.n == n && memcmp(sections[j].name.p, p, n) == 0) return (long)sections[j].id;
        j = (j + 1) & (section_capacity - 1);
    }
    return -1;
}
static uint32_t section_add(Str name) {
    uint64_t h = hash_bytes(name.p, name.n, 1469598103934665603ULL);
    long found = section_find(name.p, name.n, h);
    if (found >= 0) return (uint32_t)found;
    if ((section_count + 1) * 2 > section_capacity) {
        size_t old = section_capacity; Section *previous = sections;
        section_capacity *= 2; sections = calloc(section_capacity, sizeof(Section));
        for (size_t i = 0; i < old; i++) if (previous[i].used) {
            size_t j = previous[i].hash & (section_capacity - 1);
            while (sections[j].used) j = (j + 1) & (section_capacity - 1);
            sections[j] = previous[i];
        }
        free(previous);
    }
    size_t j = h & (section_capacity - 1);
    while (sections[j].used) j = (j + 1) & (section_capacity - 1);
    sections[j] = (Section){name, h, (uint32_t)section_count, 1};
    return (uint32_t)section_count++;
}
static uint64_t entry_hash(uint32_t section, const char *p, size_t n) {
    return hash_bytes(p, n, 1469598103934665603ULL ^ ((uint64_t)section * 0x9E3779B97F4A7C15ULL));
}
static Entry *entry_find(uint32_t section, const char *p, size_t n) {
    uint64_t h = entry_hash(section, p, n);
    size_t j = h & (entry_capacity - 1);
    while (entries[j].used) {
        if (entries[j].hash == h && entries[j].section == section && entries[j].key.n == n && memcmp(entries[j].key.p, p, n) == 0) return &entries[j];
        j = (j + 1) & (entry_capacity - 1);
    }
    return NULL;
}
static void entry_set(uint32_t section, Str key, Value value) {
    Entry *e = entry_find(section, key.p, key.n);
    if (e) { e->value = value; return; }
    if ((entry_count + 1) * 2 > entry_capacity) {
        size_t old = entry_capacity; Entry *previous = entries;
        entry_capacity *= 2; entries = calloc(entry_capacity, sizeof(Entry));
        for (size_t i = 0; i < old; i++) if (previous[i].used) {
            size_t j = previous[i].hash & (entry_capacity - 1);
            while (entries[j].used) j = (j + 1) & (entry_capacity - 1);
            entries[j] = previous[i];
        }
        free(previous);
    }
    uint64_t h = entry_hash(section, key.p, key.n);
    size_t j = h & (entry_capacity - 1);
    while (entries[j].used) j = (j + 1) & (entry_capacity - 1);
    entries[j] = (Entry){key, h, section, 1, value};
    entry_count++;
}

static char message[256];
static int parse_integer(Str s, int64_t *out) {
    size_t i = 0; int negative = 0;
    if (s.n && (s.p[0] == '-' || s.p[0] == '+')) { negative = s.p[0] == '-'; i = 1; }
    if (i == s.n) goto bad;
    int64_t v = 0;
    for (; i < s.n; i++) {
        if (s.p[i] < '0' || s.p[i] > '9') goto bad;
        if (__builtin_mul_overflow(v, 10, &v) || __builtin_add_overflow(v, s.p[i] - '0', &v)) goto bad;
    }
    *out = negative ? -v : v;
    return 1;
bad:
    snprintf(message, sizeof message, "invalid integer '%.*s'", (int)s.n, s.p);
    return 0;
}
static int parse_value(Str raw, Value *out) {
    Str v = trim(raw);
    if (v.n && v.p[0] == '"') {
        const char *close = memchr(v.p + 1, '"', v.n - 1);
        if (!close) { strcpy(message, "unterminated string"); return 0; }
        Str rest = trim((Str){close + 1, (size_t)(v.p + v.n - close - 1)});
        if (rest.n && rest.p[0] != '#') { strcpy(message, "unexpected text after string"); return 0; }
        *out = (Value){TEXT, 0, {v.p + 1, (size_t)(close - v.p - 1)}, 0, 0};
        return 1;
    }
    const char *comment = memchr(v.p, '#', v.n);
    if (comment) v = trim((Str){v.p, (size_t)(comment - v.p)});
    if (v.n && v.p[0] == '[') {
        if (v.p[v.n - 1] != ']' || v.n < 2) { strcpy(message, "unterminated list"); return 0; }
        Str inner = trim((Str){v.p + 1, v.n - 2});
        size_t first = item_count;
        if (inner.n) {
            const char *p = inner.p, *end = inner.p + inner.n;
            for (;;) {
                const char *comma = memchr(p, ',', (size_t)(end - p));
                const char *stop = comma ? comma : end;
                int64_t number;
                if (!parse_integer(trim((Str){p, (size_t)(stop - p)}), &number)) { item_count = first; return 0; }
                if (item_count == item_capacity) { item_capacity *= 2; items = realloc(items, item_capacity * sizeof *items); }
                items[item_count++] = number;
                if (!comma) break;
                p = comma + 1;
            }
        }
        *out = (Value){LIST, 0, {0, 0}, first, item_count - first};
        return 1;
    }
    if (equals(v, "true", 4)) { *out = (Value){BOOLEAN, 1}; return 1; }
    if (equals(v, "false", 5)) { *out = (Value){BOOLEAN, 0}; return 1; }
    if (v.n && (v.p[0] == '-' || (v.p[0] >= '0' && v.p[0] <= '9'))) {
        int64_t number;
        if (!parse_integer(v, &number)) return 0;
        *out = (Value){INTEGER, number};
        return 1;
    }
    snprintf(message, sizeof message, "unknown value '%.*s'", (int)v.n, v.p);
    return 0;
}

static const Value *lookup(long section, const char *key, uint8_t type) {
    Entry *e = entry_find((uint32_t)section, key, strlen(key));
    return e && e->value.type == type ? &e->value : NULL;
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); size_t size = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(size + 1); if (fread(src, 1, size, f) != size) return 1; fclose(f); src[size] = 0;
    sections = calloc(section_capacity, sizeof(Section));
    entries = calloc(entry_capacity, sizeof(Entry));
    items = malloc(item_capacity * sizeof *items);
    char errors[8][256]; long long error_count = 0;
    long current = -1; long long line_number = 0;
    const char *p = src, *end = src + size;
    while (p <= end) {
        const char *nl = memchr(p, '\n', (size_t)(end - p));
        if (!nl) nl = end;
        line_number++;
        Str line = trim((Str){p, (size_t)(nl - p)});
        p = nl + 1;
        if (!line.n || line.p[0] == '#') continue;
        const char *problem = NULL;
        if (line.p[0] == '[') {
            if (line.p[line.n - 1] != ']' || line.n < 2) problem = "unterminated section header";
            else { current = section_add(trim((Str){line.p + 1, line.n - 2})); continue; }
        } else {
            const char *eq = memchr(line.p, '=', line.n);
            if (!eq) problem = "expected '=' after a key";
            else {
                Str key = trim((Str){line.p, (size_t)(eq - line.p)});
                Value value;
                if (!key.n) problem = "missing key";
                else if (current < 0) problem = "entry outside a section";
                else if (!parse_value((Str){eq + 1, (size_t)(line.p + line.n - eq - 1)}, &value)) problem = message;
                else { entry_set((uint32_t)current, key, value); continue; }
            }
        }
        if (error_count < 8) snprintf(errors[error_count], 256, "line %lld: %s", line_number, problem);
        error_count++;
    }
    printf("sections %zu\nentries %zu\nerrors %lld\n", section_count, entry_count, error_count);
    for (int i = 0; i < error_count && i < 8; i++) puts(errors[i]);
    long long queries = (long long)section_count * 3, space_ = (long long)section_count + (long long)section_count / 10 + 1;
    long long missing_sections = 0, missing_keys = 0, port_sum = 0, enabled = 0, name_bytes = 0, weight_sum = 0, weight_count = 0, timeout_sum = 0;
    char name[64];
    for (long long q = 0; q < queries; q++) {
        int n = snprintf(name, sizeof name, "service.%lld", (q * 7919) % space_);
        long s = section_find(name, (size_t)n, hash_bytes(name, (size_t)n, 1469598103934665603ULL));
        if (s < 0) { missing_sections++; continue; }
        const Value *v;
        if ((v = lookup(s, "port", INTEGER))) port_sum += v->number; else missing_keys++;
        if ((v = lookup(s, "enabled", BOOLEAN))) enabled += v->number; else missing_keys++;
        if ((v = lookup(s, "name", TEXT))) name_bytes += (long long)v->text.n; else missing_keys++;
        if ((v = lookup(s, "weights", LIST))) {
            weight_count += (long long)v->count;
            for (size_t k = 0; k < v->count; k++) weight_sum += items[v->first + k];
        } else missing_keys++;
        timeout_sum += (v = lookup(s, "timeout", INTEGER)) ? v->number : 30;
    }
    printf("queries %lld\nmissing sections %lld\nmissing keys %lld\nport sum %lld\nenabled %lld\nname bytes %lld\nweights %lld %lld\ntimeout sum %lld\n",
           queries, missing_sections, missing_keys, port_sum, enabled, name_bytes, weight_count, weight_sum, timeout_sum);
    return 0;
}
