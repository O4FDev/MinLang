// C peer for main.min: qsort of word slices, Integers and (key, value) records.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *p; size_t n; } Word;
typedef struct { Word key; long long value; } Item;

static int word_cmp(const Word *a, const Word *b) {
    int c = memcmp(a->p, b->p, a->n < b->n ? a->n : b->n);
    if (c) return c;
    return (a->n > b->n) - (a->n < b->n);
}
static int by_word(const void *x, const void *y) { return word_cmp(x, y); }
static int by_number(const void *x, const void *y) {
    long long a = *(const long long *)x, b = *(const long long *)y;
    return (a > b) - (a < b);
}
static int by_item(const void *x, const void *y) {
    const Item *a = x, *b = y;
    int c = word_cmp(&a->key, &b->key);
    if (c) return c;
    return (a->value < b->value) - (a->value > b->value);
}
static long long checksum(const long long *v, size_t n) {
    long long total = 0;
    for (size_t i = 0; i < n; i++) total = (total * 31 + v[i]) % 1000000007;
    return total;
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END); long size = ftell(f); fseek(f, 0, SEEK_SET);
    char *text = malloc((size_t)size + 1);
    if (fread(text, 1, (size_t)size, f) != (size_t)size) return 1;
    fclose(f);
    text[size] = '\n';
    size_t lines = 0;
    for (long i = 0; i < size; i++) lines += text[i] == '\n';
    Word *words = malloc(lines * sizeof *words);
    long long *numbers = malloc(lines * sizeof *numbers), *scratch = malloc(lines * sizeof *scratch);
    Item *items = malloc(lines * sizeof *items);
    size_t n = 0;
    for (char *p = text, *end = text + size; p < end;) {
        char *line_end = memchr(p, '\n', (size_t)(end - p));
        if (!line_end) line_end = end;
        if (line_end > p) {
            char *space = memchr(p, ' ', (size_t)(line_end - p));
            long long value = 0;
            for (char *d = space + 1; d < line_end; d++) value = value * 10 + (*d - '0');
            words[n] = (Word){p, (size_t)(space - p)};
            numbers[n] = value;
            items[n] = (Item){words[n], value};
            n++;
        }
        p = line_end + 1;
    }
    qsort(words, n, sizeof *words, by_word);
    size_t distinct = 0;
    for (size_t i = 0; i < n; i++) {
        if (i == 0 || word_cmp(&words[i], &words[i - 1]) != 0) distinct++;
        scratch[i] = (long long)words[i].n;
    }
    printf("words %zu distinct %zu checksum %lld\n", n, distinct, checksum(scratch, n));
    for (size_t i = 0; i < 3; i++) printf("%.*s\n", (int)words[i].n, words[i].p);
    for (size_t i = n - 3; i < n; i++) printf("%.*s\n", (int)words[i].n, words[i].p);
    qsort(numbers, n, sizeof *numbers, by_number);
    printf("numbers min %lld median %lld max %lld checksum %lld\n", numbers[0], numbers[n / 2], numbers[n - 1], checksum(numbers, n));
    qsort(items, n, sizeof *items, by_item);
    for (size_t i = 0; i < n; i++) scratch[i] = items[i].value;
    printf("items checksum %lld\n", checksum(scratch, n));
    for (size_t i = 0; i < 3; i++) printf("%.*s %lld\n", (int)items[i].key.n, items[i].key.p, items[i].value);
    return 0;
}
