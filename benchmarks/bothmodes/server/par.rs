// Parallel Rust peer for main.min (std only): the 64 loopback connections are
// split over MINYAR_PARALLEL_THREADS threads exactly like main.min: shard s owns
// connections s, s + T, ... with its own listener, its own event loop (epoll on
// Linux through extern "C", poll elsewhere) and its own copy of the table.
use std::io::{ErrorKind, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::os::fd::AsRawFd;

const CONNECTIONS: i64 = 64;
const KEYS: i64 = 65536;
const MODULUS: i64 = 1000000007;

#[cfg(target_os = "linux")]
mod reactor {
    #[cfg_attr(target_arch = "x86_64", repr(C, packed))]
    #[cfg_attr(not(target_arch = "x86_64"), repr(C))]
    #[derive(Clone, Copy)]
    pub struct EpollEvent { pub events: u32, pub data: u64 }
    extern "C" {
        fn epoll_create1(flags: i32) -> i32;
        fn epoll_ctl(epfd: i32, op: i32, fd: i32, event: *mut EpollEvent) -> i32;
        fn epoll_wait(epfd: i32, events: *mut EpollEvent, maxevents: i32, timeout: i32) -> i32;
        fn close(fd: i32) -> i32;
    }
    pub struct Reactor { fd: i32, events: Vec<EpollEvent> }
    impl Reactor {
        pub fn new(_capacity: usize) -> Reactor { Reactor { fd: unsafe { epoll_create1(0) }, events: vec![EpollEvent { events: 0, data: 0 }; 256] } }
        pub fn add(&mut self, fd: i32, token: u64) {
            let mut ev = EpollEvent { events: 1 /* EPOLLIN */, data: token };
            if unsafe { epoll_ctl(self.fd, 1 /* EPOLL_CTL_ADD */, fd, &mut ev) } != 0 { panic!("epoll_ctl"); }
        }
        // Fills `ready` with the tokens of readable sockets.
        pub fn wait(&mut self, ready: &mut Vec<u64>) {
            ready.clear();
            let n = unsafe { epoll_wait(self.fd, self.events.as_mut_ptr(), 256, -1) };
            if n < 0 { if std::io::Error::last_os_error().kind() == std::io::ErrorKind::Interrupted { return; } panic!("epoll_wait"); }
            for e in &self.events[..n as usize] { ready.push(e.data); }
        }
    }
    impl Drop for Reactor { fn drop(&mut self) { unsafe { close(self.fd); } } }
}

#[cfg(not(target_os = "linux"))]
mod reactor {
    #[repr(C)]
    struct PollFd { fd: i32, events: i16, revents: i16 }
    extern "C" { fn poll(fds: *mut PollFd, nfds: u32, timeout: i32) -> i32; }
    pub struct Reactor { fds: Vec<PollFd>, tokens: Vec<u64> }
    impl Reactor {
        pub fn new(capacity: usize) -> Reactor { Reactor { fds: Vec::with_capacity(capacity), tokens: Vec::with_capacity(capacity) } }
        pub fn add(&mut self, fd: i32, token: u64) { self.fds.push(PollFd { fd, events: 1, revents: 0 }); self.tokens.push(token); }
        pub fn wait(&mut self, ready: &mut Vec<u64>) {
            ready.clear();
            let n = unsafe { poll(self.fds.as_mut_ptr(), self.fds.len() as u32, -1) };
            if n < 0 { if std::io::Error::last_os_error().kind() == std::io::ErrorKind::Interrupted { return; } panic!("poll"); }
            for (p, &t) in self.fds.iter().zip(&self.tokens) { if p.revents & (1 | 0x10 | 0x8) != 0 { ready.push(t); } }
        }
    }
}

fn mix(mut value: i64) -> i64 {
    for round in 0..3i64 {
        value ^= value >> 31;
        value = value.wrapping_mul(0x2545F4914F6CDD1D);
        value ^= value >> 29;
        value = value.wrapping_add(round);
    }
    value & 0x7FFFFFFFFFFFFFFF
}
fn number(data: &[u8], at: usize) -> i64 {
    let mut value = 0;
    for &c in &data[at..] { if !c.is_ascii_digit() { break; } value = value * 10 + (c - b'0') as i64; }
    value
}
fn send_all(mut stream: &TcpStream, mut data: &[u8]) {
    while !data.is_empty() {
        match stream.write(data) {
            Ok(n) => data = &data[n..],
            Err(e) if e.kind() == ErrorKind::WouldBlock || e.kind() == ErrorKind::Interrupted => {}
            Err(e) => panic!("write: {e}"),
        }
    }
}

struct Connection { id: i64, sent: i64, received: i64, client: TcpStream, server: TcpStream, client_in: Vec<u8>, server_in: Vec<u8> }

fn request(c: &mut Connection, line: &mut Vec<u8>) {
    line.clear();
    write!(line, "GET /item/{}\n", mix(c.id * 1000003 + c.sent) % KEYS).unwrap();
    send_all(&c.client, line);
    c.sent += 1;
}
// Appends what is readable; false when nothing was (would block).
fn read_some(mut stream: &TcpStream, buffer: &mut Vec<u8>) -> bool {
    let len = buffer.len();
    buffer.resize(len + 4096, 0);
    match stream.read(&mut buffer[len..]) {
        Ok(0) => panic!("connection closed"),
        Ok(n) => { buffer.truncate(len + n); true }
        Err(e) if e.kind() == ErrorKind::WouldBlock || e.kind() == ErrorKind::Interrupted => { buffer.truncate(len); false }
        Err(e) => panic!("read: {e}"),
    }
}

// Serves connections shard, shard + shards, ...; returns the checksum of their values.
fn serve(shard: i64, shards: i64, per_connection: i64) -> i64 {
    let table: Vec<i64> = (0..KEYS).map(|key| mix(key + 99991) % 1000000).collect();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let mut connections = Vec::new();
    let mut reactor = reactor::Reactor::new(2 * CONNECTIONS as usize);
    let mut id = shard;
    while id < CONNECTIONS {
        let client = TcpStream::connect(address).unwrap();
        let (server, _) = listener.accept().unwrap();
        for s in [&client, &server] { s.set_nonblocking(true).unwrap(); s.set_nodelay(true).unwrap(); }
        let index = connections.len() as u64;
        reactor.add(client.as_raw_fd(), index * 2);
        reactor.add(server.as_raw_fd(), index * 2 + 1);
        connections.push(Connection { id, sent: 0, received: 0, client, server, client_in: Vec::with_capacity(4096), server_in: Vec::with_capacity(4096) });
        id += shards;
    }
    let mut line = Vec::with_capacity(64);
    for c in connections.iter_mut() { request(c, &mut line); }
    let mut open = connections.len();
    let mut checksum = 0i64;
    let mut ready = Vec::with_capacity(256);
    while open > 0 {
        reactor.wait(&mut ready);
        for &token in &ready {
            let c = &mut connections[(token / 2) as usize];
            if token % 2 == 1 {
                if !read_some(&c.server, &mut c.server_in) { continue; }
                if c.server_in.last() == Some(&b'\n') {
                    let key = number(&c.server_in, 10);
                    line.clear();
                    write!(line, "OK {} {}\n", key, table[key as usize]).unwrap();
                    send_all(&c.server, &line);
                    c.server_in.clear();
                }
            } else {
                if !read_some(&c.client, &mut c.client_in) { continue; }
                if c.client_in.last() == Some(&b'\n') {
                    let key = number(&c.client_in, 3);
                    let mut digits = 3;
                    while c.client_in[digits] != b' ' { digits += 1; }
                    let value = number(&c.client_in, digits + 1);
                    if key != mix(c.id * 1000003 + c.received) % KEYS { panic!("answer for the wrong key"); }
                    checksum = (checksum + value * (c.id + 1)) % MODULUS;
                    c.received += 1;
                    c.client_in.clear();
                    if c.sent < per_connection { request(c, &mut line); } else { open -= 1; }
                }
            }
        }
    }
    checksum
}

fn main() {
    let per_connection: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let threads: i64 = std::env::var("MINYAR_PARALLEL_THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(4).clamp(1, 64);
    let shards = threads.min(CONNECTIONS);
    let workers: Vec<_> = (1..shards).map(|s| std::thread::spawn(move || serve(s, shards, per_connection))).collect();
    let mut checksum = serve(0, shards, per_connection);
    for w in workers { checksum = (checksum + w.join().unwrap()) % MODULUS; }
    let mut out = std::io::stdout().lock();
    writeln!(out, "requests {}", CONNECTIONS * per_connection).unwrap();
    writeln!(out, "checksum {}", checksum).unwrap();
}
