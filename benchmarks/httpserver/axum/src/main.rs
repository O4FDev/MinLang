//! Current-thread axum comparator with the same raw key, exact LRU and async
//! fresh upstream semantics as the Minyar fixture. No search or decode work.
use axum::{body::{Body, Bytes}, extract::State, http::{HeaderMap, Method, Response, Uri}, routing::any, Router};
use std::{collections::HashMap, io::{self, Write}, net::{IpAddr, SocketAddr}, sync::{Arc, Mutex}, time::Duration};
use tokio::{io::{AsyncReadExt, AsyncWriteExt}, net::{TcpListener, TcpStream}};
use axum::serve::ListenerExt;

struct Entry { key: Vec<u8>, value: Bytes, prev: Option<usize>, next: Option<usize> }
struct Cache {
    table: HashMap<Vec<u8>, usize>, entries: Vec<Entry>, free: Vec<usize>,
    head: Option<usize>, tail: Option<usize>, bytes: usize, max_entries: usize, max_bytes: usize,
    hits: u64, misses: u64, evictions: u64, connects: u64,
}
impl Cache {
    fn new(max_entries: usize, max_bytes: usize) -> Self {
        Self { table: HashMap::new(), entries: vec![], free: vec![], head: None, tail: None,
            bytes: 0, max_entries, max_bytes, hits: 0, misses: 0, evictions: 0, connects: 0 }
    }
    fn unlink(&mut self, slot: usize) {
        let e = &self.entries[slot];
        let (p, n) = (e.prev, e.next);
        if let Some(p) = p { self.entries[p].next = n } else { self.head = n }
        if let Some(n) = n { self.entries[n].prev = p } else { self.tail = p }
        self.entries[slot].prev = None; self.entries[slot].next = None;
    }
    fn push_front(&mut self, slot: usize) {
        self.entries[slot].prev = None; self.entries[slot].next = self.head;
        if let Some(h) = self.head { self.entries[h].prev = Some(slot) }
        self.head = Some(slot);
        if self.tail.is_none() { self.tail = Some(slot) }
    }
    fn lookup(&mut self, key: &[u8]) -> Option<Bytes> {
        let slot = *self.table.get(key)?;
        if self.head != Some(slot) { self.unlink(slot); self.push_front(slot) }
        Some(self.entries[slot].value.clone())
    }
    fn evict(&mut self, slot: usize) {
        self.table.remove(&self.entries[slot].key);
        self.unlink(slot);
        self.bytes -= self.entries[slot].key.len() + self.entries[slot].value.len();
        self.entries[slot].key.clear(); self.entries[slot].value = Bytes::new();
        self.free.push(slot); self.evictions += 1;
    }
    fn insert(&mut self, key: Vec<u8>, value: Bytes) {
        let size = key.len() + value.len();
        if size > self.max_bytes { return }
        if let Some(&slot) = self.table.get(&key) { self.evict(slot) }
        while self.table.len() >= self.max_entries || self.bytes + size > self.max_bytes {
            self.evict(self.tail.expect("nonempty LRU"));
        }
        let slot = self.free.pop().unwrap_or_else(|| {
            let slot = self.entries.len();
            self.entries.push(Entry { key: vec![], value: Bytes::new(), prev: None, next: None }); slot
        });
        self.entries[slot].key = key.clone(); self.entries[slot].value = value;
        self.table.insert(key, slot); self.push_front(slot); self.bytes += size;
    }
    fn stats(&self) -> Bytes {
        Bytes::from(format!("{{\"hits\":{},\"misses\":{},\"entries\":{},\"bytes\":{},\"evictions\":{},\"upstream_connects\":{}}}",
            self.hits, self.misses, self.table.len(), self.bytes, self.evictions, self.connects))
    }
}
fn parameter<'a>(query: &'a str, name: &str) -> &'a str {
    for part in query.split('&') {
        if let Some((key, value)) = part.split_once('=') { if key == name { return value } }
    }
    ""
}
fn key(query: &str) -> Vec<u8> {
    let mut key = parameter(query, "k").as_bytes().to_vec(); key.push(0);
    key.extend_from_slice(parameter(query, "q").as_bytes()); key
}
struct Front { cache: Mutex<Cache>, upstream: SocketAddr }
fn response(status: u16, body: Bytes, cache: &str, closing: bool) -> Response<Body> {
    Response::builder().status(status).header("content-type", "application/json")
        .header("content-length", body.len()).header("x-cache", cache)
        .header("connection", if closing { "close" } else { "keep-alive" })
        .body(Body::from(body)).unwrap()
}
fn bad() -> io::Error { io::Error::new(io::ErrorKind::InvalidData, "upstream failed") }
fn parse_head(data: &[u8]) -> io::Result<(u16, usize)> {
    if !data.starts_with(b"HTTP/1.1 ") || data.len() < 12 || !data.is_ascii() { return Err(bad()) }
    let text = std::str::from_utf8(data).map_err(|_| bad())?;
    let status: u16 = text[9..12].parse().map_err(|_| bad())?;
    if !(200..=599).contains(&status) { return Err(bad()) }
    let mut length = None;
    for line in text.split("\r\n").skip(1) {
        let (name, value) = line.split_once(':').ok_or_else(bad)?;
        if name.eq_ignore_ascii_case("transfer-encoding") { return Err(bad()) }
        if name.eq_ignore_ascii_case("content-length") {
            if length.is_some() { return Err(bad()) }
            let value = value.trim_matches([' ', '\t']);
            if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) { return Err(bad()) }
            let parsed: usize = value.parse().map_err(|_| bad())?;
            if parsed > 4194304 { return Err(bad()) }
            length = Some(parsed);
        }
    }
    Ok((status, length.ok_or_else(bad)?))
}
async fn upstream(address: SocketAddr, target: &str) -> io::Result<(u16, Bytes)> {
    let mut socket = TcpStream::connect(address).await?;
    socket.set_nodelay(true)?;
    let host = match address.ip() { IpAddr::V6(ip) => format!("[{ip}]"), IpAddr::V4(ip) => ip.to_string() };
    let request = format!("GET {target} HTTP/1.1\r\nhost: {host}\r\nconnection: close\r\n\r\n");
    socket.write_all(request.as_bytes()).await?;
    let mut input = Vec::with_capacity(65536);
    let mut buffer = [0u8; 65536];
    let mut scan = 0;
    let mut framed = None;
    loop {
        let limit = (4194304 + 16384usize).checked_sub(input.len()).ok_or_else(bad)?.min(65536);
        if limit == 0 { return Err(bad()) }
        let read = socket.read(&mut buffer[..limit]).await?;
        if read == 0 { return Err(bad()) }
        input.extend_from_slice(&buffer[..read]);
        if framed.is_none() {
            while scan + 3 < input.len() {
                if &input[scan..scan + 4] == b"\r\n\r\n" {
                    let (status, length) = parse_head(&input[..scan])?;
                    framed = Some((scan + 4, status, length)); break
                }
                scan += 1;
                if scan >= 16380 { return Err(bad()) }
            }
        }
        if let Some((header, status, length)) = framed {
            if input.len() >= header + length { return Ok((status, Bytes::copy_from_slice(&input[header..header+length]))) }
        }
    }
}
async fn handle(State(front): State<Arc<Front>>, method: Method, uri: Uri, headers: HeaderMap) -> Response<Body> {
    let closing = headers.get("connection").and_then(|v| v.to_str().ok()).is_some_and(|v|
        v.split(',').any(|t| t.trim().eq_ignore_ascii_case("close")));
    if method != Method::GET { return response(405, Bytes::from_static(b"method not allowed"), "none", closing) }
    if uri.path() == "/stats" { return response(200, front.cache.lock().unwrap().stats(), "none", closing) }
    let Some(query) = uri.query() else { return response(404, Bytes::from_static(b"not found"), "none", closing) };
    if uri.path() != "/api/search" { return response(404, Bytes::from_static(b"not found"), "none", closing) }
    let key = key(query);
    {
        let mut cache = front.cache.lock().unwrap();
        if let Some(body) = cache.lookup(&key) { cache.hits += 1; return response(200, body, "hit", closing) }
        cache.misses += 1; cache.connects += 1;
    }
    let target = uri.path_and_query().unwrap().as_str();
    match tokio::time::timeout(Duration::from_millis(5000), upstream(front.upstream, target)).await {
        Ok(Ok((status, body))) => {
            if status == 200 { front.cache.lock().unwrap().insert(key, body.clone()) }
            response(status, body, if status == 200 { "miss" } else { "error" }, closing)
        }
        _ => response(502, Bytes::from_static(b"upstream failed"), "error", closing),
    }
}
#[tokio::main(flavor = "current_thread")]
async fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    assert!(args.len() >= 3, "front PORT UPSTREAM_IP UPSTREAM_PORT [ENTRIES] [BYTES]");
    let port: u16 = args[0].parse().unwrap();
    let upstream = SocketAddr::new(args[1].parse::<IpAddr>().unwrap(), args[2].parse().unwrap());
    let entries = args.get(3).map(|v| v.parse().unwrap()).unwrap_or(100000);
    let bytes = args.get(4).map(|v| v.parse().unwrap()).unwrap_or(268435456);
    assert!((1..=1000000).contains(&entries) && (1..=1073741824).contains(&bytes));
    let front = Arc::new(Front { cache: Mutex::new(Cache::new(entries, bytes)), upstream });
    let listener = TcpListener::bind(("127.0.0.1", port)).await.unwrap();
    println!("{}", listener.local_addr().unwrap().port()); io::stdout().flush().unwrap();
    axum::serve(listener.tap_io(|socket| socket.set_nodelay(true).unwrap()),
        Router::new().fallback(any(handle)).with_state(front)).await.unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_lru_byte_bound_and_raw_key() {
        let mut c = Cache::new(3, 5);
        c.insert(b"a".to_vec(), Bytes::from_static(b"a")); c.insert(b"b".to_vec(), Bytes::from_static(b"b"));
        c.lookup(b"a"); c.insert(b"c".to_vec(), Bytes::from_static(b"c"));
        assert!(c.lookup(b"b").is_none()); assert_eq!(c.bytes, 4); assert_eq!(c.evictions, 1);
        c.insert(b"oversize".to_vec(), Bytes::from_static(b"ignored")); assert_eq!(c.table.len(), 2);
        c.insert(b"a".to_vec(), Bytes::from_static(b"z")); assert_eq!(c.bytes, 4); assert_eq!(c.evictions, 2);
        assert_eq!(key("k=10&q=a%20b&q=ignored"), b"10\0a%20b");
        assert_ne!(key("k=10&q=a+b"), key("k=10&q=a%20b"));
    }
}
