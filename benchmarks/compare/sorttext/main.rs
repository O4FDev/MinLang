// Rust peer for main.min: unstable sorts of &str slices, Integers and (key, value) records.
use std::io::Write;

fn checksum(values: impl Iterator<Item = i64>) -> i64 {
    values.fold(0, |total, v| (total * 31 + v) % 1000000007)
}

fn main() {
    let text = std::fs::read_to_string(std::env::args().nth(1).unwrap()).unwrap();
    let mut words: Vec<&str> = Vec::new();
    let mut numbers: Vec<i64> = Vec::new();
    let mut items: Vec<(&str, i64)> = Vec::new();
    for line in text.split('\n') {
        if line.is_empty() { continue; }
        let (key, digits) = line.split_once(' ').unwrap();
        let value = digits.bytes().fold(0i64, |v, d| v * 10 + (d - b'0') as i64);
        words.push(key);
        numbers.push(value);
        items.push((key, value));
    }
    let n = words.len();
    let mut out = std::io::BufWriter::new(std::io::stdout().lock());
    let mut sorted = words.clone();
    sorted.sort_unstable();
    let distinct = (0..n).filter(|&i| i == 0 || sorted[i] != sorted[i - 1]).count();
    writeln!(out, "words {} distinct {} checksum {}", n, distinct, checksum(sorted.iter().map(|w| w.len() as i64))).unwrap();
    for w in &sorted[..3] { writeln!(out, "{}", w).unwrap(); }
    for w in &sorted[n - 3..] { writeln!(out, "{}", w).unwrap(); }
    numbers.sort_unstable();
    writeln!(out, "numbers min {} median {} max {} checksum {}", numbers[0], numbers[n / 2], numbers[n - 1], checksum(numbers.iter().copied())).unwrap();
    items.sort_unstable_by(|a, b| a.0.cmp(b.0).then(b.1.cmp(&a.1)));
    writeln!(out, "items checksum {}", checksum(items.iter().map(|i| i.1))).unwrap();
    for i in &items[..3] { writeln!(out, "{} {}", i.0, i.1).unwrap(); }
}
