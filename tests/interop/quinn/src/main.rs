//! Independent Quinn/rustls client; application sends one bounded echo stream.
use std::{env, fs, sync::{Arc, atomic::{AtomicUsize,Ordering}}, time::Duration};
use quinn::crypto::rustls::QuicClientConfig;
use rustls::pki_types::{CertificateDer, PrivatePkcs8KeyDer};

fn remote_address(value: &str) -> Result<std::net::SocketAddr, std::net::AddrParseError> {
    if value.contains(':') { value.parse() } else { format!("127.0.0.1:{value}").parse() }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    let mut roots = rustls::RootCertStore::empty();
    roots.add(CertificateDer::from(fs::read(&args[2])?))?;
    if args[1] == "server" {
        let verifier = rustls::server::WebPkiClientVerifier::builder(Arc::new(roots)).build()?;
        let mut crypto = rustls::ServerConfig::builder()
            .with_client_cert_verifier(verifier)
            .with_single_cert(vec![CertificateDer::from(fs::read(&args[3])?)],
                              PrivatePkcs8KeyDer::from(fs::read(&args[4])?).into())?;
        crypto.alpn_protocols = vec![b"minyar-test".to_vec()];
        if env::var_os("MINYAR_QUINN_EARLY").is_some() { crypto.max_early_data_size = u32::MAX; }
        let config = quinn::ServerConfig::with_crypto(Arc::new(quinn::crypto::rustls::QuicServerConfig::try_from(crypto)?));
        let endpoint = quinn::Endpoint::server(config, "127.0.0.1:0".parse()?)?;
        println!("READY {}", endpoint.local_addr()?.port());
        tokio::time::timeout(Duration::from_secs(15), async {
            let repeats = if env::var_os("MINYAR_QUINN_RESUME").is_some() { 2 } else { 1 };
            for _ in 0..repeats {
            let connection = endpoint.accept().await.ok_or("endpoint closed")?.await?;
            let (mut send, mut receive) = connection.accept_bi().await?;
            let data = receive.read_to_end(65536).await?;
            if env::var_os("MINYAR_QUINN_KEY_UPDATE").is_some() { connection.force_key_update(); }
            send.write_all(&data).await?;
            send.finish()?;
            connection.closed().await;
            println!("Quinn/rustls server authenticated Minyar client");
            }
            Ok::<_, Box<dyn std::error::Error>>(())
        }).await??;
        return Ok(());
    }
    let mut crypto = rustls::ClientConfig::builder()
        .with_root_certificates(roots)
        .with_client_auth_cert(vec![CertificateDer::from(fs::read(&args[3])?)],
                              PrivatePkcs8KeyDer::from(fs::read(&args[4])?).into())?;
    crypto.alpn_protocols = vec![b"minyar-test".to_vec()];
    crypto.enable_early_data = env::var_os("MINYAR_QUINN_EARLY").is_some();
    let mut config = quinn::ClientConfig::new(Arc::new(QuicClientConfig::try_from(crypto)?));
    let mut transport=quinn::TransportConfig::default();
    transport.keep_alive_interval(Some(Duration::from_secs(15)));config.transport_config(Arc::new(transport));
    let mut endpoint = quinn::Endpoint::client("0.0.0.0:0".parse()?)?;
    endpoint.set_default_client_config(config);
    if args.len() > 7 {
        let duration: u64 = args[5].parse()?;
        let peers: usize = args[6].parse()?;
        let interval: u64 = args[7].parse()?;
        if peers==0 || peers>16384 || interval==0 || duration==0 { return Err("invalid bounded scale configuration".into()); }
        let setup_delay: u64 = env::var("MINYAR_QUINN_SETUP_DELAY_MS").unwrap_or_else(|_| "0".into()).parse()?;
        if setup_delay>10000 { return Err("setup delay exceeds bound".into()); }
        let authenticated=Arc::new(AtomicUsize::new(0));
        let barrier=Arc::new(tokio::sync::Barrier::new(peers));
        let mut clients = tokio::task::JoinSet::new();
        for id in 0..peers {
            let endpoint = endpoint.clone();
            let remote = remote_address(&args[1])?;
            let authenticated=authenticated.clone();
            let barrier=barrier.clone();
            clients.spawn(async move {
                let connection = tokio::time::timeout(Duration::from_secs(20),endpoint.connect(remote, "localhost")?).await??;
                let count=authenticated.fetch_add(1,Ordering::SeqCst)+1;
                if count==1 || count%1000==0 || count==peers { println!("AUTHENTICATED {count}"); }
                let (mut send, mut receive) = connection.open_bi().await?;
                tokio::time::timeout(Duration::from_secs(600),barrier.wait()).await?;
                let started = tokio::time::Instant::now();
                // Authentication completes before the common two-hour window.
                // Spread first heartbeats across the interval rather than
                // releasing ten thousand writes in a single scheduler burst.
                tokio::time::sleep(Duration::from_millis((id as u64*7919)%interval)).await;
                let mut echoes = 0u64;
                while started.elapsed() < Duration::from_secs(duration) {
                    let mut message = [0u8; 64];
                    message[..8].copy_from_slice(&(id as u64).to_be_bytes());
                    message[8..16].copy_from_slice(&echoes.to_be_bytes());
                    send.write_all(&message).await?;
                    let mut reply = [0u8; 64];
                    receive.read_exact(&mut reply).await?;
                    assert_eq!(reply, message);
                    echoes += 1;
                    tokio::time::sleep(Duration::from_millis(interval)).await;
                }
                send.finish()?;
                connection.close(0u32.into(), b"soak complete");
                Ok::<_, Box<dyn std::error::Error + Send + Sync>>(echoes)
            });
            if setup_delay>0 { tokio::time::sleep(Duration::from_millis(setup_delay)).await; }
        }
        let mut total = 0u64;
        while let Some(result) = clients.join_next().await {
            total += result?.map_err(|e| e.to_string())?;
        }
        endpoint.wait_idle().await;
        println!("RESULT {peers} {total}");
        return Ok(());
    }
    tokio::time::timeout(Duration::from_secs(10), async {
        let repeats = if env::var_os("MINYAR_QUINN_RESUME").is_some() { 2 } else { 1 };
        for iteration in 0..repeats {
        let connecting = endpoint.connect(remote_address(&args[1])?, "localhost")?;
        let (connection, early) = if iteration == 1 && env::var_os("MINYAR_QUINN_EARLY").is_some() {
            let (connection, accepted) = connecting.into_0rtt().map_err(|_| "peer did not provide early-data ticket")?;
            (connection, Some(accepted))
        } else { (connecting.await?, None) };
        if env::var_os("MINYAR_QUINN_KEY_UPDATE").is_some() { connection.force_key_update(); }
        if env::var_os("MINYAR_QUINN_REBIND").is_some() {
            tokio::time::sleep(Duration::from_millis(100)).await;
            let socket = std::net::UdpSocket::bind("0.0.0.0:0")?;
            socket.set_nonblocking(true)?;
            endpoint.rebind(socket)?;
        }
        let (mut send, mut receive) = connection.open_bi().await?;
        let message = b"Quinn authenticated Minyar QUIC";
        send.write_all(message).await?;
        send.finish()?;
        let echoed = receive.read_to_end(65536).await?;
        assert_eq!(echoed, message);
        if let Some(accepted) = early { assert!(accepted.await, "Minyar rejected initial early attempt"); println!("Quinn 0-RTT accepted"); }
        println!("Quinn/rustls to Minyar: authenticated UDP echo passed");
        connection.close(0u32.into(), b"done");
        endpoint.wait_idle().await;
        }
        Ok::<_, Box<dyn std::error::Error>>(())
    }).await??;
    Ok(())
}
