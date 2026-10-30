// Rust peer for main.min: records in a Vec, filtered, grouped and ranked.
use std::io::Write;

struct Order { id: i64, customer: i64, region: i64, price: i64, quantity: i64, discount: i64 }

fn main() {
    let count: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut seed: i64 = 12345;
    let mut orders = Vec::with_capacity(count as usize);
    for i in 0..count {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        let price = 100 + (seed / 64) % 9900;
        seed = (seed * 1103515245 + 12345) % 2147483648;
        orders.push(Order { id: i, customer: (seed / 16) % 50000, region: (seed / 8) % 16, price, quantity: 1 + (seed / 256) % 7, discount: (seed / 7) % 500 });
    }
    let mut checksum: i64 = 0;
    for pass in 0..20 {
        let mut regions = [0i64; 16];
        let mut large = 0i64;
        for o in &orders {
            let total = o.price * o.quantity - o.discount;
            if total > 5000 + pass * 100 { regions[o.region as usize] += total; large += 1; }
        }
        for r in regions { checksum = (checksum * 31 + r) % 1000000007; }
        checksum = (checksum + large) % 1000000007;
    }
    let mut ranked: Vec<(i64, i64)> = orders.iter().filter(|o| o.customer % 10 == 0)
        .map(|o| (o.id, o.price * o.quantity - o.discount)).collect();
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    for r in &ranked[..100] { checksum = (checksum * 31 + r.0) % 1000000007; }
    let mut out = std::io::stdout().lock();
    writeln!(out, "{}\n{}", ranked.len(), checksum).unwrap();
}
