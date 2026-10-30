// Rust peer for main.min: parse request lines, look up users, format JSON responses.
use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::io::Write;

// Multiplicative hash for Integer keys (std only).
#[derive(Default)]
struct IntHash(u64);
impl Hasher for IntHash {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, _: &[u8]) { unreachable!() }
    fn write_i64(&mut self, v: i64) { self.0 = (v as u64).wrapping_mul(0x9E3779B97F4A7C15).rotate_left(26); }
}

struct User { id: i64, name: String, email: String, age: i64, score: i64 }

fn main() {
    let requests: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut users: HashMap<i64, User, BuildHasherDefault<IntHash>> = HashMap::default();
    users.reserve(16384);
    for id in 0..10000i64 {
        let name = format!("user{}", id);
        let email = format!("{}@example.com", name);
        users.insert(id * 7, User { id: id * 7, name, email, age: 18 + id % 60, score: (id * 7919) % 100000 });
    }
    let (mut bytes, mut found, mut seed) = (0i64, 0i64, 42i64);
    let mut line: Vec<u8> = Vec::with_capacity(64);
    let mut response: Vec<u8> = Vec::with_capacity(256);
    for _ in 0..requests {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        line.clear();
        write!(line, "GET /users/{} HTTP/1.1", seed % 80000).unwrap();
        let mut parts = line.split(|&b| b == b' ');
        let path = parts.nth(1).unwrap();
        if !path.starts_with(b"/users/") { continue; }
        let id = std::str::from_utf8(&path[7..]).unwrap().parse::<i64>().unwrap();
        response.clear();
        match users.get(&id) {
            Some(u) => {
                write!(response, "{{\"id\":{},\"name\":\"{}\",\"email\":\"{}\",\"age\":{},\"score\":{}}}", u.id, u.name, u.email, u.age, u.score).unwrap();
                found += 1;
            }
            None => write!(response, "{{\"error\":\"not found\",\"id\":{}}}", id).unwrap(),
        }
        bytes += response.len() as i64;
    }
    println!("{}\n{}", found, bytes);
}
