// Rust peer for main.min: split log fields, search messages, mask addresses,
// replace words, format output lines and summarise per service.
use std::collections::HashMap;
use std::fmt::Write as _;
use std::io::Write as _;

#[derive(Default)]
struct Summary<'a> { lines: i64, total_ms: i64, timeouts: i64, words: i64, longest: &'a str }

fn main() {
    let source = std::fs::read_to_string(std::env::args().nth(1).unwrap()).unwrap();
    let mut summaries: HashMap<&str, Summary> = HashMap::new();
    let (mut lines, mut malformed, mut internal, mut alerts, mut timeouts, mut replaced, mut formatted_bytes) =
        (0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 0i64);
    let mut samples: Vec<String> = Vec::new();
    let mut formatted = String::with_capacity(1024);
    for line in source.split('\n') {
        if line.is_empty() { continue; }
        lines += 1;
        let mut fields = line.splitn(5, " | ");
        let (level, service, address, message, duration_field) = (fields.next().unwrap(), fields.next().unwrap(),
            fields.next().unwrap(), fields.next().unwrap(), fields.next().unwrap());
        if duration_field.is_empty() || !duration_field.bytes().all(|b| b.is_ascii_digit()) { malformed += 1; continue; }
        let duration: i64 = match duration_field.parse() { Ok(v) => v, Err(_) => { malformed += 1; continue; } };
        let tag = match level {
            "ERROR" => { alerts += 1; "[E]" }
            "WARN" => { alerts += 1; "[W]" }
            "INFO" => "[I]",
            _ => "[D]",
        };
        if address.ends_with("@example.com") { internal += 1; }
        let timed_out = message.contains("timeout");
        if timed_out { timeouts += 1; }
        let s = summaries.entry(service).or_default();
        s.lines += 1;
        s.total_ms += duration;
        if timed_out { s.timeouts += 1; }
        for word in message.split(' ') {
            if word.is_empty() { continue; }
            s.words += 1;
            if word.len() > s.longest.len() { s.longest = word; }
        }
        formatted.clear();
        formatted.push_str(tag);
        formatted.push(' ');
        formatted.push_str(if service.starts_with("auth") { "security/" } else { "app/" });
        formatted.push_str(service);
        formatted.push(' ');
        match address.find('@') {
            Some(at) if at > 0 => { formatted.push_str(&address[..1]); formatted.push_str("***"); formatted.push_str(&address[at..]); }
            _ => formatted.push_str("***"),
        }
        write!(formatted, " {}ms: ", duration).unwrap();
        let mut from = 0;
        for (hit, _) in message.match_indices("order") {
            formatted.push_str(&message[from..hit]);
            formatted.push_str("ORDER");
            from = hit + 5;
            replaced += 1;
        }
        formatted.push_str(&message[from..]);
        formatted_bytes += formatted.len() as i64;
        if samples.len() < 3 { samples.push(formatted.clone()); }
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "lines {}\nmalformed {}\nalerts {}\ninternal {}\ntimeouts {}\nreplaced {}\nformatted bytes {}",
             lines, malformed, alerts, internal, timeouts, replaced, formatted_bytes).unwrap();
    for sample in &samples { writeln!(out, "{}", sample).unwrap(); }
    let mut sorted: Vec<_> = summaries.into_iter().collect();
    sorted.sort_unstable_by(|a, b| a.0.cmp(b.0));
    for (name, s) in &sorted {
        writeln!(out, "{}: {} lines, avg {} ms, {} timeouts, {} words, longest {}", name, s.lines, s.total_ms / s.lines,
                 s.timeouts, s.words, s.longest).unwrap();
    }
}
