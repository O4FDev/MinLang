/* The vector UTF-8 validator and the vector Text search read sixteen or
 * sixty-four bytes per step. Every input here starts or ends at a page whose
 * neighbour cannot be read, so a load past either end of a Text faults, and
 * each answer is compared with the byte-at-a-time decoder and a naive search.
 * check-runtime-edges runs it at -O2 and under ASan and UBSan. */
#define MINYAR_RC_TESTING
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
static int reference(const unsigned char *b, long long n) {
    int ascii = 1;
    for (long long i = 0; i < n;) {
        if (b[i] < 0x80) { i++; continue; }
        long long w = utf8_sequence_width(b + i, n - i);
        if (!w) return -1;
        i += w; ascii = 0;
    }
    return ascii;
}
static uint64_t s = 0x9e3779b97f4a7c15u;
static uint64_t next(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
static size_t fill(unsigned char *out, size_t n) {
    static const char *pieces[] = {"a", "xyz", "\xc3\xa9", "\xe2\x82\xac", "\xf0\x9f\x98\x80", "\xed\x9f\xbf", "\xee\x80\x80", "\xf4\x8f\xbf\xbf", "\xe0\xa0\x80", "\xf0\x90\x80\x80", "\xc2\x80", " "};
    size_t at = 0;
    while (at < n) { const char *p = pieces[next() % 12]; size_t l = strlen(p); if (at + l > n) { out[at++] = 'q'; continue; } memcpy(out + at, p, l); at += l; }
    return n;
}
int main(void) {
    long page = sysconf(_SC_PAGESIZE);
    unsigned char *map = mmap(NULL, (size_t)page * 3, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    assert(map != MAP_FAILED);
    assert(!mprotect(map, (size_t)page, PROT_NONE) && !mprotect(map + 2 * page, (size_t)page, PROT_NONE));
    unsigned char *lo = map + page, *hi = map + 2 * page;
    unsigned long long checks = 0, invalid = 0, mismatches = 0;
    for (int round = 0; round < 1000000; round++) {
        size_t n = next() % 400;
        int atEnd = next() & 1;
        unsigned char *b = atEnd ? hi - n : lo;
        fill(b, n);
        int damage = next() % 4;
        for (int d = 0; d < damage && n; d++) {
            size_t at = next() % n; unsigned kind = next() % 5;
            if (kind == 0) b[at] = (unsigned char)next();
            else if (kind == 1) b[at] ^= (unsigned char)(1u << (next() % 8));
            else if (kind == 2) b[at] = (unsigned char)(0x80 | (next() & 0x7f));
            else if (kind == 3) { static const unsigned char v[] = {0xc0,0xc1,0xe0,0xed,0xf0,0xf4,0xf5,0xff,0x80,0xbf,0x9f,0xa0,0x8f,0x90}; b[at] = v[next() % sizeof v]; }
            else if (at + 1 < n) b[at] = b[at + 1];
        }
        int got = utf8_scan(b, (long long)n), want = reference(b, (long long)n);
        if (got != want) { if (mismatches++ < 5) { printf("MISMATCH n=%zu got=%d want=%d:", n, got, want); for (size_t i = 0; i < n; i++) printf(" %02x", b[i]); printf("\n"); } }
        checks++; if (want < 0) invalid++;
    }
    printf("utf8: %llu checks, %llu invalid inputs, %llu mismatches\n", checks, invalid, mismatches);
    unsigned long long searches = 0, wrong = 0;
    for (int round = 0; round < 100000; round++) {
        size_t n = next() % 200; size_t size = 1 + next() % 20;
        int atEnd = next() & 1;
        unsigned char *h = atEnd ? hi - n : lo;
        unsigned alphabet = 2 + next() % 3;
        for (size_t i = 0; i < n; i++) h[i] = (unsigned char)('a' + next() % alphabet);
        unsigned char wantedStore[64]; unsigned char *w = wantedStore;
        if (n >= size && (next() & 1)) memcpy(w, h + next() % (n - size + 1), size); else for (size_t i = 0; i < size; i++) w[i] = (unsigned char)('a' + next() % alphabet);
        MinyarText text = {0}, needle = {0};
        text.bytes = h; text.byte_length = (long long)n; needle.bytes = w; needle.byte_length = (long long)size;
        long long small[TEXT_SEARCH_SMALL];
        long long *table = text_search_table(&needle, (long long)n, small);
        for (long long start = 0; start <= (long long)n; start += 1 + (long long)(next() % 3)) {
            long long expected = -1;
            for (long long i = start; i + (long long)size <= (long long)n; i++) if (!memcmp(h + i, w, size)) { expected = i; break; }
            if (text_search_next(&text, &needle, start, table) != expected) wrong++;
            searches++;
        }
        text_search_free(table, small);
    }
    printf("search: %llu searches, %llu wrong\n", searches, wrong);
    return mismatches || wrong;
}
