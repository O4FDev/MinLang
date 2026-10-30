// C++ peer for main.min: dense matrix multiply over one contiguous vector.
#pragma STDC FP_CONTRACT OFF
#include <cstdio>
#include <cstdlib>
#include <vector>

int main(int argc, char **argv) {
    const std::size_t n = argc > 1 ? std::strtoul(argv[1], nullptr, 10) : 0;
    std::vector<double> a(n * n), b(n * n), c(n * n, 0.0);
    for (std::size_t i = 0; i < n; i++)
        for (std::size_t j = 0; j < n; j++) {
            a[i * n + j] = double((i * j) % 7 + 1);
            b[i * n + j] = double((i + j) % 5 + 1);
        }
    for (int round = 0; round < 4; round++)
        for (std::size_t i = 0; i < n; i++) {
            double *__restrict ci = c.data() + i * n;
            for (std::size_t k = 0; k < n; k++) {
                const double aik = a[i * n + k];
                const double *__restrict bk = b.data() + k * n;
                for (std::size_t j = 0; j < n; j++) ci[j] = ci[j] + aik * bk[j];
            }
        }
    double sum = 0.0;
    for (double v : c) sum = sum + v;
    std::printf("%lld\n", (long long)sum);
    return 0;
}
