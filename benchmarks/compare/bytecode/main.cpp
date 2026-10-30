// C++ peer for main.min: the same assembler and bytecode, interpreted with a
// switch over a flat std::vector of instructions.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

enum class Op : int32_t { Push, Load, Store, Add, Subtract, Multiply, Remainder, Less, NotEqual, Jump, JumpIfFalse, Call, Return, Halt };
struct Instruction { Op op; int64_t argument; };
struct Function { int64_t entry, parameters, locals; };

struct Assembler {
    std::vector<Instruction> code;
    std::vector<Function> functions;
    int emit(Op op, int64_t argument = 0) { code.push_back({op, argument}); return static_cast<int>(code.size()) - 1; }
    int here() const { return static_cast<int>(code.size()); }
    void patch(int at, int64_t target) { code[at].argument = target; }
    void begin(int64_t parameters, int64_t locals) { functions.push_back({here(), parameters, locals}); }
};

enum { MAIN, SUM_SQUARES, GCD };

static void assemble_main(Assembler &a) {
    a.begin(1, 3);
    a.emit(Op::Push, 0); a.emit(Op::Store, 1); a.emit(Op::Push, 0); a.emit(Op::Store, 2);
    int top = a.here();
    a.emit(Op::Load, 2); a.emit(Op::Load, 0); a.emit(Op::Less);
    int exit = a.emit(Op::JumpIfFalse);
    a.emit(Op::Load, 1); a.emit(Op::Load, 2); a.emit(Op::Push, 64); a.emit(Op::Remainder); a.emit(Op::Call, SUM_SQUARES); a.emit(Op::Add);
    a.emit(Op::Load, 2); a.emit(Op::Push, 360); a.emit(Op::Call, GCD); a.emit(Op::Add);
    a.emit(Op::Push, 1000000007); a.emit(Op::Remainder); a.emit(Op::Store, 1);
    a.emit(Op::Load, 2); a.emit(Op::Push, 1); a.emit(Op::Add); a.emit(Op::Store, 2);
    a.emit(Op::Jump, top);
    a.patch(exit, a.here());
    a.emit(Op::Load, 1); a.emit(Op::Return);
}

static void assemble_sum_squares(Assembler &a) {
    a.begin(1, 3);
    a.emit(Op::Push, 0); a.emit(Op::Store, 1); a.emit(Op::Push, 0); a.emit(Op::Store, 2);
    int top = a.here();
    a.emit(Op::Load, 2); a.emit(Op::Load, 0); a.emit(Op::Less);
    int exit = a.emit(Op::JumpIfFalse);
    a.emit(Op::Load, 1); a.emit(Op::Load, 2); a.emit(Op::Load, 2); a.emit(Op::Multiply); a.emit(Op::Push, 7); a.emit(Op::Remainder); a.emit(Op::Add); a.emit(Op::Store, 1);
    a.emit(Op::Load, 2); a.emit(Op::Push, 1); a.emit(Op::Add); a.emit(Op::Store, 2);
    a.emit(Op::Jump, top);
    a.patch(exit, a.here());
    a.emit(Op::Load, 1); a.emit(Op::Return);
}

static void assemble_gcd(Assembler &a) {
    a.begin(2, 3);
    int top = a.here();
    a.emit(Op::Load, 1); a.emit(Op::Push, 0); a.emit(Op::NotEqual);
    int exit = a.emit(Op::JumpIfFalse);
    a.emit(Op::Load, 0); a.emit(Op::Load, 1); a.emit(Op::Remainder); a.emit(Op::Store, 2);
    a.emit(Op::Load, 1); a.emit(Op::Store, 0); a.emit(Op::Load, 2); a.emit(Op::Store, 1);
    a.emit(Op::Jump, top);
    a.patch(exit, a.here());
    a.emit(Op::Load, 0); a.emit(Op::Return);
}

struct Machine {
    const std::vector<Instruction> &code;
    const std::vector<Function> &functions;
    std::array<int64_t, 1024> stack{};
    std::array<size_t, 64> return_to{};
    std::array<int64_t *, 64> bases{};
    int64_t executed = 0;

    int64_t run(size_t entry) {
        size_t pc = entry;
        int64_t *sp = stack.data() - 1, *base = stack.data();
        int depth = 0;
        for (;;) {
            const Instruction &in = code[pc++];
            executed++;
            switch (in.op) {
            case Op::Push: *++sp = in.argument; break;
            case Op::Load: sp[1] = base[in.argument]; sp++; break;
            case Op::Store: base[in.argument] = *sp--; break;
            case Op::Add: sp--; sp[0] += sp[1]; break;
            case Op::Subtract: sp--; sp[0] -= sp[1]; break;
            case Op::Multiply: sp--; sp[0] *= sp[1]; break;
            case Op::Remainder: sp--; sp[0] %= sp[1]; break;
            case Op::Less: sp--; sp[0] = sp[0] < sp[1]; break;
            case Op::NotEqual: sp--; sp[0] = sp[0] != sp[1]; break;
            case Op::Jump: pc = static_cast<size_t>(in.argument); break;
            case Op::JumpIfFalse: if (*sp-- == 0) pc = static_cast<size_t>(in.argument); break;
            case Op::Call: {
                const Function &f = functions[in.argument];
                return_to[depth] = pc; bases[depth] = base; depth++;
                base = sp - f.parameters + 1;
                for (int64_t slot = f.parameters; slot < f.locals; slot++) base[slot] = 0;
                sp = base + f.locals - 1;
                pc = static_cast<size_t>(f.entry);
                break;
            }
            case Op::Return: {
                int64_t value = *sp;
                sp = base; *sp = value;
                depth--; pc = return_to[depth]; base = bases[depth];
                break;
            }
            case Op::Halt: return *sp;
            }
        }
    }
};

int main(int argc, char **argv) {
    int64_t n = std::atoll(argv[1]);
    Assembler a;
    assemble_main(a); assemble_sum_squares(a); assemble_gcd(a);
    int entry = a.emit(Op::Push, n); a.emit(Op::Call, MAIN); a.emit(Op::Halt);
    Machine machine{a.code, a.functions};
    int64_t result = machine.run(static_cast<size_t>(entry));
    std::printf("result %lld\nexecuted %lld\n", (long long)result, (long long)machine.executed);
    return 0;
}
