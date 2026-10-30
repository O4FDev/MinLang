// Input for sorttext: `gen N` writes N lines "key value". Keys come from a
// vocabulary of about N/4 lowercase words, half with shared prefixes, so equal
// keys repeat and many comparisons look past the first bytes.
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 0x9E3779B97F4A7C15ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: gen N\n"); return 2; }
    long n = atol(argv[1]);
    static const char *prefixes[] = {"pre", "con", "inter", "trans", "under", "over", "anti", "micro"};
    long vocabulary = n / 4 > 1 ? n / 4 : 1;
    char (*words)[24] = malloc((size_t)vocabulary * sizeof *words);
    for (long i = 0; i < vocabulary; i++) {
        int at = 0;
        if (next() % 2 == 0) {
            const char *p = prefixes[next() % 8];
            while (*p) words[i][at++] = *p++;
        }
        int length = 3 + (int)(next() % 10);
        for (int j = 0; j < length; j++) words[i][at++] = (char)('a' + next() % 26);
        words[i][at] = 0;
    }
    for (long i = 0; i < n; i++)
        printf("%s %llu\n", words[next() % (unsigned long long)vocabulary], next() % 1000000000ULL);
    free(words);
    return 0;
}
