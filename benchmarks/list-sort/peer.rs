use std::{env, fs, time::Instant};
fn main() {
    let args: Vec<String> = env::args().collect();
    let n: usize = args[2].parse().unwrap();
    let mut checksum: i64 = 0;
    if args[1] == "hashes" {
        let input = fs::read_to_string(&args[3]).unwrap();
        let mut values: Vec<&str> = input.lines().collect();
        assert_eq!(values.len(), n);
        let start = Instant::now(); values.sort(); println!("{}", start.elapsed().as_nanos());
        for value in values { for &byte in &value.as_bytes()[..8] { checksum = (checksum*131+byte as i64)%1000000007; } }
    } else if args[1] == "records" {
        let mut values: Vec<(i64,i64)> = (0..n).map(|i| (((i as i64*1103515245+12345)%2147483647)%1024, i as i64)).collect();
        let start = Instant::now(); values.sort_by(|a,b| a.0.cmp(&b.0)); println!("{}", start.elapsed().as_nanos());
        for value in values { checksum = (checksum*131+value.1)%1000000007; }
    } else {
        let mut values: Vec<i64> = (0..n).map(|i| (i as i64*1103515245+12345)%2147483647).collect();
        let start = Instant::now(); values.sort(); println!("{}", start.elapsed().as_nanos());
        for value in values { checksum = (checksum*131+value)%1000000007; }
    }
    println!("{}", checksum);
}
