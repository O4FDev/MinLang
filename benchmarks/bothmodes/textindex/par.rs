// Parallel Rust peer for main.min (std only): the file is cut into one byte
// range per thread at line ends; each thread indexes its lines into a private
// dictionary (FNV-1a HashMap on the word bytes) with local document numbers;
// then thread p merges the terms whose hash falls in partition p from every
// range in order, shifting document numbers; terms are sorted by spelling.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::{Read, Write};

#[derive(Default)]
struct Fnv(u64);
impl Hasher for Fnv {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, bytes: &[u8]) {
        let mut h = if self.0 == 0 { 0xcbf29ce484222325 } else { self.0 };
        for &b in bytes { h = (h ^ b as u64).wrapping_mul(1099511628211); }
        self.0 = h;
    }
}
type Map<'a, V> = HashMap<&'a [u8], V, BuildHasherDefault<Fnv>>;
const MODULUS: i64 = 1000000007;

fn fnv(word: &[u8]) -> u64 { let mut h = Fnv(0); h.write(word); h.finish() }

struct Local<'a> { documents: usize, tokens: usize, terms: Vec<(&'a [u8], Vec<u32>, Vec<u32>)> }

fn index_range(text: &[u8]) -> Local<'_> {
    let mut ids: Map<u32> = Map::default();
    let mut local = Local { documents: 0, tokens: 0, terms: Vec::new() };
    for line in text.split(|&b| b == b'\n') {
        if line.as_ptr() as usize + line.len() == text.as_ptr() as usize + text.len() && line.is_empty() { break; }
        let doc = local.documents as u32;
        for word in line.split(|&b| b == b' ').filter(|w| !w.is_empty()) {
            let next = local.terms.len() as u32;
            let id = *ids.entry(word).or_insert(next) as usize;
            if id == local.terms.len() { local.terms.push((word, Vec::new(), Vec::new())); }
            let t = &mut local.terms[id];
            if t.1.last() == Some(&doc) { *t.2.last_mut().unwrap() += 1; } else { t.1.push(doc); t.2.push(1); }
            local.tokens += 1;
        }
        local.documents += 1;
    }
    local
}

fn main() {
    let threads: usize = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).max(1);
    let mut corpus = Vec::new();
    std::fs::File::open(std::env::args().nth(1).unwrap()).unwrap().read_to_end(&mut corpus).unwrap();
    let mut cuts = vec![0usize];
    for t in 1..threads {
        let mut at = (corpus.len() * t / threads).max(*cuts.last().unwrap());
        while at < corpus.len() && corpus[at - 1] != b'\n' { at += 1; }
        cuts.push(at);
    }
    cuts.push(corpus.len());
    let corpus = &corpus[..];
    let locals: Vec<Local> = std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads).map(|t| { let (lo, hi) = (cuts[t], cuts[t + 1]); s.spawn(move || index_range(&corpus[lo..hi])) }).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut offsets = vec![0u32];
    for l in &locals { offsets.push(offsets.last().unwrap() + l.documents as u32); }
    let parts: Vec<Vec<(&[u8], Vec<u32>, Vec<u32>)>> = std::thread::scope(|s| {
        let (locals, offsets) = (&locals, &offsets);
        let handles: Vec<_> = (0..threads).map(|p| s.spawn(move || {
            let mut ids: Map<usize> = Map::default();
            let mut terms: Vec<(&[u8], Vec<u32>, Vec<u32>)> = Vec::new();
            for (c, l) in locals.iter().enumerate() {
                for (word, docs, tfs) in &l.terms {
                    if fnv(word) as usize % threads != p { continue; }
                    let next = terms.len();
                    let id = *ids.entry(word).or_insert(next);
                    if id == terms.len() { terms.push((word, Vec::new(), Vec::new())); }
                    terms[id].1.extend(docs.iter().map(|d| d + offsets[c]));
                    terms[id].2.extend_from_slice(tfs);
                }
            }
            terms
        })).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut terms: Vec<_> = parts.into_iter().flatten().collect();
    terms.sort_unstable_by(|a, b| a.0.cmp(b.0));
    let documents = *offsets.last().unwrap() as i64;
    let tokens: usize = locals.iter().map(|l| l.tokens).sum();
    let (mut digest, mut best, mut total) = (0i64, 0usize, 0usize);
    for (rank, (_, docs, tfs)) in terms.iter().enumerate() {
        let (mut doc_sum, mut tf_sum) = (0i64, 0i64);
        for k in 0..docs.len() { doc_sum += docs[k] as i64; tf_sum += tfs[k] as i64 * (k as i64 % 7 + 1); }
        digest = (digest * 31 + docs.len() as i64 * 1000003 + doc_sum % 1000003 + tf_sum) % MODULUS;
        if docs.len() > terms[best].1.len() { best = rank; }
        total += docs.len();
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "documents {} tokens {}", documents, tokens).unwrap();
    writeln!(out, "terms {} postings {}", terms.len(), total).unwrap();
    writeln!(out, "widest {} {}", String::from_utf8_lossy(terms[best].0), terms[best].1.len()).unwrap();
    writeln!(out, "digest {}", digest).unwrap();
}
