// Serial Rust peer for main.min: build a random expression tree, evaluate it eight times.
use std::io::Write;

const PASSES: i64 = 8;
const MODULUS: i64 = 2147483647;

fn mix(mut value: i64) -> i64 {
    for round in 0..3i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value & 0x7FFFFFFFFFFFFFFF
}

struct Tree { left: Vec<i64>, right: Vec<i64>, size: Vec<i64>, splits: i64 }
fn build(tree: &mut Tree, leaves: i64) -> i64 {
    let node = tree.left.len() as i64;
    tree.left.push(-1);
    tree.right.push(-1);
    tree.size.push(1);
    if leaves == 1 { return node; }
    let split = 1 + mix(tree.splits) % (leaves - 1);
    tree.splits += 1;
    let l = build(tree, split);
    let r = build(tree, leaves - split);
    tree.left[node as usize] = l;
    tree.right[node as usize] = r;
    tree.size[node as usize] = 1 + tree.size[l as usize] + tree.size[r as usize];
    node
}
fn combine(node: i64, a: i64, b: i64) -> i64 {
    let value = match mix(node) % 4 { 0 => (a + b) % MODULUS, 1 => a * b % MODULUS, 2 => (a ^ b) % MODULUS, _ => a.max(b) };
    (value + mix(value + node) % 1024) % MODULUS
}
fn evaluate(t: &Tree, node: i64, pass: i64) -> i64 {
    let n = node as usize;
    if t.left[n] < 0 { return mix(node + pass * 1000003) % MODULUS; }
    let a = evaluate(t, t.left[n], pass);
    let b = evaluate(t, t.right[n], pass);
    combine(node, a, b)
}

fn main() {
    let leaves: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let cap = 2 * leaves as usize;
    let mut tree = Tree { left: Vec::with_capacity(cap), right: Vec::with_capacity(cap), size: Vec::with_capacity(cap), splits: 0 };
    let root = build(&mut tree, leaves);
    let mut out = std::io::stdout().lock();
    writeln!(out, "nodes {}", tree.left.len()).unwrap();
    let mut digest = 0;
    for pass in 0..PASSES {
        let value = evaluate(&tree, root, pass);
        writeln!(out, "pass {} {}", pass, value).unwrap();
        digest = (digest * 31 + value) % MODULUS;
    }
    writeln!(out, "digest {}", digest).unwrap();
}
