// C peer for main.min: Game of Life on a padded byte grid, then BFS shortest
// paths and connected components over the open cells.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int step_y[4] = {0, 1, 0, -1}, step_x[4] = {1, 0, -1, 0};

int main(int argc, char **argv) {
    int side = argc > 1 ? atoi(argv[1]) : 0, wide = side + 2;
    uint8_t *cells = calloc((size_t)wide * wide, 1), *next = calloc((size_t)wide * wide, 1);
    long long seed = 2024;
    for (int y = 0; y < side; y++)
        for (int x = 0; x < side; x++) {
            seed = (seed * 1103515245 + 12345) % 2147483648LL;
            cells[(y + 1) * wide + x + 1] = (seed / 65536) % 3 == 0;
        }
    long long checksum = 0, alive = 0;
    for (int generation = 0; generation < 12; generation++) {
        alive = 0;
        for (int y = 1; y <= side; y++) {
            const uint8_t *up = cells + (y - 1) * wide, *mid = cells + y * wide, *down = cells + (y + 1) * wide;
            uint8_t *out = next + y * wide;
            for (int x = 1; x <= side; x++) {
                int around = up[x - 1] + up[x] + up[x + 1] + mid[x - 1] + mid[x + 1] + down[x - 1] + down[x] + down[x + 1];
                uint8_t live = around == 3 || (around == 2 && mid[x]);
                out[x] = live;
                alive += live;
            }
        }
        uint8_t *t = cells; cells = next; next = t;
        checksum = (checksum * 31 + alive) % 1000000007;
    }
    printf("%lld\n%lld\n", checksum, alive);
    size_t n = (size_t)side * side;
    uint8_t *walls = malloc(n);
    for (int y = 0; y < side; y++) memcpy(walls + (size_t)y * side, cells + (y + 1) * wide + 1, side);
    walls[0] = 0; walls[n - 1] = 0;
    int32_t *distance = malloc(n * sizeof(int32_t)), *queue = malloc(n * sizeof(int32_t));
    for (size_t i = 0; i < n; i++) distance[i] = -1;
    size_t head = 0, tail = 0; long long total = 0;
    queue[tail++] = 0; distance[0] = 0;
    while (head < tail) {
        int at = queue[head++], y = at / side, x = at % side, here = distance[at];
        total += here;
        for (int k = 0; k < 4; k++) {
            int ny = y + step_y[k], nx = x + step_x[k];
            if (ny < 0 || ny >= side || nx < 0 || nx >= side) continue;
            int to = ny * side + nx;
            if (!walls[to] && distance[to] < 0) { distance[to] = here + 1; queue[tail++] = to; }
        }
    }
    printf("%zu %lld %d\n", tail, total, distance[n - 1]);
    int32_t *label = calloc(n, sizeof(int32_t));
    int count = 0; size_t largest = 0;
    for (size_t start = 0; start < n; start++) {
        if (walls[start] || label[start]) continue;
        label[start] = ++count;
        head = tail = 0; queue[tail++] = (int32_t)start;
        while (head < tail) {
            int at = queue[head++], y = at / side, x = at % side;
            for (int k = 0; k < 4; k++) {
                int ny = y + step_y[k], nx = x + step_x[k];
                if (ny < 0 || ny >= side || nx < 0 || nx >= side) continue;
                int to = ny * side + nx;
                if (!walls[to] && !label[to]) { label[to] = count; queue[tail++] = to; }
            }
        }
        if (tail > largest) largest = tail;
    }
    printf("%d %zu\n", count, largest);
    return 0;
}
