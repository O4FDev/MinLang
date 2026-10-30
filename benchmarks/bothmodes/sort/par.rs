// Parallel Rust peer for main.min (std only): MINYAR_PARALLEL_THREADS scoped
// threads generate the keys and sort one slice each with sort_unstable, then
// adjacent runs are merged pairwise in rounds; every round cuts each pair into
// one part per thread with a merge-path binary search.
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

// How many of the first `d` merged keys come from `a` (ties taken from `a` first).
fn split(a: &[i64], b: &[i64], d: usize) -> usize {
    let (mut low, mut high) = (d.saturating_sub(b.len()), d.min(a.len()));
    while low < high {
        let middle = (low + high) / 2;
        if a[middle] <= b[d - middle - 1] { low = middle + 1; } else { high = middle; }
    }
    low
}
fn merge(a: &[i64], b: &[i64], mut i: usize, mut j: usize, out: &mut [i64]) {
    for slot in out.iter_mut() {
        if j >= b.len() || (i < a.len() && a[i] <= b[j]) { *slot = a[i]; i += 1; } else { *slot = b[j]; j += 1; }
    }
}

fn main() {
    let count: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let threads: usize = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).max(1);
    let run = (count + threads - 1) / threads;
    let mut keys = vec![0i64; count];
    std::thread::scope(|s| {
        for (t, part) in keys.chunks_mut(run.max(1)).enumerate() {
            s.spawn(move || {
                for (k, slot) in part.iter_mut().enumerate() { *slot = mix((t * run + k) as i64) & 0xFFFFFFFFFF; }
                part.sort_unstable();
            });
        }
    });
    let mut spare = vec![0i64; count];
    let (mut source, mut target) = (&mut keys, &mut spare);
    let mut width = run.max(1);
    while width < count {
        {
            let src: &[i64] = source;
            let mut rest: &mut [i64] = target;
            let mut tasks = Vec::new();
            let mut lo = 0;
            while lo < count {
                let mid = (lo + width).min(count);
                let hi = (lo + 2 * width).min(count);
                let (a, b) = (&src[lo..mid], &src[mid..hi]);
                let total = hi - lo;
                for p in 0..threads {
                    let (d0, d1) = (total * p / threads, total * (p + 1) / threads);
                    let (out, tail) = std::mem::take(&mut rest).split_at_mut(d1 - d0);
                    rest = tail;
                    let i = split(a, b, d0);
                    tasks.push((a, b, i, d0 - i, out));
                }
                lo = hi;
            }
            let per = (tasks.len() + threads - 1) / threads;
            std::thread::scope(|s| {
                let mut tasks = tasks;
                while !tasks.is_empty() {
                    let group: Vec<_> = tasks.drain(..per.min(tasks.len())).collect();
                    s.spawn(move || for (a, b, i, j, out) in group { merge(a, b, i, j, out); });
                }
            });
        }
        std::mem::swap(&mut source, &mut target);
        width *= 2;
    }
    let keys: &[i64] = source;
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
