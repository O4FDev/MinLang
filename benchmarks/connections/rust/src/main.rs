// Rust comparator for run.py: a current-thread tokio server with one task per
// connection and the same HTTP/1.1 keep-alive responses as the Minyar server.
use std::sync::atomic::{AtomicI64, Ordering};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;

static SERVED: AtomicI64 = AtomicI64::new(0);

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let port = std::env::var("LIVEPATCH_PORT").unwrap_or_else(|_| "0".into());
    let listener = TcpListener::bind(format!("127.0.0.1:{}", port)).await.unwrap();
    println!("LISTENING {}", listener.local_addr().unwrap().port());
    loop {
        let (mut socket, _) = listener.accept().await.unwrap();
        tokio::spawn(async move {
            let mut buffer = vec![0u8; 4096];
            let mut used = 0;
            loop {
                match socket.read(&mut buffer[used..]).await {
                    Ok(0) | Err(_) => return,
                    Ok(n) => used += n,
                }
                while let Some(end) = buffer[..used].windows(4).position(|w| w == b"\r\n\r\n") {
                    let body = format!("version=1 served={}\n", SERVED.fetch_add(1, Ordering::Relaxed) + 1);
                    let reply = format!("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {}\r\n\r\n{}", body.len(), body);
                    if socket.write_all(reply.as_bytes()).await.is_err() { return; }
                    buffer.copy_within(end + 4..used, 0);
                    used -= end + 4;
                }
                if used == buffer.len() { return; }
            }
        });
    }
}
