// Parallel Rust peer for main.min (std only): MINYAR_PARALLEL_THREADS scoped
// threads generate the posting lists (interleaved term ranges, concatenated in
// term order), then take queries from a shared atomic counter; each query's
// top 10 goes to its own slot.
use std::io::Write;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

const TERMS: usize = 4096;
const K: usize = 10;
const MODULUS: i64 = 1000000007;

fn mix(mut value: i64) -> i64 {
    for round in 0..3i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value & 0x7FFFFFFFFFFFFFFF
}

struct Index { docs: Vec<i64>, tfs: Vec<i64>, starts: Vec<usize>, idf: Vec<i64>, norm: Vec<i64> }

fn term_postings(t: i64, documents: i64, docs: &mut Vec<i64>, tfs: &mut Vec<i64>) {
    let target = (documents / 2).min(documents * 4 / (t + 8));
    let step = (2 * documents / target).max(1);
    let (mut doc, mut k) = (mix(t) % step, 0i64);
    while doc < documents {
        let r = mix(t * 16777216 + k);
        docs.push(doc);
        tfs.push(1 + (r >> 32) % 5);
        doc += 1 + r % step;
        k += 1;
    }
}

fn search(ix: &Index, terms: &[i64], conjunctive: bool, docs: &mut [i64; K], scores: &mut [i64; K]) -> usize {
    let mut cursor = [0usize; 4];
    let mut n = 0;
    while n < 4 && terms[n] >= 0 { cursor[n] = ix.starts[terms[n] as usize]; n += 1; }
    let mut found = 0;
    loop {
        let mut doc = -1i64;
        for j in 0..n {
            if cursor[j] < ix.starts[terms[j] as usize + 1] {
                let d = ix.docs[cursor[j]];
                if doc < 0 || d < doc { doc = d; }
            }
        }
        if doc < 0 { break; }
        let (mut score, mut matched) = (0i64, 0);
        for j in 0..n {
            let t = terms[j] as usize;
            if cursor[j] < ix.starts[t + 1] && ix.docs[cursor[j]] == doc {
                let tf = ix.tfs[cursor[j]];
                score += ix.idf[t] * tf * 16 / (tf + ix.norm[doc as usize]);
                matched += 1;
                cursor[j] += 1;
            }
        }
        if (!conjunctive || matched == n) && (found < K || score > scores[K - 1]) {
            let mut at = found.min(K - 1);
            while at > 0 && scores[at - 1] < score { scores[at] = scores[at - 1]; docs[at] = docs[at - 1]; at -= 1; }
            scores[at] = score;
            docs[at] = doc;
            if found < K { found += 1; }
        }
    }
    found
}

fn main() {
    let n: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let threads: usize = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).max(1);
    let (documents, queries) = (n * 1000, n as usize);
    // Terms are dealt out in blocks of 64 from a shared counter; each block's lists are kept and joined in term order.
    let next = AtomicUsize::new(0);
    let blocks: Mutex<Vec<(usize, Vec<i64>, Vec<i64>, Vec<usize>)>> = Mutex::new(Vec::new());
    let norm_parts: Vec<Vec<i64>> = std::thread::scope(|s| {
        let per = (documents as usize + threads - 1) / threads;
        let handles: Vec<_> = (0..threads).map(|w| {
            let (next, blocks) = (&next, &blocks);
            s.spawn(move || {
                loop {
                    let b = next.fetch_add(1, Ordering::Relaxed);
                    if b * 64 >= TERMS { break; }
                    let (mut docs, mut tfs, mut lengths) = (Vec::new(), Vec::new(), Vec::with_capacity(64));
                    for t in b * 64..(b + 1) * 64 {
                        let before = docs.len();
                        term_postings(t as i64, documents, &mut docs, &mut tfs);
                        lengths.push(docs.len() - before);
                    }
                    blocks.lock().unwrap().push((b, docs, tfs, lengths));
                }
                let lo = (w * per).min(documents as usize);
                let hi = ((w + 1) * per).min(documents as usize);
                (lo..hi).map(|d| 3 + mix(d as i64 + 777) % 200 / 50).collect::<Vec<i64>>()
            })
        }).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut blocks = blocks.into_inner().unwrap();
    blocks.sort_by_key(|b| b.0);
    let total: usize = blocks.iter().map(|b| b.1.len()).sum();
    let mut ix = Index { docs: Vec::with_capacity(total), tfs: Vec::with_capacity(total), starts: Vec::with_capacity(TERMS + 1),
                         idf: Vec::with_capacity(TERMS), norm: norm_parts.concat() };
    for (_, docs, tfs, lengths) in blocks {
        let mut at = ix.docs.len();
        for length in lengths {
            ix.starts.push(at);
            at += length;
            let ratio = documents / (length as i64).max(1);
            let (mut r, mut bits) = (ratio, 0);
            while r > 1 { r /= 2; bits += 1; }
            ix.idf.push(1000 * (bits + 1));
        }
        ix.docs.extend_from_slice(&docs);
        ix.tfs.extend_from_slice(&tfs);
    }
    ix.starts.push(ix.docs.len());
    let next = AtomicUsize::new(0);
    let mut results = vec![(0usize, [0i64; K], [0i64; K]); queries];
    let parts: Vec<Vec<(usize, (usize, [i64; K], [i64; K]))>> = std::thread::scope(|s| {
        let (ix, next) = (&ix, &next);
        let handles: Vec<_> = (0..threads).map(|_| s.spawn(move || {
            let mut mine = Vec::new();
            loop {
                let q = next.fetch_add(1, Ordering::Relaxed);
                if q >= queries { break; }
                let count = 2 + mix(q as i64 * 7) % 3;
                let mut terms = [-1i64; 4];
                for j in 0..count as usize { terms[j] = mix(q as i64 * 7 + 1 + j as i64) % (16 << (2 * j)); }
                let (mut docs, mut scores) = ([0i64; K], [0i64; K]);
                let found = search(ix, &terms, q % 3 == 0, &mut docs, &mut scores);
                mine.push((q, (found, docs, scores)));
            }
            mine
        })).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    for part in parts { for (q, r) in part { results[q] = r; } }
    let mut out = std::io::stdout().lock();
    let mut digest = 0i64;
    for (q, (found, docs, scores)) in results.iter().enumerate() {
        for r in 0..*found { digest = (digest * 31 + (r as i64 + 1) * (docs[r] * 1000003 + scores[r])) % MODULUS; }
        if q < 4 { writeln!(out, "query {} found {} best {} {}", q, found, docs[0], scores[0]).unwrap(); }
    }
    writeln!(out, "postings {}", ix.docs.len()).unwrap();
    writeln!(out, "digest {}", digest).unwrap();
}
