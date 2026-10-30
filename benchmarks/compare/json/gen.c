// Deterministic input for the json program: `gen N` writes a JSON array of N
// user objects (nested address/geo, tag arrays, order objects, string escapes,
// negative numbers, null and Boolean members). The output is pure ASCII.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static uint64_t state = 0x9E3779B97F4A7C15ULL;
static uint64_t next(void) { state ^= state << 13; state ^= state >> 7; state ^= state << 17; return state; }

int main(int argc, char **argv) {
    long long count = argc > 1 ? atoll(argv[1]) : 0;
    char cities[40][32];
    for (int k = 0; k < 40; k++) {
        if (k % 8 == 0) snprintf(cities[k], sizeof cities[k], "Ci\\u00e9t\\u00e9 %d", k);
        else snprintf(cities[k], sizeof cities[k], "city-%02d", k);
    }
    fputs("[\n", stdout);
    for (long long i = 0; i < count; i++) {
        uint64_t r = next();
        printf("{\"id\": %lld, \"name\": \"User %lld", i, i);
        if (r % 10 == 0) fputs(" \\\"Jr\\\"", stdout);
        if (r % 13 == 0) fputs("\\nII", stdout);
        if (r % 17 == 0) fputs("\\t\\u00e9\\u00e8", stdout);
        if ((r >> 8) % 29 == 0) fputs(" a\\\\b\\/c", stdout);
        printf("\", \"email\": \"user%lld@example.com\", \"active\": %s, \"age\": %d, \"score\": %d, ",
               i, (r >> 12) % 4 ? "true" : "false", 18 + (int)((r >> 16) % 60), (int)((r >> 24) % 10001) - 5000);
        int latitude = (int)(next() % 180001) - 90000;
        int longitude = (int)(next() % 360001) - 180000;
        printf("\"address\": {\"city\": \"%s\", \"zip\": \"%05d\", \"geo\": [%d, %d]}, ", cities[(r >> 32) % 40],
               (int)((r >> 40) % 100000), latitude, longitude);
        int tags = (int)(next() % 5);
        fputs("\"tags\": [", stdout);
        for (int t = 0; t < tags; t++) printf("%s\"t%02d\"", t ? ", " : "", (int)(next() % 24));
        fputs("], \"orders\": [", stdout);
        int orders = (int)(next() % 6);
        for (int o = 0; o < orders; o++) {
            uint64_t g = next() % 3;
            int sku = (int)(next() % 5000);
            int quantity = 1 + (int)(next() % 5);
            int price = 100 + (int)(next() % 99900);
            printf("%s{\"sku\": \"sku-%d\", \"qty\": %d, \"price\": %d, \"gift\": %s}", o ? ", " : "", sku,
                   quantity, price, g == 0 ? "null" : g == 1 ? "false" : "true");
        }
        printf("], \"note\": %s}%s\n", r % 7 == 0 ? "\"see \\/notes\"" : "null", i + 1 < count ? "," : "");
    }
    fputs("]\n", stdout);
    return 0;
}
