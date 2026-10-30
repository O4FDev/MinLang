// Input generator for config: `gen SECTIONS` writes an INI/TOML-like file with
// typed values, comments, reopened sections, duplicate keys and a few bad lines.
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 0xD1B54A32D192ED03ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static const char *pad(void) { static const char *pads[] = {"", " ", "  ", "\t"}; return pads[next() % 4]; }

int main(int argc, char **argv) {
    long long sections = argc > 1 ? atoll(argv[1]) : 100;
    printf("# generated service configuration\n\n");
    for (long long s = 0; s < sections; s++) {
        long long id = next() % 20 == 0 && s > 0 ? (long long)(next() % (unsigned long long)s) : s;
        printf("[%sservice.%lld%s]\n", pad(), id, pad());
        int entries = 4 + (int)(next() % 7);
        for (int e = 0; e < entries; e++) {
            unsigned long long bad = next() % 120;
            if (bad == 0) { printf("port = %llux\n", next() % 9000); continue; }
            if (bad == 1) { printf("this line has no equals sign\n"); continue; }
            if (bad == 2) { printf("name = \"svc-%lld\n", id); continue; }
            if (bad == 3) { printf("weights = [1, 2\n"); continue; }
            if (bad == 4) { printf("enabled = maybe\n"); continue; }
            if (bad == 5) { printf("[service.%lld\n", id); continue; }
            if (bad == 6) { printf("retries = -\n"); continue; }
            if (bad == 7) { printf("weights = [4, x5]\n"); continue; }
            if (bad == 8) { printf(" = 12\n"); continue; }
            if (bad == 9) { printf("# %s note %llu\n", next() % 2 ? "maintenance" : "owner", next() % 100); continue; }
            switch (next() % 9) {
            case 0: printf("name%s=%s\"svc-%lld-%llu\"\n", pad(), pad(), id, next() % 100); break;
            case 1: printf("port = %llu\n", 1024 + next() % 60000); break;
            case 2: printf("enabled = %s%s\n", next() % 3 ? "true" : "false", next() % 4 ? "" : "   # toggled"); break;
            case 3: {
                int n = (int)(next() % 6);
                printf("weights = [");
                for (int k = 0; k < n; k++) printf(k ? ",%s%llu" : "%s%llu", pad(), next() % 1000);
                printf("]\n");
                break;
            }
            case 4: printf("timeout = %llu # milliseconds\n", next() % 5000); break;
            case 5: printf("path = \"/var/lib/service/%lld\"\n", id); break;
            case 6: printf("retries = %s%llu\n", next() % 10 ? "" : "-", next() % 10); break;
            case 7: printf("debug = %s\n", next() % 5 ? "false" : "true"); break;
            default: printf("owner = \"team-%llu\" # on call\n", next() % 40); break;
            }
        }
        if (next() % 3 == 0) printf("\n");
    }
    return 0;
}
