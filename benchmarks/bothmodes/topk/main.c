// Serial C peer for main.min: posting lists, N queries, document-at-a-time top 10.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { TERMS = 4096, K = 10 };
static const int64_t MODULUS = 1000000007;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = (int64_t)((uint64_t)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (int64_t)((uint64_t)value + (uint64_t)round);
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}
static int64_t min64(int64_t a, int64_t b) { return a < b ? a : b; }
static int64_t max64(int64_t a, int64_t b) { return a > b ? a : b; }

static int64_t *post_docs, *post_tfs, starts[TERMS + 1], idf[TERMS], *norm;

static int64_t search(const int64_t *terms, int conjunctive, int64_t *docs, int64_t *scores) {
    int64_t cursor[4], n = 0;
    while (n < 4 && terms[n] >= 0) { cursor[n] = starts[terms[n]]; ++n; }
    int64_t found = 0;
    for (;;) {
        int64_t doc = -1;
        for (int64_t j = 0; j < n; ++j)
            if (cursor[j] < starts[terms[j] + 1]) { int64_t d = post_docs[cursor[j]]; if (doc < 0 || d < doc) doc = d; }
        if (doc < 0) break;
        int64_t score = 0, matched = 0;
        for (int64_t j = 0; j < n; ++j) {
            int64_t t = terms[j];
            if (cursor[j] < starts[t + 1] && post_docs[cursor[j]] == doc) {
                int64_t tf = post_tfs[cursor[j]];
                score += idf[t] * tf * 16 / (tf + norm[doc]);
                ++matched; ++cursor[j];
            }
        }
        if ((!conjunctive || matched == n) && (found < K || score > scores[K - 1])) {
            int64_t at = min64(found, K - 1);
            while (at > 0 && scores[at - 1] < score) { scores[at] = scores[at - 1]; docs[at] = docs[at - 1]; --at; }
            scores[at] = score; docs[at] = doc;
            if (found < K) ++found;
        }
    }
    return found;
}

int main(int argc, char **argv) {
    int64_t n = atoll(argv[1]), documents = n * 1000, queries = n, length = 0, capacity = 1 << 20;
    post_docs = malloc(sizeof(int64_t) * (size_t)capacity);
    post_tfs = malloc(sizeof(int64_t) * (size_t)capacity);
    for (int64_t t = 0; t < TERMS; ++t) {
        starts[t] = length;
        int64_t target = min64(documents / 2, documents * 4 / (t + 8));
        int64_t step = max64(1, 2 * documents / target);
        for (int64_t doc = mix(t) % step, k = 0; doc < documents; ++k) {
            int64_t r = mix(t * 16777216 + k);
            if (length == capacity) {
                capacity *= 2;
                post_docs = realloc(post_docs, sizeof(int64_t) * (size_t)capacity);
                post_tfs = realloc(post_tfs, sizeof(int64_t) * (size_t)capacity);
            }
            post_docs[length] = doc;
            post_tfs[length++] = 1 + (r >> 32) % 5;
            doc += 1 + r % step;
        }
        int64_t ratio = documents / max64(length - starts[t], 1), bits = 0;
        while (ratio > 1) { ratio /= 2; ++bits; }
        idf[t] = 1000 * (bits + 1);
    }
    starts[TERMS] = length;
    norm = malloc(sizeof(int64_t) * (size_t)documents);
    for (int64_t d = 0; d < documents; ++d) norm[d] = 3 + mix(d + 777) % 200 / 50;
    int64_t digest = 0;
    for (int64_t q = 0; q < queries; ++q) {
        int64_t terms[4], count = 2 + mix(q * 7) % 3, docs[K] = {0}, scores[K] = {0};
        for (int64_t j = 0; j < 4; ++j) terms[j] = j < count ? mix(q * 7 + 1 + j) % (16 << (2 * j)) : -1;
        int64_t found = search(terms, q % 3 == 0, docs, scores);
        for (int64_t r = 0; r < found; ++r) digest = (digest * 31 + (r + 1) * (docs[r] * 1000003 + scores[r])) % MODULUS;
        if (q < 4) printf("query %lld found %lld best %lld %lld\n", (long long)q, (long long)found, (long long)docs[0], (long long)scores[0]);
    }
    printf("postings %lld\n", (long long)length);
    printf("digest %lld\n", (long long)digest);
    return 0;
}
