// Deterministic input for wordfreq: `gen BYTES` writes space-separated words
// from a skewed 40000-word vocabulary, 6-15 words per line.
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 88172645463325252ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: gen BYTES\n"); return 2; }
    long long amount = atoll(argv[1]);
    enum { V = 40000 };
    static char vocab[V][12];
    for (int i = 0; i < V; i++) {
        int n = 2 + (int)(next() % 9);
        for (int j = 0; j < n; j++) vocab[i][j] = (char)('a' + next() % 26);
        vocab[i][n] = 0;
    }
    long long written = 0;
    while (written < amount) {
        int words = 6 + (int)(next() % 10);
        for (int w = 0; w < words; w++) {
            unsigned long long a = next() % V, b = next() % V;
            const char *word = vocab[(a * b) / V];
            written += printf(w ? " %s" : "%s", word);
        }
        putchar('\n'); written++;
    }
    return 0;
}
