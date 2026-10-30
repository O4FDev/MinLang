// Rust peer for main.min: parse into nested HashMaps of &str, then query.
use std::collections::HashMap;
use std::fmt::Write as _;
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
type Map<K, V> = HashMap<K, V, BuildHasherDefault<Fnv>>;

enum Value<'a> {
    Integer(i64),
    Boolean(bool),
    Text(&'a str),
    List(Vec<i64>),
}

fn trim(s: &str) -> &str { s.trim_matches(|c: char| c == ' ' || ('\t'..='\r').contains(&c)) }

fn parse_integer(s: &str) -> Result<i64, String> {
    let bytes = s.as_bytes();
    let (negative, digits) = match bytes.first() { Some(b'-') => (true, &bytes[1..]), Some(b'+') => (false, &bytes[1..]), _ => (false, bytes) };
    let bad = || format!("invalid integer '{}'", s);
    if digits.is_empty() { return Err(bad()); }
    let mut v = 0i64;
    for &d in digits {
        if !d.is_ascii_digit() { return Err(bad()); }
        v = v.checked_mul(10).and_then(|v| v.checked_add((d - b'0') as i64)).ok_or_else(bad)?;
    }
    Ok(if negative { -v } else { v })
}

fn parse_value(raw: &str) -> Result<Value<'_>, String> {
    let mut v = trim(raw);
    if let Some(body) = v.strip_prefix('"') {
        let close = body.find('"').ok_or_else(|| "unterminated string".to_string())?;
        let rest = trim(&body[close + 1..]);
        if !rest.is_empty() && !rest.starts_with('#') { return Err("unexpected text after string".to_string()); }
        return Ok(Value::Text(&body[..close]));
    }
    if let Some(comment) = v.find('#') { v = trim(&v[..comment]); }
    if v.starts_with('[') {
        if v.len() < 2 || !v.ends_with(']') { return Err("unterminated list".to_string()); }
        let inner = trim(&v[1..v.len() - 1]);
        let mut items = Vec::new();
        if !inner.is_empty() {
            for part in inner.split(',') { items.push(parse_integer(trim(part))?); }
        }
        return Ok(Value::List(items));
    }
    if v == "true" { return Ok(Value::Boolean(true)); }
    if v == "false" { return Ok(Value::Boolean(false)); }
    if v.starts_with('-') || v.as_bytes().first().map_or(false, |b| b.is_ascii_digit()) {
        return Ok(Value::Integer(parse_integer(v)?));
    }
    Err(format!("unknown value '{}'", v))
}

fn main() {
    let src = std::fs::read_to_string(std::env::args().nth(1).unwrap()).unwrap();
    let mut sections: Map<&str, Map<&str, Value>> = Map::default();
    let mut errors: Vec<String> = Vec::new();
    let mut error_count = 0i64;
    let mut current: Option<&str> = None;
    for (index, raw) in src.split('\n').enumerate() {
        let line = trim(raw);
        if line.is_empty() || line.starts_with('#') { continue; }
        let problem: String = if line.starts_with('[') {
            if line.len() < 2 || !line.ends_with(']') { "unterminated section header".to_string() } else {
                let name = trim(&line[1..line.len() - 1]);
                sections.entry(name).or_default();
                current = Some(name);
                continue;
            }
        } else if let Some(eq) = line.find('=') {
            let key = trim(&line[..eq]);
            if key.is_empty() { "missing key".to_string() }
            else if let Some(section) = current {
                match parse_value(&line[eq + 1..]) {
                    Ok(value) => { sections.get_mut(section).unwrap().insert(key, value); continue; }
                    Err(message) => message,
                }
            } else { "entry outside a section".to_string() }
        } else { "expected '=' after a key".to_string() };
        if errors.len() < 8 { errors.push(format!("line {}: {}", index + 1, problem)); }
        error_count += 1;
    }
    let entries: usize = sections.values().map(|s| s.len()).sum();
    let mut out = std::io::BufWriter::new(std::io::stdout().lock());
    writeln!(out, "sections {}\nentries {}\nerrors {}", sections.len(), entries, error_count).unwrap();
    for e in &errors { writeln!(out, "{}", e).unwrap(); }
    let queries = sections.len() as i64 * 3;
    let space = sections.len() as i64 + sections.len() as i64 / 10 + 1;
    let (mut missing_sections, mut missing_keys, mut port_sum, mut enabled, mut name_bytes, mut weight_sum, mut weight_count, mut timeout_sum) = (0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 0i64);
    let mut name = String::new();
    for q in 0..queries {
        name.clear();
        write!(name, "service.{}", (q * 7919) % space).unwrap();
        let Some(s) = sections.get(name.as_str()) else { missing_sections += 1; continue; };
        match s.get("port") { Some(Value::Integer(v)) => port_sum += v, _ => missing_keys += 1 }
        match s.get("enabled") { Some(Value::Boolean(v)) => enabled += *v as i64, _ => missing_keys += 1 }
        match s.get("name") { Some(Value::Text(v)) => name_bytes += v.len() as i64, _ => missing_keys += 1 }
        match s.get("weights") {
            Some(Value::List(items)) => { weight_count += items.len() as i64; weight_sum += items.iter().sum::<i64>(); }
            _ => missing_keys += 1,
        }
        timeout_sum += match s.get("timeout") { Some(Value::Integer(v)) => *v, _ => 30 };
    }
    writeln!(out, "queries {}\nmissing sections {}\nmissing keys {}\nport sum {}\nenabled {}\nname bytes {}\nweights {} {}\ntimeout sum {}",
             queries, missing_sections, missing_keys, port_sum, enabled, name_bytes, weight_count, weight_sum, timeout_sum).unwrap();
}
