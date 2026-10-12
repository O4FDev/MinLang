use std::collections::HashMap;
use std::time::Instant;
fn main() {
    let n: usize = COUNT;
    let keys: Vec<KEY_TYPE> = (0..n).map(|i| KEY_EXPR).collect();
    let queries: Vec<KEY_TYPE> = (0..n).map(|i| KEY_EXPR).collect();
    let mut m = HashMap::new();
    let start = Instant::now();
    for i in 0..n { m.insert(KEY_INSERT, i as i64 * 3 + 1); }
    let inserted = start.elapsed().as_nanos();
    let start = Instant::now();
    let mut sum: i64 = 0;
    for i in 0..n { let k = i * 104729 % n; sum += m[KEY_LOOKUP]; }
    let looked = start.elapsed().as_nanos();
    let start = Instant::now();
    for i in 0..n {
        let k = i * 104729 % n;
        if i % 2 == 0 { let v = m[KEY_LOOKUP]; m.insert(KEY_MIX_INSERT, v + 5); }
        else { assert!(m.remove(KEY_LOOKUP).is_some()); m.insert(KEY_MIX_INSERT, k as i64 * 3 + 2); }
    }
    let mixed = start.elapsed().as_nanos();
    let start = Instant::now();
    for i in 0..n { let k = i * 104729 % n; assert!(m.remove(KEY_LOOKUP).is_some()); }
    let removed = start.elapsed().as_nanos();
    println!("{}\n{}\n{}\n{}\n{}\n{}", inserted, looked, mixed, removed, sum, m.len());
}
