// Rust peer for main.min: frame and parse requests as byte slices, route, and build responses.
use std::io::Write;

fn trim(s: &[u8]) -> &[u8] { s.trim_ascii() }

fn parse_integer(s: &[u8]) -> Option<i64> {
    let s = trim(s);
    let (negative, digits) = match s.first() { Some(b'-') => (true, &s[1..]), Some(b'+') => (false, &s[1..]), _ => (false, s) };
    if digits.is_empty() { return None; }
    let mut v = 0i64;
    for &d in digits {
        if !d.is_ascii_digit() { return None; }
        v = v.checked_mul(10)?.checked_add((d - b'0') as i64)?;
    }
    Some(if negative { -v } else { v })
}

fn next_line<'a>(rest: &mut &'a [u8]) -> &'a [u8] {
    let mut from = 0;
    while let Some(offset) = rest[from..].iter().position(|&b| b == b'\r') {
        let i = from + offset;
        if rest.get(i + 1) == Some(&b'\n') {
            let line = &rest[..i];
            *rest = &rest[i + 2..];
            return line;
        }
        from = i + 1;
    }
    let line = *rest;
    *rest = &[];
    line
}

fn reason(status: i64) -> &'static str {
    match status { 200 => "OK", 201 => "Created", 400 => "Bad Request", 404 => "Not Found", 405 => "Method Not Allowed", _ => "Length Required" }
}

fn main() {
    let src = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut rest: &[u8] = &src;
    let (mut requests, mut response_bytes, mut checksum, mut created) = (0i64, 0i64, 0i64, 0i64);
    let codes = [200i64, 201, 400, 404, 405, 411];
    let mut counts = [0i64; 6];
    let mut samples: Vec<Vec<u8>> = Vec::new();
    let mut body: Vec<u8> = Vec::with_capacity(256);
    let mut out: Vec<u8> = Vec::with_capacity(512);
    while !rest.is_empty() {
        let line = next_line(&mut rest);
        if line.is_empty() { break; }
        let mut parts = line.split(|&b| b == b' ');
        let (method, target) = (parts.next().unwrap_or(b""), parts.next());
        let valid = target.is_some() && parts.next().is_some() && parts.next().is_none();
        let (mut host, mut length, mut request_id, mut connection): (Option<&[u8]>, Option<&[u8]>, Option<&[u8]>, Option<&[u8]>) = (None, None, None, None);
        while !rest.is_empty() {
            let header = next_line(&mut rest);
            if header.is_empty() { break; }
            let Some(colon) = header.iter().position(|&b| b == b':') else { continue };
            if colon == 0 { continue; }
            let (name, value) = (&header[..colon], trim(&header[colon + 1..]));
            if name.eq_ignore_ascii_case(b"host") { host = Some(value); }
            else if name.eq_ignore_ascii_case(b"content-length") { length = Some(value); }
            else if name.eq_ignore_ascii_case(b"x-request-id") { request_id = Some(value); }
            else if name.eq_ignore_ascii_case(b"connection") { connection = Some(value); }
        }
        let mut body_length = 0i64;
        let mut bad_length = false;
        if let Some(l) = length {
            match parse_integer(l) {
                Some(n) => { body_length = n; rest = &rest[n as usize..]; }
                None => bad_length = true,
            }
        }
        body.clear();
        let mut location = 0i64;
        let fail = |body: &mut Vec<u8>, code: i64, message: &str| -> i64 { write!(body, "{{\"error\":\"{}\"}}", message).unwrap(); code };
        let status = if !valid { fail(&mut body, 400, "bad request line") }
        else if bad_length { fail(&mut body, 400, "bad content length") }
        else if host.is_none() { fail(&mut body, 400, "missing host") }
        else {
            let target = target.unwrap();
            let (path, query) = match target.iter().position(|&b| b == b'?') {
                Some(mark) => (&target[..mark], &target[mark + 1..]),
                None => (target, &b""[..]),
            };
            if path.starts_with(b"/users/") {
                if method != b"GET" { fail(&mut body, 405, "method not allowed") }
                else {
                    match parse_integer(&path[7..]) {
                        Some(id) if (0..50000).contains(&id) => {
                            write!(body, "{{\"id\":{},\"name\":\"user-{}\",\"tier\":{}}}", id, id, id % 5).unwrap();
                            200
                        }
                        _ => fail(&mut body, 404, "no such user"),
                    }
                }
            } else if path == b"/search" {
                if method != b"GET" { fail(&mut body, 405, "method not allowed") }
                else {
                    let mut term: Option<&[u8]> = None;
                    let mut limit = 10i64;
                    if !query.is_empty() {
                        for pair in query.split(|&b| b == b'&') {
                            let (key, value) = match pair.iter().position(|&b| b == b'=') {
                                Some(eq) => (&pair[..eq], &pair[eq + 1..]),
                                None => (pair, &b""[..]),
                            };
                            if key == b"q" { term = Some(value); } else if key == b"limit" { limit = parse_integer(value).unwrap_or(10); }
                        }
                    }
                    match term {
                        None => fail(&mut body, 400, "missing q"),
                        Some(term) => {
                            body.extend_from_slice(b"{\"query\":\"");
                            body.extend_from_slice(term);
                            write!(body, "\",\"limit\":{},\"results\":[", limit).unwrap();
                            for k in 0..limit.min(5) {
                                if k > 0 { body.push(b','); }
                                body.push(b'"');
                                body.extend_from_slice(term);
                                write!(body, "-{}\"", k).unwrap();
                            }
                            body.extend_from_slice(b"]}");
                            200
                        }
                    }
                }
            } else if path == b"/items" {
                if method != b"POST" { fail(&mut body, 405, "method not allowed") }
                else if length.is_none() { fail(&mut body, 411, "length required") }
                else {
                    created += 1;
                    location = created;
                    write!(body, "{{\"created\":true,\"bytes\":{}}}", body_length).unwrap();
                    201
                }
            } else { fail(&mut body, 404, "not found") }
        };
        out.clear();
        write!(out, "HTTP/1.1 {} {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n", status, reason(status), body.len()).unwrap();
        if let Some(id) = request_id { out.extend_from_slice(b"X-Request-Id: "); out.extend_from_slice(id); out.extend_from_slice(b"\r\n"); }
        if location > 0 { write!(out, "Location: /items/{}\r\n", location).unwrap(); }
        let close = connection == Some(&b"close"[..]);
        write!(out, "Connection: {}\r\n\r\n", if close { "close" } else { "keep-alive" }).unwrap();
        out.extend_from_slice(&body);
        requests += 1;
        for k in 0..6 { if codes[k] == status { counts[k] += 1; } }
        response_bytes += out.len() as i64;
        checksum = (checksum * 131 + out.len() as i64 * 7 + status) % 1000000007;
        if samples.len() < 3 { samples.push(out.clone()); }
    }
    let mut w = std::io::BufWriter::new(std::io::stdout().lock());
    writeln!(w, "requests {}", requests).unwrap();
    for k in 0..6 { writeln!(w, "status {} {}", codes[k], counts[k]).unwrap(); }
    writeln!(w, "response bytes {}\nitems created {}\nchecksum {}", response_bytes, created, checksum).unwrap();
    for s in &samples { w.write_all(s).unwrap(); w.write_all(b"\n").unwrap(); }
    w.write_all(&out).unwrap();
    w.write_all(b"\n").unwrap();
}
