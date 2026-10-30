// Rust peer for main.min: dense matrix multiply over one contiguous Vec.
fn main() {
    let n: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut a = vec![0.0f64; n * n];
    let mut b = vec![0.0f64; n * n];
    let mut c = vec![0.0f64; n * n];
    for i in 0..n {
        for j in 0..n {
            a[i * n + j] = ((i * j) % 7 + 1) as f64;
            b[i * n + j] = ((i + j) % 5 + 1) as f64;
        }
    }
    for _round in 0..4 {
        for (i, ci) in c.chunks_exact_mut(n).enumerate() {
            for k in 0..n {
                let aik = a[i * n + k];
                let bk = &b[k * n..k * n + n];
                for (cij, &bkj) in ci.iter_mut().zip(bk) { *cij = *cij + aik * bkj; }
            }
        }
    }
    let mut sum = 0.0f64;
    for &v in &c { sum = sum + v; }
    println!("{}", sum as i64);
}
