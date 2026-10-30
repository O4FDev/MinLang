// C peer for main.min: parse request lines, look up users, format JSON responses.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { long long id; char name[24]; char email[40]; long long age, score; int present; } User;
int main(int argc, char **argv) {
    long long requests = argc > 1 ? atoll(argv[1]) : 0;
    enum { SLOTS = 1 << 15 };
    static User users[SLOTS];
    for (long long id = 0; id < 10000; id++) {
        long long key = id * 7; size_t j = (size_t)(key * 0x9E3779B97F4A7C15ULL >> 49) & (SLOTS - 1);
        while (users[j].present) j = (j + 1) & (SLOTS - 1);
        User *u = &users[j]; u->present = 1; u->id = key; u->age = 18 + id % 60; u->score = (id * 7919) % 100000;
        snprintf(u->name, sizeof u->name, "user%lld", id); snprintf(u->email, sizeof u->email, "user%lld@example.com", id);
    }
    long long bytes = 0, found = 0, seed = 42; char line[64], response[256];
    for (long long request = 0; request < requests; request++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        snprintf(line, sizeof line, "GET /users/%lld HTTP/1.1", seed % 80000);
        char *path = strchr(line, ' ') + 1; char *end = strchr(path, ' '); *end = 0;
        if (strncmp(path, "/users/", 7) != 0) continue;
        long long id = strtoll(path + 7, NULL, 10);
        size_t j = (size_t)(id * 0x9E3779B97F4A7C15ULL >> 49) & (SLOTS - 1); User *u = NULL;
        while (users[j].present) { if (users[j].id == id) { u = &users[j]; break; } j = (j + 1) & (SLOTS - 1); }
        int n;
        if (u) { n = snprintf(response, sizeof response, "{\"id\":%lld,\"name\":\"%s\",\"email\":\"%s\",\"age\":%lld,\"score\":%lld}", u->id, u->name, u->email, u->age, u->score); found++; }
        else n = snprintf(response, sizeof response, "{\"error\":\"not found\",\"id\":%lld}", id);
        bytes += n;
    }
    printf("%lld\n%lld\n", found, bytes);
    return 0;
}
