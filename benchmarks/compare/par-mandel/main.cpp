// C++ peer for main.min: Mandelbrot escape counts, rows interleaved over 4 std::threads.
#pragma STDC FP_CONTRACT OFF
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

constexpr int LIMIT = 256;
constexpr int THREADS = 4;

static int escape_time(long px, long py, long width, long height) {
    double x = static_cast<double>(px) / static_cast<double>(width) * 3.0 - 2.2;
    double y = static_cast<double>(py) / static_cast<double>(height) * 2.4 - 1.2;
    double real = 0.0, imaginary = 0.0;
    int iterations = 0;
    while (real * real + imaginary * imaginary <= 4.0 && iterations < LIMIT) {
        double next = real * real - imaginary * imaginary + x;
        imaginary = 2.0 * real * imaginary + y;
        real = next;
        iterations++;
    }
    return iterations;
}

int main(int argc, char **argv) {
    long width = std::atol(argv[1]), height = width * 2 / 3;
    std::vector<int> counts(static_cast<size_t>(width * height));
    std::vector<std::thread> threads;
    for (int t = 0; t < THREADS; t++)
        threads.emplace_back([&, t] {
            for (long py = t; py < height; py += THREADS)
                for (long px = 0; px < width; px++) counts[py * width + px] = escape_time(px, py, width, height);
        });
    for (auto &thread : threads) thread.join();
    int64_t total = 0, inside = 0, rows = 0;
    std::array<int64_t, 8> histogram{};
    for (long py = 0; py < height; py++) {
        int64_t row = 0;
        for (long px = 0; px < width; px++) {
            int count = counts[py * width + px];
            row += count;
            if (count == LIMIT) inside++; else histogram[count * 8 / LIMIT]++;
        }
        total += row;
        rows = (rows * 31 + row) % 1000000007;
    }
    std::printf("total %lld\ninside %lld\nrows %lld\n", (long long)total, (long long)inside, (long long)rows);
    for (int b = 0; b < 8; b++) std::printf("escape %d %lld\n", b, (long long)histogram[b]);
    return 0;
}
