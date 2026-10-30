// C peer for main.min: the same assembler and bytecode, interpreted with
// direct-threaded dispatch (computed goto) over a flat instruction array.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum Op { PUSH, LOAD, STORE, ADD, SUBTRACT, MULTIPLY, REMAINDER, LESS, NOT_EQUAL, JUMP, JUMP_IF_FALSE, CALL, RETURN, HALT };
typedef struct { int32_t op; int64_t argument; } Instruction;
typedef struct { int64_t entry, parameters, locals; } Function;

static Instruction code[256];
static int length;
static Function functions[8];
static int function_count;

static int emit(enum Op op, int64_t argument) { code[length] = (Instruction){op, argument}; return length++; }
static void op(enum Op o) { emit(o, 0); }
static void patch(int at, int64_t target) { code[at].argument = target; }
static void begin(int64_t parameters, int64_t locals) { functions[function_count++] = (Function){length, parameters, locals}; }

enum { MAIN, SUM_SQUARES, GCD };

static void assemble_main(void) {
    begin(1, 3);
    emit(PUSH, 0); emit(STORE, 1); emit(PUSH, 0); emit(STORE, 2);
    int top = length;
    emit(LOAD, 2); emit(LOAD, 0); op(LESS);
    int exit = emit(JUMP_IF_FALSE, 0);
    emit(LOAD, 1); emit(LOAD, 2); emit(PUSH, 64); op(REMAINDER); emit(CALL, SUM_SQUARES); op(ADD);
    emit(LOAD, 2); emit(PUSH, 360); emit(CALL, GCD); op(ADD);
    emit(PUSH, 1000000007); op(REMAINDER); emit(STORE, 1);
    emit(LOAD, 2); emit(PUSH, 1); op(ADD); emit(STORE, 2);
    emit(JUMP, top);
    patch(exit, length);
    emit(LOAD, 1); op(RETURN);
}

static void assemble_sum_squares(void) {
    begin(1, 3);
    emit(PUSH, 0); emit(STORE, 1); emit(PUSH, 0); emit(STORE, 2);
    int top = length;
    emit(LOAD, 2); emit(LOAD, 0); op(LESS);
    int exit = emit(JUMP_IF_FALSE, 0);
    emit(LOAD, 1); emit(LOAD, 2); emit(LOAD, 2); op(MULTIPLY); emit(PUSH, 7); op(REMAINDER); op(ADD); emit(STORE, 1);
    emit(LOAD, 2); emit(PUSH, 1); op(ADD); emit(STORE, 2);
    emit(JUMP, top);
    patch(exit, length);
    emit(LOAD, 1); op(RETURN);
}

static void assemble_gcd(void) {
    begin(2, 3);
    int top = length;
    emit(LOAD, 1); emit(PUSH, 0); op(NOT_EQUAL);
    int exit = emit(JUMP_IF_FALSE, 0);
    emit(LOAD, 0); emit(LOAD, 1); op(REMAINDER); emit(STORE, 2);
    emit(LOAD, 1); emit(STORE, 0); emit(LOAD, 2); emit(STORE, 1);
    emit(JUMP, top);
    patch(exit, length);
    emit(LOAD, 0); op(RETURN);
}

static int64_t stack[1024];
static const Instruction *return_to[64];
static int64_t *bases[64];
static int64_t executed;

static int64_t run(int entry) {
    static void *labels[] = {&&push, &&load, &&store, &&add, &&subtract, &&multiply, &&remainder, &&less,
                             &&not_equal, &&jump, &&jump_if_false, &&call, &&ret, &&halt};
    const Instruction *pc = &code[entry], *instruction;
    int64_t *sp = stack - 1, *base = stack;
    int depth = 0;
    int64_t count = 0;
#define NEXT do { instruction = pc++; count++; goto *labels[instruction->op]; } while (0)
    NEXT;
push: *++sp = instruction->argument; NEXT;
load: sp[1] = base[instruction->argument]; sp++; NEXT;
store: base[instruction->argument] = *sp--; NEXT;
add: sp--; sp[0] += sp[1]; NEXT;
subtract: sp--; sp[0] -= sp[1]; NEXT;
multiply: sp--; sp[0] *= sp[1]; NEXT;
remainder: sp--; sp[0] %= sp[1]; NEXT;
less: sp--; sp[0] = sp[0] < sp[1]; NEXT;
not_equal: sp--; sp[0] = sp[0] != sp[1]; NEXT;
jump: pc = &code[instruction->argument]; NEXT;
jump_if_false: if (*sp-- == 0) pc = &code[instruction->argument]; NEXT;
call: {
    const Function *f = &functions[instruction->argument];
    return_to[depth] = pc; bases[depth] = base; depth++;
    base = sp - f->parameters + 1;
    for (int64_t slot = f->parameters; slot < f->locals; slot++) base[slot] = 0;
    sp = base + f->locals - 1;
    pc = &code[f->entry];
    NEXT;
}
ret: {
    int64_t value = *sp;
    sp = base; *sp = value;
    depth--; pc = return_to[depth]; base = bases[depth];
    NEXT;
}
halt:
    executed = count;
    return *sp;
#undef NEXT
}

int main(int argc, char **argv) {
    int64_t n = atoll(argv[1]);
    assemble_main(); assemble_sum_squares(); assemble_gcd();
    int entry = emit(PUSH, n); emit(CALL, MAIN); op(HALT);
    int64_t result = run(entry);
    printf("result %lld\nexecuted %lld\n", (long long)result, (long long)executed);
    return 0;
}
