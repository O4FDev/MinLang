// C peer for main.min: the same AST (tagged nodes, variables resolved to
// frame slots), interpreted recursively; frames live on the C stack.
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum Operator { ADD, SUBTRACT, MULTIPLY, DIVIDE, REMAINDER, LESS, LESS_EQUAL, EQUAL, NOT_EQUAL };
enum ExprKind { NUMBER, LOCAL, BINARY, CALL };
enum StmtKind { ASSIGN, IF, WHILE, RETURN };

typedef struct Expr Expr;
struct Expr {
    enum ExprKind kind;
    int operator_or_function;
    int64_t value;          // NUMBER value, LOCAL slot
    Expr *left, *right;     // BINARY
    Expr **arguments;       // CALL
    int argument_count;
};

typedef struct Stmt Stmt;
typedef struct { Stmt **items; int count; } Block;
struct Stmt {
    enum StmtKind kind;
    int slot;
    Expr *value;            // ASSIGN value, IF/WHILE condition, RETURN value
    Block then, otherwise;  // IF branches, WHILE body in `then`
};

typedef struct { const char *name; int parameters, locals; Block body; } Function;

static Function functions[4];
static int64_t calls;

static Expr *new_expr(enum ExprKind kind) { Expr *e = calloc(1, sizeof *e); e->kind = kind; return e; }
static Expr *number(int64_t value) { Expr *e = new_expr(NUMBER); e->value = value; return e; }
static Expr *local(int slot) { Expr *e = new_expr(LOCAL); e->value = slot; return e; }
static Expr *binary(enum Operator op, Expr *left, Expr *right) { Expr *e = new_expr(BINARY); e->operator_or_function = op; e->left = left; e->right = right; return e; }
static Expr *call1(int function, Expr *argument) {
    Expr *e = new_expr(CALL); e->operator_or_function = function;
    e->arguments = malloc(sizeof(Expr *)); e->arguments[0] = argument; e->argument_count = 1; return e;
}
static Block block(int count, ...) {
    Block b = {count ? malloc((size_t)count * sizeof(Stmt *)) : NULL, count};
    va_list list; va_start(list, count);
    for (int i = 0; i < count; i++) b.items[i] = va_arg(list, Stmt *);
    va_end(list);
    return b;
}
static Stmt *new_stmt(enum StmtKind kind) { Stmt *s = calloc(1, sizeof *s); s->kind = kind; return s; }
static Stmt *assign(int slot, Expr *value) { Stmt *s = new_stmt(ASSIGN); s->slot = slot; s->value = value; return s; }
static Stmt *if_(Expr *condition, Block then, Block otherwise) { Stmt *s = new_stmt(IF); s->value = condition; s->then = then; s->otherwise = otherwise; return s; }
static Stmt *while_(Expr *condition, Block body) { Stmt *s = new_stmt(WHILE); s->value = condition; s->then = body; return s; }
static Stmt *return_(Expr *value) { Stmt *s = new_stmt(RETURN); s->value = value; return s; }

enum { IS_PRIME, COUNT_PRIMES, FIB, FIB_SUM };

static int64_t call(int index, Expr **arguments, int argument_count, const int64_t *caller);

static int64_t evaluate(const Expr *e, const int64_t *frame) {
    switch (e->kind) {
    case NUMBER: return e->value;
    case LOCAL: return frame[e->value];
    case CALL: return call(e->operator_or_function, e->arguments, e->argument_count, frame);
    case BINARY: {
        int64_t l = evaluate(e->left, frame), r = evaluate(e->right, frame);
        switch ((enum Operator)e->operator_or_function) {
        case ADD: return l + r;
        case SUBTRACT: return l - r;
        case MULTIPLY: return l * r;
        case DIVIDE: return l / r;
        case REMAINDER: return l % r;
        case LESS: return l < r;
        case LESS_EQUAL: return l <= r;
        case EQUAL: return l == r;
        case NOT_EQUAL: return l != r;
        }
    }
    }
    return 0;
}

// Returns 1 when a RETURN ran, storing its value in *result.
static int execute(Block block, int64_t *frame, int64_t *result) {
    for (int i = 0; i < block.count; i++) {
        const Stmt *s = block.items[i];
        switch (s->kind) {
        case ASSIGN: frame[s->slot] = evaluate(s->value, frame); break;
        case IF:
            if (execute(evaluate(s->value, frame) != 0 ? s->then : s->otherwise, frame, result)) return 1;
            break;
        case WHILE:
            while (evaluate(s->value, frame) != 0)
                if (execute(s->then, frame, result)) return 1;
            break;
        case RETURN: *result = evaluate(s->value, frame); return 1;
        }
    }
    return 0;
}

static int64_t call(int index, Expr **arguments, int argument_count, const int64_t *caller) {
    const Function *f = &functions[index];
    int64_t frame[8] = {0};
    for (int i = 0; i < argument_count; i++) frame[i] = evaluate(arguments[i], caller);
    calls++;
    int64_t result = 0;
    execute(f->body, frame, &result);
    return result;
}

int main(int argc, char **argv) {
    int64_t n = atoll(argv[1]);
    {
        Expr *p = local(0), *d = local(1);
        functions[IS_PRIME] = (Function){"isPrime", 1, 2, block(4,
            if_(binary(LESS, p, number(2)), block(1, return_(number(0))), block(0)),
            assign(1, number(2)),
            while_(binary(LESS_EQUAL, binary(MULTIPLY, d, d), p), block(2,
                if_(binary(EQUAL, binary(REMAINDER, p, d), number(0)), block(1, return_(number(0))), block(0)),
                assign(1, binary(ADD, d, number(1))))),
            return_(number(1)))};
    }
    {
        Expr *limit = local(0), *count = local(1), *i = local(2);
        functions[COUNT_PRIMES] = (Function){"countPrimes", 1, 3, block(4,
            assign(1, number(0)),
            assign(2, number(0)),
            while_(binary(LESS, i, limit), block(2,
                assign(1, binary(ADD, count, call1(IS_PRIME, i))),
                assign(2, binary(ADD, i, number(1))))),
            return_(count))};
    }
    {
        Expr *k = local(0);
        functions[FIB] = (Function){"fib", 1, 1, block(2,
            if_(binary(LESS, k, number(2)), block(1, return_(k)), block(0)),
            return_(binary(ADD, call1(FIB, binary(SUBTRACT, k, number(1))), call1(FIB, binary(SUBTRACT, k, number(2))))))};
    }
    {
        Expr *k = local(0), *total = local(1), *j = local(2);
        functions[FIB_SUM] = (Function){"fibSum", 1, 3, block(4,
            assign(1, number(0)),
            assign(2, number(0)),
            while_(binary(LESS, j, k), block(2,
                assign(1, binary(ADD, total, call1(FIB, binary(ADD, number(12), binary(REMAINDER, j, number(8)))))),
                assign(2, binary(ADD, j, number(1))))),
            return_(total))};
    }
    Expr *argument = number(n);
    printf("primes below %lld: %lld\n", (long long)n, (long long)call(COUNT_PRIMES, &argument, 1, NULL));
    argument = number(n / 100);
    printf("fib sum %lld: %lld\n", (long long)(n / 100), (long long)call(FIB_SUM, &argument, 1, NULL));
    printf("calls %lld\n", (long long)calls);
    return 0;
}
