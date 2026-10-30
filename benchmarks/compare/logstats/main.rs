// Rust peer for main.min: parse CSV log lines and aggregate per service.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

#[derive(Default)]
struct Fnv(u64);
impl Hasher for Fnv {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, bytes: &[u8]) {
        let mut h = if self.0 == 0 { 0xcbf29ce484222325 } else { self.0 };
        for &b in bytes { h ^= b as u64; h = h.wrapping_mul(0x100000001b3); }
        self.0 = h;
    }
}

#[derive(Default)]
struct Stats { count: i64, total: i64, slowest: i64, errors: i64 }

fn to_int(s: &[u8]) -> i64 {
    let (negative, digits) = if s.first() == Some(&b'-') { (true, &s[1..]) } else { (false, s) };
    let v = digits.iter().fold(0i64, |v, &d| v * 10 + (d - b'0') as i64);
    if negative { -v } else { v }
}

fn main() {
    let text = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut services: HashMap<&[u8], Stats, BuildHasherDefault<Fnv>> = HashMap::default();
    let mut warnings = 0i64;
    for line in text.split(|&b| b == b'\n') {
        if line.is_empty() { continue; }
        let mut fields = line.splitn(5, |&b| b == b',');
        let (_, level, name) = (fields.next(), fields.next().unwrap(), fields.next().unwrap());
        let latency = to_int(fields.next().unwrap());
        let status = to_int(fields.next().unwrap());
        if level == b"WARN" { warnings += 1; }
        let s = services.entry(name).or_default();
        s.count += 1;
        s.total += latency;
        if latency > s.slowest { s.slowest = latency; }
        if status >= 500 { s.errors += 1; }
    }
    let mut sorted: Vec<_> = services.into_iter().collect();
    sorted.sort_unstable_by(|a, b| a.0.cmp(b.0));
    let mut out = std::io::stdout().lock();
    writeln!(out, "{}", warnings).unwrap();
    for (name, s) in &sorted {
        out.write_all(name).unwrap();
        writeln!(out, " {} {} {} {}", s.count, s.total / s.count, s.slowest, s.errors).unwrap();
    }
}
