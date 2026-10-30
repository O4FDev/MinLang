// Rust peer for main.min: Game of Life on a padded byte grid, then BFS shortest
// paths and connected components over the open cells.
use std::io::Write;

const STEP_Y: [i32; 4] = [0, 1, 0, -1];
const STEP_X: [i32; 4] = [1, 0, -1, 0];

fn neighbours(at: usize, side: usize) -> impl Iterator<Item = usize> {
    let (y, x) = ((at / side) as i32, (at % side) as i32);
    (0..4).filter_map(move |k| {
        let (ny, nx) = (y + STEP_Y[k], x + STEP_X[k]);
        if ny < 0 || nx < 0 || ny >= side as i32 || nx >= side as i32 { None } else { Some(ny as usize * side + nx as usize) }
    })
}

fn main() {
    let side: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let wide = side + 2;
    let mut cells = vec![0u8; wide * wide];
    let mut next = vec![0u8; wide * wide];
    let mut seed: i64 = 2024;
    for y in 0..side {
        for x in 0..side {
            seed = (seed * 1103515245 + 12345) % 2147483648;
            cells[(y + 1) * wide + x + 1] = ((seed / 65536) % 3 == 0) as u8;
        }
    }
    let (mut checksum, mut alive) = (0i64, 0i64);
    for _ in 0..12 {
        alive = 0;
        for y in 1..=side {
            let (up, mid, down) = (&cells[(y - 1) * wide..y * wide], &cells[y * wide..(y + 1) * wide], &cells[(y + 1) * wide..(y + 2) * wide]);
            let out = &mut next[y * wide..(y + 1) * wide];
            for x in 1..=side {
                let around = up[x - 1] + up[x] + up[x + 1] + mid[x - 1] + mid[x + 1] + down[x - 1] + down[x] + down[x + 1];
                let live = (around == 3 || (around == 2 && mid[x] == 1)) as u8;
                out[x] = live;
                alive += live as i64;
            }
        }
        std::mem::swap(&mut cells, &mut next);
        checksum = (checksum * 31 + alive) % 1000000007;
    }
    let mut out = std::io::stdout().lock();
    writeln!(out, "{}\n{}", checksum, alive).unwrap();
    let n = side * side;
    let mut walls = vec![0u8; n];
    for y in 0..side { walls[y * side..(y + 1) * side].copy_from_slice(&cells[(y + 1) * wide + 1..(y + 1) * wide + 1 + side]); }
    walls[0] = 0;
    walls[n - 1] = 0;
    let mut distance = vec![-1i32; n];
    let mut queue: Vec<u32> = Vec::with_capacity(n);
    let mut total = 0i64;
    queue.push(0);
    distance[0] = 0;
    let mut head = 0;
    while head < queue.len() {
        let at = queue[head] as usize;
        head += 1;
        let here = distance[at];
        total += here as i64;
        for to in neighbours(at, side) {
            if walls[to] == 0 && distance[to] < 0 { distance[to] = here + 1; queue.push(to as u32); }
        }
    }
    writeln!(out, "{} {} {}", queue.len(), total, distance[n - 1]).unwrap();
    let mut label = vec![0i32; n];
    let (mut count, mut largest) = (0i32, 0usize);
    for start in 0..n {
        if walls[start] != 0 || label[start] != 0 { continue; }
        count += 1;
        label[start] = count;
        queue.clear();
        queue.push(start as u32);
        let mut head = 0;
        while head < queue.len() {
            let at = queue[head] as usize;
            head += 1;
            for to in neighbours(at, side) {
                if walls[to] == 0 && label[to] == 0 { label[to] = count; queue.push(to as u32); }
            }
        }
        largest = largest.max(queue.len());
    }
    writeln!(out, "{} {}", count, largest).unwrap();
}
