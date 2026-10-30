// Input generator for exprparse: `gen LINES` writes one arithmetic expression per line.
// Parentheses nest at most two levels and right operands of * / % are literals,
// so every well-formed line evaluates without 64-bit overflow.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long long state = 0x2545F4914F6CDD1DULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static char buffer[1 << 16];
static size_t length;
static void put(const char *s) { size_t n = strlen(s); memcpy(buffer + length, s, n); length += n; }
static void number(void) { length += (size_t)sprintf(buffer + length, "%llu", next() % 100); }
static void sum(int depth);
static void factor(int depth) {
    if (next() % 8 == 0) { put("-"); factor(depth); return; }
    if (depth < 2 && next() % 3 == 0) { put("("); sum(depth + 1); put(")"); return; }
    number();
}
static void term(int depth) {
    factor(depth);
    int ops = (int)(next() % 3);
    for (int i = 0; i < ops; i++) {
        static const char *mul[] = {" * ", " * ", " / ", " % "};
        put(mul[next() % 4]);
        if (next() % 40 == 0) put("0"); else number();
    }
}
static void sum(int depth) {
    int terms = 1 + (int)(next() % 4);
    for (int i = 0; i < terms; i++) {
        if (i) put(next() % 2 ? " + " : " - ");
        term(depth);
    }
}
int main(int argc, char **argv) {
    long long lines = argc > 1 ? atoll(argv[1]) : 1000;
    static const char *compare[] = {" < ", " > ", " <= ", " >= ", " == ", " != "};
    for (long long line = 0; line < lines; line++) {
        length = 0;
        sum(0);
        if (next() % 5 == 0) { put(compare[next() % 6]); sum(0); }
        buffer[length] = 0;
        unsigned long long corrupt = next() % 60;
        if (corrupt == 0) { // drop the last closing parenthesis
            char *close = strrchr(buffer, ')');
            if (close) memmove(close, close + 1, strlen(close));
        } else if (corrupt == 1) { // a dangling operator
            strcat(buffer, " *");
        } else if (corrupt == 2) { // a name where a number belongs
            char *digit = strpbrk(buffer, "0123456789");
            if (digit) *digit = 'x';
        } else if (corrupt == 3) { // trailing junk
            strcat(buffer, " )");
        }
        puts(buffer);
    }
    return 0;
}
