// Parallel Rust peer for main.min: the same tree evaluated with a hand-written,
// std-only rayon-style join (Chase-Lev deques, MINYAR_PARALLEL_THREADS threads
// including the caller, stack tasks, help-while-waiting), same cutoff.
use std::cell::Cell;
use std::io::Write;
use std::sync::atomic::{fence, AtomicBool, AtomicI32, AtomicI64, AtomicPtr, Ordering::*};

const SIZE: usize = 4096;
const PASSES: i64 = 8;
const MODULUS: i64 = 2147483647;
const CUTOFF: i64 = 4096;

struct Task { run: unsafe fn(*mut u8), arg: *mut u8, done: AtomicI32 }
#[repr(align(64))] struct Padded(AtomicI64);
struct Deque { top: Padded, bottom: Padded, slots: Vec<AtomicPtr<Task>> }
static DEQUES: std::sync::OnceLock<Vec<Deque>> = std::sync::OnceLock::new();
static ACTIVE: AtomicBool = AtomicBool::new(true);
thread_local! { static SELF: Cell<usize> = const { Cell::new(0) }; }

fn threads() -> usize { DEQUES.get().unwrap().len() }
fn deque(k: usize) -> &'static Deque { &DEQUES.get().unwrap()[k] }
fn push(d: &Deque, t: *mut Task) -> bool {
    let b = d.bottom.0.load(Relaxed);
    let top = d.top.0.load(Acquire);
    if b - top >= SIZE as i64 { return false; }
    d.slots[(b as usize) & (SIZE - 1)].store(t, Relaxed);
    d.bottom.0.store(b + 1, Release);
    true
}
fn pop(d: &Deque) -> *mut Task {
    let b = d.bottom.0.load(Relaxed) - 1;
    d.bottom.0.store(b, Relaxed);
    fence(SeqCst);
    let t = d.top.0.load(Relaxed);
    let mut x = std::ptr::null_mut();
    if t <= b {
        x = d.slots[(b as usize) & (SIZE - 1)].load(Relaxed);
        if t == b {
            if d.top.0.compare_exchange(t, t + 1, SeqCst, Relaxed).is_err() { x = std::ptr::null_mut(); }
            d.bottom.0.store(b + 1, Relaxed);
        }
    } else { d.bottom.0.store(b + 1, Relaxed); }
    x
}
fn steal(d: &Deque) -> *mut Task {
    let t = d.top.0.load(Acquire);
    fence(SeqCst);
    let b = d.bottom.0.load(Acquire);
    if t >= b { return std::ptr::null_mut(); }
    let x = d.slots[(t as usize) & (SIZE - 1)].load(Relaxed);
    if d.top.0.compare_exchange(t, t + 1, SeqCst, Relaxed).is_err() { return std::ptr::null_mut(); }
    x
}
unsafe fn execute(t: *mut Task) { ((*t).run)((*t).arg); (*t).done.store(1, Release); }
fn steal_once(me: usize) -> bool {
    let n = threads();
    for k in 1..n {
        let t = steal(deque((me + k) % n));
        if !t.is_null() { unsafe { execute(t) }; return true; }
    }
    false
}
fn idle(n: &mut u32) { *n += 1; if *n < 64 { std::hint::spin_loop(); } else { std::thread::yield_now(); } }

unsafe fn call<A: FnOnce()>(arg: *mut u8) { let f = (arg as *mut Option<A>).as_mut().unwrap().take().unwrap(); f(); }
fn join<A: FnOnce() + Send, B: FnOnce() + Send>(a: A, b: B) {
    if threads() == 1 { a(); b(); return; }
    let me = SELF.with(|s| s.get());
    let mut b = Some(b);
    let mut task = Task { run: call::<B>, arg: &mut b as *mut Option<B> as *mut u8, done: AtomicI32::new(0) };
    let pointer = &mut task as *mut Task;
    if !push(deque(me), pointer) { a(); (b.take().unwrap())(); return; }
    a();
    let p = pop(deque(me));
    if p == pointer { (b.take().unwrap())(); return; }
    if !p.is_null() { push(deque(me), p); }
    let mut n = 0;
    while task.done.load(Acquire) == 0 { if steal_once(me) { n = 0; } else { idle(&mut n); } }
}
fn worker(k: usize) {
    SELF.with(|s| s.set(k));
    let mut n = 0;
    while ACTIVE.load(Acquire) {
        let t = pop(deque(k));
        if !t.is_null() { unsafe { execute(t) }; n = 0; continue; }
        if steal_once(k) { n = 0; } else { idle(&mut n); }
    }
}

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
fn serial(t: &Tree, node: i64, pass: i64) -> i64 {
    let n = node as usize;
    if t.left[n] < 0 { return mix(node + pass * 1000003) % MODULUS; }
    let a = serial(t, t.left[n], pass);
    let b = serial(t, t.right[n], pass);
    combine(node, a, b)
}
fn evaluate(t: &Tree, node: i64, pass: i64) -> i64 {
    let n = node as usize;
    if t.size[n] < CUTOFF { return serial(t, node, pass); }
    let (mut a, mut b) = (0, 0);
    join(|| a = evaluate(t, t.left[n], pass), || b = evaluate(t, t.right[n], pass));
    combine(node, a, b)
}

fn main() {
    let leaves: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let n: usize = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).max(1);
    DEQUES.set((0..n).map(|_| Deque { top: Padded(AtomicI64::new(0)), bottom: Padded(AtomicI64::new(0)),
        slots: (0..SIZE).map(|_| AtomicPtr::new(std::ptr::null_mut())).collect() }).collect()).ok().unwrap();
    let workers: Vec<_> = (1..n).map(|k| std::thread::spawn(move || worker(k))).collect();
    let mut out = std::io::stdout().lock();
    let mut tree = Tree { left: Vec::new(), right: Vec::new(), size: Vec::new(), splits: 0 };
    let root = build(&mut tree, leaves);
    writeln!(out, "nodes {}", tree.left.len()).unwrap();
    let mut digest = 0;
    for pass in 0..PASSES {
        let value = evaluate(&tree, root, pass);
        writeln!(out, "pass {} {}", pass, value).unwrap();
        digest = (digest * 31 + value) % MODULUS;
    }
    writeln!(out, "digest {}", digest).unwrap();
    ACTIVE.store(false, Release);
    for w in workers { w.join().unwrap(); }
}
