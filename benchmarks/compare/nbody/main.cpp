// C++ peer for main.min: the classic five-body simulation over a std::array of structs.
#pragma STDC FP_CONTRACT OFF
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>

struct Body { double x, y, z, vx, vy, vz, mass; };
constexpr double pi = 3.141592653589793;
constexpr double solarMass = 4.0 * pi * pi;
constexpr double daysPerYear = 365.24;
constexpr std::size_t N = 5;

static double energy(const std::array<Body, N> &bodies) {
    double e = 0.0;
    for (std::size_t i = 0; i < N; i++) {
        const Body &b = bodies[i];
        e = e + 0.5 * b.mass * (b.vx * b.vx + b.vy * b.vy + b.vz * b.vz);
        for (std::size_t j = i + 1; j < N; j++) {
            const Body &o = bodies[j];
            double dx = b.x - o.x, dy = b.y - o.y, dz = b.z - o.z;
            e = e - b.mass * o.mass / std::sqrt(dx * dx + dy * dy + dz * dz);
        }
    }
    return e;
}

static void advance(std::array<Body, N> &bodies, double dt) {
    for (std::size_t i = 0; i < N; i++) {
        Body &b = bodies[i];
        for (std::size_t j = i + 1; j < N; j++) {
            Body &o = bodies[j];
            double dx = b.x - o.x, dy = b.y - o.y, dz = b.z - o.z;
            double d2 = dx * dx + dy * dy + dz * dz;
            double magnitude = dt / (d2 * std::sqrt(d2));
            b.vx = b.vx - dx * o.mass * magnitude;
            b.vy = b.vy - dy * o.mass * magnitude;
            b.vz = b.vz - dz * o.mass * magnitude;
            o.vx = o.vx + dx * b.mass * magnitude;
            o.vy = o.vy + dy * b.mass * magnitude;
            o.vz = o.vz + dz * b.mass * magnitude;
        }
    }
    for (Body &b : bodies) {
        b.x = b.x + dt * b.vx;
        b.y = b.y + dt * b.vy;
        b.z = b.z + dt * b.vz;
    }
}

int main(int argc, char **argv) {
    long steps = argc > 1 ? std::atol(argv[1]) : 0;
    std::array<Body, N> bodies{{
        {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, solarMass},
        {4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01, 1.66007664274403694e-03 * daysPerYear, 7.69901118419740425e-03 * daysPerYear, -6.90460016972063023e-05 * daysPerYear, 9.54791938424326609e-04 * solarMass},
        {8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01, -2.76742510726862411e-03 * daysPerYear, 4.99852801234917238e-03 * daysPerYear, 2.30417297573763929e-05 * daysPerYear, 2.85885980666130812e-04 * solarMass},
        {1.28943695621391310e+01, -1.51111514016986312e+01, -2.23307578892655734e-01, 2.96460137564761618e-03 * daysPerYear, 2.37847173959480950e-03 * daysPerYear, -2.96589568540237556e-05 * daysPerYear, 4.36624404335156298e-05 * solarMass},
        {1.53796971148509165e+01, -2.59193146099879641e+01, 1.79258772950371181e-01, 2.68067772490389322e-03 * daysPerYear, 1.62824170038242295e-03 * daysPerYear, -9.51592254519715870e-05 * daysPerYear, 5.15138902046611451e-05 * solarMass},
    }};
    double px = 0.0, py = 0.0, pz = 0.0;
    for (const Body &b : bodies) { px = px + b.vx * b.mass; py = py + b.vy * b.mass; pz = pz + b.vz * b.mass; }
    bodies[0].vx = 0.0 - px / solarMass;
    bodies[0].vy = 0.0 - py / solarMass;
    bodies[0].vz = 0.0 - pz / solarMass;
    std::printf("%lld\n", (long long)(energy(bodies) * 1000000000.0));
    for (long s = 0; s < steps; s++) advance(bodies, 0.01);
    std::printf("%lld\n", (long long)(energy(bodies) * 1000000000.0));
    return 0;
}
