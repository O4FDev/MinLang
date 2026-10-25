// Same workload as cache.min. Build: rustc -C opt-level=3 -C codegen-units=1 cache.rs
use std::time::Instant;

struct Session { name: String, items: Vec<i64>, score: i64 }

fn setting(name: &str, fallback: i64) -> i64 {
    std::env::var(name).ok().and_then(|v| v.parse().ok()).unwrap_or(fallback)
}

fn make_session(id: i64) -> Session {
    let mut items = Vec::new();
    items.push(id); items.push(id * 3); items.push(id * 7); items.push(id % 97);
    Session { name: format!("session-{}", id), items, score: id % 1000 }
}

fn serve(current: &[Session], request: i64, reads: i64) -> i64 {
    let size = current.len() as i64;
    if size == 0 { return 0; }
    let mut total = 0;
    for k in 0..reads {
        let s = &current[((request * 7919 + k * 104729) % size) as usize];
        total += s.score + s.items[(k % 4) as usize];
    }
    total
}

fn rss() -> i64 {
    std::fs::read_to_string("/proc/self/statm").ok()
        .and_then(|s| s.split_whitespace().nth(1).and_then(|v| v.parse::<i64>().ok()))
        .map(|p| p * 4096).unwrap_or(-1)
}

fn main() {
    let requests = setting("TAIL_REQUESTS", 20000);
    let per_request = setting("TAIL_BUILD", 200);
    let swap_every = setting("TAIL_SWAP", 1000);
    let reads = setting("TAIL_READS", 64);
    let interval = setting("TAIL_INTERVAL_NS", 0) as u64;
    // TAIL_DEFER=1: hand the old generation to a background thread to drop.
    let defer = setting("TAIL_DEFER", 0) == 1;
    let mut current: Vec<Session> = Vec::new();
    let mut next: Vec<Session> = Vec::new();
    let mut latencies: Vec<i64> = Vec::new();
    let (mut checksum, mut id) = (0i64, 0i64);
    let begin = Instant::now();
    for r in 0..requests {
        if interval > 0 {
            let arrival = begin + std::time::Duration::from_nanos(r as u64 * interval);
            let now = Instant::now();
            if arrival > now { std::thread::sleep(arrival - now); }
        }
        let start = Instant::now();
        for _ in 0..per_request { next.push(make_session(id)); id += 1; }
        checksum = (checksum + serve(&current, r, reads)) % 1000000007;
        if (r + 1) % swap_every == 0 {
            let old = std::mem::replace(&mut current, std::mem::take(&mut next));
            if defer { std::thread::spawn(move || drop(old)); } else { drop(old); }
        }
        latencies.push(start.elapsed().as_nanos() as i64);
    }
    let elapsed = begin.elapsed().as_nanos();
    latencies.sort();
    let p = |m: usize| latencies[std::cmp::min(latencies.len() * m / 1000000, latencies.len() - 1)];
    println!("lang=rust requests={} checksum={} total_ns={} p50={} p99={} p999={} max={} rss={}",
        requests, checksum, elapsed, p(500000), p(990000), p(999000), latencies[latencies.len() - 1], rss());
}
