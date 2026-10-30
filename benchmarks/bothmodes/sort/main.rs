// Serial Rust peer for main.min: sort N 40-bit keys with sort_unstable and print the same summary.
use std::io::Write;

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
    let count: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut keys: Vec<i64> = (0..count as i64).map(|i| mix(i) & 0xFFFFFFFFFF).collect();
    keys.sort_unstable();
    let mut checksum = 0i64;
    let mut disorder = 0;
    for i in 0..count {
        checksum = checksum.wrapping_add(keys[i].wrapping_mul(i as i64 + 1));
        if i > 0 && keys[i - 1] > keys[i] { disorder += 1; }
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "count {} disorder {}", count, disorder).unwrap();
    writeln!(out, "first {} middle {} last {}", keys[0], keys[count / 2], keys[count - 1]).unwrap();
    writeln!(out, "checksum {}", checksum).unwrap();
}
