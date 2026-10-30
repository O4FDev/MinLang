// Rust peer for main.min: the same AST (boxed enums, variables resolved to
// frame slots), interpreted recursively; frames on the stack.
use std::io::Write;

#[derive(Clone, Copy)]
#[allow(dead_code)]
enum Operator { Add, Subtract, Multiply, Divide, Remainder, Less, LessEqual, Equal, NotEqual }

enum Expr {
    Number(i64),
    Local(usize),
    Binary(Operator, Box<Expr>, Box<Expr>),
    Call(usize, Vec<Expr>),
}

enum Stmt {
    Assign(usize, Expr),
    If(Expr, Vec<Stmt>, Vec<Stmt>),
    While(Expr, Vec<Stmt>),
    Return(Expr),
}

#[allow(dead_code)]
struct Function { name: &'static str, parameters: usize, locals: usize, body: Vec<Stmt> }

const IS_PRIME: usize = 0;
const COUNT_PRIMES: usize = 1;
const FIB: usize = 2;
const FIB_SUM: usize = 3;

fn number(v: i64) -> Expr { Expr::Number(v) }
fn local(slot: usize) -> Expr { Expr::Local(slot) }
fn binary(op: Operator, l: Expr, r: Expr) -> Expr { Expr::Binary(op, Box::new(l), Box::new(r)) }
fn call(f: usize, argument: Expr) -> Expr { Expr::Call(f, vec![argument]) }

struct Interpreter<'a> { functions: &'a [Function], calls: i64 }

impl<'a> Interpreter<'a> {
    fn evaluate(&mut self, e: &Expr, frame: &[i64; 8]) -> i64 {
        match e {
            Expr::Number(v) => *v,
            Expr::Local(slot) => frame[*slot],
            Expr::Call(f, arguments) => self.call(*f, arguments, frame),
            Expr::Binary(op, l, r) => {
                let (l, r) = (self.evaluate(l, frame), self.evaluate(r, frame));
                match op {
                    Operator::Add => l + r,
                    Operator::Subtract => l - r,
                    Operator::Multiply => l * r,
                    Operator::Divide => l / r,
                    Operator::Remainder => l % r,
                    Operator::Less => (l < r) as i64,
                    Operator::LessEqual => (l <= r) as i64,
                    Operator::Equal => (l == r) as i64,
                    Operator::NotEqual => (l != r) as i64,
                }
            }
        }
    }

    fn execute(&mut self, block: &[Stmt], frame: &mut [i64; 8]) -> Option<i64> {
        for s in block {
            match s {
                Stmt::Assign(slot, v) => frame[*slot] = self.evaluate(v, frame),
                Stmt::If(c, then, otherwise) => {
                    let branch = if self.evaluate(c, frame) != 0 { then } else { otherwise };
                    if let Some(v) = self.execute(branch, frame) { return Some(v); }
                }
                Stmt::While(c, body) => {
                    while self.evaluate(c, frame) != 0 {
                        if let Some(v) = self.execute(body, frame) { return Some(v); }
                    }
                }
                Stmt::Return(v) => return Some(self.evaluate(v, frame)),
            }
        }
        None
    }

    fn call(&mut self, index: usize, arguments: &[Expr], caller: &[i64; 8]) -> i64 {
        let mut frame = [0i64; 8];
        for (i, a) in arguments.iter().enumerate() { frame[i] = self.evaluate(a, caller); }
        self.calls += 1;
        let functions = self.functions;
        self.execute(&functions[index].body, &mut frame).unwrap_or(0)
    }
}

fn main() {
    use Operator::*;
    let n: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let functions = vec![
        Function { name: "isPrime", parameters: 1, locals: 2, body: vec![
            Stmt::If(binary(Less, local(0), number(2)), vec![Stmt::Return(number(0))], vec![]),
            Stmt::Assign(1, number(2)),
            Stmt::While(binary(LessEqual, binary(Multiply, local(1), local(1)), local(0)), vec![
                Stmt::If(binary(Equal, binary(Remainder, local(0), local(1)), number(0)), vec![Stmt::Return(number(0))], vec![]),
                Stmt::Assign(1, binary(Add, local(1), number(1))),
            ]),
            Stmt::Return(number(1)),
        ] },
        Function { name: "countPrimes", parameters: 1, locals: 3, body: vec![
            Stmt::Assign(1, number(0)),
            Stmt::Assign(2, number(0)),
            Stmt::While(binary(Less, local(2), local(0)), vec![
                Stmt::Assign(1, binary(Add, local(1), call(IS_PRIME, local(2)))),
                Stmt::Assign(2, binary(Add, local(2), number(1))),
            ]),
            Stmt::Return(local(1)),
        ] },
        Function { name: "fib", parameters: 1, locals: 1, body: vec![
            Stmt::If(binary(Less, local(0), number(2)), vec![Stmt::Return(local(0))], vec![]),
            Stmt::Return(binary(Add, call(FIB, binary(Subtract, local(0), number(1))), call(FIB, binary(Subtract, local(0), number(2))))),
        ] },
        Function { name: "fibSum", parameters: 1, locals: 3, body: vec![
            Stmt::Assign(1, number(0)),
            Stmt::Assign(2, number(0)),
            Stmt::While(binary(Less, local(2), local(0)), vec![
                Stmt::Assign(1, binary(Add, local(1), call(FIB, binary(Add, number(12), binary(Remainder, local(2), number(8)))))),
                Stmt::Assign(2, binary(Add, local(2), number(1))),
            ]),
            Stmt::Return(local(1)),
        ] },
    ];
    let mut interpreter = Interpreter { functions: &functions, calls: 0 };
    let none = [0i64; 8];
    let primes = interpreter.call(COUNT_PRIMES, &[number(n)], &none);
    let fibs = interpreter.call(FIB_SUM, &[number(n / 100)], &none);
    let mut out = std::io::stdout().lock();
    writeln!(out, "primes below {}: {}\nfib sum {}: {}\ncalls {}", n, primes, n / 100, fibs, interpreter.calls).unwrap();
}
