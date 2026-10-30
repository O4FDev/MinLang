// Rust peer for main.min: a general JSON DOM parser (byte slices borrowed from
// the input, Cow for decoded strings), the same query, and a compact
// serialiser with the same escaping as json.quote.
use std::borrow::Cow;
use std::collections::HashMap;
use std::io::Write;

enum Value<'a> {
    Null,
    Bool(bool),
    Number(i64),
    Str(Cow<'a, [u8]>),
    Array(Vec<Value<'a>>),
    Object(Vec<(Cow<'a, [u8]>, Value<'a>)>),
}

fn invalid(why: &str) -> ! {
    println!("invalid input: {}", why);
    std::process::exit(1)
}

struct Parser<'a> { s: &'a [u8], p: usize }

impl<'a> Parser<'a> {
    fn space(&mut self) { while self.p < self.s.len() && matches!(self.s[self.p], b' ' | b'\n' | b'\r' | b'\t') { self.p += 1; } }
    fn hex4(&self, at: usize) -> u32 {
        if at + 4 > self.s.len() { invalid("short unicode escape"); }
        let mut v = 0u32;
        for &c in &self.s[at..at + 4] {
            v = v << 4 | match c { b'0'..=b'9' => c - b'0', b'a'..=b'f' => c - b'a' + 10, b'A'..=b'F' => c - b'A' + 10, _ => invalid("bad unicode escape") } as u32;
        }
        v
    }
    fn string(&mut self) -> Cow<'a, [u8]> {
        self.p += 1;
        let start = self.p;
        let s = self.s;
        let mut i = start;
        while i < s.len() && s[i] != b'"' && s[i] != b'\\' { if s[i] < 32 { invalid("control in string"); } i += 1; }
        if i < s.len() && s[i] == b'"' { self.p = i + 1; return Cow::Borrowed(&s[start..i]); }
        let mut o = s[start..i].to_vec();
        while i < s.len() && s[i] != b'"' {
            let c = s[i];
            if c < 32 { invalid("control in string"); }
            if c != b'\\' { o.push(c); i += 1; continue; }
            if i + 1 >= s.len() { invalid("unfinished escape"); }
            match s[i + 1] {
                b'"' => o.push(b'"'), b'\\' => o.push(b'\\'), b'/' => o.push(b'/'),
                b'b' => o.push(8), b'f' => o.push(12), b'n' => o.push(b'\n'), b'r' => o.push(b'\r'), b't' => o.push(b'\t'),
                b'u' => {
                    let mut u = self.hex4(i + 2);
                    i += 4;
                    if (0xD800..0xDC00).contains(&u) && i + 8 <= s.len() && s[i + 2] == b'\\' && s[i + 3] == b'u' {
                        let low = self.hex4(i + 4);
                        if (0xDC00..0xE000).contains(&low) { u = 0x10000 + ((u - 0xD800) << 10) + (low - 0xDC00); i += 6; }
                    }
                    let ch = char::from_u32(u).unwrap_or('\u{FFFD}');
                    let mut buf = [0u8; 4];
                    o.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
                }
                _ => invalid("unknown escape"),
            }
            i += 2;
        }
        if i >= s.len() { invalid("unterminated string"); }
        self.p = i + 1;
        Cow::Owned(o)
    }
    fn literal(&mut self, word: &[u8]) -> bool {
        if self.s[self.p..].starts_with(word) { self.p += word.len(); true } else { false }
    }
    fn value(&mut self, depth: u32) -> Value<'a> {
        if depth > 512 { invalid("nesting too deep"); }
        self.space();
        if self.p >= self.s.len() { invalid("unexpected end"); }
        match self.s[self.p] {
            b'{' => {
                self.p += 1;
                let mut members = Vec::new();
                self.space();
                if self.p < self.s.len() && self.s[self.p] == b'}' { self.p += 1; return Value::Object(members); }
                loop {
                    self.space();
                    if self.p >= self.s.len() || self.s[self.p] != b'"' { invalid("expected member name"); }
                    let key = self.string();
                    self.space();
                    if self.p >= self.s.len() || self.s[self.p] != b':' { invalid("expected ':'"); }
                    self.p += 1;
                    members.push((key, self.value(depth + 1)));
                    self.space();
                    match self.s.get(self.p) {
                        Some(b',') => self.p += 1,
                        Some(b'}') => { self.p += 1; return Value::Object(members); }
                        _ => invalid("expected ',' or '}'"),
                    }
                }
            }
            b'[' => {
                self.p += 1;
                let mut items = Vec::new();
                self.space();
                if self.p < self.s.len() && self.s[self.p] == b']' { self.p += 1; return Value::Array(items); }
                loop {
                    items.push(self.value(depth + 1));
                    self.space();
                    match self.s.get(self.p) {
                        Some(b',') => self.p += 1,
                        Some(b']') => { self.p += 1; return Value::Array(items); }
                        _ => invalid("expected ',' or ']'"),
                    }
                }
            }
            b'"' => Value::Str(self.string()),
            b'-' | b'0'..=b'9' => {
                let negative = self.s[self.p] == b'-';
                if negative { self.p += 1; }
                let digits = self.p;
                let mut n: i64 = 0;
                while self.p < self.s.len() && self.s[self.p].is_ascii_digit() { n = n * 10 + (self.s[self.p] - b'0') as i64; self.p += 1; }
                let count = self.p - digits;
                if count == 0 || (count > 1 && self.s[digits] == b'0') || count > 18 { invalid("bad number"); }
                if matches!(self.s.get(self.p), Some(b'.' | b'e' | b'E')) { invalid("expected an integer"); }
                Value::Number(if negative { -n } else { n })
            }
            _ => {
                if self.literal(b"true") { Value::Bool(true) }
                else if self.literal(b"false") { Value::Bool(false) }
                else if self.literal(b"null") { Value::Null }
                else { invalid("unexpected character") }
            }
        }
    }
}

impl<'a> Value<'a> {
    fn get(&self, name: &str) -> &Value<'a> {
        match self {
            Value::Object(members) => members.iter().find(|(k, _)| k.as_ref() == name.as_bytes()).map(|(_, v)| v).unwrap_or_else(|| invalid("missing member")),
            _ => invalid("expected a JSON object"),
        }
    }
    fn integer(&self) -> i64 { if let Value::Number(n) = self { *n } else { invalid("expected a JSON integer") } }
    fn text(&self) -> &[u8] { if let Value::Str(s) = self { s } else { invalid("expected a JSON string") } }
    fn array(&self) -> &[Value<'a>] { if let Value::Array(items) = self { items } else { invalid("expected a JSON array") } }
    fn boolean(&self) -> bool { if let Value::Bool(b) = self { *b } else { invalid("expected a JSON boolean") } }
}

fn quote(o: &mut Vec<u8>, s: &[u8]) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    o.push(b'"');
    for &c in s {
        if c >= 32 && c != b'"' && c != b'\\' { o.push(c); continue; }
        o.push(b'\\');
        match c {
            b'"' => o.push(b'"'), b'\\' => o.push(b'\\'), b'\n' => o.push(b'n'), b'\t' => o.push(b't'), b'\r' => o.push(b'r'),
            8 => o.push(b'b'), 12 => o.push(b'f'),
            _ => o.extend_from_slice(&[b'u', b'0', b'0', HEX[(c >> 4) as usize], HEX[(c & 15) as usize]]),
        }
    }
    o.push(b'"');
}

#[derive(Default)]
struct CityStats<'t> { users: i64, active: i64, spent: i64, oldest: i64, top_spent: i64, top: &'t [u8] }

fn main() {
    let source = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut parser = Parser { s: &source, p: 0 };
    let root = parser.value(0);
    parser.space();
    if parser.p != source.len() { invalid("unexpected trailing input"); }
    let users = root.array();
    let mut cities: HashMap<&[u8], CityStats> = HashMap::new();
    let mut tag_counts: HashMap<&[u8], i64> = HashMap::new();
    let (mut active, mut checksum, mut geo_sum) = (0i64, 0i64, 0i64);
    let mut spenders: Vec<Vec<u8>> = Vec::new();
    for user in users {
        let address = user.get("address");
        let geo = address.get("geo").array();
        let tags: Vec<&[u8]> = user.get("tags").array().iter().map(|t| t.text()).collect();
        let spent: i64 = user.get("orders").array().iter().map(|o| o.get("qty").integer() * o.get("price").integer()).sum();
        let id = user.get("id").integer();
        let name = user.get("name").text();
        let is_active = user.get("active").boolean();
        let age = user.get("age").integer();
        let score = user.get("score").integer();
        let city = address.get("city").text();
        let zip = address.get("zip").text().iter().fold(0i64, |z, &d| z * 10 + (d - b'0') as i64);
        if geo.len() < 2 { invalid("short geo"); }
        let stats = cities.entry(city).or_insert_with(|| CityStats { top_spent: -1, ..Default::default() });
        stats.users += 1;
        stats.spent += spent;
        stats.oldest = stats.oldest.max(age);
        if spent > stats.top_spent { stats.top_spent = spent; stats.top = name; }
        checksum = (checksum * 31 + name.len() as i64 + age + score + 5000 + zip) % 1000000007;
        geo_sum += geo[0].integer() + geo[1].integer();
        if !is_active { continue; }
        active += 1;
        stats.active += 1;
        for &tag in &tags { *tag_counts.entry(tag).or_insert(0) += 1; }
        if spent > 600000 {
            let mut s = Vec::with_capacity(128);
            write!(s, "{{\"id\":{},\"name\":", id).unwrap();
            quote(&mut s, name);
            s.extend_from_slice(b",\"city\":");
            quote(&mut s, city);
            write!(s, ",\"spent\":{},\"tags\":[", spent).unwrap();
            for (t, tag) in tags.iter().enumerate() { if t > 0 { s.push(b','); } quote(&mut s, tag); }
            s.extend_from_slice(b"]}");
            spenders.push(s);
        }
    }
    let mut city_names: Vec<&[u8]> = cities.keys().copied().collect();
    city_names.sort_unstable();
    let mut tag_names: Vec<&[u8]> = tag_counts.keys().copied().collect();
    tag_names.sort_unstable();
    let city_lines: Vec<Vec<u8>> = city_names.iter().map(|city| {
        let s = &cities[city];
        let mut o = b"{\"city\":".to_vec();
        quote(&mut o, city);
        write!(o, ",\"users\":{},\"active\":{},\"spent\":{},\"oldest\":{},\"top\":", s.users, s.active, s.spent, s.oldest).unwrap();
        quote(&mut o, s.top);
        write!(o, ",\"topSpent\":{}}}", s.top_spent).unwrap();
        o
    }).collect();
    let mut output = b"{\"cities\":[".to_vec();
    output.extend_from_slice(&city_lines.join(&b","[..]));
    output.extend_from_slice(b"],\"tags\":{");
    for (t, tag) in tag_names.iter().enumerate() {
        if t > 0 { output.push(b','); }
        quote(&mut output, tag);
        write!(output, ":{}", tag_counts[tag]).unwrap();
    }
    output.extend_from_slice(b"},\"spenders\":[");
    output.extend_from_slice(&spenders.join(&b","[..]));
    output.extend_from_slice(b"]}");
    let hash = output.iter().fold(14695981039346656037u64, |h, &c| (h ^ c as u64).wrapping_mul(1099511628211));
    let mut out = std::io::stdout().lock();
    writeln!(out, "{} {}\n{} {}\n{}\n{} {}", users.len(), active, checksum, geo_sum, spenders.len(), output.len(), hash as i64).unwrap();
    for line in &city_lines { out.write_all(line).unwrap(); out.write_all(b"\n").unwrap(); }
}
