// Serial Rust peer for main.min: build N sales, six passes of three grouped aggregations.
use std::io::Write;

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

fn main() {
    let count: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let sales: Vec<Sale> = (0..count).map(|i| {
        let (a, b) = (mix(i * 2), mix(i * 2 + 1));
        Sale { _customer: a % 100000, product: (a >> 20) % 512, region: (a >> 32) % 16, month: (a >> 40) % 12,
               quantity: 1 + b % 9, price: 100 + (b >> 8) % 20000, discount: (b >> 30) % 30 }
    }).collect();
    let mut out = std::io::stdout().lock();
    let mut digest = 0i64;
    for pass in 0..PASSES {
        let (minimum, skip, threshold) = (1 + pass % 3, pass % 12, 100000 + pass * 10000);
        let (mut revenue, mut units, mut large) = ([0i64; 192], [0i64; 512], 0i64);
        for x in &sales {
            let net = x.price * x.quantity * (100 - x.discount) / 100;
            if x.quantity >= minimum { revenue[(x.region * 12 + x.month) as usize] += net; }
            if x.month != skip { units[x.product as usize] += x.quantity; }
            if net > threshold { large += 1; }
        }
        for v in revenue { digest = (digest * 31 + v) % MODULUS; }
        for v in units { digest = (digest * 31 + v) % MODULUS; }
        digest = (digest * 31 + large) % MODULUS;
        writeln!(out, "pass {} large {}", pass, large).unwrap();
    }
    writeln!(out, "digest {}", digest).unwrap();
}
