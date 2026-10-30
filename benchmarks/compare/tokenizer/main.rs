// Rust peer for main.min: lex into a token Vec, then count kinds, rank identifiers, checksum.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

#[derive(Default)]
struct Fnv(u64);
impl Hasher for Fnv {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, bytes: &[u8]) {
        let mut h = if self.0 == 0 { 1469598103934665603u64 } else { self.0 };
        for &b in bytes { h ^= b as u64; h = h.wrapping_mul(1099511628211); }
        self.0 = h;
    }
}

const IDENT: u8 = 0;
const KEYWORD: u8 = 1;
const NUMBER: u8 = 2;
const STRING: u8 = 3;
const OPERATOR: u8 = 4;
const COMMENT: u8 = 5;

struct Token { start: u32, width: u32, line: u32, extra: u32, kind: u8 }

fn is_letter(c: u8) -> bool { c.is_ascii_alphabetic() || c == b'_' }
fn is_keyword(w: &[u8]) -> bool {
    matches!(w, b"let" | b"if" | b"else" | b"while" | b"return" | b"function" | b"for" | b"in")
}
fn two_char(a: u8, b: u8) -> bool {
    (b == b'=' && matches!(a, b'=' | b'!' | b'<' | b'>')) || (a == b'&' && b == b'&') || (a == b'|' && b == b'|') || (a == b'-' && b == b'>')
}

fn main() {
    let src = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let size = src.len();
    let mut tokens: Vec<Token> = Vec::with_capacity(size / 4);
    let mut line = 1u32;
    let mut i = 0usize;
    while i < size {
        let c = src[i];
        if c == b'\n' { line += 1; i += 1; }
        else if c == b' ' || c == b'\t' || c == b'\r' { i += 1; }
        else if is_letter(c) {
            let start = i;
            i += 1;
            while i < size && (is_letter(src[i]) || src[i].is_ascii_digit()) { i += 1; }
            let kind = if is_keyword(&src[start..i]) { KEYWORD } else { IDENT };
            tokens.push(Token { start: start as u32, width: (i - start) as u32, line, extra: 0, kind });
        } else if c.is_ascii_digit() {
            let start = i;
            i += 1;
            while i < size && src[i].is_ascii_digit() { i += 1; }
            tokens.push(Token { start: start as u32, width: (i - start) as u32, line, extra: 0, kind: NUMBER });
        } else if c == b'"' {
            let start = i;
            i += 1;
            let mut decoded = 0u32;
            while i < size && src[i] != b'"' {
                i += if src[i] == b'\\' && i + 1 < size { 2 } else { 1 };
                decoded += 1;
            }
            i += 1;
            tokens.push(Token { start: start as u32, width: (i - start) as u32, line, extra: decoded, kind: STRING });
        } else if c == b'/' && i + 1 < size && src[i + 1] == b'/' {
            let start = i;
            i = src[i..].iter().position(|&b| b == b'\n').map_or(size, |p| i + p);
            tokens.push(Token { start: start as u32, width: (i - start) as u32, line, extra: 0, kind: COMMENT });
        } else {
            let width = if i + 1 < size && two_char(src[i], src[i + 1]) { 2 } else { 1 };
            tokens.push(Token { start: i as u32, width, line, extra: 0, kind: OPERATOR });
            i += width as usize;
        }
    }
    let mut identifiers: HashMap<&[u8], u32, BuildHasherDefault<Fnv>> = HashMap::with_capacity_and_hasher(4096, Default::default());
    let mut counts = [0i64; 6];
    let (mut number_sum, mut string_bytes, mut checksum) = (0i64, 0i64, 0i64);
    for t in &tokens {
        counts[t.kind as usize] += 1;
        let text = &src[t.start as usize..(t.start + t.width) as usize];
        match t.kind {
            IDENT => *identifiers.entry(text).or_insert(0) += 1,
            NUMBER => {
                let v = text.iter().fold(0i64, |v, &d| v * 10 + (d - b'0') as i64);
                number_sum = (number_sum + v) % 1000000007;
            }
            STRING => string_bytes += t.extra as i64,
            _ => {}
        }
        checksum = (checksum * 31 + t.kind as i64 * 1000 + t.width as i64 + t.line as i64) % 1000000007;
    }
    let mut entries: Vec<(&[u8], u32)> = identifiers.into_iter().collect();
    entries.sort_unstable_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    let names = ["identifier", "keyword", "number", "string", "operator", "comment"];
    let mut out = std::io::BufWriter::new(std::io::stdout().lock());
    writeln!(out, "tokens {}", tokens.len()).unwrap();
    for k in 0..6 { writeln!(out, "{} {}", names[k], counts[k]).unwrap(); }
    writeln!(out, "number sum {}\nstring bytes {}\ndistinct identifiers {}", number_sum, string_bytes, entries.len()).unwrap();
    for (name, count) in entries.iter().take(10) {
        out.write_all(name).unwrap();
        writeln!(out, " {}", count).unwrap();
    }
    writeln!(out, "checksum {}", checksum).unwrap();
}
