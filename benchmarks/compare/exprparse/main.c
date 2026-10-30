// C peer for main.min: recursive descent into an arena-allocated tree, then evaluate.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { NUMBER, NEGATE, BINARY, COMPARE };
enum { LT, GT, LE, GE, EQ, NE };
typedef struct { uint8_t kind, op; int32_t left, right; int64_t value; } Node;

static Node *nodes; static size_t node_count, node_capacity;
static const char *text; static size_t length, position; static long long line;
static char error[128]; static int failed;

static int32_t node(uint8_t kind, uint8_t op, int32_t left, int32_t right, int64_t value) {
    if (node_count == node_capacity) { node_capacity *= 2; nodes = realloc(nodes, node_capacity * sizeof(Node)); }
    nodes[node_count] = (Node){kind, op, left, right, value};
    return (int32_t)node_count++;
}
static char peek(void) {
    while (position < length && text[position] == ' ') position++;
    return position < length ? text[position] : '\n';
}
static int32_t fail(const char *expected) {
    if (!failed) snprintf(error, sizeof error, "line %lld: expected %s at column %zu", line, expected, position + 1);
    failed = 1;
    return -1;
}
static int32_t sum(void);
static int32_t expression(void) {
    int32_t left = sum();
    if (failed) return -1;
    char c = peek();
    if (c == '<' || c == '>' || c == '=' || c == '!') {
        int two = position + 1 < length && text[position + 1] == '=';
        if (!two && (c == '=' || c == '!')) return fail("a comparison");
        uint8_t op = c == '<' ? (two ? LE : LT) : c == '>' ? (two ? GE : GT) : c == '=' ? EQ : NE;
        position += two ? 2 : 1;
        int32_t right = sum();
        if (failed) return -1;
        return node(COMPARE, op, left, right, 0);
    }
    return left;
}
static int32_t unary(void);
static int32_t primary(void) {
    char c = peek();
    if (c >= '0' && c <= '9') {
        int64_t v = 0;
        while (position < length && text[position] >= '0' && text[position] <= '9') v = v * 10 + (text[position++] - '0');
        return node(NUMBER, 0, -1, -1, v);
    }
    if (c == '(') {
        position++;
        int32_t inner = expression();
        if (failed) return -1;
        if (peek() != ')') return fail("')'");
        position++;
        return inner;
    }
    return fail("a number");
}
static int32_t unary(void) {
    if (peek() == '-') {
        position++;
        int32_t operand = unary();
        if (failed) return -1;
        return node(NEGATE, 0, operand, -1, 0);
    }
    return primary();
}
static int32_t term(void) {
    int32_t left = unary();
    while (!failed) {
        char c = peek();
        if (c != '*' && c != '/' && c != '%') break;
        position++;
        int32_t right = unary();
        if (failed) return -1;
        left = node(BINARY, (uint8_t)c, left, right, 0);
    }
    return failed ? -1 : left;
}
static int32_t sum(void) {
    int32_t left = term();
    while (!failed) {
        char c = peek();
        if (c != '+' && c != '-') break;
        position++;
        int32_t right = term();
        if (failed) return -1;
        left = node(BINARY, (uint8_t)c, left, right, 0);
    }
    return failed ? -1 : left;
}
static int64_t evaluate(int32_t index) {
    const Node *n = &nodes[index];
    switch (n->kind) {
    case NUMBER: return n->value;
    case NEGATE: { int64_t v = evaluate(n->left); return failed ? 0 : -v; }
    case BINARY: {
        int64_t a = evaluate(n->left); if (failed) return 0;
        int64_t b = evaluate(n->right); if (failed) return 0;
        switch (n->op) {
        case '+': return a + b;
        case '-': return a - b;
        case '*': return a * b;
        }
        if (b == 0) { snprintf(error, sizeof error, "line %lld: division by zero", line); failed = 1; return 0; }
        return n->op == '/' ? a / b : a % b;
    }
    default: {
        int64_t a = evaluate(n->left); if (failed) return 0;
        int64_t b = evaluate(n->right); if (failed) return 0;
        switch (n->op) {
        case LT: return a < b;
        case GT: return a > b;
        case LE: return a <= b;
        case GE: return a >= b;
        case EQ: return a == b;
        default: return a != b;
        }
    }
    }
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); size_t size = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(size + 1); if (fread(src, 1, size, f) != size) return 1; fclose(f); src[size] = 0;
    node_capacity = 1024; nodes = malloc(node_capacity * sizeof(Node));
    long long evaluated = 0, division_errors = 0, syntax_errors = 0, comparisons_true = 0, total_nodes = 0, total = 0;
    char messages[6][128]; int message_count = 0;
    const char *p = src, *end = src + size;
    line = 0;
    while (p <= end) {
        const char *nl = memchr(p, '\n', (size_t)(end - p));
        if (!nl) nl = end;
        line++;
        text = p; length = (size_t)(nl - p); p = nl + 1;
        if (length == 0) continue;
        position = 0; failed = 0; node_count = 0;
        int32_t root = expression();
        if (!failed && peek() != '\n') fail("the end of the line");
        if (failed) {
            syntax_errors++;
            if (message_count < 6) strcpy(messages[message_count++], error);
            continue;
        }
        total_nodes += (long long)node_count;
        int64_t value = evaluate(root);
        if (failed) {
            division_errors++;
            if (message_count < 6) strcpy(messages[message_count++], error);
            continue;
        }
        evaluated++;
        total = (total + value % 1000000007) % 1000000007;
        if (nodes[root].kind == COMPARE) comparisons_true += value;
    }
    printf("evaluated %lld\ndivision errors %lld\nsyntax errors %lld\ntrue comparisons %lld\nnodes %lld\ntotal %lld\n",
           evaluated, division_errors, syntax_errors, comparisons_true, total_nodes, total);
    for (int i = 0; i < message_count; i++) puts(messages[i]);
    return 0;
}
