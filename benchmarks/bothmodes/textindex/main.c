// Serial C peer for main.min: inverted index of the input's lines (documents),
// open-addressing dictionary on the word bytes, posting lists with term
// frequencies, terms ranked by spelling.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *word; int64_t length, count, capacity; int64_t *docs, *tfs; } Term;
static Term *terms;
static int64_t nterms, term_capacity, *table, table_size;
static const int64_t MODULUS = 1000000007;

static uint64_t hash_word(const char *w, int64_t n) {
    uint64_t h = 0xcbf29ce484222325ULL;
    for (int64_t i = 0; i < n; ++i) h = (h ^ (unsigned char)w[i]) * 1099511628211ULL;
    return h;
}
static void grow_table(void) {
    int64_t size = table_size ? table_size * 2 : 1 << 16;
    int64_t *next = malloc(sizeof(int64_t) * (size_t)size);
    for (int64_t i = 0; i < size; ++i) next[i] = -1;
    for (int64_t id = 0; id < nterms; ++id) {
        uint64_t s = hash_word(terms[id].word, terms[id].length) & (uint64_t)(size - 1);
        while (next[s] >= 0) s = (s + 1) & (uint64_t)(size - 1);
        next[s] = id;
    }
    free(table); table = next; table_size = size;
}
static int64_t lookup(const char *w, int64_t n) {
    if (2 * (nterms + 1) > table_size) grow_table();
    uint64_t s = hash_word(w, n) & (uint64_t)(table_size - 1);
    while (table[s] >= 0) {
        Term *t = &terms[table[s]];
        if (t->length == n && memcmp(t->word, w, (size_t)n) == 0) return table[s];
        s = (s + 1) & (uint64_t)(table_size - 1);
    }
    if (nterms == term_capacity) { term_capacity = term_capacity ? term_capacity * 2 : 1024; terms = realloc(terms, sizeof(Term) * (size_t)term_capacity); }
    terms[nterms] = (Term){w, n, 0, 0, NULL, NULL};
    table[s] = nterms;
    return nterms++;
}
static int by_word(const void *a, const void *b) {
    const Term *x = &terms[*(const int64_t *)a], *y = &terms[*(const int64_t *)b];
    int64_t n = x->length < y->length ? x->length : y->length;
    int c = memcmp(x->word, y->word, (size_t)n);
    if (c) return c;
    return (x->length > y->length) - (x->length < y->length);
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *corpus = malloc((size_t)size + 1);
    if (fread(corpus, 1, (size_t)size, f) != (size_t)size) return 1;
    fclose(f);
    int64_t documents = 0, tokens = 0;
    for (long i = 0; i < size;) {
        long end = i;
        while (end < size && corpus[end] != '\n') ++end;
        if (end == size) break;
        for (long p = i; p < end;) {
            while (p < end && corpus[p] == ' ') ++p;
            if (p == end) break;
            long start = p;
            while (p < end && corpus[p] != ' ') ++p;
            int64_t id = lookup(corpus + start, p - start);
            Term *t = &terms[id];
            if (t->count > 0 && t->docs[t->count - 1] == documents) t->tfs[t->count - 1]++;
            else {
                if (t->count == t->capacity) {
                    t->capacity = t->capacity ? t->capacity * 2 : 4;
                    t->docs = realloc(t->docs, sizeof(int64_t) * (size_t)t->capacity);
                    t->tfs = realloc(t->tfs, sizeof(int64_t) * (size_t)t->capacity);
                }
                t->docs[t->count] = documents; t->tfs[t->count++] = 1;
            }
            ++tokens;
        }
        ++documents;
        i = end + 1;
    }
    int64_t *order = malloc(sizeof(int64_t) * (size_t)nterms), total = 0;
    for (int64_t id = 0; id < nterms; ++id) { order[id] = id; total += terms[id].count; }
    qsort(order, (size_t)nterms, sizeof(int64_t), by_word);
    int64_t digest = 0, best = 0;
    for (int64_t rank = 0; rank < nterms; ++rank) {
        Term *t = &terms[order[rank]];
        int64_t doc_sum = 0, tf_sum = 0;
        for (int64_t k = 0; k < t->count; ++k) { doc_sum += t->docs[k]; tf_sum += t->tfs[k] * (k % 7 + 1); }
        digest = (digest * 31 + t->count * 1000003 + doc_sum % 1000003 + tf_sum) % MODULUS;
        if (t->count > terms[order[best]].count) best = rank;
    }
    Term *w = &terms[order[best]];
    printf("documents %lld tokens %lld\n", (long long)documents, (long long)tokens);
    printf("terms %lld postings %lld\n", (long long)nterms, (long long)total);
    printf("widest %.*s %lld\n", (int)w->length, w->word, (long long)w->count);
    printf("digest %lld\n", (long long)digest);
    return 0;
}
