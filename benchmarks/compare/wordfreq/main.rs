// Rust peer for main.min: word frequencies over a text file, top 10 words.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

// FNV-1a: the usual std-only replacement for SipHash on short keys.
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

fn main() {
    let path = std::env::args().nth(1).unwrap();
    let text = std::fs::read(path).unwrap();
    let mut counts: HashMap<&[u8], u64, BuildHasherDefault<Fnv>> = HashMap::default();
    counts.reserve(1 << 16);
    let mut total = 0u64;
    for word in text.split(|&b| b == b' ' || b == b'\n') {
        if word.is_empty() { continue; }
        total += 1;
        *counts.entry(word).or_insert(0) += 1;
    }
    let mut entries: Vec<(&[u8], u64)> = counts.into_iter().collect();
    entries.sort_unstable_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    let mut out = std::io::stdout().lock();
    writeln!(out, "{}\n{}", total, entries.len()).unwrap();
    for (word, count) in &entries[..10] {
        out.write_all(word).unwrap();
        writeln!(out, " {}", count).unwrap();
    }
}
