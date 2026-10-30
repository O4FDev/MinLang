// C peer for main.min: dense matrix multiply over contiguous row-major storage.
#pragma STDC FP_CONTRACT OFF
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    long n = argc > 1 ? atol(argv[1]) : 0;
    double *a = malloc((size_t)(n * n) * sizeof(double)), *b = malloc((size_t)(n * n) * sizeof(double));
    double *c = calloc((size_t)(n * n), sizeof(double));
    for (long i = 0; i < n; i++)
        for (long j = 0; j < n; j++) { a[i * n + j] = (double)((i * j) % 7 + 1); b[i * n + j] = (double)((i + j) % 5 + 1); }
    for (int round = 0; round < 4; round++)
        for (long i = 0; i < n; i++) {
            double *restrict ci = c + i * n;
            for (long k = 0; k < n; k++) {
                double aik = a[i * n + k];
                const double *restrict bk = b + k * n;
                for (long j = 0; j < n; j++) ci[j] = ci[j] + aik * bk[j];
            }
        }
    double sum = 0.0;
    for (long i = 0; i < n * n; i++) sum = sum + c[i];
    printf("%lld\n", (long long)sum);
    return 0;
}
