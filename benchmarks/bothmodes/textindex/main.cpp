// Serial C++ peer for main.min: inverted index of the input's lines (documents),
// open-addressing dictionary on the word bytes, posting lists with term
// frequencies, terms ranked by spelling.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <vector>

constexpr int64_t MODULUS = 1000000007;
struct Term { std::string_view word; std::vector<int64_t> docs, tfs; };

static uint64_t hash_word(std::string_view w) {
    uint64_t h = 0xcbf29ce484222325ULL;
    for (unsigned char c : w) h = (h ^ c) * 1099511628211ULL;
    return h;
}

struct Dictionary {
    std::vector<Term> terms;
    std::vector<int32_t> table = std::vector<int32_t>(1 << 16, -1);
    void grow() {
        std::vector<int32_t> next(table.size() * 2, -1);
        size_t mask = next.size() - 1;
        for (size_t id = 0; id < terms.size(); ++id) {
            size_t s = hash_word(terms[id].word) & mask;
            while (next[s] >= 0) s = (s + 1) & mask;
            next[s] = int32_t(id);
        }
        table.swap(next);
    }
    Term &lookup(std::string_view w) {
        if (2 * (terms.size() + 1) > table.size()) grow();
        size_t mask = table.size() - 1, s = hash_word(w) & mask;
        while (table[s] >= 0) {
            Term &t = terms[size_t(table[s])];
            if (t.word == w) return t;
            s = (s + 1) & mask;
        }
        table[s] = int32_t(terms.size());
        terms.push_back(Term{w, {}, {}});
        return terms.back();
    }
};

int main(int, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string corpus((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::string_view text(corpus);
    Dictionary dict;
    int64_t documents = 0, tokens = 0;
    size_t i = 0;
    while (true) {
        size_t end = text.find('\n', i);
        if (end == std::string_view::npos) break;
        size_t p = i;
        while (p < end) {
            while (p < end && text[p] == ' ') ++p;
            if (p == end) break;
            size_t start = p;
            while (p < end && text[p] != ' ') ++p;
            Term &t = dict.lookup(text.substr(start, p - start));
            if (!t.docs.empty() && t.docs.back() == documents) t.tfs.back()++;
            else { t.docs.push_back(documents); t.tfs.push_back(1); }
            ++tokens;
        }
        ++documents;
        i = end + 1;
    }
    std::vector<int64_t> order(dict.terms.size());
    int64_t total = 0;
    for (size_t id = 0; id < order.size(); ++id) { order[id] = int64_t(id); total += int64_t(dict.terms[id].docs.size()); }
    std::sort(order.begin(), order.end(), [&](int64_t a, int64_t b) { return dict.terms[size_t(a)].word < dict.terms[size_t(b)].word; });
    int64_t digest = 0;
    size_t best = 0;
    for (size_t rank = 0; rank < order.size(); ++rank) {
        const Term &t = dict.terms[size_t(order[rank])];
        int64_t doc_sum = 0, tf_sum = 0;
        for (size_t k = 0; k < t.docs.size(); ++k) { doc_sum += t.docs[k]; tf_sum += t.tfs[k] * int64_t(k % 7 + 1); }
        digest = (digest * 31 + int64_t(t.docs.size()) * 1000003 + doc_sum % 1000003 + tf_sum) % MODULUS;
        if (t.docs.size() > dict.terms[size_t(order[best])].docs.size()) best = rank;
    }
    const Term &w = dict.terms[size_t(order[best])];
    std::printf("documents %lld tokens %lld\n", (long long)documents, (long long)tokens);
    std::printf("terms %lld postings %lld\n", (long long)dict.terms.size(), (long long)total);
    std::printf("widest %.*s %lld\n", int(w.word.size()), w.word.data(), (long long)w.docs.size());
    std::printf("digest %lld\n", (long long)digest);
}
