// Rust peer for main.min: unstable sorts of row structs by value. Every
// comparator is a total order (id breaks ties), so stability does not matter.
struct Row { id: i64, score: i64, name: &'static str }

fn main() {
    const NAMES: [&str; 8] = ["ada", "bob", "cy", "dee", "eve", "fay", "gus", "hal"];
    let n: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut seed: i64 = 7;
    let mut rows = Vec::with_capacity(n);
    for i in 0..n {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        rows.push(Row { id: i as i64, score: (seed / 1024) % 1000, name: NAMES[((seed / 16) % 8) as usize] });
    }
    let by_score = |a: &Row, b: &Row| b.score.cmp(&a.score).then_with(|| a.name.cmp(b.name)).then_with(|| a.id.cmp(&b.id));
    for _ in 0..3 {
        rows.sort_unstable_by(by_score);
        rows.sort_unstable_by_key(|r| r.id);
    }
    let mut checksum: i64 = 0;
    for r in &rows { checksum = (checksum * 31 + r.score) % 1000000007; }
    rows.sort_unstable_by(by_score);
    for r in &rows[..100] { checksum = (checksum * 31 + r.id) % 1000000007; }
    println!("{}", checksum);
}
