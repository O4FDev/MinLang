// Rust peer for main.min: the classic five-body simulation over an array of structs.
#[derive(Clone, Copy)]
struct Body { x: f64, y: f64, z: f64, vx: f64, vy: f64, vz: f64, mass: f64 }

const PI: f64 = 3.141592653589793;
const SOLAR_MASS: f64 = 4.0 * PI * PI;
const DAYS_PER_YEAR: f64 = 365.24;
const N: usize = 5;

fn energy(bodies: &[Body; N]) -> f64 {
    let mut e = 0.0;
    for i in 0..N {
        let b = &bodies[i];
        e = e + 0.5 * b.mass * (b.vx * b.vx + b.vy * b.vy + b.vz * b.vz);
        for o in &bodies[i + 1..] {
            let (dx, dy, dz) = (b.x - o.x, b.y - o.y, b.z - o.z);
            e = e - b.mass * o.mass / (dx * dx + dy * dy + dz * dz).sqrt();
        }
    }
    e
}

fn advance(bodies: &mut [Body; N], dt: f64) {
    for i in 0..N {
        let (head, tail) = bodies.split_at_mut(i + 1);
        let b = &mut head[i];
        for o in tail.iter_mut() {
            let (dx, dy, dz) = (b.x - o.x, b.y - o.y, b.z - o.z);
            let d2 = dx * dx + dy * dy + dz * dz;
            let magnitude = dt / (d2 * d2.sqrt());
            b.vx = b.vx - dx * o.mass * magnitude;
            b.vy = b.vy - dy * o.mass * magnitude;
            b.vz = b.vz - dz * o.mass * magnitude;
            o.vx = o.vx + dx * b.mass * magnitude;
            o.vy = o.vy + dy * b.mass * magnitude;
            o.vz = o.vz + dz * b.mass * magnitude;
        }
    }
    for b in bodies.iter_mut() {
        b.x = b.x + dt * b.vx;
        b.y = b.y + dt * b.vy;
        b.z = b.z + dt * b.vz;
    }
}

fn main() {
    let steps: u64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut bodies = [
        Body { x: 0.0, y: 0.0, z: 0.0, vx: 0.0, vy: 0.0, vz: 0.0, mass: SOLAR_MASS },
        Body { x: 4.84143144246472090e+00, y: -1.16032004402742839e+00, z: -1.03622044471123109e-01, vx: 1.66007664274403694e-03 * DAYS_PER_YEAR, vy: 7.69901118419740425e-03 * DAYS_PER_YEAR, vz: -6.90460016972063023e-05 * DAYS_PER_YEAR, mass: 9.54791938424326609e-04 * SOLAR_MASS },
        Body { x: 8.34336671824457987e+00, y: 4.12479856412430479e+00, z: -4.03523417114321381e-01, vx: -2.76742510726862411e-03 * DAYS_PER_YEAR, vy: 4.99852801234917238e-03 * DAYS_PER_YEAR, vz: 2.30417297573763929e-05 * DAYS_PER_YEAR, mass: 2.85885980666130812e-04 * SOLAR_MASS },
        Body { x: 1.28943695621391310e+01, y: -1.51111514016986312e+01, z: -2.23307578892655734e-01, vx: 2.96460137564761618e-03 * DAYS_PER_YEAR, vy: 2.37847173959480950e-03 * DAYS_PER_YEAR, vz: -2.96589568540237556e-05 * DAYS_PER_YEAR, mass: 4.36624404335156298e-05 * SOLAR_MASS },
        Body { x: 1.53796971148509165e+01, y: -2.59193146099879641e+01, z: 1.79258772950371181e-01, vx: 2.68067772490389322e-03 * DAYS_PER_YEAR, vy: 1.62824170038242295e-03 * DAYS_PER_YEAR, vz: -9.51592254519715870e-05 * DAYS_PER_YEAR, mass: 5.15138902046611451e-05 * SOLAR_MASS },
    ];
    let (mut px, mut py, mut pz) = (0.0, 0.0, 0.0);
    for b in &bodies { px = px + b.vx * b.mass; py = py + b.vy * b.mass; pz = pz + b.vz * b.mass; }
    bodies[0].vx = 0.0 - px / SOLAR_MASS;
    bodies[0].vy = 0.0 - py / SOLAR_MASS;
    bodies[0].vz = 0.0 - pz / SOLAR_MASS;
    println!("{}", (energy(&bodies) * 1000000000.0) as i64);
    for _ in 0..steps { advance(&mut bodies, 0.01); }
    println!("{}", (energy(&bodies) * 1000000000.0) as i64);
}
