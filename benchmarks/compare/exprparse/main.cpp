// C++ peer for main.min: recursive descent into a vector-backed tree, then evaluate.
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

enum Kind : uint8_t { NUMBER, NEGATE, BINARY, COMPARE };
enum Cmp : uint8_t { LT, GT, LE, GE, EQ, NE };
struct Node { Kind kind; uint8_t op; int32_t left, right; int64_t value; };

struct Parser {
    std::string_view text;
    size_t position = 0;
    long long line = 0;
    std::vector<Node> &nodes;
    std::string error;

    char peek() {
        while (position < text.size() && text[position] == ' ') position++;
        return position < text.size() ? text[position] : '\n';
    }
    std::optional<int32_t> fail(const char *expected) {
        error = "line " + std::to_string(line) + ": expected " + expected + " at column " + std::to_string(position + 1);
        return std::nullopt;
    }
    int32_t add(Node n) { nodes.push_back(n); return int32_t(nodes.size() - 1); }
    std::optional<int32_t> expression() {
        auto left = sum();
        if (!left) return left;
        char c = peek();
        if (c == '<' || c == '>' || c == '=' || c == '!') {
            bool two = position + 1 < text.size() && text[position + 1] == '=';
            if (!two && (c == '=' || c == '!')) return fail("a comparison");
            uint8_t op = c == '<' ? (two ? LE : LT) : c == '>' ? (two ? GE : GT) : c == '=' ? EQ : NE;
            position += two ? 2 : 1;
            auto right = sum();
            if (!right) return right;
            return add({COMPARE, op, *left, *right, 0});
        }
        return left;
    }
    std::optional<int32_t> sum() {
        auto left = term();
        while (left) {
            char c = peek();
            if (c != '+' && c != '-') break;
            position++;
            auto right = term();
            if (!right) return right;
            left = add({BINARY, uint8_t(c), *left, *right, 0});
        }
        return left;
    }
    std::optional<int32_t> term() {
        auto left = unary();
        while (left) {
            char c = peek();
            if (c != '*' && c != '/' && c != '%') break;
            position++;
            auto right = unary();
            if (!right) return right;
            left = add({BINARY, uint8_t(c), *left, *right, 0});
        }
        return left;
    }
    std::optional<int32_t> unary() {
        if (peek() == '-') {
            position++;
            auto operand = unary();
            if (!operand) return operand;
            return add({NEGATE, 0, *operand, -1, 0});
        }
        return primary();
    }
    std::optional<int32_t> primary() {
        char c = peek();
        if (c >= '0' && c <= '9') {
            int64_t v = 0;
            while (position < text.size() && text[position] >= '0' && text[position] <= '9') v = v * 10 + (text[position++] - '0');
            return add({NUMBER, 0, -1, -1, v});
        }
        if (c == '(') {
            position++;
            auto inner = expression();
            if (!inner) return inner;
            if (peek() != ')') return fail("')'");
            position++;
            return inner;
        }
        return fail("a number");
    }
};

struct Evaluator {
    const std::vector<Node> &nodes;
    bool failed = false;
    int64_t operator()(int32_t index) {
        const Node &n = nodes[index];
        if (n.kind == NUMBER) return n.value;
        if (n.kind == NEGATE) { int64_t v = (*this)(n.left); return -v; }
        int64_t a = (*this)(n.left); if (failed) return 0;
        int64_t b = (*this)(n.right); if (failed) return 0;
        if (n.kind == COMPARE) {
            switch (n.op) {
            case LT: return a < b;
            case GT: return a > b;
            case LE: return a <= b;
            case GE: return a >= b;
            case EQ: return a == b;
            default: return a != b;
            }
        }
        switch (n.op) {
        case '+': return a + b;
        case '-': return a - b;
        case '*': return a * b;
        }
        if (b == 0) { failed = true; return 0; }
        return n.op == '/' ? a / b : a % b;
    }
};

int main(int, char **argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::string src((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::vector<Node> nodes;
    nodes.reserve(1024);
    long long evaluated = 0, division_errors = 0, syntax_errors = 0, comparisons_true = 0, total_nodes = 0, total = 0;
    std::vector<std::string> messages;
    std::string_view all(src);
    long long line = 0;
    size_t start = 0;
    while (start <= all.size()) {
        size_t nl = all.find('\n', start);
        if (nl == std::string_view::npos) nl = all.size();
        std::string_view text = all.substr(start, nl - start);
        start = nl + 1;
        line++;
        if (text.empty()) continue;
        nodes.clear();
        Parser parser{text, 0, line, nodes, {}};
        auto root = parser.expression();
        if (root && parser.peek() != '\n') root = parser.fail("the end of the line");
        if (!root) {
            syntax_errors++;
            if (messages.size() < 6) messages.push_back(parser.error);
            continue;
        }
        total_nodes += (long long)nodes.size();
        Evaluator evaluate{nodes};
        int64_t value = evaluate(*root);
        if (evaluate.failed) {
            division_errors++;
            if (messages.size() < 6) messages.push_back("line " + std::to_string(line) + ": division by zero");
            continue;
        }
        evaluated++;
        total = (total + value % 1000000007) % 1000000007;
        if (nodes[*root].kind == COMPARE) comparisons_true += value;
    }
    std::printf("evaluated %lld\ndivision errors %lld\nsyntax errors %lld\ntrue comparisons %lld\nnodes %lld\ntotal %lld\n",
                evaluated, division_errors, syntax_errors, comparisons_true, total_nodes, total);
    for (const auto &m : messages) std::puts(m.c_str());
}
