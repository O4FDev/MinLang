// Rust peer for main.min: the same assembler and bytecode, interpreted with a
// match over a flat Vec of instructions.
use std::io::Write;

#[derive(Clone, Copy)]
#[allow(dead_code)]
enum Op { Push, Load, Store, Add, Subtract, Multiply, Remainder, Less, NotEqual, Jump, JumpIfFalse, Call, Return, Halt }

#[derive(Clone, Copy)]
struct Instruction { op: Op, argument: i64 }
struct Function { entry: usize, parameters: usize, locals: usize }

#[derive(Default)]
struct Assembler { code: Vec<Instruction>, functions: Vec<Function> }

impl Assembler {
    fn emit(&mut self, op: Op, argument: i64) -> usize { self.code.push(Instruction { op, argument }); self.code.len() - 1 }
    fn op(&mut self, op: Op) { self.emit(op, 0); }
    fn here(&self) -> usize { self.code.len() }
    fn patch(&mut self, at: usize, target: usize) { self.code[at].argument = target as i64; }
    fn begin(&mut self, parameters: usize, locals: usize) { let entry = self.here(); self.functions.push(Function { entry, parameters, locals }); }
}

const MAIN: i64 = 0;
const SUM_SQUARES: i64 = 1;
const GCD: i64 = 2;

fn assemble_main(a: &mut Assembler) {
    use Op::*;
    a.begin(1, 3);
    a.emit(Push, 0); a.emit(Store, 1); a.emit(Push, 0); a.emit(Store, 2);
    let top = a.here() as i64;
    a.emit(Load, 2); a.emit(Load, 0); a.op(Less);
    let exit = a.emit(JumpIfFalse, 0);
    a.emit(Load, 1); a.emit(Load, 2); a.emit(Push, 64); a.op(Remainder); a.emit(Call, SUM_SQUARES); a.op(Add);
    a.emit(Load, 2); a.emit(Push, 360); a.emit(Call, GCD); a.op(Add);
    a.emit(Push, 1000000007); a.op(Remainder); a.emit(Store, 1);
    a.emit(Load, 2); a.emit(Push, 1); a.op(Add); a.emit(Store, 2);
    a.emit(Jump, top);
    let here = a.here(); a.patch(exit, here);
    a.emit(Load, 1); a.op(Return);
}

fn assemble_sum_squares(a: &mut Assembler) {
    use Op::*;
    a.begin(1, 3);
    a.emit(Push, 0); a.emit(Store, 1); a.emit(Push, 0); a.emit(Store, 2);
    let top = a.here() as i64;
    a.emit(Load, 2); a.emit(Load, 0); a.op(Less);
    let exit = a.emit(JumpIfFalse, 0);
    a.emit(Load, 1); a.emit(Load, 2); a.emit(Load, 2); a.op(Multiply); a.emit(Push, 7); a.op(Remainder); a.op(Add); a.emit(Store, 1);
    a.emit(Load, 2); a.emit(Push, 1); a.op(Add); a.emit(Store, 2);
    a.emit(Jump, top);
    let here = a.here(); a.patch(exit, here);
    a.emit(Load, 1); a.op(Return);
}

fn assemble_gcd(a: &mut Assembler) {
    use Op::*;
    a.begin(2, 3);
    let top = a.here() as i64;
    a.emit(Load, 1); a.emit(Push, 0); a.op(NotEqual);
    let exit = a.emit(JumpIfFalse, 0);
    a.emit(Load, 0); a.emit(Load, 1); a.op(Remainder); a.emit(Store, 2);
    a.emit(Load, 1); a.emit(Store, 0); a.emit(Load, 2); a.emit(Store, 1);
    a.emit(Jump, top);
    let here = a.here(); a.patch(exit, here);
    a.emit(Load, 0); a.op(Return);
}

fn run(code: &[Instruction], functions: &[Function], entry: usize, executed: &mut i64) -> i64 {
    let mut stack = [0i64; 1024];
    let mut return_to = [0usize; 64];
    let mut bases = [0usize; 64];
    let (mut pc, mut sp, mut base, mut depth) = (entry, 0usize, 0usize, 0usize);
    // sp is one past the top of the stack.
    let mut count = 0i64;
    loop {
        let instruction = code[pc];
        pc += 1;
        count += 1;
        match instruction.op {
            Op::Push => { stack[sp] = instruction.argument; sp += 1; }
            Op::Load => { stack[sp] = stack[base + instruction.argument as usize]; sp += 1; }
            Op::Store => { sp -= 1; stack[base + instruction.argument as usize] = stack[sp]; }
            Op::Add => { sp -= 1; stack[sp - 1] += stack[sp]; }
            Op::Subtract => { sp -= 1; stack[sp - 1] -= stack[sp]; }
            Op::Multiply => { sp -= 1; stack[sp - 1] *= stack[sp]; }
            Op::Remainder => { sp -= 1; stack[sp - 1] %= stack[sp]; }
            Op::Less => { sp -= 1; stack[sp - 1] = (stack[sp - 1] < stack[sp]) as i64; }
            Op::NotEqual => { sp -= 1; stack[sp - 1] = (stack[sp - 1] != stack[sp]) as i64; }
            Op::Jump => pc = instruction.argument as usize,
            Op::JumpIfFalse => { sp -= 1; if stack[sp] == 0 { pc = instruction.argument as usize; } }
            Op::Call => {
                let f = &functions[instruction.argument as usize];
                return_to[depth] = pc; bases[depth] = base; depth += 1;
                base = sp - f.parameters;
                for slot in f.parameters..f.locals { stack[base + slot] = 0; }
                sp = base + f.locals;
                pc = f.entry;
            }
            Op::Return => {
                let value = stack[sp - 1];
                stack[base] = value;
                sp = base + 1;
                depth -= 1; pc = return_to[depth]; base = bases[depth];
            }
            Op::Halt => { *executed = count; return stack[sp - 1]; }
        }
    }
}

fn main() {
    let n: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut a = Assembler::default();
    assemble_main(&mut a); assemble_sum_squares(&mut a); assemble_gcd(&mut a);
    let entry = a.emit(Op::Push, n); a.emit(Op::Call, MAIN); a.op(Op::Halt);
    let mut executed = 0;
    let result = run(&a.code, &a.functions, entry, &mut executed);
    let mut out = std::io::stdout().lock();
    writeln!(out, "result {}\nexecuted {}", result, executed).unwrap();
}
