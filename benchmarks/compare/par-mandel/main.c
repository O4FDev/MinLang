// C peer for main.min: Mandelbrot escape counts, rows interleaved over 4 pthreads.
#pragma STDC FP_CONTRACT OFF
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

enum { LIMIT = 256, THREADS = 4 };
static long width, height;
static int *counts;

static int escape_time(long px, long py) {
    double x = (double)px / (double)width * 3.0 - 2.2;
    double y = (double)py / (double)height * 2.4 - 1.2;
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

static void *worker(void *arg) {
    long t = (long)arg;
    for (long py = t; py < height; py += THREADS)
        for (long px = 0; px < width; px++) counts[py * width + px] = escape_time(px, py);
    return NULL;
}

int main(int argc, char **argv) {
    width = atol(argv[1]);
    height = width * 2 / 3;
    counts = malloc((size_t)(width * height) * sizeof *counts);
    pthread_t threads[THREADS];
    for (long t = 0; t < THREADS; t++) pthread_create(&threads[t], NULL, worker, (void *)t);
    for (int t = 0; t < THREADS; t++) pthread_join(threads[t], NULL);
    long long total = 0, inside = 0, rows = 0, histogram[8] = {0};
    for (long py = 0; py < height; py++) {
        long long row = 0;
        for (long px = 0; px < width; px++) {
            int count = counts[py * width + px];
            row += count;
            if (count == LIMIT) inside++; else histogram[count * 8 / LIMIT]++;
        }
        total += row;
        rows = (rows * 31 + row) % 1000000007;
    }
    printf("total %lld\ninside %lld\nrows %lld\n", total, inside, rows);
    for (int b = 0; b < 8; b++) printf("escape %d %lld\n", b, histogram[b]);
    return 0;
}
