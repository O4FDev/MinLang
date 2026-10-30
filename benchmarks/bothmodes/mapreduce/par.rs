// Parallel Rust peer for main.min (std only): MINYAR_PARALLEL_THREADS scoped
// threads build the sales in parallel slices, then every pass aggregates one
// contiguous slice per thread into private counters, merged in thread order.
use std::io::Write;

#[derive(Clone, Copy, Default)]
struct Sale { _customer: i64, product: i64, region: i64, month: i64, quantity: i64, price: i64, discount: i64 }
const PASSES: i64 = 6;
const MODULUS: i64 = 1000000007;

fn mix(mut value: i64) -> i64 {
    for round in 0..3i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value & 0x7FFFFFFFFFFFFFFF
}
fn sale(i: i64) -> Sale {
    let (a, b) = (mix(i * 2), mix(i * 2 + 1));
    Sale { _customer: a % 100000, product: (a >> 20) % 512, region: (a >> 32) % 16, month: (a >> 40) % 12,
           quantity: 1 + b % 9, price: 100 + (b >> 8) % 20000, discount: (b >> 30) % 30 }
}

fn main() {
    let count: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let threads: usize = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).max(1);
    let per = (count + threads - 1) / threads;
    let mut sales = vec![Sale::default(); count];
    std::thread::scope(|s| {
        for (t, part) in sales.chunks_mut(per.max(1)).enumerate() {
            s.spawn(move || for (k, slot) in part.iter_mut().enumerate() { *slot = sale((t * per + k) as i64); });
        }
    });
    let mut out = std::io::stdout().lock();
    let mut digest = 0i64;
    for pass in 0..PASSES {
        let (minimum, skip, threshold) = (1 + pass % 3, pass % 12, 100000 + pass * 10000);
        let parts: Vec<(Vec<i64>, Vec<i64>, i64)> = std::thread::scope(|s| {
            let handles: Vec<_> = sales.chunks(per.max(1)).map(|part| s.spawn(move || {
                let (mut revenue, mut units, mut large) = (vec![0i64; 192], vec![0i64; 512], 0i64);
                for x in part {
                    let net = x.price * x.quantity * (100 - x.discount) / 100;
                    if x.quantity >= minimum { revenue[(x.region * 12 + x.month) as usize] += net; }
                    if x.month != skip { units[x.product as usize] += x.quantity; }
                    if net > threshold { large += 1; }
                }
                (revenue, units, large)
            })).collect();
            handles.into_iter().map(|h| h.join().unwrap()).collect()
        });
        let (mut revenue, mut units, mut large) = (vec![0i64; 192], vec![0i64; 512], 0i64);
        for (r, u, l) in &parts {
            for k in 0..192 { revenue[k] += r[k]; }
            for k in 0..512 { units[k] += u[k]; }
            large += l;
        }
        for k in 0..192 { digest = (digest * 31 + revenue[k]) % MODULUS; }
        for k in 0..512 { digest = (digest * 31 + units[k]) % MODULUS; }
        digest = (digest * 31 + large) % MODULUS;
        writeln!(out, "pass {} large {}", pass, large).unwrap();
    }
    writeln!(out, "digest {}", digest).unwrap();
}
