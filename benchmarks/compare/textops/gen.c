// Deterministic input for textops: `gen LINES` writes application log lines
//   LEVEL | service | first.last@domain | message words | duration
// About one line in 200 has a malformed duration ("n/a").
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 0x9E3779B97F4A7C15ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: gen LINES\n"); return 2; }
    long long lines = atoll(argv[1]);
    static const char *levels[] = {"INFO", "INFO", "INFO", "INFO", "DEBUG", "WARN", "WARN", "ERROR"};
    static const char *services[] = {"auth-api", "auth-worker", "billing-api", "billing-worker", "catalog", "checkout",
                                     "gateway", "inventory", "notifications", "search", "shipping", "users"};
    static const char *first[] = {"ada", "grace", "alan", "edsger", "barbara", "ken", "dennis", "margaret",
                                  "john", "frances", "donald", "leslie", "radia", "tony", "niklaus", "sophie"};
    static const char *last[] = {"lovelace", "hopper", "turing", "dijkstra", "liskov", "thompson", "ritchie",
                                 "hamilton", "backus", "allen", "knuth", "lamport", "perlman", "hoare", "wirth", "wilson"};
    static const char *domains[] = {"example.com", "example.com", "mail.org", "corp.net"};
    static const char *words[] = {"payment", "retry", "for", "order", "failed", "after", "timeout", "request", "accepted",
        "user", "session", "expired", "cache", "miss", "on", "key", "reorder", "queued", "message", "delivered",
        "slow", "query", "took", "longer", "than", "expected", "connection", "reset", "by", "peer", "orders",
        "shipment", "created", "with", "tracking", "label", "inventory", "reserved", "items", "released",
        "token", "refreshed", "rate", "limit", "exceeded", "search", "index", "rebuilt", "partially", "the"};
    enum { WORDS = sizeof words / sizeof *words };
    for (long long i = 0; i < lines; i++) {
        printf("%s | %s | %s.%s@%s | ", levels[next() % 8], services[next() % 12], first[next() % 16],
               last[next() % 16], domains[next() % 4]);
        int count = 5 + (int)(next() % 10);
        for (int w = 0; w < count; w++) {
            unsigned long long r = next();
            const char *word = words[(r % WORDS) * ((r >> 32) % WORDS) / WORDS];
            printf(w ? " %s" : "%s", word);
            if (word[0] == 'o' && word[1] == 'r' && word[5] == 0) printf(" %d", (int)(next() % 10000));
        }
        if (next() % 200 == 0) printf(" | n/a\n"); else printf(" | %d\n", (int)(next() % 5000));
    }
    return 0;
}
