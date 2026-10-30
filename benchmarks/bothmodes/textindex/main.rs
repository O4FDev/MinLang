// Serial Rust peer for main.min: inverted index of the input's lines (documents),
// a HashMap keyed by the word bytes (FNV-1a hasher), posting lists with term
// frequencies, terms ranked by spelling.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

const MODULUS: i64 = 1000000007;

struct Fnv(u64);
impl Default for Fnv { fn default() -> Self { Fnv(0xcbf29ce484222325) } }
impl Hasher for Fnv {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, bytes: &[u8]) {
        let mut h = self.0;
        for &b in bytes { h = (h ^ b as u64).wrapping_mul(1099511628211); }
        self.0 = h;
    }
    fn write_usize(&mut self, _: usize) {}
}

struct Term<'a> { word: &'a [u8], docs: Vec<i64>, tfs: Vec<i64> }

fn main() {
    let corpus = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut ids: HashMap<&[u8], u32, BuildHasherDefault<Fnv>> = HashMap::default();
    let mut terms: Vec<Term> = Vec::new();
    let (mut documents, mut tokens) = (0i64, 0i64);
    let mut i = 0;
    while let Some(offset) = corpus[i..].iter().position(|&c| c == b'\n') {
        let end = i + offset;
        for word in corpus[i..end].split(|&c| c == b' ').filter(|w| !w.is_empty()) {
            let id = *ids.entry(word).or_insert_with(|| {
                terms.push(Term { word, docs: Vec::new(), tfs: Vec::new() });
                (terms.len() - 1) as u32
            });
            let t = &mut terms[id as usize];
            if t.docs.last() == Some(&documents) { *t.tfs.last_mut().unwrap() += 1; } else { t.docs.push(documents); t.tfs.push(1); }
            tokens += 1;
        }
        documents += 1;
        i = end + 1;
    }
    let mut order: Vec<usize> = (0..terms.len()).collect();
    order.sort_unstable_by(|&a, &b| terms[a].word.cmp(terms[b].word));
    let total: usize = terms.iter().map(|t| t.docs.len()).sum();
    let (mut digest, mut best) = (0i64, 0usize);
    for (rank, &id) in order.iter().enumerate() {
        let t = &terms[id];
        let (mut doc_sum, mut tf_sum) = (0i64, 0i64);
        for k in 0..t.docs.len() { doc_sum += t.docs[k]; tf_sum += t.tfs[k] * (k as i64 % 7 + 1); }
        digest = (digest * 31 + t.docs.len() as i64 * 1000003 + doc_sum % 1000003 + tf_sum) % MODULUS;
        if t.docs.len() > terms[order[best]].docs.len() { best = rank; }
    }
    let w = &terms[order[best]];
    let mut out = std::io::stdout().lock();
    writeln!(out, "documents {} tokens {}", documents, tokens).unwrap();
    writeln!(out, "terms {} postings {}", terms.len(), total).unwrap();
    out.write_all(b"widest ").unwrap();
    out.write_all(w.word).unwrap();
    writeln!(out, " {}", w.docs.len()).unwrap();
    writeln!(out, "digest {}", digest).unwrap();
}
