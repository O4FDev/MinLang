// C++ peer for main.min: the same AST (nodes owned by unique_ptr, variables
// resolved to frame slots), interpreted recursively; frames on the stack.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>

enum class Operator { Add, Subtract, Multiply, Divide, Remainder, Less, LessEqual, Equal, NotEqual };

struct Expr {
    enum class Kind { Number, Local, Binary, Call } kind;
    int64_t value = 0;  // Number value, Local slot, Call function index
    Operator op = Operator::Add;
    std::unique_ptr<Expr> left, right;
    std::vector<std::unique_ptr<Expr>> arguments;
};
using ExprPtr = std::unique_ptr<Expr>;

struct Stmt;
using Block = std::vector<std::unique_ptr<Stmt>>;
struct Stmt {
    enum class Kind { Assign, If, While, Return } kind;
    int slot = 0;
    ExprPtr value;  // Assign value, If/While condition, Return value
    Block then, otherwise;
};

struct Function { const char *name; int parameters, locals; Block body; };

static ExprPtr number(int64_t v) { auto e = std::make_unique<Expr>(); e->kind = Expr::Kind::Number; e->value = v; return e; }
static ExprPtr local(int slot) { auto e = std::make_unique<Expr>(); e->kind = Expr::Kind::Local; e->value = slot; return e; }
static ExprPtr binary(Operator op, ExprPtr l, ExprPtr r) {
    auto e = std::make_unique<Expr>(); e->kind = Expr::Kind::Binary; e->op = op; e->left = std::move(l); e->right = std::move(r); return e;
}
static ExprPtr call(int function, ExprPtr argument) {
    auto e = std::make_unique<Expr>(); e->kind = Expr::Kind::Call; e->value = function; e->arguments.push_back(std::move(argument)); return e;
}
template <class... S> static Block block(S... items) { Block b; (b.push_back(std::move(items)), ...); return b; }
static std::unique_ptr<Stmt> assign(int slot, ExprPtr v) { auto s = std::make_unique<Stmt>(); s->kind = Stmt::Kind::Assign; s->slot = slot; s->value = std::move(v); return s; }
static std::unique_ptr<Stmt> if_(ExprPtr c, Block t, Block o) { auto s = std::make_unique<Stmt>(); s->kind = Stmt::Kind::If; s->value = std::move(c); s->then = std::move(t); s->otherwise = std::move(o); return s; }
static std::unique_ptr<Stmt> while_(ExprPtr c, Block body) { auto s = std::make_unique<Stmt>(); s->kind = Stmt::Kind::While; s->value = std::move(c); s->then = std::move(body); return s; }
static std::unique_ptr<Stmt> return_(ExprPtr v) { auto s = std::make_unique<Stmt>(); s->kind = Stmt::Kind::Return; s->value = std::move(v); return s; }

enum { IS_PRIME, COUNT_PRIMES, FIB, FIB_SUM };

struct Interpreter {
    std::vector<Function> functions;
    int64_t calls = 0;

    int64_t evaluate(const Expr &e, const int64_t *frame) {
        switch (e.kind) {
        case Expr::Kind::Number: return e.value;
        case Expr::Kind::Local: return frame[e.value];
        case Expr::Kind::Call: return call(static_cast<int>(e.value), e.arguments, frame);
        case Expr::Kind::Binary: {
            int64_t l = evaluate(*e.left, frame), r = evaluate(*e.right, frame);
            switch (e.op) {
            case Operator::Add: return l + r;
            case Operator::Subtract: return l - r;
            case Operator::Multiply: return l * r;
            case Operator::Divide: return l / r;
            case Operator::Remainder: return l % r;
            case Operator::Less: return l < r;
            case Operator::LessEqual: return l <= r;
            case Operator::Equal: return l == r;
            case Operator::NotEqual: return l != r;
            }
        }
        }
        return 0;
    }

    // Returns true when a Return ran, storing its value in result.
    bool execute(const Block &block, int64_t *frame, int64_t &result) {
        for (const auto &s : block) {
            switch (s->kind) {
            case Stmt::Kind::Assign: frame[s->slot] = evaluate(*s->value, frame); break;
            case Stmt::Kind::If:
                if (execute(evaluate(*s->value, frame) != 0 ? s->then : s->otherwise, frame, result)) return true;
                break;
            case Stmt::Kind::While:
                while (evaluate(*s->value, frame) != 0)
                    if (execute(s->then, frame, result)) return true;
                break;
            case Stmt::Kind::Return: result = evaluate(*s->value, frame); return true;
            }
        }
        return false;
    }

    int64_t call(int index, const std::vector<ExprPtr> &arguments, const int64_t *caller) {
        const Function &f = functions[index];
        std::array<int64_t, 8> frame{};
        for (size_t i = 0; i < arguments.size(); i++) frame[i] = evaluate(*arguments[i], caller);
        calls++;
        int64_t result = 0;
        execute(f.body, frame.data(), result);
        return result;
    }
};

int main(int argc, char **argv) {
    int64_t n = std::atoll(argv[1]);
    Interpreter in;
    in.functions.push_back({"isPrime", 1, 2, block(
        if_(binary(Operator::Less, local(0), number(2)), block(return_(number(0))), block()),
        assign(1, number(2)),
        while_(binary(Operator::LessEqual, binary(Operator::Multiply, local(1), local(1)), local(0)), block(
            if_(binary(Operator::Equal, binary(Operator::Remainder, local(0), local(1)), number(0)), block(return_(number(0))), block()),
            assign(1, binary(Operator::Add, local(1), number(1))))),
        return_(number(1)))});
    in.functions.push_back({"countPrimes", 1, 3, block(
        assign(1, number(0)),
        assign(2, number(0)),
        while_(binary(Operator::Less, local(2), local(0)), block(
            assign(1, binary(Operator::Add, local(1), call(IS_PRIME, local(2)))),
            assign(2, binary(Operator::Add, local(2), number(1))))),
        return_(local(1)))});
    in.functions.push_back({"fib", 1, 1, block(
        if_(binary(Operator::Less, local(0), number(2)), block(return_(local(0))), block()),
        return_(binary(Operator::Add, call(FIB, binary(Operator::Subtract, local(0), number(1))),
                       call(FIB, binary(Operator::Subtract, local(0), number(2))))))});
    in.functions.push_back({"fibSum", 1, 3, block(
        assign(1, number(0)),
        assign(2, number(0)),
        while_(binary(Operator::Less, local(2), local(0)), block(
            assign(1, binary(Operator::Add, local(1), call(FIB, binary(Operator::Add, number(12), binary(Operator::Remainder, local(2), number(8)))))),
            assign(2, binary(Operator::Add, local(2), number(1))))),
        return_(local(1)))});
    std::vector<ExprPtr> arguments;
    arguments.push_back(number(n));
    std::printf("primes below %lld: %lld\n", (long long)n, (long long)in.call(COUNT_PRIMES, arguments, nullptr));
    arguments[0] = number(n / 100);
    std::printf("fib sum %lld: %lld\n", (long long)(n / 100), (long long)in.call(FIB_SUM, arguments, nullptr));
    std::printf("calls %lld\n", (long long)in.calls);
    return 0;
}
