// Serial Rust peer for main.min: posting lists, N queries, document-at-a-time top 10.
use std::io::Write;

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

impl Index {
    fn search(&self, terms: &[usize], conjunctive: bool, best: &mut [i64; K], scores: &mut [i64; K]) -> usize {
        let n = terms.len();
        let mut cursor = [0usize; 4];
        for j in 0..n { cursor[j] = self.starts[terms[j]]; }
        let mut found = 0;
        loop {
            let mut doc = -1i64;
            for j in 0..n {
                if cursor[j] < self.starts[terms[j] + 1] {
                    let d = self.docs[cursor[j]];
                    if doc < 0 || d < doc { doc = d; }
                }
            }
            if doc < 0 { break; }
            let (mut score, mut matched) = (0i64, 0usize);
            for j in 0..n {
                let t = terms[j];
                let c = cursor[j];
                if c < self.starts[t + 1] && self.docs[c] == doc {
                    let tf = self.tfs[c];
                    score += self.idf[t] * tf * 16 / (tf + self.norm[doc as usize]);
                    matched += 1;
                    cursor[j] += 1;
                }
            }
            if (!conjunctive || matched == n) && (found < K || score > scores[K - 1]) {
                let mut at = found.min(K - 1);
                while at > 0 && scores[at - 1] < score { scores[at] = scores[at - 1]; best[at] = best[at - 1]; at -= 1; }
                scores[at] = score;
                best[at] = doc;
                if found < K { found += 1; }
            }
        }
        found
    }
}

fn main() {
    let n: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let (documents, queries) = (n * 1000, n);
    let mut ix = Index { docs: Vec::new(), tfs: Vec::new(), starts: vec![0; TERMS + 1], idf: vec![0; TERMS], norm: Vec::new() };
    for t in 0..TERMS {
        ix.starts[t] = ix.docs.len();
        let ti = t as i64;
        let target = (documents / 2).min(documents * 4 / (ti + 8));
        let step = (2 * documents / target).max(1);
        let (mut doc, mut k) = (mix(ti) % step, 0i64);
        while doc < documents {
            let r = mix(ti * 16777216 + k);
            ix.docs.push(doc);
            ix.tfs.push(1 + (r >> 32) % 5);
            doc += 1 + r % step;
            k += 1;
        }
        let mut ratio = documents / ((ix.docs.len() - ix.starts[t]) as i64).max(1);
        let mut bits = 0;
        while ratio > 1 { ratio /= 2; bits += 1; }
        ix.idf[t] = 1000 * (bits + 1);
    }
    ix.starts[TERMS] = ix.docs.len();
    ix.norm = (0..documents).map(|d| 3 + mix(d + 777) % 200 / 50).collect();
    let mut out = std::io::stdout().lock();
    let mut digest = 0i64;
    for q in 0..queries {
        let count = 2 + mix(q * 7) % 3;
        let terms: Vec<usize> = (0..count).map(|j| (mix(q * 7 + 1 + j) % (16 << (2 * j))) as usize).collect();
        let (mut best, mut scores) = ([0i64; K], [0i64; K]);
        let found = ix.search(&terms, q % 3 == 0, &mut best, &mut scores);
        for r in 0..found { digest = (digest * 31 + (r as i64 + 1) * (best[r] * 1000003 + scores[r])) % MODULUS; }
        if q < 4 { writeln!(out, "query {} found {} best {} {}", q, found, best[0], scores[0]).unwrap(); }
    }
    writeln!(out, "postings {}", ix.docs.len()).unwrap();
    writeln!(out, "digest {}", digest).unwrap();
}
