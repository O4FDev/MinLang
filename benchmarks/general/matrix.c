// C reference for matrix.min: same output.
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    int n = 300;
    double **a = malloc(n * sizeof *a), **b = malloc(n * sizeof *b), **c = malloc(n * sizeof *c);
    for (int i = 0; i < n; i++) {
        a[i] = malloc(n * sizeof(double)); b[i] = malloc(n * sizeof(double)); c[i] = calloc(n, sizeof(double));
        for (int j = 0; j < n; j++) { a[i][j] = (i * j) % 7 + 1; b[i][j] = (i + j) % 5 + 1; }
    }
    for (int round = 0; round < 4; round++)
        for (int i = 0; i < n; i++)
            for (int k = 0; k < n; k++) { double aik = a[i][k]; for (int j = 0; j < n; j++) c[i][j] = c[i][j] + aik * b[k][j]; }
    double sum = 0; for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) sum += c[i][j];
    printf("%lld\n", (long long)sum);
    return 0;
}
