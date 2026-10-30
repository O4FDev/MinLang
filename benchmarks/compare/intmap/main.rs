// Rust peer for main.min: HashMap degrees and node indices (multiplicative
// hasher), adjacency Vecs of indices, BFS and a FIFO cache.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

#[derive(Default)]
struct Mix(u64);
impl Hasher for Mix {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, _: &[u8]) { unreachable!() }
    fn write_i64(&mut self, key: i64) { let h = (key as u64).wrapping_mul(0x9E3779B97F4A7C15); self.0 = h ^ (h >> 29); }
}
type Map = HashMap<i64, i64, BuildHasherDefault<Mix>>;

struct Random(i64);
impl Random {
    fn next(&mut self) -> i64 { self.0 = (self.0 * 1103515245 + 12345) % 2147483648; self.0 / 16 }
}
fn node_key(index: i64) -> i64 { index * 7919 + 13 }

fn main() {
    let edges: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let nodes = edges / 4 + 1;
    let mut random = Random(99);
    let mut degrees = Map::with_capacity_and_hasher(nodes as usize, Default::default());
    let mut index = Map::with_capacity_and_hasher(nodes as usize, Default::default());
    let mut lists: Vec<Vec<u32>> = Vec::with_capacity(nodes as usize);
    let (mut removed, mut start) = (0i64, 0i64);
    for i in 0..edges {
        let a = node_key(random.next() % nodes);
        let b = node_key(random.next() % nodes);
        if i == 0 { start = a; }
        *degrees.entry(a).or_insert(0) += 1;
        *degrees.entry(b).or_insert(0) += 1;
        let mut node_index = |key: i64| -> usize {
            let fresh = lists.len() as i64;
            let found = *index.entry(key).or_insert(fresh);
            if found == fresh { lists.push(Vec::new()); }
            found as usize
        };
        let la = node_index(a);
        let lb = node_index(b);
        lists[la].push(lb as u32);
        lists[lb].push(la as u32);
        if i % 7 == 0 && degrees.remove(&node_key(random.next() % nodes)).is_some() { removed += 1; }
    }
    let mut sorted: Vec<(i64, i64)> = degrees.iter().map(|(&k, &v)| (k, v)).collect();
    sorted.sort_unstable();
    let (mut checksum, mut busiest) = (0i64, 0i64);
    for &(key, degree) in &sorted {
        checksum = (checksum * 31 + key + degree) % 1000000007;
        busiest = busiest.max(degree);
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "{} {} {}\n{} {}", degrees.len(), index.len(), removed, checksum, busiest).unwrap();

    let mut visited = vec![false; lists.len()];
    let first = index[&start] as u32;
    visited[first as usize] = true;
    let mut frontier = vec![first];
    let mut next: Vec<u32> = Vec::new();
    let (mut reached, mut depth, mut depth_sum) = (1i64, 0i64, 0i64);
    while !frontier.is_empty() {
        next.clear();
        for &node in &frontier {
            depth_sum += depth;
            for &to in &lists[node as usize] {
                if !visited[to as usize] { visited[to as usize] = true; next.push(to); reached += 1; }
            }
        }
        std::mem::swap(&mut frontier, &mut next);
        depth += 1;
    }
    writeln!(out, "{} {} {}", reached, depth_sum, depth).unwrap();

    let capacity = (nodes / 8 + 1) as usize;
    let mut cache = Map::with_capacity_and_hasher(capacity + 1, Default::default());
    let mut arrivals: Vec<i64> = Vec::new();
    let mut oldest = 0;
    let (mut hits, mut misses, mut value_sum) = (0i64, 0i64, 0i64);
    for _ in 0..edges {
        let x = random.next() % nodes;
        let y = random.next() % nodes;
        let key = node_key(x.min(y));
        if let Some(&value) = cache.get(&key) { hits += 1; value_sum += value; continue; }
        misses += 1;
        let value = key * 3 % 1000;
        cache.insert(key, value);
        value_sum += value;
        arrivals.push(key);
        if cache.len() > capacity { cache.remove(&arrivals[oldest]); oldest += 1; }
    }
    writeln!(out, "{} {} {} {}", hits, misses, value_sum, cache.len()).unwrap();
}
