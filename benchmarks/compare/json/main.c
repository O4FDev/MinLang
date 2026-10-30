// C peer for main.min: a general JSON DOM parser (arena-allocated, strings
// without escapes point into the input), the same query, and a compact
// serialiser with the same escaping as json.quote.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef enum { J_NULL, J_FALSE, J_TRUE, J_NUMBER, J_STRING, J_ARRAY, J_OBJECT } Kind;
typedef struct { const char *ptr; size_t len; } Str;
typedef struct Value Value;
typedef struct Member Member;
struct Value { Kind kind; uint32_t count; union { int64_t number; Str text; Value *items; Member *members; }; };
struct Member { Str key; Value value; };

// ----- arena (chunked bump allocator) and scratch stack -----
static char *arena; static size_t arena_used, arena_size;
static void *arena_alloc(size_t n) {
    n = (n + 15) & ~(size_t)15;
    if (arena_used + n > arena_size) {
        arena_size = n > (8u << 20) ? n : (8u << 20);
        arena = malloc(arena_size); arena_used = 0;
    }
    void *p = arena + arena_used; arena_used += n; return p;
}
static Member *stack; static size_t stack_used, stack_size;
static void stack_push(Member m) {
    if (stack_used == stack_size) { stack_size = stack_size ? stack_size * 2 : 1024; stack = realloc(stack, stack_size * sizeof(Member)); }
    stack[stack_used++] = m;
}

// ----- parser -----
static const char *at, *end;
static _Noreturn void invalid(const char *why) { printf("invalid input: %s\n", why); exit(1); }
static void skip_space(void) { while (at < end && (*at == ' ' || *at == '\n' || *at == '\r' || *at == '\t')) at++; }
static unsigned hex4(const char *p) {
    unsigned v = 0;
    for (int i = 0; i < 4; i++) {
        char c = p[i]; v <<= 4;
        if (c >= '0' && c <= '9') v |= c - '0'; else if (c >= 'a' && c <= 'f') v |= c - 'a' + 10;
        else if (c >= 'A' && c <= 'F') v |= c - 'A' + 10; else invalid("bad unicode escape");
    }
    return v;
}
static char *put_utf8(char *o, unsigned c) {
    if (c < 0x80) *o++ = (char)c;
    else if (c < 0x800) { *o++ = (char)(0xC0 | c >> 6); *o++ = (char)(0x80 | (c & 63)); }
    else if (c < 0x10000) { *o++ = (char)(0xE0 | c >> 12); *o++ = (char)(0x80 | (c >> 6 & 63)); *o++ = (char)(0x80 | (c & 63)); }
    else { *o++ = (char)(0xF0 | c >> 18); *o++ = (char)(0x80 | (c >> 12 & 63)); *o++ = (char)(0x80 | (c >> 6 & 63)); *o++ = (char)(0x80 | (c & 63)); }
    return o;
}
static Str parse_string(void) {
    const char *start = ++at, *p = at;
    while (p < end && *p != '"' && *p != '\\') { if ((unsigned char)*p < 32) invalid("control in string"); p++; }
    if (p < end && *p == '"') { at = p + 1; return (Str){start, (size_t)(p - start)}; }
    // Escaped: decode into the arena; the decoded form is never longer than the source.
    const char *close = p;
    while (close < end && *close != '"') close += *close == '\\' ? 2 : 1;
    char *out = arena_alloc((size_t)(close - start) + 1), *o = out;
    memcpy(o, start, (size_t)(p - start)); o += p - start;
    while (p < end && *p != '"') {
        unsigned char c = (unsigned char)*p;
        if (c < 32) invalid("control in string");
        if (c != '\\') { *o++ = (char)c; p++; continue; }
        if (p + 1 >= end) invalid("unfinished escape");
        switch (p[1]) {
        case '"': *o++ = '"'; break; case '\\': *o++ = '\\'; break; case '/': *o++ = '/'; break;
        case 'b': *o++ = 8; break; case 'f': *o++ = 12; break; case 'n': *o++ = '\n'; break;
        case 'r': *o++ = '\r'; break; case 't': *o++ = '\t'; break;
        case 'u': {
            if (end - p < 6) invalid("short unicode escape");
            unsigned u = hex4(p + 2); p += 4;
            if (u >= 0xD800 && u < 0xDC00 && end - p >= 8 && p[2] == '\\' && p[3] == 'u') {
                unsigned low = hex4(p + 4);
                if (low >= 0xDC00 && low < 0xE000) { u = 0x10000 + ((u - 0xD800) << 10) + (low - 0xDC00); p += 6; }
            }
            o = put_utf8(o, u); break;
        }
        default: invalid("unknown escape");
        }
        p += 2;
    }
    if (p >= end) invalid("unterminated string");
    at = p + 1;
    return (Str){out, (size_t)(o - out)};
}
static Value parse_value(int depth);
static Value parse_value(int depth) {
    if (depth > 512) invalid("nesting too deep");
    skip_space();
    if (at >= end) invalid("unexpected end");
    Value v; memset(&v, 0, sizeof v);
    char c = *at;
    if (c == '{') {
        at++; size_t base = stack_used; skip_space();
        if (at < end && *at == '}') at++;
        else for (;;) {
            skip_space();
            if (at >= end || *at != '"') invalid("expected member name");
            Member m; m.key = parse_string(); skip_space();
            if (at >= end || *at != ':') invalid("expected ':'");
            at++; m.value = parse_value(depth + 1); stack_push(m); skip_space();
            if (at < end && *at == ',') { at++; continue; }
            if (at < end && *at == '}') { at++; break; }
            invalid("expected ',' or '}'");
        }
        v.kind = J_OBJECT; v.count = (uint32_t)(stack_used - base);
        v.members = arena_alloc(v.count * sizeof(Member)); memcpy(v.members, stack + base, v.count * sizeof(Member));
        stack_used = base;
    } else if (c == '[') {
        at++; size_t base = stack_used; skip_space();
        if (at < end && *at == ']') at++;
        else for (;;) {
            Member m; m.value = parse_value(depth + 1); stack_push(m); skip_space();
            if (at < end && *at == ',') { at++; continue; }
            if (at < end && *at == ']') { at++; break; }
            invalid("expected ',' or ']'");
        }
        v.kind = J_ARRAY; v.count = (uint32_t)(stack_used - base);
        v.items = arena_alloc(v.count * sizeof(Value));
        for (uint32_t i = 0; i < v.count; i++) v.items[i] = stack[base + i].value;
        stack_used = base;
    } else if (c == '"') { v.kind = J_STRING; v.text = parse_string(); }
    else if (c == 't' && end - at >= 4 && !memcmp(at, "true", 4)) { v.kind = J_TRUE; at += 4; }
    else if (c == 'f' && end - at >= 5 && !memcmp(at, "false", 5)) { v.kind = J_FALSE; at += 5; }
    else if (c == 'n' && end - at >= 4 && !memcmp(at, "null", 4)) { v.kind = J_NULL; at += 4; }
    else if (c == '-' || (c >= '0' && c <= '9')) {
        int negative = c == '-'; if (negative) at++;
        const char *digits = at; uint64_t n = 0;
        while (at < end && *at >= '0' && *at <= '9') { n = n * 10 + (uint64_t)(*at - '0'); at++; }
        if (at == digits || (at - digits > 1 && *digits == '0') || at - digits > 18) invalid("bad number");
        if (at < end && (*at == '.' || *at == 'e' || *at == 'E')) invalid("expected an integer");
        v.kind = J_NUMBER; v.number = negative ? -(int64_t)n : (int64_t)n;
    } else invalid("unexpected character");
    return v;
}

// ----- typed access -----
static const Value *get(const Value *v, const char *name) {
    if (v->kind != J_OBJECT) invalid("expected a JSON object");
    size_t n = strlen(name);
    for (uint32_t i = 0; i < v->count; i++)
        if (v->members[i].key.len == n && !memcmp(v->members[i].key.ptr, name, n)) return &v->members[i].value;
    invalid("missing member");
}
static int64_t integer(const Value *v) { if (v->kind != J_NUMBER) invalid("expected a JSON integer"); return v->number; }
static Str text(const Value *v) { if (v->kind != J_STRING) invalid("expected a JSON string"); return v->text; }
static const Value *array(const Value *v) { if (v->kind != J_ARRAY) invalid("expected a JSON array"); return v; }

// ----- string-keyed table -----
typedef struct { Str key; int64_t users, active, spent, oldest, top_spent; Str top; uint64_t hash; int used; } Entry;
typedef struct { Entry *slots; size_t mask, used; } Table;
static uint64_t hash_str(Str s) { uint64_t h = 1469598103934665603ULL; for (size_t i = 0; i < s.len; i++) { h ^= (unsigned char)s.ptr[i]; h *= 1099511628211ULL; } return h; }
static Entry *table_get(Table *t, Str key, int *created) {
    if ((t->used + 1) * 2 > t->mask + 1) {
        Table old = *t; t->mask = old.mask ? old.mask * 2 + 1 : 63; t->slots = calloc(t->mask + 1, sizeof(Entry)); t->used = 0;
        for (size_t i = 0; old.slots && i <= old.mask; i++) if (old.slots[i].used) {
            size_t j = old.slots[i].hash & t->mask; while (t->slots[j].used) j = (j + 1) & t->mask;
            t->slots[j] = old.slots[i]; t->used++;
        }
        free(old.slots);
    }
    uint64_t h = hash_str(key); size_t j = h & t->mask;
    while (t->slots[j].used) {
        if (t->slots[j].hash == h && t->slots[j].key.len == key.len && !memcmp(t->slots[j].key.ptr, key.ptr, key.len)) { *created = 0; return &t->slots[j]; }
        j = (j + 1) & t->mask;
    }
    Entry *e = &t->slots[j]; memset(e, 0, sizeof *e); e->used = 1; e->key = key; e->hash = h; t->used++; *created = 1;
    return e;
}
static int compare_str(Str a, Str b) {
    int c = memcmp(a.ptr, b.ptr, a.len < b.len ? a.len : b.len);
    return c ? c : (a.len > b.len) - (a.len < b.len);
}
static int compare_entries(const void *x, const void *y) { return compare_str((*(Entry *const *)x)->key, (*(Entry *const *)y)->key); }
static Entry **sorted(Table *t) {
    Entry **list = malloc((t->used + 1) * sizeof(Entry *)); size_t n = 0;
    for (size_t i = 0; i <= t->mask; i++) if (t->slots[i].used) list[n++] = &t->slots[i];
    qsort(list, n, sizeof(Entry *), compare_entries);
    return list;
}

// ----- output buffer -----
static char *out; static size_t out_len, out_cap;
static void reserve(size_t n) { if (out_len + n > out_cap) { while (out_len + n > out_cap) out_cap = out_cap ? out_cap * 2 : 1 << 16; out = realloc(out, out_cap); } }
static void put(const char *s, size_t n) { reserve(n); memcpy(out + out_len, s, n); out_len += n; }
static void puts_lit(const char *s) { put(s, strlen(s)); }
static void put_int(int64_t v) {
    char buf[24], *p = buf + sizeof buf; uint64_t u = v < 0 ? -(uint64_t)v : (uint64_t)v;
    do { *--p = (char)('0' + u % 10); u /= 10; } while (u);
    if (v < 0) *--p = '-';
    put(p, (size_t)(buf + sizeof buf - p));
}
static void put_quoted(Str s) {
    static const char hex[] = "0123456789abcdef";
    reserve(s.len * 6 + 2);
    char *o = out + out_len; *o++ = '"';
    for (size_t i = 0; i < s.len; i++) {
        unsigned char c = (unsigned char)s.ptr[i];
        if (c >= 32 && c != '"' && c != '\\') { *o++ = (char)c; continue; }
        *o++ = '\\';
        switch (c) {
        case '"': *o++ = '"'; break; case '\\': *o++ = '\\'; break; case '\n': *o++ = 'n'; break;
        case '\t': *o++ = 't'; break; case '\r': *o++ = 'r'; break; case 8: *o++ = 'b'; break; case 12: *o++ = 'f'; break;
        default: *o++ = 'u'; *o++ = '0'; *o++ = '0'; *o++ = hex[c >> 4]; *o++ = hex[c & 15];
        }
    }
    *o++ = '"'; out_len = (size_t)(o - out);
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); if (!f) return 1;
    fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *source = malloc((size_t)size + 1); if (fread(source, 1, (size_t)size, f) != (size_t)size) return 1; fclose(f);
    at = source; end = source + size;
    Value root = parse_value(0); skip_space();
    if (at != end) invalid("unexpected trailing input");
    array(&root);

    Table cities = {0}, tags = {0};
    int64_t active = 0, checksum = 0, geo_sum = 0, spenders = 0; int created;
    puts_lit("{\"cities\":[");
    size_t cities_at = out_len;
    // Spenders are serialised into a second buffer region later; collect indices first.
    uint32_t *spender_index = malloc((root.count + 1) * sizeof(uint32_t));
    int64_t *spent_of = malloc((root.count + 1) * sizeof(int64_t));
    for (uint32_t i = 0; i < root.count; i++) {
        const Value *user = &root.items[i], *address = get(user, "address"), *geo = array(get(address, "geo"));
        const Value *orders = array(get(user, "orders")), *user_tags = array(get(user, "tags"));
        for (uint32_t t = 0; t < user_tags->count; t++) text(&user_tags->items[t]);
        int64_t spent = 0;
        for (uint32_t o = 0; o < orders->count; o++) spent += integer(get(&orders->items[o], "qty")) * integer(get(&orders->items[o], "price"));
        Str name = text(get(user, "name")), city = text(get(address, "city")), zip_text = text(get(address, "zip"));
        const Value *flag = get(user, "active");
        if (flag->kind != J_TRUE && flag->kind != J_FALSE) invalid("expected a JSON boolean");
        int64_t age = integer(get(user, "age")), score = integer(get(user, "score")), zip = 0;
        integer(get(user, "id"));
        if (geo->count < 2) invalid("short geo");
        for (size_t k = 0; k < zip_text.len; k++) zip = zip * 10 + (zip_text.ptr[k] - '0');
        Entry *stats = table_get(&cities, city, &created);
        if (created) stats->top_spent = -1;
        stats->users++; stats->spent += spent;
        if (age > stats->oldest) stats->oldest = age;
        if (spent > stats->top_spent) { stats->top_spent = spent; stats->top = name; }
        checksum = (checksum * 31 + (int64_t)name.len + age + score + 5000 + zip) % 1000000007;
        geo_sum += integer(&geo->items[0]) + integer(&geo->items[1]);
        spent_of[i] = spent;
        if (flag->kind != J_TRUE) continue;
        active++; stats->active++;
        for (uint32_t t = 0; t < user_tags->count; t++) table_get(&tags, user_tags->items[t].text, &created)->users++;
        if (spent > 600000) spender_index[spenders++] = i;
    }
    Entry **city_list = sorted(&cities);
    size_t *city_end = malloc((cities.used + 1) * sizeof(size_t));
    for (size_t c = 0; c < cities.used; c++) {
        const Entry *s = city_list[c];
        if (c) puts_lit(",");
        puts_lit("{\"city\":"); put_quoted(s->key);
        puts_lit(",\"users\":"); put_int(s->users); puts_lit(",\"active\":"); put_int(s->active);
        puts_lit(",\"spent\":"); put_int(s->spent); puts_lit(",\"oldest\":"); put_int(s->oldest);
        puts_lit(",\"top\":"); put_quoted(s->top); puts_lit(",\"topSpent\":"); put_int(s->top_spent); puts_lit("}");
        city_end[c] = out_len;
    }
    puts_lit("],\"tags\":{");
    Entry **tag_list = sorted(&tags);
    for (size_t t = 0; t < tags.used; t++) { if (t) puts_lit(","); put_quoted(tag_list[t]->key); puts_lit(":"); put_int(tag_list[t]->users); }
    puts_lit("},\"spenders\":[");
    for (int64_t k = 0; k < spenders; k++) {
        const Value *user = &root.items[spender_index[k]], *user_tags = get(user, "tags");
        if (k) puts_lit(",");
        puts_lit("{\"id\":"); put_int(integer(get(user, "id")));
        puts_lit(",\"name\":"); put_quoted(get(user, "name")->text);
        puts_lit(",\"city\":"); put_quoted(get(get(user, "address"), "city")->text);
        puts_lit(",\"spent\":"); put_int(spent_of[spender_index[k]]);
        puts_lit(",\"tags\":[");
        for (uint32_t t = 0; t < user_tags->count; t++) { if (t) puts_lit(","); put_quoted(user_tags->items[t].text); }
        puts_lit("]}");
    }
    puts_lit("]}");
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < out_len; i++) { hash ^= (unsigned char)out[i]; hash *= 1099511628211ULL; }
    printf("%u %lld\n%lld %lld\n%lld\n%zu %lld\n", root.count, (long long)active, (long long)checksum, (long long)geo_sum,
           (long long)spenders, out_len, (long long)hash);
    size_t from = cities_at;
    for (size_t c = 0; c < cities.used; c++) {
        fwrite(out + from, 1, city_end[c] - from, stdout); fputc('\n', stdout);
        from = city_end[c] + 1;
    }
    return 0;
}
