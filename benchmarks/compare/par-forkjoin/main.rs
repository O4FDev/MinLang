// Rust peer for main.min: the same fork-join on a hand-written, std-only
// work-stealing pool (rayon-style join: Chase-Lev deques, 4 threads including
// the caller, stack tasks, help-while-waiting).
use std::cell::Cell;
use std::sync::atomic::{fence, AtomicBool, AtomicI32, AtomicI64, AtomicPtr, Ordering::*};
use std::io::Write;

const THREADS: usize = 4;
const SIZE: usize = 4096;
const CUTOFF: i64 = 25;
const LEAF: usize = 4096;

struct Task { run: unsafe fn(*mut u8), arg: *mut u8, done: AtomicI32 }
#[repr(align(64))] struct Padded(AtomicI64);
struct Deque { top: Padded, bottom: Padded, slots: Vec<AtomicPtr<Task>> }
static DEQUES: std::sync::OnceLock<Vec<Deque>> = std::sync::OnceLock::new();
static ACTIVE: AtomicBool = AtomicBool::new(true);
thread_local! { static SELF: Cell<usize> = const { Cell::new(0) }; }

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
    for k in 1..THREADS {
        let t = steal(deque((me + k) % THREADS));
        if !t.is_null() { unsafe { execute(t) }; return true; }
    }
    false
}
fn idle(n: &mut u32) { *n += 1; if *n < 64 { std::hint::spin_loop(); } else { std::thread::yield_now(); } }

unsafe fn call<A: FnOnce()>(arg: *mut u8) { let f = (arg as *mut Option<A>).as_mut().unwrap().take().unwrap(); f(); }
fn join<A: FnOnce() + Send, B: FnOnce() + Send>(a: A, b: B) {
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

fn fib_serial(n: i64) -> i64 { if n < 2 { n } else { fib_serial(n - 1) + fib_serial(n - 2) } }
fn fib(n: i64) -> i64 {
    if n < CUTOFF { return fib_serial(n); }
    let (mut l, mut r) = (0, 0);
    join(|| l = fib(n - 1), || r = fib(n - 2));
    l + r
}
fn mix(mut value: i64) -> i64 {
    for round in 0..4i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value
}
fn total(values: &[i64]) -> i64 {
    if values.len() <= LEAF { return values.iter().sum(); }
    let (low, high) = values.split_at(values.len() / 2);
    let (mut l, mut r) = (0, 0);
    join(|| l = total(low), || r = total(high));
    l + r
}

fn main() {
    let n: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    DEQUES.set((0..THREADS).map(|_| Deque { top: Padded(AtomicI64::new(0)), bottom: Padded(AtomicI64::new(0)),
        slots: (0..SIZE).map(|_| AtomicPtr::new(std::ptr::null_mut())).collect() }).collect()).ok().unwrap();
    let threads: Vec<_> = (1..THREADS).map(|k| std::thread::spawn(move || worker(k))).collect();
    let mut out = std::io::stdout().lock();
    writeln!(out, "fib {} {}", n, fib(n)).unwrap();
    let count = n as usize * 262144;
    let values: Vec<i64> = (0..count as i64).map(|i| (mix(i) >> 40) & 65535).collect();
    writeln!(out, "sum {} {}", count, total(&values)).unwrap();
    ACTIVE.store(false, Release);
    for t in threads { t.join().unwrap(); }
}
