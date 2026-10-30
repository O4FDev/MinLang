// Input generator for tokenizer: `gen LINES` writes source-like text.
#include <stdio.h>
#include <stdlib.h>

static unsigned long long state = 0x9E3779B97F4A7C15ULL;
static unsigned long long next(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
enum { V = 3000 };
static char vocab[V][16];
static const char *keywords[] = {"let", "if", "else", "while", "return", "function", "for", "in"};
static const char *operators[] = {"+", "-", "*", "/", "%", "=", "==", "!=", "<", "<=", ">", ">=", "&&", "||", "->", "(", ")", "{", "}", "[", "]", ";", ",", "."};

static const char *identifier(void) {
    unsigned long long a = next() % V, b = next() % V;
    return vocab[(a * b) / V];
}
int main(int argc, char **argv) {
    long long lines = argc > 1 ? atoll(argv[1]) : 1000;
    for (int i = 0; i < V; i++) {
        int n = 1 + (int)(next() % 10);
        for (int j = 0; j < n; j++) {
            unsigned long long r = next() % 40;
            vocab[i][j] = j > 0 && r >= 34 ? (char)('0' + r % 10) : r == 33 ? '_' : (char)('a' + r % 26);
        }
        vocab[i][n] = 0;
        if (vocab[i][0] >= '0' && vocab[i][0] <= '9') vocab[i][0] = 'x';
    }
    for (long long line = 0; line < lines; line++) {
        int indent = (int)(next() % 4) * 4;
        for (int s = 0; s < indent; s++) putchar(' ');
        int tokens = 3 + (int)(next() % 12);
        for (int t = 0; t < tokens; t++) {
            if (t) putchar(next() % 8 == 0 ? '\t' : ' ');
            unsigned long long kind = next() % 20;
            if (kind < 8) fputs(identifier(), stdout);
            else if (kind < 10) fputs(keywords[next() % 8], stdout);
            else if (kind < 13) printf("%llu", next() % (next() % 2 ? 100 : 100000000));
            else if (kind < 14) {
                putchar('"');
                int n = (int)(next() % 16);
                for (int k = 0; k < n; k++) {
                    unsigned long long c = next() % 32;
                    if (c == 0) fputs("\\\"", stdout);
                    else if (c == 1) fputs("\\\\", stdout);
                    else if (c == 2) fputs("\\n", stdout);
                    else if (c < 6) putchar(' ');
                    else putchar('a' + (int)(c - 6));
                }
                putchar('"');
            } else fputs(operators[next() % 24], stdout);
        }
        if (next() % 6 == 0) printf(" // %s note %llu", identifier(), next() % 1000);
        putchar('\n');
    }
    return 0;
}
