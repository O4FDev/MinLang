// Rust peer for main.min: Collatz step sum and hash histogram over 4 std threads,
// chunks of indices interleaved across threads, per-thread partial results.
use std::io::Write;

const THREADS: usize = 4;
const BUCKETS: usize = 16;
const CHUNK: usize = 4096;

fn collatz_steps(mut value: u64) -> u32 {
    let mut n = 0;
    while value != 1 { value = if value & 1 == 1 { 3 * value + 1 } else { value >> 1 }; n += 1; }
    n
}

fn mix(mut value: i64) -> i64 {
    for round in 0..4i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value
}

fn main() {
    let count: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut steps = vec![0u32; count];
    let total: u64 = std::thread::scope(|scope| {
        let mut parts: Vec<Vec<(usize, &mut [u32])>> = (0..THREADS).map(|_| Vec::new()).collect();
        for (k, chunk) in steps.chunks_mut(CHUNK).enumerate() { parts[k % THREADS].push((k * CHUNK, chunk)); }
        let handles: Vec<_> = parts.into_iter().map(|part| scope.spawn(move || {
            let mut sum = 0u64;
            for (first, chunk) in part {
                for (offset, slot) in chunk.iter_mut().enumerate() {
                    *slot = collatz_steps((first + offset) as u64 + 1);
                    sum += *slot as u64;
                }
            }
            sum
        })).collect();
        handles.into_iter().map(|h| h.join().unwrap()).sum()
    });
    let (mut longest, mut longest_start) = (0u32, 1usize);
    for (i, &s) in steps.iter().enumerate() { if s > longest { longest = s; longest_start = i + 1; } }
    let mut out = std::io::stdout().lock();
    writeln!(out, "steps {}\nlongest {} {}", total, longest_start, longest).unwrap();
    let samples = count * 8;
    let bins: [u64; BUCKETS] = std::thread::scope(|scope| {
        let handles: Vec<_> = (0..THREADS).map(|t| scope.spawn(move || {
            let mut local = [0u64; BUCKETS];
            let mut first = t * CHUNK;
            while first < samples {
                for s in first..(first + CHUNK).min(samples) { local[((mix(s as i64) >> 11) & 15) as usize] += 1; }
                first += THREADS * CHUNK;
            }
            local
        })).collect();
        let mut sum = [0u64; BUCKETS];
        for h in handles { for (b, v) in h.join().unwrap().iter().enumerate() { sum[b] += v; } }
        sum
    });
    for (b, v) in bins.iter().enumerate() { writeln!(out, "bucket {} {}", b, v).unwrap(); }
}
