//! Independent Quinn/rustls peer-edge device-scale client.
//! AUTHENTICATED means TLS plus initial control writes, not Redis admission:
//! the external fixture observes every unique live entry before supplying START_FILE.
use std::{
    env, fs,
    io::Read,
    net::SocketAddr,
    path::{Path, PathBuf},
    sync::{Arc, atomic::{AtomicUsize, Ordering}},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use quinn::crypto::rustls::QuicClientConfig;
use rustls::pki_types::{CertificateDer, PrivatePkcs8KeyDer};
use tokio::{sync::watch, task::{JoinError, JoinSet}, time::Instant};

type Failure = Box<dyn std::error::Error + Send + Sync>;
const HEALTH: &[u8] = br#"{"in_flight":0,"max_concurrent":8,"paused":false,"policy_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","public_ip":"203.0.113.2","asn":64500,"country":"GB"}"#;
const HEARTBEAT_INTERVAL: Duration = Duration::from_secs(15);
const SETUP_LIMIT: Duration = Duration::from_secs(1800);
const IO_LIMIT: Duration = Duration::from_secs(20);

struct Options {
    address: SocketAddr,
    fixtures: PathBuf,
    peers: usize,
    duration: Duration,
    start_file: PathBuf,
    setup_delay: Duration,
}

fn decimal(value: &str) -> Result<u64, String> {
    if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit())
        || (value.len() > 1 && value.starts_with('0'))
    {
        return Err("expected a canonical unsigned integer".into());
    }
    value.parse().map_err(|_| "integer exceeds range".into())
}

impl Options {
    fn parse(args: &[String]) -> Result<Self, String> {
        if !(5..=6).contains(&args.len()) {
            return Err("usage: peer-edge-scale ADDRESS FIXTURES PEERS DURATION_SECONDS START_FILE [SETUP_DELAY_MS]".into());
        }
        let address: SocketAddr = args[0].parse().map_err(|_| "ADDRESS must be an IPv4 or bracketed IPv6 socket address")?;
        if address.port() == 0 || args[1].is_empty() || args[4].is_empty() {
            return Err("nonzero port and fixture/start paths are required".into());
        }
        let peers = decimal(&args[2])?;
        let seconds = decimal(&args[3])?;
        let delay = if args.len() == 6 { decimal(&args[5])? } else { 0 };
        if !(1..=20000).contains(&peers) || !(30..=82800).contains(&seconds) || delay > 10000 {
            return Err("bounded peers 1..20000, duration 30..82800 and setup delay 0..10000 are required".into());
        }
        Ok(Self {
            address, fixtures: args[1].clone().into(), peers: peers as usize,
            duration: Duration::from_secs(seconds), start_file: args[4].clone().into(),
            setup_delay: Duration::from_millis(delay),
        })
    }
}

// Deliberately accepts only this small JSON object. No floats, extra/duplicate
// fields, strings, permissive numeric conversions or trailing JSON are accepted.
fn parse_start(bytes: &[u8]) -> Result<u64, String> {
    if bytes.len() > 256 { return Err("start file exceeds 256 bytes".into()); }
    let text = std::str::from_utf8(bytes).map_err(|_| "start file is not UTF-8")?;
    let body = text.trim_matches([' ', '\t', '\r', '\n'])
        .strip_prefix('{').and_then(|s| s.strip_suffix('}'))
        .ok_or("start file must be one JSON object")?;
    let body = body.trim_start_matches([' ', '\t', '\r', '\n'])
        .strip_prefix("\"utc_start\"").ok_or("start file requires utc_start")?;
    let value = body.trim_start_matches([' ', '\t', '\r', '\n'])
        .strip_prefix(':').ok_or("start file requires colon")?
        .trim_matches([' ', '\t', '\r', '\n']);
    decimal(value)
}

fn fresh_start(utc: u64, wall: SystemTime, clock: Instant) -> Result<Instant, String> {
    let date = UNIX_EPOCH.checked_add(Duration::from_secs(utc)).ok_or("start timestamp overflow")?;
    let wait = date.duration_since(wall).map_err(|_| "start timestamp is stale")?;
    if wait.is_zero() || wait > Duration::from_secs(30) {
        return Err("start must be a fresh future UTC second within thirty seconds".into());
    }
    Ok(clock + wait)
}

fn read_start(path: &Path) -> Result<Option<(u64, Instant)>, Failure> {
    let file = match fs::File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    };
    let mut bytes = Vec::new();
    file.take(257).read_to_end(&mut bytes)?;
    let utc = parse_start(&bytes)?;
    let clock = Instant::now();
    let start = fresh_start(utc, SystemTime::now(), clock)?;
    Ok(Some((utc, start)))
}

fn control_frame(kind: u8, body: &[u8]) -> Result<Vec<u8>, String> {
    if !matches!(kind, 1 | 2) || body.is_empty() || body.len() > 16384 {
        return Err("invalid bounded HPW1 control frame".into());
    }
    let mut frame = Vec::with_capacity(16 + body.len());
    frame.extend_from_slice(b"HPW1");
    frame.extend_from_slice(&[kind, 0, 0, 0]);
    frame.extend_from_slice(&0u32.to_be_bytes());
    frame.extend_from_slice(&(body.len() as u32).to_be_bytes());
    frame.extend_from_slice(body);
    Ok(frame)
}

fn hello_frame(id: usize) -> Result<Vec<u8>, String> {
    if id >= 20000 { return Err("device identity exceeds cohort bound".into()); }
    control_frame(1, format!(r#"{{"device_id":"device-{id:05}","exit_id":"exit-{id:05}"}}"#).as_bytes())
}

fn heartbeat_phase(id: usize) -> Duration {
    // 7919 is coprime to 15000, spreading the first periodic write across all
    // millisecond slots. Subsequent writes retain that phase every 15 seconds.
    Duration::from_millis(1 + (id as u64 * 7919) % 15000)
}

fn close_time(start: Instant, duration: Duration, id: usize) -> Instant {
    start + duration + Duration::from_secs(10) + Duration::from_millis(id as u64 * 5)
}

async fn write_hello(send: &mut quinn::SendStream, bytes: &[u8]) -> Result<(), Failure> {
    tokio::time::timeout(IO_LIMIT, async {
        // Split the magic, header and payload across separate asynchronous
        // writes, exercising the edge decoder before its first heartbeat.
        send.write_all(&bytes[..3]).await?;
        tokio::time::sleep(Duration::from_millis(1)).await;
        send.write_all(&bytes[3..11]).await?;
        tokio::time::sleep(Duration::from_millis(1)).await;
        send.write_all(&bytes[11..]).await?;
        Ok::<_, Failure>(())
    }).await??;
    Ok(())
}

async fn device(
    endpoint: quinn::Endpoint,
    config: quinn::ClientConfig,
    address: SocketAddr,
    id: usize,
    peers: usize,
    duration: Duration,
    mut start: watch::Receiver<Option<Instant>>,
    authenticated: Arc<AtomicUsize>,
) -> Result<u64, Failure> {
    let connection = tokio::time::timeout(IO_LIMIT, endpoint.connect_with(config, address, "localhost")?).await??;
    let (mut send, mut receive) = tokio::time::timeout(IO_LIMIT, connection.open_bi()).await??;
    write_hello(&mut send, &hello_frame(id)?).await?;
    let health = control_frame(2, HEALTH)?;
    tokio::time::timeout(IO_LIMIT, send.write_all(&health)).await??;
    let count = authenticated.fetch_add(1, Ordering::SeqCst) + 1;
    if count == 1 || count % 1000 == 0 || count == peers {
        println!("AUTHENTICATED {count}");
    }

    // Keep both halves alive. Any EOF, reset, STOP_SENDING, unexpected control
    // response or connection loss is a failure even while awaiting the start.
    let stopped = send.stopped();
    tokio::pin!(stopped);
    let mut input = [0u8; 1];
    let mut heartbeats = 1u64;
    let mut next_heartbeat = Instant::now() + heartbeat_phase(id);
    let mut close_at = (*start.borrow()).map(|instant| close_time(instant, duration, id));
    loop {
        let closing = close_at.unwrap_or_else(|| Instant::now() + SETUP_LIMIT);
        tokio::select! {
            biased;
            error = connection.closed() => return Err(format!("device-{id:05} closed early: {error}").into()),
            value = receive.read(&mut input) => {
                return Err(format!("device-{id:05} control ended or received unexpected input: {value:?}").into());
            },
            value = &mut stopped => {
                return Err(format!("device-{id:05} control send stopped early: {value:?}").into());
            },
            changed = start.changed(), if close_at.is_none() => {
                changed.map_err(|_| "measurement coordinator disappeared")?;
                if let Some(instant) = *start.borrow_and_update() {
                    close_at = Some(close_time(instant, duration, id));
                }
            },
            _ = tokio::time::sleep_until(next_heartbeat) => {
                tokio::time::timeout(IO_LIMIT, send.write_all(&health)).await??;
                heartbeats += 1;
                next_heartbeat += HEARTBEAT_INTERVAL;
                // Never emit a catch-up burst after a scheduler stall. The
                // independent Redis oracle checks actual heartbeat freshness.
                if next_heartbeat <= Instant::now() {
                    next_heartbeat = Instant::now() + HEARTBEAT_INTERVAL;
                }
            },
            _ = tokio::time::sleep_until(closing), if close_at.is_some() => {
                send.finish()?;
                connection.close(0u32.into(), b"device-scale measurement complete");
                return Ok(heartbeats);
            },
        }
    }
}

fn premature_completion(result: Option<Result<Result<u64, Failure>, JoinError>>) -> Failure {
    match result {
        Some(Ok(Err(error))) => error,
        Some(Err(error)) => error.into(),
        _ => "a device task ended before the common measurement start".into(),
    }
}

async fn run(options: Options) -> Result<(), Failure> {
    if options.start_file.try_exists()? {
        return Err("START_FILE must not exist before this cohort is admitted".into());
    }
    let mut roots = rustls::RootCertStore::empty();
    roots.add(CertificateDer::from(fs::read(options.fixtures.join("root.der"))?))?;
    let roots = Arc::new(roots);
    let key = fs::read(options.fixtures.join("leaf.pk8"))?;
    let mut transport = quinn::TransportConfig::default();
    transport.max_idle_timeout(Some(Duration::from_secs(60).try_into()?));
    transport.keep_alive_interval(None);
    let transport = Arc::new(transport);
    let bind = if options.address.is_ipv6() { "[::]:0" } else { "0.0.0.0:0" };
    let endpoint = quinn::Endpoint::client(bind.parse()?)?;
    let authenticated = Arc::new(AtomicUsize::new(0));
    let (start_tx, start_rx) = watch::channel(None);
    let mut devices = JoinSet::new();
    let setup_deadline = Instant::now() + SETUP_LIMIT;

    for id in 0..options.peers {
        if Instant::now() >= setup_deadline { return Err("cohort setup exceeded 1800 seconds".into()); }
        if let Some(result) = devices.try_join_next() { return Err(premature_completion(Some(result))); }
        let cert = CertificateDer::from(fs::read(options.fixtures.join(format!("device-{id:05}.der")))?);
        let mut crypto = rustls::ClientConfig::builder()
            .with_root_certificates(roots.clone())
            .with_client_auth_cert(vec![cert], PrivatePkcs8KeyDer::from(key.clone()).into())?;
        crypto.alpn_protocols = vec![b"hearth-peer".to_vec()];
        crypto.resumption = rustls::client::Resumption::disabled();
        let mut config = quinn::ClientConfig::new(Arc::new(QuicClientConfig::try_from(crypto)?));
        config.transport_config(transport.clone());
        devices.spawn(device(
            endpoint.clone(), config, options.address, id, options.peers,
            options.duration, start_rx.clone(), authenticated.clone(),
        ));
        if options.setup_delay.is_zero() {
            tokio::task::yield_now().await;
        } else {
            tokio::select! {
                result = devices.join_next() => return Err(premature_completion(result)),
                _ = tokio::time::sleep_until(setup_deadline) => return Err("cohort setup exceeded 1800 seconds".into()),
                _ = tokio::time::sleep(options.setup_delay) => {},
            }
        }
    }

    // Only the independent live-state fixture may authorize the measured
    // window. Existing devices keep renewing health throughout cohort setup.
    let (utc, start) = loop {
        if authenticated.load(Ordering::SeqCst) == options.peers {
            if let Some(start) = read_start(&options.start_file)? { break start; }
        }
        tokio::select! {
            result = devices.join_next() => return Err(premature_completion(result)),
            _ = tokio::time::sleep_until(setup_deadline) => return Err("cohort admission/start exceeded 1800 seconds".into()),
            _ = tokio::time::sleep(Duration::from_millis(200)) => {},
        }
    };
    start_tx.send(Some(start)).map_err(|_| "all device tasks disappeared before measurement")?;
    println!("START {utc}");
    let mut total = 0u64;
    let mut completed = 0usize;
    while let Some(result) = devices.join_next().await {
        total += result??;
        completed += 1;
    }
    if completed != options.peers || authenticated.load(Ordering::SeqCst) != options.peers {
        return Err("incomplete authenticated device cohort".into());
    }
    tokio::time::timeout(Duration::from_secs(30), endpoint.wait_idle()).await?;
    println!("RESULT {} {total}", options.peers);
    Ok(())
}

#[tokio::main(flavor = "multi_thread", worker_threads = 1)]
async fn main() -> Result<(), Failure> {
    run(Options::parse(&env::args().skip(1).collect::<Vec<_>>())?).await
}

#[cfg(test)]
mod tests {
    use super::*;
    fn arguments() -> Vec<String> {
        ["[::1]:24567", "/fixtures", "32", "30", "/fresh-start"].map(str::to_string).to_vec()
    }
    #[test]
    fn bounded_arguments_cover_extremes_and_ipv6() {
        let mut args = arguments();
        let value = Options::parse(&args).unwrap();
        assert!(value.address.is_ipv6());
        assert_eq!(value.peers, 32);
        assert_eq!(value.duration, Duration::from_secs(30));
        assert_eq!(value.setup_delay, Duration::ZERO);
        args[0] = "127.0.0.1:24567".into();
        args[2] = "20000".into();
        args[3] = "82800".into();
        args.push("10000".into());
        let value = Options::parse(&args).unwrap();
        assert!(value.address.is_ipv4());
        assert_eq!(value.peers, 20000);
        assert_eq!(value.setup_delay, Duration::from_secs(10));
        args[2] = "1".into();
        args[3] = "30".into();
        args[5] = "0".into();
        assert!(Options::parse(&args).is_ok());
    }
    #[test]
    fn malformed_arguments_never_start_a_partial_cohort() {
        let original = arguments();
        for (field, values) in [
            (0, vec!["localhost:443", "[::1]:0", "127.0.0.1:70000", ""]),
            (1, vec![""]),
            (2, vec!["0", "20001", "-1", "+1", "1.0", " 2", "02", "18446744073709551616"]),
            (3, vec!["0", "29", "82801", "NaN", "30.0"]),
            (4, vec![""]),
        ] {
            for input in values {
                let mut args = original.clone();
                args[field] = input.into();
                assert!(Options::parse(&args).is_err(), "{field}: {input}");
            }
        }
        for delay in ["10001", "-1", "+1", "1.5", " 0"] {
            let mut args = original.clone();
            args.push(delay.into());
            assert!(Options::parse(&args).is_err(), "{delay}");
        }
        for length in [0, 4, 7] {
            let mut args = original.clone();
            args.resize(length, "extra".into());
            assert!(Options::parse(&args).is_err(), "{length}");
        }
    }
    #[test]
    fn start_is_one_strict_integer_object() {
        for input in [r#"{"utc_start":12345}"#, " \n{ \"utc_start\" : 12345 }\t"] {
            assert_eq!(parse_start(input.as_bytes()).unwrap(), 12345);
        }
        for input in [
            "", "[]", "{}", r#"{"utc_start":"12345"}"#,
            r#"{"utc_start":12.5}"#, r#"{"utc_start":1e5}"#,
            r#"{"utc_start":-1}"#, r#"{"utc_start":+1}"#,
            r#"{"utc_start":0123}"#, r#"{"utc_start":true}"#,
            r#"{"utc_start":NaN}"#, r#"{"utc_start":123,"extra":1}"#,
            r#"{"utc_start":123,"utc_start":124}"#, r#"{"utc_start":123,}"#,
            r#"{"utc_start":18446744073709551616}"#, r#"{"UTC_START":123}"#,
            "{\"utc_start\":123}\0", "{\"utc_start\":123} {}",
        ] {
            assert!(parse_start(input.as_bytes()).is_err(), "{input:?}");
        }
        assert!(parse_start(&vec![b' '; 257]).is_err());
        assert!(parse_start(&[0xff]).is_err());
    }
    #[test]
    fn start_is_fresh_and_maps_to_one_monotonic_deadline() {
        let wall = UNIX_EPOCH + Duration::from_millis(100_250);
        let clock = Instant::now();
        assert_eq!(fresh_start(115, wall, clock).unwrap(), clock + Duration::from_millis(14_750));
        assert_eq!(fresh_start(130, wall, clock).unwrap(), clock + Duration::from_millis(29_750));
        for utc in [0, 99, 100, 131, u64::MAX] {
            assert!(fresh_start(utc, wall, clock).is_err(), "{utc}");
        }
    }
    #[test]
    fn hpw1_metadata_frames_have_exact_control_header_and_identity() {
        let hello = hello_frame(19999).unwrap();
        assert_eq!(&hello[..8], b"HPW1\x01\0\0\0");
        assert_eq!(&hello[8..12], &[0, 0, 0, 0]);
        let body = br#"{"device_id":"device-19999","exit_id":"exit-19999"}"#;
        assert_eq!(&hello[12..16], &(body.len() as u32).to_be_bytes());
        assert_eq!(&hello[16..], body);
        let heartbeat = control_frame(2, HEALTH).unwrap();
        assert_eq!(&heartbeat[..8], b"HPW1\x02\0\0\0");
        assert_eq!(&heartbeat[16..], HEALTH);
        assert!(control_frame(0, b"{}").is_err());
        assert!(control_frame(3, b"{}").is_err());
        assert!(control_frame(1, b"").is_err());
        assert!(control_frame(1, &vec![b'a'; 16385]).is_err());
        assert!(control_frame(2, &vec![b'a'; 16384]).is_ok());
    }
    #[test]
    fn heartbeat_and_close_schedules_are_staggered_without_skipping_holds() {
        assert_eq!(heartbeat_phase(0), Duration::from_millis(1));
        let phases: std::collections::HashSet<_> = (0..15000).map(heartbeat_phase).collect();
        assert_eq!(phases.len(), 15000);
        assert!(phases.iter().all(|p| *p <= Duration::from_secs(15)));
        let start = Instant::now();
        assert_eq!(close_time(start, Duration::from_secs(30), 0), start + Duration::from_secs(40));
        assert_eq!(close_time(start, Duration::from_secs(30), 19999), start + Duration::from_millis(139_995));
    }
}
