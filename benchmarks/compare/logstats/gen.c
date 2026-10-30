// Deterministic input generator for the general benchmark set.
//   gen words BYTES > words.txt    space-separated words, skewed vocabulary
//   gen log LINES > log.csv        timestamp,level,service,latency,status
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long long state = 88172645463325252ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: gen words BYTES | gen log LINES\n"); return 2; }
    long long amount = atoll(argv[2]);
    if (strcmp(argv[1], "words") == 0) {
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
    } else if (strcmp(argv[1], "log") == 0) {
        static const char *levels[] = {"INFO", "INFO", "INFO", "WARN", "ERROR", "DEBUG"};
        for (long long i = 0; i < amount; i++) {
            int service = (int)(next() % 64);
            int latency = (int)(next() % 2000);
            int status = next() % 20 == 0 ? 500 : (next() % 10 == 0 ? 404 : 200);
            long long t = 1761350400LL + i / 10;
            printf("%lld.%03d,%s,service-%d,%d,%d\n", t, (int)(i % 1000),
                   levels[next() % 6], service, latency, status);
        }
    } else return 2;
    return 0;
}
