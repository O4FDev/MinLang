// Serial C++ peer for main.min: posting lists, N queries, document-at-a-time top 10.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

constexpr int64_t TERMS = 4096, K = 10, MODULUS = 1000000007;

static int64_t mix(int64_t value) {
    for (int64_t round = 0; round < 3; ++round) {
        value ^= value >> 31;
        value = int64_t(uint64_t(value) * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = int64_t(uint64_t(value) + uint64_t(round));
    }
    return value & 0x7FFFFFFFFFFFFFFFLL;
}

struct Index {
    std::vector<int64_t> docs, tfs, starts, idf, norm;
    int64_t search(const std::array<int64_t, 4> &terms, bool conjunctive, std::array<int64_t, K> &best, std::array<int64_t, K> &scores) const {
        std::array<int64_t, 4> cursor{};
        int64_t n = 0;
        while (n < 4 && terms[size_t(n)] >= 0) { cursor[size_t(n)] = starts[size_t(terms[size_t(n)])]; ++n; }
        int64_t found = 0;
        for (;;) {
            int64_t doc = -1;
            for (int64_t j = 0; j < n; ++j)
                if (cursor[size_t(j)] < starts[size_t(terms[size_t(j)] + 1)]) {
                    int64_t d = docs[size_t(cursor[size_t(j)])];
                    if (doc < 0 || d < doc) doc = d;
                }
            if (doc < 0) break;
            int64_t score = 0, matched = 0;
            for (int64_t j = 0; j < n; ++j) {
                int64_t t = terms[size_t(j)];
                int64_t &c = cursor[size_t(j)];
                if (c < starts[size_t(t + 1)] && docs[size_t(c)] == doc) {
                    int64_t tf = tfs[size_t(c)];
                    score += idf[size_t(t)] * tf * 16 / (tf + norm[size_t(doc)]);
                    ++matched; ++c;
                }
            }
            if ((!conjunctive || matched == n) && (found < K || score > scores[K - 1])) {
                int64_t at = std::min(found, K - 1);
                while (at > 0 && scores[size_t(at - 1)] < score) { scores[size_t(at)] = scores[size_t(at - 1)]; best[size_t(at)] = best[size_t(at - 1)]; --at; }
                scores[size_t(at)] = score; best[size_t(at)] = doc;
                if (found < K) ++found;
            }
        }
        return found;
    }
};

int main(int, char **argv) {
    int64_t n = std::atoll(argv[1]), documents = n * 1000, queries = n;
    Index ix;
    ix.starts.resize(TERMS + 1);
    ix.idf.resize(TERMS);
    for (int64_t t = 0; t < TERMS; ++t) {
        ix.starts[size_t(t)] = int64_t(ix.docs.size());
        int64_t target = std::min(documents / 2, documents * 4 / (t + 8));
        int64_t step = std::max<int64_t>(1, 2 * documents / target);
        for (int64_t doc = mix(t) % step, k = 0; doc < documents; ++k) {
            int64_t r = mix(t * 16777216 + k);
            ix.docs.push_back(doc);
            ix.tfs.push_back(1 + (r >> 32) % 5);
            doc += 1 + r % step;
        }
        int64_t ratio = documents / std::max<int64_t>(int64_t(ix.docs.size()) - ix.starts[size_t(t)], 1), bits = 0;
        while (ratio > 1) { ratio /= 2; ++bits; }
        ix.idf[size_t(t)] = 1000 * (bits + 1);
    }
    ix.starts[TERMS] = int64_t(ix.docs.size());
    ix.norm.resize(size_t(documents));
    for (int64_t d = 0; d < documents; ++d) ix.norm[size_t(d)] = 3 + mix(d + 777) % 200 / 50;
    int64_t digest = 0;
    for (int64_t q = 0; q < queries; ++q) {
        std::array<int64_t, 4> terms;
        std::array<int64_t, K> best{}, scores{};
        int64_t count = 2 + mix(q * 7) % 3;
        for (int64_t j = 0; j < 4; ++j) terms[size_t(j)] = j < count ? mix(q * 7 + 1 + j) % (16 << (2 * j)) : -1;
        int64_t found = ix.search(terms, q % 3 == 0, best, scores);
        for (int64_t r = 0; r < found; ++r) digest = (digest * 31 + (r + 1) * (best[size_t(r)] * 1000003 + scores[size_t(r)])) % MODULUS;
        if (q < 4) std::printf("query %lld found %lld best %lld %lld\n", (long long)q, (long long)found, (long long)best[0], (long long)scores[0]);
    }
    std::printf("postings %lld\n", (long long)ix.docs.size());
    std::printf("digest %lld\n", (long long)digest);
}
