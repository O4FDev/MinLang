// Rust peer for main.min: Mandelbrot escape counts, rows interleaved over 4 std threads.
use std::io::Write;

const LIMIT: u32 = 256;
const THREADS: usize = 4;

fn escape_time(px: usize, py: usize, width: usize, height: usize) -> u32 {
    let x = px as f64 / width as f64 * 3.0 - 2.2;
    let y = py as f64 / height as f64 * 2.4 - 1.2;
    let (mut real, mut imaginary) = (0.0f64, 0.0f64);
    let mut iterations = 0;
    while real * real + imaginary * imaginary <= 4.0 && iterations < LIMIT {
        let next = real * real - imaginary * imaginary + x;
        imaginary = 2.0 * real * imaginary + y;
        real = next;
        iterations += 1;
    }
    iterations
}

fn main() {
    let width: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let height = width * 2 / 3;
    let mut counts = vec![0u32; width * height];
    std::thread::scope(|scope| {
        // Row r goes to thread r % THREADS, like the C and C++ peers.
        let mut parts: Vec<Vec<(usize, &mut [u32])>> = (0..THREADS).map(|_| Vec::new()).collect();
        for (py, row) in counts.chunks_mut(width).enumerate() { parts[py % THREADS].push((py, row)); }
        for part in parts {
            scope.spawn(move || {
                for (py, row) in part {
                    for (px, slot) in row.iter_mut().enumerate() { *slot = escape_time(px, py, width, height); }
                }
            });
        }
    });
    let (mut total, mut inside, mut rows) = (0i64, 0i64, 0i64);
    let mut histogram = [0i64; 8];
    for row in counts.chunks(width) {
        let mut sum = 0i64;
        for &count in row {
            sum += count as i64;
            if count == LIMIT { inside += 1 } else { histogram[(count * 8 / LIMIT) as usize] += 1 }
        }
        total += sum;
        rows = (rows * 31 + sum) % 1000000007;
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "total {}\ninside {}\nrows {}", total, inside, rows).unwrap();
    for (b, h) in histogram.iter().enumerate() { writeln!(out, "escape {} {}", b, h).unwrap(); }
}
