// Rust peer for main.min: recursive descent into a Vec-backed tree, then evaluate.
use std::io::Write;

#[derive(Clone, Copy)]
enum Node {
    Number(i64),
    Negate(u32),
    Binary(u8, u32, u32),
    Compare(u8, u32, u32),
}

struct Parser<'a> {
    text: &'a [u8],
    position: usize,
    line: usize,
    nodes: &'a mut Vec<Node>,
}

impl<'a> Parser<'a> {
    fn peek(&mut self) -> u8 {
        while self.position < self.text.len() && self.text[self.position] == b' ' { self.position += 1; }
        if self.position < self.text.len() { self.text[self.position] } else { b'\n' }
    }
    fn fail<T>(&self, expected: &str) -> Result<T, String> {
        Err(format!("line {}: expected {} at column {}", self.line, expected, self.position + 1))
    }
    fn add(&mut self, node: Node) -> u32 { self.nodes.push(node); (self.nodes.len() - 1) as u32 }
    fn expression(&mut self) -> Result<u32, String> {
        let left = self.sum()?;
        let c = self.peek();
        if matches!(c, b'<' | b'>' | b'=' | b'!') {
            let two = self.position + 1 < self.text.len() && self.text[self.position + 1] == b'=';
            if !two && (c == b'=' || c == b'!') { return self.fail("a comparison"); }
            let op = match (c, two) { (b'<', false) => 0, (b'>', false) => 1, (b'<', true) => 2, (b'>', true) => 3, (b'=', _) => 4, _ => 5 };
            self.position += if two { 2 } else { 1 };
            let right = self.sum()?;
            return Ok(self.add(Node::Compare(op, left, right)));
        }
        Ok(left)
    }
    fn sum(&mut self) -> Result<u32, String> {
        let mut left = self.term()?;
        loop {
            let c = self.peek();
            if c != b'+' && c != b'-' { return Ok(left); }
            self.position += 1;
            let right = self.term()?;
            left = self.add(Node::Binary(c, left, right));
        }
    }
    fn term(&mut self) -> Result<u32, String> {
        let mut left = self.unary()?;
        loop {
            let c = self.peek();
            if c != b'*' && c != b'/' && c != b'%' { return Ok(left); }
            self.position += 1;
            let right = self.unary()?;
            left = self.add(Node::Binary(c, left, right));
        }
    }
    fn unary(&mut self) -> Result<u32, String> {
        if self.peek() == b'-' {
            self.position += 1;
            let operand = self.unary()?;
            return Ok(self.add(Node::Negate(operand)));
        }
        self.primary()
    }
    fn primary(&mut self) -> Result<u32, String> {
        let c = self.peek();
        if c.is_ascii_digit() {
            let mut v = 0i64;
            while self.position < self.text.len() && self.text[self.position].is_ascii_digit() {
                v = v * 10 + (self.text[self.position] - b'0') as i64;
                self.position += 1;
            }
            return Ok(self.add(Node::Number(v)));
        }
        if c == b'(' {
            self.position += 1;
            let inner = self.expression()?;
            if self.peek() != b')' { return self.fail("')'"); }
            self.position += 1;
            return Ok(inner);
        }
        self.fail("a number")
    }
}

fn evaluate(nodes: &[Node], index: u32) -> Option<i64> {
    Some(match nodes[index as usize] {
        Node::Number(v) => v,
        Node::Negate(operand) => -evaluate(nodes, operand)?,
        Node::Binary(op, l, r) => {
            let a = evaluate(nodes, l)?;
            let b = evaluate(nodes, r)?;
            match op {
                b'+' => a + b,
                b'-' => a - b,
                b'*' => a * b,
                _ if b == 0 => return None,
                b'/' => a / b,
                _ => a % b,
            }
        }
        Node::Compare(op, l, r) => {
            let a = evaluate(nodes, l)?;
            let b = evaluate(nodes, r)?;
            (match op { 0 => a < b, 1 => a > b, 2 => a <= b, 3 => a >= b, 4 => a == b, _ => a != b }) as i64
        }
    })
}

fn main() {
    let src = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut nodes: Vec<Node> = Vec::with_capacity(1024);
    let (mut evaluated, mut division_errors, mut syntax_errors, mut comparisons_true, mut total_nodes, mut total) = (0i64, 0i64, 0i64, 0i64, 0i64, 0i64);
    let mut messages: Vec<String> = Vec::new();
    for (index, text) in src.split(|&b| b == b'\n').enumerate() {
        let line = index + 1;
        if text.is_empty() { continue; }
        nodes.clear();
        let mut parser = Parser { text, position: 0, line, nodes: &mut nodes };
        let root = parser.expression().and_then(|root| if parser.peek() != b'\n' { parser.fail("the end of the line") } else { Ok(root) });
        let root = match root {
            Ok(root) => root,
            Err(message) => {
                syntax_errors += 1;
                if messages.len() < 6 { messages.push(message); }
                continue;
            }
        };
        total_nodes += nodes.len() as i64;
        match evaluate(&nodes, root) {
            Some(value) => {
                evaluated += 1;
                total = (total + value % 1000000007) % 1000000007;
                if let Node::Compare(..) = nodes[root as usize] { comparisons_true += value; }
            }
            None => {
                division_errors += 1;
                if messages.len() < 6 { messages.push(format!("line {}: division by zero", line)); }
            }
        }
    }
    let mut out = std::io::BufWriter::new(std::io::stdout().lock());
    writeln!(out, "evaluated {}\ndivision errors {}\nsyntax errors {}\ntrue comparisons {}\nnodes {}\ntotal {}",
             evaluated, division_errors, syntax_errors, comparisons_true, total_nodes, total).unwrap();
    for m in &messages { writeln!(out, "{}", m).unwrap(); }
}
