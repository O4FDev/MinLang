// Deterministic input for logstats: `gen LINES` writes
// timestamp,level,service,latency,status CSV lines.
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 88172645463325252ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: gen LINES\n"); return 2; }
    long long amount = atoll(argv[1]);
    static const char *levels[] = {"INFO", "INFO", "INFO", "WARN", "ERROR", "DEBUG"};
    for (long long i = 0; i < amount; i++) {
        int service = (int)(next() % 64);
        int latency = (int)(next() % 2000);
        int status = next() % 20 == 0 ? 500 : (next() % 10 == 0 ? 404 : 200);
        long long t = 1761350400LL + i / 10;
        printf("%lld.%03d,%s,service-%d,%d,%d\n", t, (int)(i % 1000),
               levels[next() % 6], service, latency, status);
    }
    return 0;
}
