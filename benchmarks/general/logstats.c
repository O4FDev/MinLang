// C reference for logstats.min: same output.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char name[32]; long long count, total, slowest, errors; } Stats;
static Stats services[256]; static int used;

static Stats *find(const char *p, int n) {
    for (int i = 0; i < used; i++) if ((int)strlen(services[i].name) == n && memcmp(services[i].name, p, n) == 0) return &services[i];
    memcpy(services[used].name, p, n); services[used].name[n] = 0;
    return &services[used++];
}
static int compare(const void *a, const void *b) { return strcmp(((const Stats *)a)->name, ((const Stats *)b)->name); }

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *text = malloc(size + 1); fread(text, 1, size, f); fclose(f); text[size] = 0;
    long long warnings = 0;
    char *line = text;
    while (*line) {
        char *end = strchr(line, '\n'); if (!end) end = text + size;
        char *field[5]; int length[5]; char *p = line;
        for (int k = 0; k < 5; k++) {
            field[k] = p;
            while (p < end && *p != ',') p++;
            length[k] = (int)(p - field[k]); p++;
        }
        long long latency = strtoll(field[3], NULL, 10), status = strtoll(field[4], NULL, 10);
        if (length[1] == 4 && memcmp(field[1], "WARN", 4) == 0) warnings++;
        Stats *s = find(field[2], length[2]);
        s->count++; s->total += latency;
        if (latency > s->slowest) s->slowest = latency;
        if (status >= 500) s->errors++;
        line = *end ? end + 1 : end;
    }
    qsort(services, used, sizeof(Stats), compare);
    printf("%lld\n", warnings);
    for (int i = 0; i < used; i++) printf("%s %lld %lld %lld %lld\n", services[i].name, services[i].count, services[i].total / services[i].count, services[i].slowest, services[i].errors);
    return 0;
}
