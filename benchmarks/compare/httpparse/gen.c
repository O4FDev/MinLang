// Input generator for httpparse: `gen REQUESTS` writes concatenated HTTP/1.1
// requests (CRLF framing, Content-Length bodies, mixed-case header names).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long long state = 0x8CB92BA72F3D8DD7ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static void header(const char *name, const char *value) {
    char spelled[64];
    size_t n = strlen(name);
    unsigned long long style = next() % 4;
    for (size_t i = 0; i < n; i++) {
        char c = name[i];
        if (style == 1 && c >= 'A' && c <= 'Z') c = (char)(c + 32);
        if (style == 2 && c >= 'a' && c <= 'z') c = (char)(c - 32);
        spelled[i] = c;
    }
    spelled[n] = 0;
    printf("%s:%s%s\r\n", spelled, next() % 5 ? " " : "", value);
}
int main(int argc, char **argv) {
    long long requests = argc > 1 ? atoll(argv[1]) : 1000;
    static const char *words[] = {"lamp", "harbour", "lantern", "tide", "beacon", "keel", "mast", "rope", "anchor", "gull"};
    char value[128], body[128];
    for (long long r = 0; r < requests; r++) {
        unsigned long long kind = next() % 100;
        const char *bodyText = NULL;
        int badLength = 0, noLength = 0;
        if (kind < 40) printf("GET /users/%llu HTTP/1.1\r\n", next() % 60000);
        else if (kind < 60) {
            unsigned long long form = next() % 10;
            const char *w = words[next() % 10];
            if (form == 0) printf("GET /search?limit=%llu HTTP/1.1\r\n", next() % 9);
            else if (form < 4) printf("GET /search?q=%s HTTP/1.1\r\n", w);
            else printf("GET /search?q=%s&limit=%llu HTTP/1.1\r\n", w, next() % 9);
        } else if (kind < 82) {
            printf("POST /items HTTP/1.1\r\n");
            snprintf(body, sizeof body, "{\"name\":\"item-%llu\",\"qty\":%llu}", next() % 100000, next() % 50);
            bodyText = body;
            unsigned long long odd = next() % 40;
            badLength = odd == 0; noLength = odd == 1;
        } else if (kind < 87) printf("DELETE /users/%llu HTTP/1.1\r\n", next() % 60000);
        else if (kind < 92) printf("GET /static/app-%llu.js HTTP/1.1\r\n", next() % 100);
        else if (kind < 94) printf("PUT /search?q=x HTTP/1.1\r\n");
        else if (kind < 95) printf("BROKEN\r\n");
        else printf("GET /users/%llu?verbose=1 HTTP/1.1\r\n", next() % 50000);
        if (next() % 20) header("Host", next() % 2 ? "example.com" : "api.example.com");
        header("User-Agent", "bench-client/1.0");
        header("Accept", "application/json");
        if (next() % 2) { snprintf(value, sizeof value, "%llu", next() % 1000000000); header("X-Request-Id", value); }
        if (next() % 10 == 0) header("Connection", "close");
        if (bodyText) {
            header("Content-Type", "application/json");
            if (badLength) header("Content-Length", "12x");
            else if (!noLength) { snprintf(value, sizeof value, "%zu", strlen(bodyText)); header("Content-Length", value); }
        }
        printf("\r\n");
        if (bodyText && !badLength && !noLength) fputs(bodyText, stdout);
    }
    return 0;
}
